from app.core.exceptions import BusinessError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.customer import Customer
from app.models.system import ApprovalInstance
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.user import LoginRequest, LoginResponse, RegisterRequest
from app.services.approval_engine import approval_engine
from app.services.event_bus import event_bus
from app.services.event_contracts import EventType


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def login(self, request: LoginRequest) -> LoginResponse:
        user = await self.repo.get_by_username(request.username)
        if not user:
            raise BusinessError(code=40001, message="用户名或密码错误")

        if not verify_password(request.password, user.password_hash):
            raise BusinessError(code=40001, message="用户名或密码错误")

        if user.status == "待审批":
            # v6.10.0：待审批与禁用区分提示（错误码表 40006 账号待开通）
            raise BusinessError(code=40006, message="账号待开通，请等待管理员审批")

        if user.status != "正常":
            raise BusinessError(code=40003, message="账号已被禁用")

        # JWT sub 必须是字符串（python-jose 新版对 int 会报 Subject must be a string）
        token = create_access_token({"sub": str(user.id), "type": user.user_type})

        return LoginResponse(
            access_token=token,
            user_id=user.id,
            username=user.username,
            real_name=user.real_name,
            user_type=user.user_type,
        )

    async def register(self, request: RegisterRequest) -> dict:
        existing = await self.repo.get_by_username(request.username)
        if existing:
            raise BusinessError(code=40002, message="用户名已存在")

        user = User(
            username=request.username,
            password_hash=hash_password(request.password),
            real_name=request.real_name,
            user_type=request.user_type,
            contact_info=request.contact_info,
        )

        # PROSPECT 自助注册立即生效，无需管理员审批
        if request.user_type == "PROSPECT":
            user.status = "正常"
            self.repo.db.add(user)
            await self.repo.db.flush()
            customer = Customer(
                phone=request.phone,
                wechat=request.wechat,
                name=request.real_name,
                age=request.age,
                education=request.education,
                source_channel="WEBSITE_REGISTER",
                status="NEW",
                phone_status="normal",
                sys_user_id=user.id,
            )
            self.repo.db.add(customer)
            await self.repo.db.commit()
            await self.repo.db.refresh(user)
            await self.repo.db.refresh(customer)
            await event_bus.publish(
                EventType.CUSTOMER_REGISTERED,
                "M1",
                {
                    "customer_id": customer.id,
                    "phone": customer.phone,
                    "name": customer.name or "未知客户",
                },
            )
            return {
                "user_id": user.id,
                "username": user.username,
                "status": "正常",
                "customer_id": customer.id,
            }

        # STUDENT/EMPLOYEE 直接注册（原逻辑）
        created = await self.repo.create(user)
        return {"user_id": created.id, "username": created.username}

    async def approve_prospect(self, approval_id: int, approver_id: int, action: str, comment: str | None = None) -> dict:
        """PROSPECT 注册审批（MANAGER）：通过 → 用户状态正常 + customer 发事件；驳回 → 用户禁用。"""
        instance = await approval_engine.get_by_id(approval_id)
        if not instance:
            raise BusinessError(code=40401, message="审批单不存在")
        if instance.biz_type != "prospect_register":
            raise BusinessError(code=40002, message="非客户注册审批单")
        if instance.status != "pending":
            raise BusinessError(code=40901, message=f"审批单已处理，当前状态: {instance.status}")

        # 校验审批人权限（v6.10.0：改用请求会话，不再绕过 DI 直连全局引擎）
        approver = await self.repo.get_by_id(approver_id)
        if not approver or approver.user_type != "MANAGER":
            raise BusinessError(code=40301, message="无权限审批")

        if action == "approve":
            await approval_engine.approve(approval_id, approver_id, comment)
            # 激活用户
            user = await self.repo.get_by_id(instance.initiator_id)
            if user:
                user.status = "正常"
                await self.repo.db.commit()

            # 发 customer.registered 事件
            if instance.biz_id:
                from sqlalchemy import select as _select
                from app.models.customer import Customer
                result = await self.repo.db.execute(_select(Customer).where(Customer.id == instance.biz_id))
                customer = result.scalar_one_or_none()
                if customer:
                    await event_bus.publish(
                        EventType.CUSTOMER_REGISTERED,
                        "M1",
                        {
                            "customer_id": customer.id,
                            "phone": customer.phone,
                            "name": customer.name or "未知客户",
                        },
                    )
            return {"status": "approved", "message": "审批通过，客户已激活"}

        elif action == "reject":
            await approval_engine.reject(approval_id, approver_id, comment)
            # 禁用用户
            user = await self.repo.get_by_id(instance.initiator_id)
            if user:
                user.status = "禁用"
                await self.repo.db.commit()
            return {"status": "rejected", "message": "审批驳回，账号已禁用"}

        else:
            raise BusinessError(code=40002, message="action 必须是 approve 或 reject")

    async def get_me(self, user: User) -> dict:
        return {
            "id": user.id,
            "username": user.username,
            "real_name": user.real_name,
            "user_type": user.user_type,
            "employee_role": user.employee_role,
            "department": user.department,
            "contact_info": user.contact_info,
            "status": user.status,
            "create_time": user.create_time,
        }

    async def update_me(self, user: User, data: dict) -> dict:
        for key, value in data.items():
            if value is not None:
                setattr(user, key, value)
        await self.repo.update(user)
        return await self.get_me(user)
