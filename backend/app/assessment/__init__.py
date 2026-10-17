"""客户研判模块（新增、独立交付）。

本包不修改现有公共框架。将其复制到既有项目的 ``backend/app/assessment``
后，可由后续公共框架负责人在 ``app.main`` 中注册 router。
"""

from .engine import CustomerAssessmentEngine

__all__ = ["CustomerAssessmentEngine"]
