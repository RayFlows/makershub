# tests/test_points.py
"""
积分账本测试

本文件验证积分域的第一阶段硬约束：账户懒创建、流水追加、幂等键防重复、
不允许透支、冻结生命周期，以及后台人工调整必须经过权限和审计。
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
from app.core.errors import AppError
from app.core.permissions.models import Permission, Role, RolePermission, UserRoleGrant
from app.core.permissions.repository import PermissionRepository
from app.core.permissions.service import sync_registered_permissions
from app.main import create_app
from app.modules.audit.models import AuditLog
from app.modules.identity.models import AuthSession, EmailPasswordAccount, EmailVerificationCode, User, WechatAccount
from app.modules.organization.models import Position, UserPosition
from app.modules.points.accounts import get_or_create_point_account
from app.modules.points.adjustments import manually_adjust_points
from app.modules.points.holds import deduct_point_hold, freeze_points, release_point_hold
from app.modules.points.ledger import reverse_ledger_entry
from app.modules.points.models import (
    PointAccount,
    PointHold,
    PointLedgerEntry,
    PointRule,
    TemporaryPointRule,
    TemporaryPointRuleEvent,
)
from app.modules.points.rules import (
    approve_temporary_point_rule,
    grant_points_by_rule,
    submit_temporary_point_rule,
)
from app.shared.time import utc_now


@dataclass(frozen=True)
class PointsTestContext:
    """积分接口测试上下文。"""

    client: TestClient
    session_factory: async_sessionmaker[AsyncSession]


@pytest.fixture
def points_context(tmp_path: Path) -> Iterator[PointsTestContext]:
    """创建使用临时 SQLite 数据库的积分接口测试上下文。"""

    # 显式引用模型，确保 Base.metadata 在 create_all 前已经收集相关表。
    _ = (
        AuthSession,
        AuditLog,
        EmailVerificationCode,
        EmailPasswordAccount,
        Permission,
        PointAccount,
        PointHold,
        PointLedgerEntry,
        PointRule,
        TemporaryPointRule,
        TemporaryPointRuleEvent,
        Position,
        Role,
        RolePermission,
        User,
        UserPosition,
        UserRoleGrant,
        WechatAccount,
    )

    database_path = tmp_path / "points.db"
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
        yield PointsTestContext(client=client, session_factory=session_factory)

    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


async def create_user(session: AsyncSession, *, display_name: str = "积分测试用户") -> User:
    """创建测试用户。"""

    user = User(display_name=display_name, status="active")
    session.add(user)
    await session.flush()
    return user


def login_and_get_identity(
    client: TestClient,
    *,
    openid: str,
    display_name: str = "积分接口测试用户",
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
    context: PointsTestContext,
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


def load_audit_logs(context: PointsTestContext) -> list[AuditLog]:
    """读取积分测试产生的审计日志。"""

    async def load() -> list[AuditLog]:
        async with context.session_factory() as session:
            result = await session.scalars(select(AuditLog).order_by(AuditLog.id))
            return list(result)

    return asyncio.run(load())


@pytest.mark.asyncio
async def test_manual_adjustment_is_ledger_based_and_idempotent() -> None:
    """人工积分调整必须追加流水，并通过幂等键避免重复发放。"""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        user = await create_user(session)
        operator = await create_user(session, display_name="积分操作人")
        income = await manually_adjust_points(
            session,
            user_id=user.id,
            amount=20,
            reason="测试补发积分",
            operator_id=operator.id,
            idempotency_key="points:test:income",
        )
        repeated = await manually_adjust_points(
            session,
            user_id=user.id,
            amount=20,
            reason="测试补发积分",
            operator_id=operator.id,
            idempotency_key="points:test:income",
        )
        expense = await manually_adjust_points(
            session,
            user_id=user.id,
            amount=-5,
            reason="测试扣减积分",
            operator_id=operator.id,
            idempotency_key="points:test:expense",
        )
        await session.commit()

        entries = list(await session.scalars(select(PointLedgerEntry).order_by(PointLedgerEntry.id)))

    assert income.account.balance == 15
    assert repeated.idempotent is True
    assert repeated.ledger_entry.id == income.ledger_entry.id
    assert expense.account.balance == 15
    assert [entry.direction for entry in entries] == ["income", "expense"]
    assert [entry.balance_after for entry in entries] == [20, 15]

    await engine.dispose()


@pytest.mark.asyncio
async def test_points_do_not_allow_overdraft() -> None:
    """积分扣减不能超过可用余额。"""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        user = await create_user(session)
        operator = await create_user(session, display_name="积分操作人")
        with pytest.raises(AppError) as error:
            await manually_adjust_points(
                session,
                user_id=user.id,
                amount=-1,
                reason="测试透支",
                operator_id=operator.id,
                idempotency_key="points:test:overdraft",
            )

    assert error.value.code == "POINT_BALANCE_NOT_ENOUGH"

    await engine.dispose()


@pytest.mark.asyncio
async def test_point_hold_can_release_or_deduct_without_direct_balance_mutation() -> None:
    """冻结记录可以解冻或转扣除，并且每一步都产生流水。"""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        user = await create_user(session)
        operator = await create_user(session, display_name="积分操作人")
        await manually_adjust_points(
            session,
            user_id=user.id,
            amount=30,
            reason="测试初始积分",
            operator_id=operator.id,
            idempotency_key="points:test:seed",
        )
        hold_for_release = await freeze_points(
            session,
            user_id=user.id,
            amount=10,
            business_type="borrowing_deposit",
            business_id="borrow-1",
            idempotency_key="points:test:freeze:release",
            reason="测试借用押金冻结",
            operator_id=operator.id,
        )
        released = await release_point_hold(
            session,
            hold_id=hold_for_release.hold.id,
            idempotency_key="points:test:release",
            reason="测试正常归还解冻",
            operator_id=operator.id,
        )
        hold_for_deduct = await freeze_points(
            session,
            user_id=user.id,
            amount=8,
            business_type="print_order",
            business_id="print-1",
            idempotency_key="points:test:freeze:deduct",
            reason="测试打印接单冻结",
            operator_id=operator.id,
        )
        deducted = await deduct_point_hold(
            session,
            hold_id=hold_for_deduct.hold.id,
            idempotency_key="points:test:deduct",
            reason="测试打印完成扣除",
            operator_id=operator.id,
        )
        account = await get_or_create_point_account(session, user_id=user.id)
        entries = list(await session.scalars(select(PointLedgerEntry).order_by(PointLedgerEntry.id)))

    assert hold_for_release.account.frozen_balance == 0
    assert released.hold.status == "released"
    assert deducted.hold.status == "deducted"
    assert account.balance == 22
    assert account.frozen_balance == 0
    assert [entry.direction for entry in entries] == [
        "income",
        "freeze",
        "unfreeze",
        "freeze",
        "hold_deduct",
    ]

    await engine.dispose()


@pytest.mark.asyncio
async def test_temporary_rule_generates_template_and_uses_reverse_ledger() -> None:
    """临时规则审批后生成一次性模板，异常追回必须追加反向流水。"""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        applicant = await create_user(session, display_name="临时规则申请人")
        reviewer = await create_user(session, display_name="临时规则审批人")
        target = await create_user(session, display_name="临时规则积分目标")
        now = utc_now()
        temporary_rule = await submit_temporary_point_rule(
            session,
            applicant_id=applicant.id,
            name="临时搬运任务",
            task_type="special_task",
            target_scope="members",
            reason="活动物料临时搬运",
            amount_per_completion=10,
            max_participants=3,
            total_points_limit=30,
            effective_from=now,
            effective_to=now + timedelta(days=7),
        )
        approved_rule = await approve_temporary_point_rule(
            session,
            rule_id=temporary_rule.id,
            approver_id=reviewer.id,
            approval_reason="符合临时任务发分要求",
        )
        assert approved_rule.generated_point_rule_id is not None

        awarded = await grant_points_by_rule(
            session,
            rule_id=approved_rule.generated_point_rule_id,
            user_id=target.id,
            operator_id=reviewer.id,
            idempotency_key="points:temporary-rule:award",
            business_id="task-1",
        )
        reversed_result = await reverse_ledger_entry(
            session,
            ledger_entry_id=awarded.ledger_entry.id,
            reason="测试异常追回",
            operator_id=reviewer.id,
            idempotency_key="points:temporary-rule:reverse",
        )
        await session.commit()

        entries = list(await session.scalars(select(PointLedgerEntry).order_by(PointLedgerEntry.id)))
        events = list(await session.scalars(select(TemporaryPointRuleEvent).order_by(TemporaryPointRuleEvent.id)))

    assert approved_rule.approval_status == "approved"
    assert approved_rule.generated_point_rule is not None
    assert approved_rule.generated_point_rule.rule_type == "temporary_task_template"
    assert awarded.account.balance == 0
    assert reversed_result.ledger_entry.direction == "reversal"
    assert [entry.direction for entry in entries] == ["income", "reversal"]
    assert [event.event_type for event in events] == ["submitted", "approved"]

    await engine.dispose()


def test_current_user_can_view_own_point_account_and_ledger(points_context: PointsTestContext) -> None:
    """普通用户可以查看自己的积分账户和流水。"""

    token, _ = login_and_get_identity(points_context.client, openid="points_self_user")

    account_response = points_context.client.get(
        "/api/v1/me/points/account",
        headers={"Authorization": f"Bearer {token}"},
    )
    ledger_response = points_context.client.get(
        "/api/v1/me/points/ledger",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert account_response.status_code == 200
    assert account_response.json()["data"]["balance"] == 0
    assert account_response.json()["data"]["available_balance"] == 0
    assert ledger_response.status_code == 200
    assert ledger_response.json()["data"]["items"] == []


def test_manual_adjustment_api_requires_permission_and_writes_audit(
    points_context: PointsTestContext,
) -> None:
    """后台人工调整接口需要系统兜底权限，并写入一条审计日志。"""

    admin_token, admin_id = login_and_get_identity(
        points_context.client,
        openid="points_manual_admin",
        display_name="积分管理员",
    )
    target_token, target_id = login_and_get_identity(
        points_context.client,
        openid="points_manual_target",
        display_name="积分目标用户",
    )

    denied_response = points_context.client.post(
        "/api/v1/points/manual-adjustments",
        headers={"Authorization": f"Bearer {target_token}", "Idempotency-Key": "points:api:denied"},
        json={"user_id": target_id, "amount": 10, "reason": "普通用户尝试调整积分"},
    )
    grant_role_to_user(points_context, user_id=admin_id, role_code="system_super_admin")

    response = points_context.client.post(
        "/api/v1/points/manual-adjustments",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "points:api:manual"},
        json={"user_id": target_id, "amount": 12, "reason": "测试后台人工补发"},
    )
    repeated_response = points_context.client.post(
        "/api/v1/points/manual-adjustments",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "points:api:manual"},
        json={"user_id": target_id, "amount": 12, "reason": "测试后台人工补发"},
    )

    target_account_response = points_context.client.get(
        "/api/v1/me/points/account",
        headers={"Authorization": f"Bearer {target_token}"},
    )
    logs = load_audit_logs(points_context)
    point_logs = [item for item in logs if item.action == "points.manual_adjustment.create"]

    assert denied_response.status_code == 403
    assert response.status_code == 200
    assert response.json()["data"]["account"]["balance"] == 12
    assert repeated_response.status_code == 200
    assert repeated_response.json()["data"]["ledger_entry"]["id"] == response.json()["data"]["ledger_entry"]["id"]
    assert target_account_response.json()["data"]["balance"] == 12
    assert len(point_logs) == 1
    assert point_logs[0].actor_id == admin_id
    assert point_logs[0].target_type == "point_account"
    assert point_logs[0].extra["target_user_id"] == target_id


def test_ledger_reverse_api_is_system_fallback(points_context: PointsTestContext) -> None:
    """反向流水接口只服务系统兜底，并且同样需要幂等键和审计。"""

    admin_token, admin_id = login_and_get_identity(
        points_context.client,
        openid="points_reverse_admin",
        display_name="积分兜底管理员",
    )
    target_token, target_id = login_and_get_identity(
        points_context.client,
        openid="points_reverse_target",
        display_name="积分反向目标",
    )
    grant_role_to_user(points_context, user_id=admin_id, role_code="system_super_admin")

    adjustment_response = points_context.client.post(
        "/api/v1/points/manual-adjustments",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "points:api:reverse:seed"},
        json={"user_id": target_id, "amount": 9, "reason": "测试反向流水初始发放"},
    )
    ledger_entry_id = adjustment_response.json()["data"]["ledger_entry"]["id"]
    reverse_response = points_context.client.post(
        f"/api/v1/points/ledger/{ledger_entry_id}/reverse",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "points:api:reverse"},
        json={"reason": "测试追回异常发放"},
    )
    repeated_response = points_context.client.post(
        f"/api/v1/points/ledger/{ledger_entry_id}/reverse",
        headers={"Authorization": f"Bearer {admin_token}", "Idempotency-Key": "points:api:reverse"},
        json={"reason": "测试追回异常发放"},
    )
    target_account_response = points_context.client.get(
        "/api/v1/me/points/account",
        headers={"Authorization": f"Bearer {target_token}"},
    )
    logs = load_audit_logs(points_context)
    reverse_logs = [item for item in logs if item.action == "points.ledger.reverse"]

    assert adjustment_response.status_code == 200
    assert reverse_response.status_code == 200
    assert repeated_response.status_code == 200
    assert (
        repeated_response.json()["data"]["ledger_entry"]["id"]
        == reverse_response.json()["data"]["ledger_entry"]["id"]
    )
    assert reverse_response.json()["data"]["ledger_entry"]["direction"] == "reversal"
    assert target_account_response.json()["data"]["balance"] == 0
    assert len(reverse_logs) == 1
    assert reverse_logs[0].actor_id == admin_id


def test_points_manager_can_view_user_point_account(points_context: PointsTestContext) -> None:
    """积分账本查看员可以查看他人积分账户，但不能人工调整积分。"""

    manager_token, manager_id = login_and_get_identity(
        points_context.client,
        openid="points_view_manager",
        display_name="积分账本查看员",
    )
    _, target_id = login_and_get_identity(
        points_context.client,
        openid="points_view_target",
        display_name="积分被查看用户",
    )
    grant_role_to_user(points_context, user_id=manager_id, role_code="points_manager")

    account_response = points_context.client.get(
        f"/api/v1/points/accounts/{target_id}",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    adjustment_response = points_context.client.post(
        "/api/v1/points/manual-adjustments",
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "points:api:view-only"},
        json={"user_id": target_id, "amount": 1, "reason": "查看员不能调整"},
    )

    assert account_response.status_code == 200
    assert account_response.json()["data"]["user_id"] == target_id
    assert adjustment_response.status_code == 403


def test_points_rule_manager_can_manage_fixed_rules(points_context: PointsTestContext) -> None:
    """积分规则管理员可以维护固定规则，但不会自动获得系统兜底改分权限。"""

    manager_token, manager_id = login_and_get_identity(
        points_context.client,
        openid="points_rule_manager",
        display_name="积分规则管理员",
    )
    _, target_id = login_and_get_identity(
        points_context.client,
        openid="points_rule_target",
        display_name="积分规则目标用户",
    )
    grant_role_to_user(points_context, user_id=manager_id, role_code="points_rule_manager")
    now = utc_now()

    create_response = points_context.client.post(
        "/api/v1/points/rules",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={
            "code": "weekly-cleaning",
            "name": "每周打扫卫生",
            "amount": 10,
            "description": "测试固定规则",
            "effective_from": now.isoformat(),
            "effective_to": (now + timedelta(days=30)).isoformat(),
        },
    )
    rule_id = create_response.json()["data"]["id"]
    list_response = points_context.client.get(
        "/api/v1/points/rules",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    revoke_response = points_context.client.post(
        f"/api/v1/points/rules/{rule_id}/revoke",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"reason": "测试撤回固定规则"},
    )
    adjustment_response = points_context.client.post(
        "/api/v1/points/manual-adjustments",
        headers={"Authorization": f"Bearer {manager_token}", "Idempotency-Key": "points:api:rule-manager"},
        json={"user_id": target_id, "amount": 1, "reason": "规则管理员不能兜底改分"},
    )
    logs = load_audit_logs(points_context)
    rule_log_actions = [item.action for item in logs if item.action.startswith("points.rule.")]

    assert create_response.status_code == 200
    assert create_response.json()["data"]["amount"] == 10
    assert list_response.status_code == 200
    assert [item["code"] for item in list_response.json()["data"]] == ["weekly-cleaning"]
    assert revoke_response.status_code == 200
    assert revoke_response.json()["data"]["status"] == "revoked"
    assert adjustment_response.status_code == 403
    assert rule_log_actions == ["points.rule.create", "points.rule.revoke"]


def test_temporary_rule_api_has_application_and_review_flow(points_context: PointsTestContext) -> None:
    """临时规则必须先申请再审批，申请人与审批权限分离。"""

    applicant_token, applicant_id = login_and_get_identity(
        points_context.client,
        openid="points_temp_applicant",
        display_name="临时规则申请人",
    )
    reviewer_token, reviewer_id = login_and_get_identity(
        points_context.client,
        openid="points_temp_reviewer",
        display_name="临时规则审批人",
    )
    grant_role_to_user(points_context, user_id=applicant_id, role_code="points_rule_applicant")
    grant_role_to_user(points_context, user_id=reviewer_id, role_code="points_rule_reviewer")
    now = utc_now()

    submit_response = points_context.client.post(
        "/api/v1/points/rules/temporary",
        headers={"Authorization": f"Bearer {applicant_token}"},
        json={
            "name": "临时展台搭建",
            "task_type": "special_task",
            "target_scope": "members",
            "reason": "临时活动需要搭建展台",
            "completion_requirements": "按要求完成搬运和搭建",
            "amount_per_completion": 10,
            "max_participants": 2,
            "total_points_limit": 20,
            "effective_from": now.isoformat(),
            "effective_to": (now + timedelta(days=7)).isoformat(),
        },
    )
    rule_id = submit_response.json()["data"]["id"]
    applicant_approve_response = points_context.client.post(
        f"/api/v1/points/rules/temporary/{rule_id}/approve",
        headers={"Authorization": f"Bearer {applicant_token}"},
        json={"approval_reason": "申请人不能自己审批"},
    )
    approve_response = points_context.client.post(
        f"/api/v1/points/rules/temporary/{rule_id}/approve",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={"approval_reason": "符合临时任务规则"},
    )
    revoke_response = points_context.client.post(
        f"/api/v1/points/rules/temporary/{rule_id}/revoke",
        headers={"Authorization": f"Bearer {reviewer_token}"},
        json={"revoke_reason": "测试撤回临时规则", "revoke_impact_note": "通知未领取任务的成员"},
    )
    logs = load_audit_logs(points_context)
    temporary_log_actions = [item.action for item in logs if item.action.startswith("points.temporary_rule.")]

    assert submit_response.status_code == 200
    assert submit_response.json()["data"]["approval_status"] == "pending"
    assert applicant_approve_response.status_code == 403
    assert approve_response.status_code == 200
    assert approve_response.json()["data"]["approval_status"] == "approved"
    assert approve_response.json()["data"]["generated_point_rule"]["rule_type"] == "temporary_task_template"
    assert revoke_response.status_code == 200
    assert revoke_response.json()["data"]["revoke_status"] == "revoked"
    assert temporary_log_actions == [
        "points.temporary_rule.submit",
        "points.temporary_rule.approve",
        "points.temporary_rule.revoke",
    ]
