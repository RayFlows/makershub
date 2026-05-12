# app/modules/points/constants.py
"""
积分账本常量

本文件集中保存积分账户状态、冻结状态和流水方向，避免各能力模块散落硬编码字符串。
这些常量只表达账本事实，不代表权限点，也不代表前端展示文案。
"""

POINT_ACCOUNT_ACTIVE = "active"

POINT_HOLD_ACTIVE = "active"
POINT_HOLD_RELEASED = "released"
POINT_HOLD_DEDUCTED = "deducted"

POINT_DIRECTION_INCOME = "income"
POINT_DIRECTION_EXPENSE = "expense"
POINT_DIRECTION_FREEZE = "freeze"
POINT_DIRECTION_UNFREEZE = "unfreeze"
POINT_DIRECTION_HOLD_DEDUCT = "hold_deduct"
