# app/modules/identity/accounts/wechat.py
"""
微信身份登录服务

本文件只处理小程序微信身份：openid/unionid 归一化、用户主体创建或复用、
以及首次登录时授予 0 外部成员基础身份。它不处理邮箱密码、令牌签发和权限授予。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.identity.repositories import IdentityRepository
from app.modules.identity.types import WechatLoginResult
from app.modules.identity.utils import normalize_wechat_identifier
from app.modules.organization.models import Position, UserPosition

EXTERNAL_MEMBER_POSITION_CODE = "0"
"""外部成员/协会会员的基础身份代码，不附带任何后台管理权限。"""


async def login_wechat_identity(
    session: AsyncSession,
    *,
    openid: str,
    unionid: str | None = None,
    session_key_hash: str | None = None,
    display_name: str | None = None,
) -> WechatLoginResult:
    """处理小程序微信登录。

    - 已存在 openid：复用同一个用户主体，并刷新登录时间；
    - 首次出现 openid：创建用户主体和微信凭证；
    - unionid 暂时可空，但如果传入，必须和已有绑定关系一致。
    """

    normalized_openid = normalize_wechat_identifier(openid, field_name="openid")
    normalized_unionid = normalize_wechat_identifier(unionid, field_name="unionid") if unionid else None

    repository = IdentityRepository(session)
    account = await repository.get_wechat_account_by_openid(normalized_openid)

    if account is not None:
        if account.status != "active":
            raise AppError("WECHAT_ACCOUNT_DISABLED", "微信账号已被禁用", status_code=403)
        # 同一个 openid 后续拿到的 unionid 不能变化，否则说明微信身份映射异常。
        if account.unionid and normalized_unionid and account.unionid != normalized_unionid:
            raise AppError("WECHAT_UNIONID_CONFLICT", "微信 unionid 与已有账号不一致", status_code=409)
        user = await repository.mark_wechat_login(
            account,
            unionid=normalized_unionid,
            session_key_hash=session_key_hash,
        )
        return WechatLoginResult(user=user, wechat_account=account, created=False)

    if normalized_unionid:
        # 避免把新的 openid 错绑到已经属于另一个用户主体的 unionid 上。
        existing_union_account = await repository.get_wechat_account_by_unionid(normalized_unionid)
        if existing_union_account is not None:
            raise AppError("WECHAT_UNIONID_ALREADY_BOUND", "微信 unionid 已经绑定其他账号", status_code=409)

    user, account = await repository.create_wechat_user(
        openid=normalized_openid,
        unionid=normalized_unionid,
        session_key_hash=session_key_hash,
        display_name=display_name or "微信用户",
    )
    await _grant_default_external_member_position(session, repository=repository, user_id=user.id)
    return WechatLoginResult(user=user, wechat_account=account, created=True)


async def _grant_default_external_member_position(
    session: AsyncSession,
    *,
    repository: IdentityRepository,
    user_id: int,
) -> None:
    """
    给小程序首次登录用户授予 0 基础身份。

    `0` 表示外部成员/协会会员，是系统内最低协会身份，不等于后台权限点。
    它让后续公开任务、积分账户和成员范围判断有明确数据落点；真正的后台能力仍然
    必须通过 permissions 模块的权限点和角色授予。
    """

    position = await repository.get_position_by_code(EXTERNAL_MEMBER_POSITION_CODE)
    if position is None:
        position = Position(
            code=EXTERNAL_MEMBER_POSITION_CODE,
            name="外部成员",
            status="active",
            sort_order=0,
            is_system=False,
        )
        session.add(position)
        await session.flush()

    session.add(
        UserPosition(
            user_id=user_id,
            position_id=position.id,
            scope_type="global",
            scope_id=None,
            granted_by=None,
        ),
    )
    await session.flush()
