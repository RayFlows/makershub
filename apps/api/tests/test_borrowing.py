# tests/test_borrowing.py
"""
资源与物资借用测试

本文件验证第一阶段物资借用闭环：资源管理员维护物资，普通成员提交借用申请，审批通过
后扣减可借库存并冻结押金，正常归还后恢复库存并解冻押金。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
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
from app.modules.borrowing.models import BorrowApplication, BorrowItem, BorrowReturn, BorrowReview
from app.modules.identity.models import AuthSession, EmailPasswordAccount, EmailVerificationCode, User, WechatAccount
from app.modules.organization.models import Department, MemberProfile, Position, UserPosition
from app.modules.points.models import (
    PointAccount,
    PointHold,
    PointLedgerEntry,
    PointRule,
    TemporaryPointRule,
    TemporaryPointRuleEvent,
)
from app.modules.resources.models import Material, ResourceCategory
from app.modules.workbench.models import WorkbenchTask


@dataclass(frozen=True)
class BorrowingTestContext:
    """物资借用接口测试上下文。"""

    client: TestClient
    session_factory: async_sessionmaker[AsyncSession]


BORROW_EXPECTED_RETURN_AT = "2026-06-01T12:00:00+00:00"


@pytest.fixture
def borrowing_context(tmp_path: Path) -> Iterator[BorrowingTestContext]:
    """创建使用临时 SQLite 数据库的物资借用接口测试上下文。"""

    # 显式引用模型，确保 Base.metadata 在 create_all 前已经收集相关表。
    _ = (
        AuditLog,
        AuthSession,
        BorrowApplication,
        BorrowItem,
        BorrowReturn,
        BorrowReview,
        Department,
        EmailPasswordAccount,
        EmailVerificationCode,
        Material,
        MemberProfile,
        Permission,
        PointAccount,
        PointHold,
        PointLedgerEntry,
        PointRule,
        Position,
        ResourceCategory,
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

    database_path = tmp_path / "borrowing.db"
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
        yield BorrowingTestContext(client=client, session_factory=session_factory)

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
    context: BorrowingTestContext,
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


def seed_point_account(
    context: BorrowingTestContext,
    *,
    user_id: int,
    balance: int,
) -> None:
    """在测试数据库中准备用户积分账户余额。"""

    async def seed() -> None:
        async with context.session_factory() as session:
            account = PointAccount(
                user_id=user_id,
                balance=balance,
                frozen_balance=0,
                status="active",
            )
            session.add(account)
            await session.commit()

    asyncio.run(seed())


def seed_member_profile(context: BorrowingTestContext, *, user_id: int) -> None:
    """准备完整成员资料，供借用申请生成申请人快照。"""

    async def seed() -> None:
        async with context.session_factory() as session:
            profile = MemberProfile(
                user_id=user_id,
                real_name="借用成员",
                student_id=f"2026{user_id:06d}",
                phone=f"139{user_id:08d}",
                email=f"borrower{user_id}@example.com",
                grade="2026",
                major="电子信息工程",
            )
            session.add(profile)
            await session.commit()

    asyncio.run(seed())


def seed_borrower_for_borrowing(
    context: BorrowingTestContext,
    *,
    user_id: int,
    balance: int,
) -> None:
    """准备借用申请所需的资料和积分账户。"""

    seed_member_profile(context, user_id=user_id)
    seed_point_account(context, user_id=user_id, balance=balance)


def update_point_account_balance(
    context: BorrowingTestContext,
    *,
    user_id: int,
    balance: int,
) -> None:
    """直接调整测试积分账户余额，用于模拟等待审核期间积分变化。"""

    async def update() -> None:
        async with context.session_factory() as session:
            account = await session.scalar(select(PointAccount).where(PointAccount.user_id == user_id))
            assert account is not None
            account.balance = balance
            await session.commit()

    asyncio.run(update())


def get_material_stock(context: BorrowingTestContext, *, material_id: int) -> tuple[int, int]:
    """读取物资总量和可借数量。"""

    async def load() -> tuple[int, int]:
        async with context.session_factory() as session:
            material = await session.scalar(select(Material).where(Material.id == material_id))
            assert material is not None
            return material.total_quantity, material.available_quantity

    return asyncio.run(load())


def get_point_account_balance(context: BorrowingTestContext, *, user_id: int) -> tuple[int, int]:
    """读取用户积分账户总余额和冻结余额。"""

    async def load() -> tuple[int, int]:
        async with context.session_factory() as session:
            account = await session.scalar(select(PointAccount).where(PointAccount.user_id == user_id))
            assert account is not None
            return account.balance, account.frozen_balance

    return asyncio.run(load())


def update_snapshot_sources(
    context: BorrowingTestContext,
    *,
    user_id: int,
    material_id: int,
) -> None:
    """修改成员资料和物资台账，用于验证历史快照不被污染。"""

    async def update() -> None:
        async with context.session_factory() as session:
            profile = await session.scalar(select(MemberProfile).where(MemberProfile.user_id == user_id))
            assert profile is not None
            profile.real_name = "更新后姓名"
            profile.phone = "13999990000"
            profile.email = "updated-borrower@example.com"
            profile.grade = "2027"
            profile.major = "自动化"

            material = await session.scalar(select(Material).where(Material.id == material_id))
            assert material is not None
            material.name = "改名后的开发板"
            material.deposit_points = 20
            if material.category_id is not None:
                category = await session.scalar(
                    select(ResourceCategory).where(ResourceCategory.id == material.category_id),
                )
                assert category is not None
                category.name = "改名后的分类"
            await session.commit()

    asyncio.run(update())


def create_material_for_test(
    context: BorrowingTestContext,
    *,
    manager_token: str,
    total_quantity: int = 5,
    deposit_points: int = 5,
) -> int:
    """通过接口创建测试物资并返回物资 ID。"""

    category_response = context.client.post(
        "/api/v1/resources/material-categories",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"name": "电子元件", "sort_order": 1},
    )
    assert category_response.status_code == 200
    category_id = category_response.json()["data"]["id"]
    material_response = context.client.post(
        "/api/v1/resources/materials",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={
            "name": "Arduino Uno",
            "category_id": category_id,
            "description": "开发板",
            "location": "A 区",
            "cabinet_no": "A1",
            "shelf_no": "2",
            "total_quantity": total_quantity,
            "deposit_points": deposit_points,
        },
    )
    assert material_response.status_code == 200
    return material_response.json()["data"]["id"]


def test_material_borrow_create_writes_applicant_and_item_snapshots(
    borrowing_context: BorrowingTestContext,
) -> None:
    """借用申请保存申请人和物资明细快照，历史详情不被后续资料修改污染。"""

    manager_token, manager_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_snapshot_manager",
        display_name="快照管理员",
    )
    borrower_token, borrower_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_snapshot_member",
        display_name="快照成员",
    )
    grant_role_to_user(borrowing_context, user_id=manager_id, role_code="resource_manager")
    seed_borrower_for_borrowing(borrowing_context, user_id=borrower_id, balance=50)
    material_id = create_material_for_test(borrowing_context, manager_token=manager_token)

    create_response = borrowing_context.client.post(
        "/api/v1/borrowing/applications",
        headers={"Authorization": f"Bearer {borrower_token}"},
        json={
            "borrow_type": "material",
            "usage_type": "personal",
            "reason": "测试快照",
            "expected_return_at": BORROW_EXPECTED_RETURN_AT,
            "items": [{"material_id": material_id, "quantity": 2}],
        },
    )
    application_id = create_response.json()["data"]["id"]
    update_snapshot_sources(borrowing_context, user_id=borrower_id, material_id=material_id)
    detail_response = borrowing_context.client.get(
        f"/api/v1/borrowing/applications/{application_id}",
        headers={"Authorization": f"Bearer {borrower_token}"},
    )
    list_response = borrowing_context.client.get(
        "/api/v1/borrowing/applications?mine=true",
        headers={"Authorization": f"Bearer {borrower_token}"},
    )

    assert create_response.status_code == 200
    create_data = create_response.json()["data"]
    assert create_data["applicant_snapshot"]["name"] == "借用成员"
    assert create_data["applicant_snapshot"]["email"] == f"borrower{borrower_id}@example.com"
    assert create_data["items"][0]["material_name"] == "Arduino Uno"
    assert create_data["items"][0]["category_name"] == "电子元件"
    assert create_data["items"][0]["unit_deposit_points"] == 5
    assert create_data["items"][0]["subtotal_deposit_points"] == 10

    assert detail_response.status_code == 200
    detail_data = detail_response.json()["data"]
    assert detail_data["applicant_snapshot"]["name"] == "借用成员"
    assert detail_data["applicant_snapshot"]["phone"] == f"139{borrower_id:08d}"
    assert detail_data["applicant_current_contact"] == {
        "phone": "13999990000",
        "email": "updated-borrower@example.com",
    }
    assert detail_data["items"][0]["material_name"] == "Arduino Uno"
    assert detail_data["items"][0]["category_name"] == "电子元件"
    assert detail_data["items"][0]["unit_deposit_points"] == 5

    assert list_response.status_code == 200
    list_item = list_response.json()["data"]["items"][0]
    assert list_item["applicant_summary"] == {
        "name": "借用成员",
        "grade": "2026",
        "major": "电子信息工程",
    }
    assert list_item["material_summary"] == "Arduino Uno x 2"
    assert "applicant_snapshot" not in list_item
    assert "applicant_current_contact" not in list_item
    assert "items" not in list_item


def test_material_borrow_approval_freezes_deposit_and_return_releases_it(
    borrowing_context: BorrowingTestContext,
) -> None:
    """物资借用审批通过后扣库存冻结押金，正常归还后恢复库存并解冻。"""

    manager_token, manager_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_manager",
        display_name="资源管理员",
    )
    borrower_token, borrower_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_member",
        display_name="借用成员",
    )
    grant_role_to_user(borrowing_context, user_id=manager_id, role_code="resource_manager")
    seed_borrower_for_borrowing(borrowing_context, user_id=borrower_id, balance=50)
    material_id = create_material_for_test(borrowing_context, manager_token=manager_token)

    create_response = borrowing_context.client.post(
        "/api/v1/borrowing/applications",
        headers={"Authorization": f"Bearer {borrower_token}"},
        json={
            "borrow_type": "material",
            "usage_type": "personal",
            "reason": "课程展示需要",
            "expected_return_at": BORROW_EXPECTED_RETURN_AT,
            "items": [{"material_id": material_id, "quantity": 2}],
        },
    )
    application_id = create_response.json()["data"]["id"]
    approve_response = borrowing_context.client.post(
        f"/api/v1/borrowing/applications/{application_id}/review",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"decision": "approve", "comment": "用途合理"},
    )
    stock_after_approval = get_material_stock(borrowing_context, material_id=material_id)
    balance_after_approval = get_point_account_balance(borrowing_context, user_id=borrower_id)
    return_response = borrowing_context.client.post(
        f"/api/v1/borrowing/applications/{application_id}/return",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"condition": "normal"},
    )
    stock_after_return = get_material_stock(borrowing_context, material_id=material_id)
    balance_after_return = get_point_account_balance(borrowing_context, user_id=borrower_id)

    assert create_response.status_code == 200
    assert create_response.json()["data"]["status"] == "pending_review"
    assert create_response.json()["data"]["deposit_points"] == 10
    assert approve_response.status_code == 200
    assert approve_response.json()["data"]["status"] == "approved"
    assert approve_response.json()["data"]["point_hold_id"] is not None
    assert stock_after_approval == (5, 3)
    assert balance_after_approval == (50, 10)
    assert return_response.status_code == 200
    assert return_response.json()["data"]["status"] == "returned"
    assert return_response.json()["data"]["returns"][0]["point_action"] == "release"
    assert stock_after_return == (5, 5)
    assert balance_after_return == (50, 0)


def test_material_borrow_exception_return_deducts_full_deposit(
    borrowing_context: BorrowingTestContext,
) -> None:
    """异常归还会全额扣除本次申请冻结押金，不恢复可借库存。"""

    manager_token, manager_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_exception_manager",
        display_name="异常归还管理员",
    )
    borrower_token, borrower_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_exception_member",
        display_name="异常归还成员",
    )
    grant_role_to_user(borrowing_context, user_id=manager_id, role_code="resource_manager")
    seed_borrower_for_borrowing(borrowing_context, user_id=borrower_id, balance=50)
    material_id = create_material_for_test(borrowing_context, manager_token=manager_token)

    create_response = borrowing_context.client.post(
        "/api/v1/borrowing/applications",
        headers={"Authorization": f"Bearer {borrower_token}"},
        json={
            "borrow_type": "material",
            "usage_type": "personal",
            "reason": "测试异常归还",
            "expected_return_at": BORROW_EXPECTED_RETURN_AT,
            "items": [{"material_id": material_id, "quantity": 2}],
        },
    )
    application_id = create_response.json()["data"]["id"]
    approve_response = borrowing_context.client.post(
        f"/api/v1/borrowing/applications/{application_id}/review",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"decision": "approve", "comment": "用途合理"},
    )
    return_response = borrowing_context.client.post(
        f"/api/v1/borrowing/applications/{application_id}/return",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"condition": "damaged", "comment": "损坏无法正常入库"},
    )
    stock_after_return = get_material_stock(borrowing_context, material_id=material_id)
    balance_after_return = get_point_account_balance(borrowing_context, user_id=borrower_id)

    assert create_response.status_code == 200
    assert approve_response.status_code == 200
    assert approve_response.json()["data"]["deposit_points"] == 10
    assert return_response.status_code == 200
    assert return_response.json()["data"]["status"] == "exception_closed"
    assert return_response.json()["data"]["returns"][0]["condition"] == "damaged"
    assert return_response.json()["data"]["returns"][0]["point_action"] == "deduct"
    assert stock_after_return == (5, 3)
    assert balance_after_return == (40, 0)


def test_material_borrow_exception_return_requires_comment(
    borrowing_context: BorrowingTestContext,
) -> None:
    """异常归还必须填写备注，避免扣押金和库存异常缺少审计原因。"""

    manager_token, manager_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_exception_comment_manager",
        display_name="异常备注管理员",
    )
    borrower_token, borrower_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_exception_comment_member",
        display_name="异常备注成员",
    )
    grant_role_to_user(borrowing_context, user_id=manager_id, role_code="resource_manager")
    seed_borrower_for_borrowing(borrowing_context, user_id=borrower_id, balance=50)
    material_id = create_material_for_test(borrowing_context, manager_token=manager_token)

    create_response = borrowing_context.client.post(
        "/api/v1/borrowing/applications",
        headers={"Authorization": f"Bearer {borrower_token}"},
        json={
            "borrow_type": "material",
            "usage_type": "personal",
            "reason": "测试异常归还备注",
            "expected_return_at": BORROW_EXPECTED_RETURN_AT,
            "items": [{"material_id": material_id, "quantity": 2}],
        },
    )
    application_id = create_response.json()["data"]["id"]
    approve_response = borrowing_context.client.post(
        f"/api/v1/borrowing/applications/{application_id}/review",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"decision": "approve", "comment": "用途合理"},
    )
    return_response = borrowing_context.client.post(
        f"/api/v1/borrowing/applications/{application_id}/return",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"condition": "lost", "comment": "  "},
    )
    stock_after_return = get_material_stock(borrowing_context, material_id=material_id)
    balance_after_return = get_point_account_balance(borrowing_context, user_id=borrower_id)

    assert create_response.status_code == 200
    assert approve_response.status_code == 200
    assert return_response.status_code == 422
    assert return_response.json()["error"]["code"] == "BORROW_FIELD_REQUIRED"
    assert stock_after_return == (5, 3)
    assert balance_after_return == (50, 10)


def test_material_borrow_exception_return_is_terminal(
    borrowing_context: BorrowingTestContext,
) -> None:
    """异常归还是第一阶段终态，不能再用正常归还把库存和押金洗回去。"""

    manager_token, manager_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_exception_terminal_manager",
        display_name="异常终态管理员",
    )
    borrower_token, borrower_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_exception_terminal_member",
        display_name="异常终态成员",
    )
    grant_role_to_user(borrowing_context, user_id=manager_id, role_code="resource_manager")
    seed_borrower_for_borrowing(borrowing_context, user_id=borrower_id, balance=50)
    material_id = create_material_for_test(borrowing_context, manager_token=manager_token)

    create_response = borrowing_context.client.post(
        "/api/v1/borrowing/applications",
        headers={"Authorization": f"Bearer {borrower_token}"},
        json={
            "borrow_type": "material",
            "usage_type": "personal",
            "reason": "测试异常归还终态",
            "expected_return_at": BORROW_EXPECTED_RETURN_AT,
            "items": [{"material_id": material_id, "quantity": 2}],
        },
    )
    application_id = create_response.json()["data"]["id"]
    approve_response = borrowing_context.client.post(
        f"/api/v1/borrowing/applications/{application_id}/review",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"decision": "approve", "comment": "用途合理"},
    )
    exception_return_response = borrowing_context.client.post(
        f"/api/v1/borrowing/applications/{application_id}/return",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"condition": "consumed", "comment": "耗材已使用完"},
    )
    repeat_return_response = borrowing_context.client.post(
        f"/api/v1/borrowing/applications/{application_id}/return",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"condition": "normal"},
    )
    stock_after_repeat = get_material_stock(borrowing_context, material_id=material_id)
    balance_after_repeat = get_point_account_balance(borrowing_context, user_id=borrower_id)

    assert create_response.status_code == 200
    assert approve_response.status_code == 200
    assert exception_return_response.status_code == 200
    assert exception_return_response.json()["data"]["status"] == "exception_closed"
    assert repeat_return_response.status_code == 409
    assert repeat_return_response.json()["error"]["code"] == "BORROW_APPLICATION_NOT_RETURNABLE"
    assert stock_after_repeat == (5, 3)
    assert balance_after_repeat == (40, 0)


def test_material_borrow_approval_rejects_when_stock_is_insufficient(
    borrowing_context: BorrowingTestContext,
) -> None:
    """审批时库存不足会自动驳回申请，不扣库存也不冻结押金。"""

    manager_token, manager_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_shortage_manager",
        display_name="短缺管理员",
    )
    borrower_token, borrower_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_shortage_member",
        display_name="短缺成员",
    )
    grant_role_to_user(borrowing_context, user_id=manager_id, role_code="resource_manager")
    seed_borrower_for_borrowing(borrowing_context, user_id=borrower_id, balance=50)
    material_id = create_material_for_test(
        borrowing_context,
        manager_token=manager_token,
        total_quantity=1,
        deposit_points=5,
    )

    create_response = borrowing_context.client.post(
        "/api/v1/borrowing/applications",
        headers={"Authorization": f"Bearer {borrower_token}"},
        json={
            "borrow_type": "material",
            "usage_type": "personal",
            "reason": "测试库存不足",
            "expected_return_at": BORROW_EXPECTED_RETURN_AT,
            "items": [{"material_id": material_id, "quantity": 2}],
        },
    )
    application_id = create_response.json()["data"]["id"]
    approve_response = borrowing_context.client.post(
        f"/api/v1/borrowing/applications/{application_id}/review",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"decision": "approve", "comment": "尝试审批"},
    )
    stock_after_review = get_material_stock(borrowing_context, material_id=material_id)
    balance_after_review = get_point_account_balance(borrowing_context, user_id=borrower_id)

    assert create_response.status_code == 200
    assert approve_response.status_code == 200
    assert approve_response.json()["data"]["status"] == "rejected"
    assert "库存不足" in approve_response.json()["data"]["reviews"][0]["comment"]
    assert approve_response.json()["data"]["point_hold_id"] is None
    assert stock_after_review == (1, 1)
    assert balance_after_review == (50, 0)


def test_material_borrow_create_rejects_when_deposit_is_insufficient(
    borrowing_context: BorrowingTestContext,
) -> None:
    """提交借用申请时可用积分不足会直接拒绝，不创建待审核申请。"""

    manager_token, manager_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_create_deposit_manager",
        display_name="押金管理员",
    )
    borrower_token, borrower_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_create_deposit_member",
        display_name="押金不足成员",
    )
    grant_role_to_user(borrowing_context, user_id=manager_id, role_code="resource_manager")
    seed_borrower_for_borrowing(borrowing_context, user_id=borrower_id, balance=5)
    material_id = create_material_for_test(
        borrowing_context,
        manager_token=manager_token,
        total_quantity=5,
        deposit_points=5,
    )

    create_response = borrowing_context.client.post(
        "/api/v1/borrowing/applications",
        headers={"Authorization": f"Bearer {borrower_token}"},
        json={
            "borrow_type": "material",
            "usage_type": "personal",
            "reason": "押金不足仍尝试提交",
            "expected_return_at": BORROW_EXPECTED_RETURN_AT,
            "items": [{"material_id": material_id, "quantity": 2}],
        },
    )
    stock_after_create = get_material_stock(borrowing_context, material_id=material_id)
    balance_after_create = get_point_account_balance(borrowing_context, user_id=borrower_id)

    assert create_response.status_code == 409
    assert create_response.json()["error"]["code"] == "BORROW_DEPOSIT_NOT_ENOUGH"
    assert create_response.json()["error"]["details"]["required_deposit_points"] == 10
    assert stock_after_create == (5, 5)
    assert balance_after_create == (5, 0)


def test_material_borrow_create_requires_expected_return_at(
    borrowing_context: BorrowingTestContext,
) -> None:
    """提交个人物资借用必须填写预计归还时间，后端不能只依赖端侧日期选择器。"""

    manager_token, manager_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_expected_return_manager",
        display_name="归还时间管理员",
    )
    borrower_token, borrower_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_expected_return_member",
        display_name="归还时间成员",
    )
    grant_role_to_user(borrowing_context, user_id=manager_id, role_code="resource_manager")
    seed_borrower_for_borrowing(borrowing_context, user_id=borrower_id, balance=50)
    material_id = create_material_for_test(borrowing_context, manager_token=manager_token)

    create_response = borrowing_context.client.post(
        "/api/v1/borrowing/applications",
        headers={"Authorization": f"Bearer {borrower_token}"},
        json={
            "borrow_type": "material",
            "usage_type": "personal",
            "reason": "未填写预计归还时间",
            "items": [{"material_id": material_id, "quantity": 1}],
        },
    )

    assert create_response.status_code == 422
    assert create_response.json()["error"]["code"] == "BORROW_FIELD_REQUIRED"


def test_material_borrow_create_requires_complete_member_profile(
    borrowing_context: BorrowingTestContext,
) -> None:
    """提交借用申请时必须能从成员资料生成申请人快照。"""

    manager_token, manager_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_profile_required_manager",
        display_name="资料校验管理员",
    )
    borrower_token, borrower_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_profile_required_member",
        display_name="资料缺失成员",
    )
    grant_role_to_user(borrowing_context, user_id=manager_id, role_code="resource_manager")
    seed_point_account(borrowing_context, user_id=borrower_id, balance=50)
    material_id = create_material_for_test(borrowing_context, manager_token=manager_token)

    create_response = borrowing_context.client.post(
        "/api/v1/borrowing/applications",
        headers={"Authorization": f"Bearer {borrower_token}"},
        json={
            "borrow_type": "material",
            "usage_type": "personal",
            "reason": "资料未完善",
            "expected_return_at": BORROW_EXPECTED_RETURN_AT,
            "items": [{"material_id": material_id, "quantity": 1}],
        },
    )

    assert create_response.status_code == 422
    assert create_response.json()["error"]["code"] == "BORROW_PROFILE_INCOMPLETE"


def test_material_borrow_review_rejects_when_deposit_becomes_insufficient(
    borrowing_context: BorrowingTestContext,
) -> None:
    """等待审核期间可用积分变少时，审批通过动作会自动驳回并保留记录。"""

    manager_token, manager_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_review_deposit_manager",
        display_name="押金复核管理员",
    )
    borrower_token, borrower_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_review_deposit_member",
        display_name="审核前押金不足成员",
    )
    grant_role_to_user(borrowing_context, user_id=manager_id, role_code="resource_manager")
    seed_borrower_for_borrowing(borrowing_context, user_id=borrower_id, balance=10)
    material_id = create_material_for_test(
        borrowing_context,
        manager_token=manager_token,
        total_quantity=5,
        deposit_points=5,
    )

    create_response = borrowing_context.client.post(
        "/api/v1/borrowing/applications",
        headers={"Authorization": f"Bearer {borrower_token}"},
        json={
            "borrow_type": "material",
            "usage_type": "personal",
            "reason": "提交时押金足够",
            "expected_return_at": BORROW_EXPECTED_RETURN_AT,
            "items": [{"material_id": material_id, "quantity": 2}],
        },
    )
    application_id = create_response.json()["data"]["id"]
    update_point_account_balance(borrowing_context, user_id=borrower_id, balance=4)

    approve_response = borrowing_context.client.post(
        f"/api/v1/borrowing/applications/{application_id}/review",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"decision": "approve", "comment": "审核时余额不足"},
    )
    stock_after_review = get_material_stock(borrowing_context, material_id=material_id)
    balance_after_review = get_point_account_balance(borrowing_context, user_id=borrower_id)

    assert create_response.status_code == 200
    assert approve_response.status_code == 200
    assert approve_response.json()["data"]["status"] == "rejected"
    assert "积分余额不足" in approve_response.json()["data"]["reviews"][0]["comment"]
    assert approve_response.json()["data"]["point_hold_id"] is None
    assert stock_after_review == (5, 5)
    assert balance_after_review == (4, 0)


def test_material_borrow_manual_reject_requires_comment(
    borrowing_context: BorrowingTestContext,
) -> None:
    """人工驳回必须填写理由，避免申请人只看到无原因打回。"""

    manager_token, manager_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_manual_reject_comment_manager",
        display_name="驳回理由管理员",
    )
    borrower_token, borrower_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_manual_reject_comment_member",
        display_name="驳回理由成员",
    )
    grant_role_to_user(borrowing_context, user_id=manager_id, role_code="resource_manager")
    seed_borrower_for_borrowing(borrowing_context, user_id=borrower_id, balance=50)
    material_id = create_material_for_test(borrowing_context, manager_token=manager_token)

    create_response = borrowing_context.client.post(
        "/api/v1/borrowing/applications",
        headers={"Authorization": f"Bearer {borrower_token}"},
        json={
            "borrow_type": "material",
            "usage_type": "personal",
            "reason": "测试空理由驳回",
            "expected_return_at": BORROW_EXPECTED_RETURN_AT,
            "items": [{"material_id": material_id, "quantity": 1}],
        },
    )
    application_id = create_response.json()["data"]["id"]
    reject_response = borrowing_context.client.post(
        f"/api/v1/borrowing/applications/{application_id}/review",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"decision": "reject", "comment": "  "},
    )
    detail_response = borrowing_context.client.get(
        f"/api/v1/borrowing/applications/{application_id}",
        headers={"Authorization": f"Bearer {borrower_token}"},
    )

    assert create_response.status_code == 200
    assert reject_response.status_code == 422
    assert reject_response.json()["error"]["code"] == "BORROW_FIELD_REQUIRED"
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["status"] == "pending_review"
    assert detail_response.json()["data"]["reviews"] == []


def test_material_borrow_cancel_keeps_application_record(
    borrowing_context: BorrowingTestContext,
) -> None:
    """成员取消申请后保留记录，便于后续追踪。"""

    manager_token, manager_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_cancel_manager",
        display_name="取消管理员",
    )
    borrower_token, borrower_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_cancel_member",
        display_name="取消成员",
    )
    grant_role_to_user(borrowing_context, user_id=manager_id, role_code="resource_manager")
    seed_borrower_for_borrowing(borrowing_context, user_id=borrower_id, balance=50)
    material_id = create_material_for_test(borrowing_context, manager_token=manager_token)
    create_response = borrowing_context.client.post(
        "/api/v1/borrowing/applications",
        headers={"Authorization": f"Bearer {borrower_token}"},
        json={
            "borrow_type": "material",
            "usage_type": "personal",
            "reason": "临时借用",
            "expected_return_at": BORROW_EXPECTED_RETURN_AT,
            "items": [{"material_id": material_id, "quantity": 1}],
        },
    )
    application_id = create_response.json()["data"]["id"]

    cancel_response = borrowing_context.client.post(
        f"/api/v1/borrowing/applications/{application_id}/cancel",
        headers={"Authorization": f"Bearer {borrower_token}"},
        json={"cancel_reason": "计划取消"},
    )
    detail_response = borrowing_context.client.get(
        f"/api/v1/borrowing/applications/{application_id}",
        headers={"Authorization": f"Bearer {borrower_token}"},
    )

    assert cancel_response.status_code == 200
    assert cancel_response.json()["data"]["status"] == "cancelled"
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["status"] == "cancelled"
    assert detail_response.json()["data"]["cancel_reason"] == "计划取消"


def test_material_borrow_rejected_application_can_be_cancelled_by_owner(
    borrowing_context: BorrowingTestContext,
) -> None:
    """已驳回申请允许申请人取消收尾，但审核记录仍然保留。"""

    manager_token, manager_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_rejected_cancel_manager",
        display_name="驳回取消管理员",
    )
    borrower_token, borrower_id = login_and_get_identity(
        borrowing_context.client,
        openid="borrow_rejected_cancel_member",
        display_name="驳回取消成员",
    )
    grant_role_to_user(borrowing_context, user_id=manager_id, role_code="resource_manager")
    seed_borrower_for_borrowing(borrowing_context, user_id=borrower_id, balance=50)
    material_id = create_material_for_test(borrowing_context, manager_token=manager_token)
    create_response = borrowing_context.client.post(
        "/api/v1/borrowing/applications",
        headers={"Authorization": f"Bearer {borrower_token}"},
        json={
            "borrow_type": "material",
            "usage_type": "personal",
            "reason": "测试驳回后取消",
            "expected_return_at": BORROW_EXPECTED_RETURN_AT,
            "items": [{"material_id": material_id, "quantity": 1}],
        },
    )
    application_id = create_response.json()["data"]["id"]
    reject_response = borrowing_context.client.post(
        f"/api/v1/borrowing/applications/{application_id}/review",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={"decision": "reject", "comment": "用途不充分"},
    )

    cancel_response = borrowing_context.client.post(
        f"/api/v1/borrowing/applications/{application_id}/cancel",
        headers={"Authorization": f"Bearer {borrower_token}"},
        json={"cancel_reason": "已知悉驳回原因，关闭申请"},
    )

    assert create_response.status_code == 200
    assert reject_response.status_code == 200
    assert reject_response.json()["data"]["status"] == "rejected"
    assert cancel_response.status_code == 200
    assert cancel_response.json()["data"]["status"] == "cancelled"
    assert cancel_response.json()["data"]["reviews"][0]["decision"] == "reject"
    assert cancel_response.json()["data"]["reviews"][0]["comment"] == "用途不充分"
    assert cancel_response.json()["data"]["cancel_reason"] == "已知悉驳回原因，关闭申请"
