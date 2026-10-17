from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


# SQLite 仅 INTEGER PRIMARY KEY 自增；用 with_variant 让测试(SQLite)退化为 INTEGER，生产(MySQL)仍为 BIGINT
BigInt = BigInteger().with_variant(Integer, "sqlite")


class Customer(Base):
    __tablename__ = "customer"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True, index=True, comment="手机号(业务唯一键)")
    wechat: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="微信号")
    name: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="姓名")
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True, comment="性别")
    age: Mapped[int | None] = mapped_column(Integer, nullable=True, comment="年龄")
    education: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="学历")
    economy: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="家庭经济状况")
    needs: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="职业/教育需求")
    study_intent: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="留学意愿及意向国家")
    german_ability: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="德语能力")
    english_ability: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="英语能力")
    closed_training: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="是否接受封闭式实训")
    criminal_record: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="有无犯罪记录")
    belt_and_road: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="一带一路/政策认知")
    source_channel: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True, comment="来源渠道")
    owner_employee_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=True, index=True, comment="负责员工")
    status: Mapped[str] = mapped_column(String(20), default="NEW", index=True, comment="客户状态(6态)")
    phone_status: Mapped[str] = mapped_column(String(20), default="normal", comment="手机号状态(normal/pending)")
    first_register_at = mapped_column(DateTime, nullable=True, comment="首次注册时间")
    first_submit_at = mapped_column(DateTime, nullable=True, comment="首次员工提交时间")
    last_login_at = mapped_column(DateTime, nullable=True, comment="最后登录时间")
    auto_churned: Mapped[bool] = mapped_column(Boolean, default=False, comment="系统自动流失标记")
    churned_at = mapped_column(DateTime, nullable=True, comment="流失时间")
    reflowed_at = mapped_column(DateTime, nullable=True, comment="回流时间")
    sys_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sys_user.id"), nullable=True, comment="关联账号ID")
    created_at = mapped_column(DateTime, server_default=func.now())
    updated_at = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class PendingLead(Base):
    __tablename__ = "pending_lead"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    wechat: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="微信号")
    name: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="姓名")
    raw_info = mapped_column(Text, nullable=True, comment="原始信息")
    source_session_id: Mapped[int | None] = mapped_column(BigInt, nullable=True, comment="来源会话ID")
    merged_customer_id: Mapped[int | None] = mapped_column(BigInt, ForeignKey("customer.id"), nullable=True, comment="合并后的客户ID")
    status: Mapped[str] = mapped_column(String(20), default="pending", comment="状态")
    created_at = mapped_column(DateTime, server_default=func.now())
    updated_at = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
