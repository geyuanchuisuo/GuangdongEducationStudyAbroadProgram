from app.models.base import Base
from app.models.course import CourseProject
from app.models.crm import AiReport, AiReportAttachment, CrmFollowUp, CrmLead, CustomerAssessment
from app.models.customer import Customer, PendingLead
from app.models.customer_service import CsChatMessage, CsChatSession, CsFaq, CsIntentLog
from app.models.employee import EmployeeDailyReport, EmployeeOrg, EmployeeTodo
from app.models.event import EventLecture, EventRegistration
from app.models.student import (
    StudentAcademic,
    StudentAdminService,
    StudentApplicationProgress,
    StudentFeedbackTicket,
    StudentPsychAlert,
    StudentPsychProfile,
    StudentScore,
)
from app.models.system import (
    ApprovalInstance,
    ApprovalTask,
    SysEvent,
    SysNotification,
    SysOperationLog,
)
from app.models.user import User

__all__ = [
    "Base",
    "User",
    "Customer",
    "PendingLead",
    "CrmLead",
    "CustomerAssessment",
    "CrmFollowUp",
    "AiReport",
    "AiReportAttachment",
    "CourseProject",
    "EventLecture",
    "EventRegistration",
    "CsChatSession",
    "CsChatMessage",
    "CsIntentLog",
    "CsFaq",
    "EmployeeDailyReport",
    "EmployeeTodo",
    "EmployeeOrg",
    "StudentAdminService",
    "StudentPsychProfile",
    "StudentPsychAlert",
    "StudentFeedbackTicket",
    "StudentScore",
    "StudentAcademic",
    "StudentApplicationProgress",
    "SysEvent",
    "ApprovalInstance",
    "ApprovalTask",
    "SysOperationLog",
    "SysNotification",
]
