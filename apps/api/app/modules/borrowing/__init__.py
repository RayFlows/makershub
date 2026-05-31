# app/modules/borrowing/__init__.py
"""
借用业务域

借用域负责申请、审批、取消、归还和异常关闭，不直接暴露资源库存或积分账本细节。
"""

from app.modules.borrowing.models import BorrowApplication, BorrowItem, BorrowReturn, BorrowReview

__all__ = ["BorrowApplication", "BorrowItem", "BorrowReturn", "BorrowReview"]
