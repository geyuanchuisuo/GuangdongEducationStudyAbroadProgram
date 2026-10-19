from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")

_ROLE_SPLIT_RE = re.compile(r"(客服|客户|用户|顾客|家长|学生|访客)\s*[：:]")


def _customer_side_text(text: str) -> str:
    """对话记录中仅保留客户侧发言，避免客服话术污染字段提取；无角色标记时返回原文。"""
    if not _ROLE_SPLIT_RE.search(text):
        return text
    parts = _ROLE_SPLIT_RE.split(text)
    # split 结果：[前置内容, 角色1, 发言1, 角色2, 发言2, ...]
    customer_parts: list[str] = []
    for i in range(1, len(parts) - 1, 2):
        role, segment = parts[i], parts[i + 1]
        if role != "客服":
            customer_parts.append(segment)
    if not customer_parts:
        return text
    # 角色标记之前的前置内容可能含客户信息（如“客户信息：”引子），保守并入
    merged = "。".join(
        seg.strip() for seg in [parts[0], *customer_parts] if seg and seg.strip()
    )
    return merged or text


@dataclass
class CustomerFacts:
    name: str | None = None
    phone: str | None = None
    gender: str | None = None
    age: int | None = None
    age_text: str | None = None
    education: str | None = None
    economy: str | None = None
    needs: str | None = None
    study_intent: str | None = None
    german_ability: str | None = None
    english_ability: str | None = None
    closed_training: str | None = None
    criminal_record: str | None = None
    belt_and_road: str | None = None
    raw: str = ""
    evidence: dict[str, str] = field(default_factory=dict)

    def set(self, key: str, value: str | None, evidence: str | None = None) -> None:
        if not value:
            return
        setattr(self, key, value)
        self.evidence[key] = evidence or value


def _field_value(text: str, labels: tuple[str, ...]) -> str | None:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(rf"(?:{label_pattern})\s*[：: ]\s*([^；;\n，,]+)", text, re.I)
    return match.group(1).strip() if match else None


# v6.11.32：简历 PDF 常把「姓名」排版拆行（「姓\n名：许剑鸿」），标签正则需容许标签内空白；
# 另有些简历姓名独占首行（「黄学勤」）无任何标签，仅对文档渠道启用首行兜底，避免污染文本/对话渠道。
_NAME_LABEL_RE = re.compile(r"(?:客户姓名|姓\s*名|名\s*字)\s*[：:]?\s*([\u4e00-\u9fff]{2,4})(?=[，,；;\s]|$)")
_NAME_CALL_RE = re.compile(r"我叫\s*([\u4e00-\u9fff]{2,4})")
_NAME_LINE_RE = re.compile(r"^[\u4e00-\u9fff]{2,4}$")
_NAME_LINE_STOPWORDS = {
    "基本信息", "个人信息", "个人简历", "个人技能", "简历", "求职简历", "求职意向",
    "教育背景", "教育经历", "工作经历", "项目经历", "实习经历", "联系方式",
    "自我评价", "技能特长", "技能清单", "客户信息", "工作年限", "出生日期", "现所在地",
}


def _extract_name(text: str, document: bool = False) -> str | None:
    match = _NAME_LABEL_RE.search(text)
    if match:
        return match.group(1)
    match = _NAME_CALL_RE.search(text)
    if match:
        return match.group(1)
    if not document:
        return None
    # 文档兜底：取首个「整行恰为 2-4 个汉字且不是栏目名」的行（简历姓名通常独占首行）
    for line in text.splitlines()[:8]:
        line = line.strip()
        if line and _NAME_LINE_RE.match(line) and line not in _NAME_LINE_STOPWORDS:
            return line
    return None


