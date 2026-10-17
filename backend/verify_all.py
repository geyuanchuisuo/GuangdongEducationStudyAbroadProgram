import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')

passed = 0
failed = 0

def test(name, fn):
    global passed, failed
    try:
        fn()
        print(f'  PASS: {name}')
        passed += 1
    except Exception as e:
        print(f'  FAIL: {name} -> {e}')
        failed += 1

# ===== Suite 1: 31 tables =====
print('=' * 60)
print('Suite 1: Model Import (31 tables)')
print('=' * 60)

from app.models import Base
all_tables = sorted(Base.metadata.tables.keys())
print(f'  Tables ({len(all_tables)}): {all_tables}')
test(f'table count = 31 (got {len(all_tables)})',
     lambda: None if len(all_tables) == 31 else
     (_ for _ in ()).throw(Exception(f'got {len(all_tables)}')))

from app.models.user import User
from app.models.customer import Customer, PendingLead
from app.models.crm import CrmLead, CustomerAssessment, CrmFollowUp, AiReport, AiReportAttachment
from app.models.customer_service import CsChatSession, CsChatMessage, CsIntentLog, CsFaq
from app.models.student import (StudentAdminService, StudentPsychProfile, StudentPsychAlert,
                                 StudentFeedbackTicket, StudentScore, StudentAcademic,
                                 StudentApplicationProgress)
from app.models.employee import DailyReportAnnotation, EmployeeDailyReport, EmployeeTodo, EmployeeOrg
from app.models.course import CourseProject
from app.models.event import EventLecture, EventRegistration
from app.models.system import SysEvent, ApprovalInstance, ApprovalTask, SysOperationLog, SysNotification
test('all 31 model classes import OK', lambda: None)

# ===== Suite 2: API Endpoints =====
print()
print('=' * 60)
print('Suite 2: API Endpoints (20 unique paths)')
print('=' * 60)

from app.main import app
schema = app.openapi()
routes = sorted(schema.get('paths', {}).keys())
api_routes = [r for r in routes if r.startswith('/api')]
print(f'  Routes ({len(routes)} total, {len(api_routes)} API): {routes}')

test('/health', lambda: None if '/health' in routes else
     (_ for _ in ()).throw(Exception('missing')))

test('/api/v1/auth/login + /register',
     lambda: None if '/api/v1/auth/login' in routes and '/api/v1/auth/register' in routes else
     (_ for _ in ()).throw(Exception('missing')))

test('/api/v1/users/me',
     lambda: None if '/api/v1/users/me' in routes else
     (_ for _ in ()).throw(Exception('missing')))

test('/api/v1/customers (GET+POST, {id} GET+PUT)',
     lambda: None if '/api/v1/customers' in routes and '/api/v1/customers/{customer_id}' in routes else
     (_ for _ in ()).throw(Exception('missing')))

expected_approval_paths = [
    '/api/v1/approvals',
    '/api/v1/approvals/{instance_id}',
    '/api/v1/approvals/{instance_id}/approve',
    '/api/v1/approvals/{instance_id}/reject',
    '/api/v1/approvals/batch-approve',
    '/api/v1/approvals/pending',
    '/api/v1/approvals/my',
]
test('/api/v1/approvals (7 paths)',
     lambda: None if all(p in routes for p in expected_approval_paths) else
     (_ for _ in ()).throw(Exception('missing')))

expected_notification_paths = [
    '/api/v1/notifications',
    '/api/v1/notifications/unread-count',
    '/api/v1/notifications/read-all',
    '/api/v1/notifications/{notification_id}/read',
]
test('/api/v1/notifications (4 paths, contract §8.2)',
     lambda: None if all(p in routes for p in expected_notification_paths) else
     (_ for _ in ()).throw(Exception('missing')))

expected_file_paths = [
    '/api/v1/files/upload',
    '/api/v1/files/download',
    '/api/v1/files/presigned',
]
test('/api/v1/files (3 paths, contract §8.3)',
     lambda: None if all(p in routes for p in expected_file_paths) else
     (_ for _ in ()).throw(Exception('missing')))

