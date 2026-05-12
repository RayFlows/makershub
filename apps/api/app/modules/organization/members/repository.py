# app/modules/organization/members/repository.py
"""
成员资料仓储

本文件封装 users 与 member_profiles 在成员管理场景下需要的查询和写入。用户主体属于
identity 域事实，但组织成员列表需要以用户主体为根聚合资料，因此这里只做读取聚合。
"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.identity.models import EmailPasswordAccount, User
from app.modules.organization.models import MemberProfile


class MemberRepository:
    """成员资料仓储。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_member_profile_by_user_id(self, user_id: int) -> MemberProfile | None:
        """按内部用户主键查找成员资料。"""

        statement = select(MemberProfile).where(MemberProfile.user_id == user_id)
        return await self.session.scalar(statement)

    async def get_member_profile_by_student_id(self, student_id: str) -> MemberProfile | None:
        """按学号查找成员资料，用于后台维护时检查唯一性。"""

        statement = select(MemberProfile).where(MemberProfile.student_id == student_id)
        return await self.session.scalar(statement)

    async def list_users(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
    ) -> tuple[list[User], int]:
        """
        分页列出用户主体。

        第一阶段成员管理以用户主体为列表根，成员资料和组织关系作为附加信息聚合返回。
        这样微信先创建、资料后补齐的用户不会被后台遗漏。
        """

        conditions = [User.deleted_at.is_(None)]
        statement = select(User).options(selectinload(User.email_password_account))
        count_statement = select(func.count(func.distinct(User.id))).select_from(User)

        normalized_search = search.strip() if search else None
        if normalized_search:
            like_text = f"%{normalized_search.lower()}%"
            statement = statement.outerjoin(MemberProfile, MemberProfile.user_id == User.id).outerjoin(
                EmailPasswordAccount,
                EmailPasswordAccount.user_id == User.id,
            )
            count_statement = count_statement.outerjoin(
                MemberProfile,
                MemberProfile.user_id == User.id,
            ).outerjoin(EmailPasswordAccount, EmailPasswordAccount.user_id == User.id)
            conditions.append(
                or_(
                    func.lower(User.display_name).like(like_text),
                    func.lower(EmailPasswordAccount.email).like(like_text),
                    func.lower(MemberProfile.real_name).like(like_text),
                    MemberProfile.student_id.like(f"%{normalized_search}%"),
                    MemberProfile.phone.like(f"%{normalized_search}%"),
                ),
            )

        statement = (
            statement.where(*conditions).order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size)
        )
        count_statement = count_statement.where(*conditions)
        users = list((await self.session.scalars(statement)).all())
        total = await self.session.scalar(count_statement)
        return users, total or 0

    async def list_member_profiles_by_user_ids(self, user_ids: list[int]) -> list[MemberProfile]:
        """批量查询成员资料。"""

        if not user_ids:
            return []
        statement = select(MemberProfile).where(MemberProfile.user_id.in_(user_ids))
        return list((await self.session.scalars(statement)).all())

    async def create_member_profile(self, *, user_id: int, email: str | None = None) -> MemberProfile:
        """为已有用户主体创建成员资料。"""

        profile = MemberProfile(user_id=user_id, email=email)
        self.session.add(profile)
        await self.session.flush()
        # 迁移使用数据库默认时间字段；显式刷新避免异步响应序列化时触发隐式 IO。
        await self.session.refresh(profile)
        return profile