def _extract_education(text: str) -> str | None:
    value = _field_value(text, ("学历", "教育经历", "在读阶段", "毕业院校"))
    if value:
        return value
    patterns = (
        r"(?:初中|高中|高二|中职|中专|职高|技校|专科|大专|本科|硕士|研究生|博士)[^，。；;\n]{0,18}(?:毕业|在读|就读|学历|文凭)?",
        r"(?:初中毕业|高中毕业|本科毕业|专科毕业|大专毕业)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0).strip()
    return None


def extract_facts(
    content: str,
    registration: dict[str, Any] | None = None,
    dialogue: bool = False,
    document: bool = False,
) -> CustomerFacts:
    """提取明确字段；注册渠道完全以结构化字段优先，不对空选填字段推测；对话渠道仅提取客户侧发言。

    document=True 表示内容来自文档（简历等）解析，允许启用「姓名独占首行」兜底规则。
    """
    text = content.strip()
    if dialogue:
        text = _customer_side_text(text)
    facts = CustomerFacts(raw=text)
    data = registration or {}

    def get_registration(*keys: str) -> str | None:
        for key in keys:
            value = data.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return None

    if registration is not None:
        facts.set("name", get_registration("姓名", "name"))
        facts.set("phone", get_registration("联系方式", "电话", "手机号", "phone"))
        facts.set("gender", get_registration("性别", "gender"))
        age = get_registration("年龄", "age")
        if age:
            match = re.search(r"\d{1,3}", age)
            facts.age = int(match.group(0)) if match else None
            facts.age_text = age
            facts.evidence["age"] = age
        facts.set("education", get_registration("学历", "教育", "education"))
        facts.set("economy", get_registration("家庭经济状况", "家庭经济", "economy"))
        facts.set("needs", get_registration("职业需求", "需求", "needs"))
        facts.set("german_ability", get_registration("德语能力", "德语", "german_ability"))
        # 注册表单不存在的自由字段不得从 content 猜测。
        return facts

    phone_match = PHONE_RE.search(text)
    facts.set("phone", phone_match.group(1) if phone_match else None)
    facts.set("name", _extract_name(text, document))
    gender_match = re.search(r"(?:性别[：: ]*|\b)(男|女)(?:\b|[，,；;\n])", text)
    facts.set("gender", gender_match.group(1) if gender_match else None)
    # v6.11.32：简历常写「年龄：25」不带「岁」单位，显式「年龄」标签下也应识别；
    # 无标签时仍要求「岁/周岁」，避免把学号、年份等数字误判成年龄。
    age_match = re.search(r"年龄\s*[：:]\s*(\d{1,3})(?!\d)|(\d{1,3})\s*(?:岁|周岁)", text)
    if age_match:
        facts.age = int(age_match.group(1) or age_match.group(2))
        facts.age_text = f"{facts.age}岁"
        facts.evidence["age"] = facts.age_text
    facts.set("education", _extract_education(text))
    facts.set("economy", _field_value(text, ("家庭经济状况", "家庭经济", "经济状况")))
    if not facts.economy:
        economy_match = re.search(r"家里(?:很有钱|条件(?:不错|较好|一般|困难)|经济(?:条件)?(?:不错|较好|一般|困难))", text)
        facts.set("economy", economy_match.group(0) if economy_match else None)
    facts.set("needs", _field_value(text, ("职业需求", "需求", "升学需求", "就业需求", "移民需求")))
    if not facts.needs:
        need_match = re.search(r"(?:想|希望|打算)[^。；;\n，,？?]{0,30}(?:升学|就业|工作|移民|学历|收入)", text)
        facts.set("needs", need_match.group(0) if need_match else None)
    # 常见录入形式为“意向：新加坡留学”；将“意向”作为显式字段标签，
    # 避免仅因未出现“想/希望”等动词而遗漏已明确给出的国家和留学计划。
    facts.set("study_intent", _field_value(text, ("留学意愿", "意向国家", "留学方向", "意向")))
    if not facts.study_intent:
        intent_match = re.search(r"(?:想|希望|打算|考虑|不考虑|拒绝)[^。；;\n，,？?]{0,30}(?:留学|出国|新加坡|德国)", text)
        facts.set("study_intent", intent_match.group(0) if intent_match else None)
    facts.set("german_ability", _field_value(text, ("德语能力", "德语基础", "德语")))
    if not facts.german_ability:
        german_match = re.search(r"(?:德语(?:零基础|[AB][12]|基础[^，。；;\n]{0,12}|水平[^，。；;\n]{0,12}))", text, re.I)
        facts.set("german_ability", german_match.group(0) if german_match else None)
    english_match = re.search(r"(?:英语(?:零基础|[四六]级|基础[^，。；;\n]{0,12}|水平[^，。；;\n]{0,12}))", text, re.I)
    facts.set("english_ability", english_match.group(0) if english_match else None)
    training_match = re.search(r"(?:接受|不接受|可以接受|不能接受)[^。；;\n]{0,16}(?:封闭式|严格管理|实训)", text)
    facts.set("closed_training", training_match.group(0) if training_match else None)
    crime_match = re.search(r"(?:无|有|没有)[^。；;\n]{0,8}犯罪记录", text)
    facts.set("criminal_record", crime_match.group(0) if crime_match else None)
    belt_match = re.search(r"(?:一带一路|德国职业教育政策|移民政策)[^。；;\n]{0,20}", text)
    facts.set("belt_and_road", belt_match.group(0) if belt_match else None)
    return facts


def has_recognizable_customer_info(facts: CustomerFacts) -> bool:
    return any(
        (
            facts.name,
            facts.phone,
            facts.gender,
            facts.age,
            facts.education,
            facts.economy,
            facts.needs,
            facts.study_intent,
            facts.german_ability,
        )
    )
