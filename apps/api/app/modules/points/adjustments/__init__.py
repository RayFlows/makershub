# app/modules/points/adjustments/__init__.py
"""
人工积分调整能力导出
"""

from app.modules.points.adjustments.service import manually_adjust_points

__all__ = ["manually_adjust_points"]
