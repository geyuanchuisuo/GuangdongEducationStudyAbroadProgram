from enum import Enum


class EventType(str, Enum):
    CUSTOMER_REGISTERED = "customer.registered"
    CUSTOMER_CONVERTED_TO_STUDENT = "customer.converted_to_student"
    LEAVE_APPROVED = "leave.approved"
    LEAVE_REJECTED = "leave.rejected"
    PSYCH_ALERT_CREATED = "psych_alert.created"
    COMPLAINT_RESOLVED = "complaint.resolved"
    LEAD_TRANSFERRED = "lead.transferred"
    APPROVAL_APPROVED = "approval.approved"


EVENT_CONTRACTS: dict[str, dict] = {
    EventType.CUSTOMER_REGISTERED: {
        "source": "M1",
        "consumers": ["M3"],
        "fields": ["customer_id", "phone", "name"],
        "description": "客户注册后，员工端出现待办",
    },
    EventType.CUSTOMER_CONVERTED_TO_STUDENT: {
        "source": "M1/M3",
        "consumers": ["M4", "M5", "M3"],
        "fields": ["customer_id", "student_id"],
        "description": "审批通过后，学生端开通 + 报告更新",
    },
    EventType.LEAVE_APPROVED: {
        "source": "M3",
        "consumers": ["M4", "通知中心"],
        "fields": ["student_id", "leave_id", "status"],
        "description": "员工审批通过，学生收到通知",
    },
    EventType.LEAVE_REJECTED: {
        "source": "M3",
        "consumers": ["M4", "通知中心"],
        "fields": ["student_id", "leave_id", "status"],
        "description": "员工审批拒绝，学生收到通知",
    },
    EventType.PSYCH_ALERT_CREATED: {
        "source": "M4",
        "consumers": ["M3", "管理层", "通知中心"],
        "fields": ["student_id", "risk_level", "reason"],
        "description": "心理预警，员工/管理层待办 + 即时通知",
    },
    EventType.COMPLAINT_RESOLVED: {
        "source": "M3",
        "consumers": ["M4", "通知中心"],
        "fields": ["ticket_id", "student_id", "solution"],
        "description": "投诉处理完成，学生收到反馈通知",
    },
    EventType.LEAD_TRANSFERRED: {
        "source": "M2",
        "consumers": ["M3"],
        "fields": ["lead_id", "customer_fields"],
        "description": "客服识别高意向，CRM 新增线索",
    },
    EventType.APPROVAL_APPROVED: {
        "source": "M0",
        "consumers": ["M1", "M3", "M4"],
        "fields": ["instance_id", "biz_type", "biz_id", "approver_id"],
        "description": "审批通过，各业务模块按 biz_type 执行后置处理",
    },
}