# ── M3 员工模块路由（30 paths） ─────────────────────────
expected_employee_paths = [
    '/api/v1/employee/reports',
    '/api/v1/employee/reports/summary',
    '/api/v1/employee/reports/oral',
    '/api/v1/employee/reports/late-review',
    '/api/v1/employee/reports/{report_id}',
    '/api/v1/employee/reports/{report_id}/late-apply',
    '/api/v1/employee/reports/{report_id}/annotations',
    '/api/v1/employee/todos',
    '/api/v1/employee/todos/{todo_id}',
    '/api/v1/employee/org',
    '/api/v1/employee/scores',
    '/api/v1/employee/convert-applies',
    '/api/v1/employee/admin-services',
    '/api/v1/employee/admin-services/{service_id}/review',
    '/api/v1/employee/crm/leads',
    '/api/v1/employee/crm/follow-ups',
    '/api/v1/employee/commands/parse',
    '/api/v1/employee/commands/execute',
    '/api/v1/employee/customers',
    '/api/v1/employee/customers/reassign',
    '/api/v1/employee/customers/{customer_id}/status',
    '/api/v1/employee/tickets',
    '/api/v1/employee/tickets/{ticket_id}/handle',
    '/api/v1/employee/psych-alerts/{alert_id}/handle',
    '/api/v1/employee/profile',
    '/api/v1/employee/profile/password',
    '/api/v1/employee/profile/stats',
    '/api/v1/employee/export/customers',
    '/api/v1/employee/export/daily-reports',
    '/api/v1/employee/export/follow-ups',
    '/api/v1/employee/agent/chat',
    '/api/v1/employee/guide/onboarding',
    '/api/v1/employee/guide/ask',
    '/api/v1/employee/reminders',
]
test('/api/v1/employee (34 paths, M3 v6.5.0)',
     lambda: None if all(p in routes for p in expected_employee_paths) else
     (_ for _ in ()).throw(Exception('missing')))

test(f'total paths = 54 (53 API + 1 health, got {len(routes)})',
     lambda: None if len(routes) == 54 else
     (_ for _ in ()).throw(Exception(f'expected 54')))

# ===== Suite 3: MVC Layer =====
print()
print('=' * 60)
print('Suite 3: MVC Layer Import')
print('=' * 60)

from app.schemas.user import LoginRequest, RegisterRequest, LoginResponse, UserOut, UserUpdate
from app.schemas.customer import (CustomerCreate, CustomerOut, CustomerUpdate,
                                   LeadCreate, LeadOut, AssessmentOut, FollowUpCreate, FollowUpOut)
from app.schemas.approval import (ApprovalCreate, ApprovalAction, ApprovalTaskOut,
                                   ApprovalInstanceOut, BatchApprovalRequest)
from app.schemas.common import PageParams, PageResult, IdResponse, StatusResponse, MessageResponse
from app.schemas.notification import NotificationOut
test('schemas (5 modules, 20 classes)', lambda: None)

from app.repositories.user_repo import UserRepository
from app.repositories.customer_repo import CustomerRepository
test('repositories (2 modules)', lambda: None)

from app.services.user_service import UserService
from app.services.customer_service import CustomerService
from app.services.ai_service import AIService, AgentType, AIResponse
from app.services.approval_engine import ApprovalEngine, ApprovalBizType, ApprovalStatus, TaskStatus
from app.services.event_bus import EventBus
from app.services.event_contracts import EventType
from app.services.file_storage import FileStorageService, FileModule, FileStorageError
from app.services.notification_service import NotificationService, NotificationType
test('services (8 modules, all classes)', lambda: None)

# ===== Suite 4: Migration =====
print()
print('=' * 60)
print('Suite 4: Migration Scripts')
print('=' * 60)

test('migrations/versions/ exists',
     lambda: None if os.path.exists('migrations/versions') else
     (_ for _ in ()).throw(Exception('missing')))
mfiles = [f for f in os.listdir('migrations/versions') if f.endswith('.py')]
test(f'migration .py files (got {len(mfiles)}: {mfiles})',
     lambda: None if mfiles else (_ for _ in ()).throw(Exception('no .py files')))

# ===== Suite 5: Seed scripts =====
print()
print('=' * 60)
print('Suite 5: Seed Data Scripts')
print('=' * 60)

test('scripts/seed_data.py',
     lambda: None if os.path.exists('scripts/seed_data.py') else
     (_ for _ in ()).throw(Exception('missing')))

# ===== Suite 6: FK Consistency =====
print()
print('=' * 60)
print('Suite 6: Foreign Key Consistency (customer master)')
print('=' * 60)

from sqlalchemy import inspect as sa_inspect

def get_fks(model):
    m = sa_inspect(model)
    return {c.name: list(c.foreign_keys)[0].target_fullname for c in m.columns if c.foreign_keys}

for model_cls, label in [
    (CrmLead, 'CrmLead'),
    (CustomerAssessment, 'CustomerAssessment'),
    (CrmFollowUp, 'CrmFollowUp'),
    (CsChatSession, 'CsChatSession'),
    (CsIntentLog, 'CsIntentLog'),
]:
    fk = get_fks(model_cls)
    actual = fk.get('customer_id', 'NONE')
    test(f'{label}.customer_id -> customer.id (actual: {actual})',
         lambda a=actual: None if a == 'customer.id' else
         (_ for _ in ()).throw(Exception(f'wrong FK: {a}')))

# ===== Summary =====
print()
print('=' * 60)
total = passed + failed
print(f'RESULT: {passed}/{total} passed, {failed} failed')
if failed == 0:
    print('ALL TESTS PASSED')
print('=' * 60)
