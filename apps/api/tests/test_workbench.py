# tests/test_workbench.py
"""
工作台任务测试

本文件验证工作台任务第一阶段闭环：任务发布必须引用积分规则，执行人提交完成材料，
发布人审核后才发积分；悬赏任务领取范围要区分公开任务和协会内任务。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_session
from app.core.database.base import Base
from app.core.permissions.models import Permission, Role, RolePermission, UserRoleGrant
from app.core.permissions.repository import PermissionRepository
from app.core.permissions.service import sync_registered_permissions
from app.main import create_app
from app.modules.audit.models import AuditLog
from app.modules.identity.models import AuthSession, EmailPasswordAccount, EmailVerificationCode, User, WechatAccount
from app.modules.organization.models import Department, Position, UserPosition
from app.modules.points.models import (
    PointAccount,
    PointHold,
    PointLedgerEntry,
    PointRule,
    TemporaryPointRule,
    TemporaryPointRuleEvent,
)
from app.modules.workbench.models import WorkbenchTask
from app.shared.time import utc_now


@dataclass(frozen=True)
class WorkbenchTestContext:
    """工作台接口测试上下文。"""

    client: TestClient
    session_factory: async_sessionmaker[AsyncSession]


@pytest.fixture
def workbench_context(tmp_path: Path) -> Iterator[WorkbenchTestContext]:
    """创建使用临时 SQLite 数据库的工作台接口测试上下文。"""

    # 显式引用模型，确保 Base.metadata 在 create_all 前已经收集相关表。
    _ = (
        AuthSession,
        AuditLog,
        Department,
        EmailVerificationCode,
        EmailPasswordAccount,
        Permission,
        PointAccount,
        PointHold,
        PointLedgerEntry,
        PointRule,
        Position,
        Role,
        RolePermission,
        TemporaryPointRule,
        TemporaryPointRuleEvent,
        User,
        UserPosition,
        UserRoleGrant,
        WechatAccount,
        WorkbenchTask,
    )

    database_path = tmp_path / "workbench.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare_database() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            await sync_registered_permissions(session)
            await session.commit()

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    asyncio.run(prepare_database())
    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as client:
        yield WorkbenchTestContext(client=client, session_factory=session_factory)

    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


def login_and_get_identity(
    client: TestClient,
    *,
    openid: str,
    display_name: str,
) -> tuple[str, int]:
    """通过开发态微信登录获取访问令牌和用户 ID。"""

    response = client.post(
        "/api/v1/auth/wechat/login",
        json={"dev_openid": openid, "display_name": display_name},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    return data["access_token"], data["user"]["id"]


def grant_role_to_user(
    context: WorkbenchTestContext,
    *,
    user_id: int,
    role_code: str,
) -> None:
    """在测试数据库中直接授予预置角色。"""

    async def grant() -> None:
        async with context.session_factory() as session:
            repository = PermissionRepository(session)
            role = await repository.get_role_by_code(role_code)
            assert role is not None
            await repository.grant_role_to_user(user_id=user_id, role=role)
            await session.commit()

    asyncio.run(grant())


def create_fixed_point_rule(
    context: WorkbenchTestContext,
    *,
    operator_id: int,
    code: str,
    amount: int = 10,
) -> int:
    """在测试数据库中创建一个启用的固定积分规则。"""

    async def create() -> int:
        async with context.session_factory() as session:
            rule = PointRule(
                code=code,
                name=f"测试规则 {code}",
                rule_type="fixed",
                status="active",
                version=1,
                amount=amount,
                created_by=operator_id,
                updated_by=operator_id,
            )
            session.add(rule)
            await session.flush()
            rule_id = rule.id
            await session.commit()
            return rule_id

    return asyncio.run(create())


def load_audit_actions(context: WorkbenchTestContext) -> list[str]:
    """读取工作台测试产生的审计动作。"""

    async def load() -> list[str]:
        async with context.session_factory() as session:
            result = await session.scalars(select(AuditLog).order_by(AuditLog.id))
            return [item.action for item in result]

    return asyncio.run(load())


def test_assigned_task_requires_submission_and_publisher_review(
    workbench_context: WorkbenchTestContext,
) -> None:
    """指定任务需要执行人提交、发布人审核，审核通过后才发积分。"""

    publisher_token, publisher_id = login_and_get_identity(
        workbench_context.client,
        openid="workbench_assigned_publisher",
        display_name="任务发布人",
    )
    assignee_token, assignee_id = login_and_get_identity(
        workbench_context.client,
        openid="workbench_assigned_assignee",
        display_name="任务执行人",
    )
    grant_role_to_user(workbench_context, user_id=publisher_id, role_code="workbench_task_publisher")
    rule_id = create_fixed_point_rule(workbench_context, operator_id=publisher_id, code="workbench-assigned")
    now = utc_now()

    create_response = workbench_context.client.post(
        "/api/v1/workbench/tasks",
        headers={"Authorization": f"Bearer {publisher_token}"},
        json={
            "title": "完成展台海报",
            "task_type": "poster",
            "assignment_type": "assigned",
            "visibility": "association",
            "content": "完成百团大战展台海报设计",
            "deadline": (now + timedelta(days=3)).isoformat(),
            "point_rule_id": rule_id,
            "assignee_id": assignee_id,
        },
    )
    task_id = create_response.json()["data"]["id"]
    mine_response = workbench_context.client.get(
        "/api/v1/workbench/tasks?mine=true",
        headers={"Authorization": f"Bearer {assignee_token}"},
    )
    submit_response = workbench_context.client.post(
        f"/api/v1/workbench/tasks/{task_id}/submit",
        headers={"Authorization": f"Bearer {assignee_token}"},
        json={"submission_content": "已完成海报并提交源文件"},
    )
    assignee_review_response = workbench_context.client.post(
        f"/api/v1/workbench/tasks/{task_id}/review",
        headers={"Authorization": f"Bearer {assignee_token}"},
        json={"action": "approve", "review_comment": "执行人不能自己审核"},
    )
    approve_response = workbench_context.client.post(
        f"/api/v1/workbench/tasks/{task_id}/review",
        headers={"Authorization": f"Bearer {publisher_token}"},
        json={"action": "approve", "review_comment": "完成质量合格"},
    )
    account_response = workbench_context.client.get(
        "/api/v1/me/points/account",
        headers={"Authorization": f"Bearer {assignee_token}"},
    )
    audit_actions = load_audit_actions(workbench_context)

    assert create_response.status_code == 200
    assert create_response.json()["data"]["status"] == "pending_completion"
    assert create_response.json()["data"]["point_rule_amount"] == 10
    assert mine_response.status_code == 200
    assert mine_response.json()["data"]["total"] == 1
    assert submit_response.status_code == 200
    assert submit_response.json()["data"]["status"] == "pending_review"
    assert assignee_review_response.status_code == 403
    assert approve_response.status_code == 200
    assert approve_response.json()["data"]["status"] == "completed"
    assert approve_response.json()["data"]["point_ledger_entry_id"] is not None
    assert account_response.json()["data"]["balance"] == 10
    assert audit_actions == [
        "workbench.task.publish",
        "workbench.task.submit",
        "workbench.task.review",
    ]


def test_public_bounty_can_be_claimed_but_association_bounty_blocks_external_member(
    workbench_context: WorkbenchTestContext,
) -> None:
    """公开悬赏允许外部成员领取，协会内悬赏不开放给只有 0 身份的用户。"""

    publisher_token, publisher_id = login_and_get_identity(
        workbench_context.client,
        openid="workbench_bounty_publisher",
        display_name="悬赏发布人",
    )
    external_token, external_id = login_and_get_identity(
        workbench_context.client,
        openid="workbench_bounty_external",
        display_name="外部成员",
    )
    grant_role_to_user(workbench_context, user_id=publisher_id, role_code="workbench_task_publisher")
    rule_id = create_fixed_point_rule(workbench_context, operator_id=publisher_id, code="workbench-bounty")

    association_response = workbench_context.client.post(
        "/api/v1/workbench/tasks",
        headers={"Authorization": f"Bearer {publisher_token}"},
        json={
            "title": "协会内悬赏",
            "task_type": "internal_bounty",
            "assignment_type": "bounty",
            "visibility": "association",
            "content": "只开放给协会成员的悬赏任务",
            "point_rule_id": rule_id,
        },
    )
    association_task_id = association_response.json()["data"]["id"]
    denied_claim_response = workbench_context.client.post(
        f"/api/v1/workbench/tasks/{association_task_id}/claim",
        headers={"Authorization": f"Bearer {external_token}"},
    )

    public_response = workbench_context.client.post(
        "/api/v1/workbench/tasks",
        headers={"Authorization": f"Bearer {publisher_token}"},
        json={
            "title": "公开悬赏",
            "task_type": "public_bounty",
            "assignment_type": "bounty",
            "visibility": "public",
            "content": "公开给外部成员的悬赏任务",
            "point_rule_id": rule_id,
        },
    )
    public_task_id = public_response.json()["data"]["id"]
    claim_response = workbench_context.client.post(
        f"/api/v1/workbench/tasks/{public_task_id}/claim",
        headers={"Authorization": f"Bearer {external_token}"},
    )
    submit_response = workbench_context.client.post(
        f"/api/v1/workbench/tasks/{public_task_id}/submit",
        headers={"Authorization": f"Bearer {external_token}"},
        json={"submission_content": "已完成公开悬赏任务"},
    )
    reject_response = workbench_context.client.post(
        f"/api/v1/workbench/tasks/{public_task_id}/review",
        headers={"Authorization": f"Bearer {publisher_token}"},
        json={"action": "reject", "review_comment": "材料需要补充"},
    )
    account_response = workbench_context.client.get(
        "/api/v1/me/points/account",
        headers={"Authorization": f"Bearer {external_token}"},
    )

    assert association_response.status_code == 200
    assert denied_claim_response.status_code == 403
    assert denied_claim_response.json()["error"]["code"] == "WORKBENCH_TASK_CLAIM_FORBIDDEN"
    assert public_response.status_code == 200
    assert claim_response.status_code == 200
    assert claim_response.json()["data"]["assignee_id"] == external_id
    assert claim_response.json()["data"]["status"] == "pending_completion"
    assert submit_response.status_code == 200
    assert reject_response.status_code == 200
    assert reject_response.json()["data"]["status"] == "rejected"
    assert account_response.json()["data"]["balance"] == 0
