# app/core/security/passwords.py
"""
密码哈希工具

本模块统一封装密码哈希和校验，业务代码禁止直接操作明文密码或手写哈希算法。
当前使用 passlib 的 bcrypt 上下文，后续如果需要升级算法，也只应在这里切换。
"""

from passlib.context import CryptContext

# --- 密码哈希上下文 ---
# deprecated="auto" 允许未来算法升级时自动识别旧哈希并逐步迁移。
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    生成密码哈希。

    Args:
        password: 用户提交的明文密码，仅在本函数入参中短暂存在。

    Returns:
        可安全落库保存的 bcrypt 哈希字符串。
    """

    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
    校验明文密码是否匹配数据库中的哈希。

    Args:
        password: 用户本次提交的明文密码。
        password_hash: 数据库中保存的密码哈希。

    Returns:
        True 表示密码正确，False 表示密码错误。
    """

    return pwd_context.verify(password, password_hash)
