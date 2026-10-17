from __future__ import annotations

from collections import defaultdict
from typing import Any

from .extractors import CustomerFacts, extract_facts, has_recognizable_customer_info
from .schemas import AssessmentRecord, AssessmentRequest


SINGAPORE_PROGRAMS = [
    "2+2 新加坡定向培养本科班",
    "2+2+1 本硕连读",
    "0.5/1+2 新加坡定向培养本科班",
    "0.5/1+2+1 本硕连读",
    "一年制专升本项目",
    "一年制本升硕项目",
    "6+6 酒店运营大专就业班",
    "9+6 航空运营大专就业班",
]


def dim(name: str, result: str, evidence: str) -> dict[str, str]:
    return {"dimension": name, "result": result, "evidence": evidence}


def missing_evidence(label: str) -> str:
    return f"输入未提供{label}"


class CustomerAssessmentEngine:
    """严格按研判提示词的确定性规则执行，保留原文证据且不调用外部模型。"""

    def assess_one(self, request: AssessmentRequest, index: int = 1) -> AssessmentRecord:
        facts = extract_facts(request.content, request.registration)
        customer = self._customer(facts)
        if not has_recognizable_customer_info(facts):
            return self._invalid(index, "invalid_input", "未提取到任何可识别的客户信息", customer)
        if not facts.phone:
            return self._invalid(index, "invalid_phone", "未提取到电话号码", customer)
        if len(facts.phone) != 11 or not facts.phone.startswith("1"):
            return self._invalid(index, "invalid_phone", f"电话号码不合规：{facts.phone}", customer)

        singapore = self._assess_singapore(facts)
        germany = self._assess_germany(facts)
        missing = self._missing_info(facts)
        recommended = self._recommend(singapore, germany, facts)
        overview = self._overview(facts, recommended)
        advice = self._advice(facts, missing, [])
        return AssessmentRecord(
            index=index,
            status="valid",
            customer=customer,
            assessments={"singapore": singapore, "germany": germany},
            recommended_projects=recommended,
            missing_info=missing,
            customer_overview=overview,
            follow_up_advice=advice,
        )

    def assess_batch(self, requests: list[AssessmentRequest]) -> list[AssessmentRecord]:
        """按手机号合并批内记录，结果 index 为最早出现记录的序号。"""
        groups: dict[str, list[tuple[int, AssessmentRequest]]] = defaultdict(list)
        no_phone: list[tuple[int, AssessmentRequest]] = []
        for index, request in enumerate(requests, start=1):
            facts = extract_facts(request.content, request.registration)
            if facts.phone:
                groups[facts.phone].append((index, request))
            else:
                no_phone.append((index, request))
        results = [self.assess_one(request, index) for index, request in no_phone]
        for phone_group in groups.values():
            first_index, first_request = phone_group[0]
            if len(phone_group) == 1:
                results.append(self.assess_one(first_request, first_index))
                continue
            merged, conflicts = self._merge(phone_group)
            result = self.assess_one(merged, first_index)
            result.conflicts = conflicts
            if result.status == "valid":
                facts = extract_facts(merged.content, merged.registration)
                result.follow_up_advice = self._advice(facts, result.missing_info, conflicts)
            results.append(result)
        return sorted(results, key=lambda item: item.index)

    def _invalid(self, index: int, status: str, reason: str, customer: dict[str, Any]) -> AssessmentRecord:
        return AssessmentRecord(
            index=index,
            status=status, invalid_reason=reason, customer=customer,
            conflicts=[], assessments=None, recommended_projects=None,
            missing_info=[], customer_overview=None, follow_up_advice=None,
        )

    @staticmethod
    def _customer(facts: CustomerFacts) -> dict[str, Any]:
        other = []
        for label, key in (("家庭经济状况", "economy"), ("职业/教育需求", "needs"), ("留学意愿", "study_intent"), ("德语能力", "german_ability")):
            value = getattr(facts, key)
            if value:
                other.append(f"{label}：{value}")
        return {
            "name": facts.name,
            "phone": facts.phone,
            "gender": facts.gender,
            "age": facts.age_text,
            "education": facts.education,
            "economy": facts.economy,
            "needs": facts.needs,
            "study_intent": facts.study_intent,
            "german_ability": facts.german_ability,
            "english_ability": facts.english_ability,
            "closed_training": facts.closed_training,
            "criminal_record": facts.criminal_record,
            "belt_and_road": facts.belt_and_road,
            "other_info": "；".join(other) or None,
        }

    def _assess_singapore(self, f: CustomerFacts) -> dict[str, Any]:
        dimensions: list[dict[str, str]] = []
        programs: list[str] = []
        age_ok = False
        if f.age is None:
            dimensions.append(dim("年龄", "insufficient", missing_evidence("年龄")))
        elif 14 <= f.age <= 16:
            age_ok = True; programs += SINGAPORE_PROGRAMS[:2]
            dimensions.append(dim("年龄", "satisfied", f"{f.evidence['age']}，可对应初中毕业生班型"))
        elif 16 <= f.age <= 19:
            age_ok = True; programs += SINGAPORE_PROGRAMS[2:4]
            if f.age >= 17: programs += SINGAPORE_PROGRAMS[6:]
            dimensions.append(dim("年龄", "satisfied", f"{f.evidence['age']}，处于高中/中职阶段及就业班型年龄范围"))
        elif f.age >= 17:
            age_ok = True
            dimensions.append(dim("年龄", "satisfied", f"{f.evidence['age']}，年龄不构成统一淘汰，需结合学历确定班型"))
        else:
            dimensions.append(dim("年龄", "unsatisfied", f"{f.evidence['age']}，与已列班型年龄区间明显不符"))

        education_ok = False
        if not f.education:
            dimensions.append(dim("学历", "insufficient", missing_evidence("学历/在读阶段")))
        else:
            edu = f.education
            if "初中" in edu:
                education_ok = True; programs = SINGAPORE_PROGRAMS[:2]
            elif any(word in edu for word in ("高中", "高二", "中职", "中专", "职高", "技校")):
                education_ok = True; programs = SINGAPORE_PROGRAMS[2:4] + (SINGAPORE_PROGRAMS[6:] if (f.age or 0) >= 17 else [])
            elif any(word in edu for word in ("专科", "大专")):
                education_ok = True; programs = [SINGAPORE_PROGRAMS[4]]
            elif "本科" in edu:
                education_ok = True; programs = [SINGAPORE_PROGRAMS[5]]
            dimensions.append(dim("学历", "satisfied" if education_ok else "unsatisfied", edu))
        dimensions.append(dim("家庭经济状况", "satisfied" if f.economy else "insufficient", (f"{f.economy}（客户自述，实际支付能力需电话核实）" if f.economy else missing_evidence("家庭经济状况"))))
        dimensions.append(dim("教育需求", "satisfied" if f.needs else "insufficient", f.needs or missing_evidence("升学或就业需求")))
        intent_refusal = f.study_intent and ("不考虑" in f.study_intent or "拒绝" in f.study_intent) and ("新加坡" in f.study_intent or "出国" in f.study_intent or "留学" in f.study_intent)
        dimensions.append(dim("留学意愿", "unsatisfied" if intent_refusal else ("satisfied" if f.study_intent else "insufficient"), f.study_intent or missing_evidence("留学意愿及意向国家")))
        dimensions.append(dim("语言能力", "satisfied" if f.english_ability else "insufficient", f.english_ability or missing_evidence("英语学习能力")))
        if intent_refusal or (f.age is not None and f.age < 14) or (f.education and not education_ok):
            conclusion = "not_matched"
        elif f.age is None or not f.education:
            conclusion = "pending"
        elif age_ok and education_ok and f.needs and f.study_intent:
            conclusion = "matched"
        else:
            conclusion = "partial"
        if conclusion == "pending" and not programs:
            programs = SINGAPORE_PROGRAMS
        return {"conclusion": conclusion, "dimensions": dimensions, "matched_programs": list(dict.fromkeys(programs)) if conclusion != "not_matched" else [], "summary": self._summary("新加坡", conclusion, f)}

    def _assess_germany(self, f: CustomerFacts) -> dict[str, Any]:
        dimensions: list[dict[str, str]] = []
        age_ok = f.age is not None and 18 <= f.age <= 35
        if f.age is None: dimensions.append(dim("年龄", "insufficient", missing_evidence("年龄")))
        else: dimensions.append(dim("年龄", "satisfied" if age_ok else "unsatisfied", f"{f.evidence['age']}，{'在' if age_ok else '不在'}18-35岁范围内"))
        edu_ok: bool | None = None
        if not f.education:
            dimensions.append(dim("学历", "insufficient", missing_evidence("学历/毕业状态")))
        else:
            in_study = "在读" in f.education and not any(word in f.education for word in ("毕业", "应届"))
            level_ok = any(word in f.education for word in ("高中", "中职", "中专", "职高", "技校", "专科", "大专", "本科", "硕士", "博士"))
            edu_ok = level_ok and not in_study
            dimensions.append(dim("学历", "satisfied" if edu_ok else "unsatisfied", f.education))
        dimensions.append(dim("职业需求", "satisfied" if f.needs else "insufficient", f.needs or missing_evidence("就业/升学/移民需求")))
        language_result = "insufficient" if not f.german_ability else ("unsatisfied" if "零基础" in f.german_ability else "satisfied")
        dimensions.append(dim("语言能力", language_result, f.german_ability or missing_evidence("德语基础及学习能力")))
        dimensions.append(dim("家庭经济状况", "satisfied" if f.economy else "insufficient", (f"{f.economy}（客户自述，实际支付能力需电话核实）" if f.economy else missing_evidence("家庭经济状况"))))
        dimensions.append(dim("留学意愿", "satisfied" if f.study_intent and ("德国" in f.study_intent or "出国" in f.study_intent or "留学" in f.study_intent) else "insufficient", f.study_intent or missing_evidence("赴德意愿")))
        dimensions.append(dim("学习态度", "satisfied" if f.closed_training and "不接受" not in f.closed_training else ("unsatisfied" if f.closed_training else "insufficient"), f.closed_training or missing_evidence("是否接受线下封闭式实训")))
        crime_bad = f.criminal_record and f.criminal_record.startswith("有")
        dimensions.append(dim("无犯罪记录", "unsatisfied" if crime_bad else ("satisfied" if f.criminal_record else "insufficient"), f.criminal_record or missing_evidence("有无犯罪记录")))
        refusal = f.study_intent and ("不考虑德国" in f.study_intent or "拒绝德国" in f.study_intent or "不去德国" in f.study_intent)
        if (f.age is not None and not age_ok) or edu_ok is False or crime_bad or refusal:
            conclusion = "not_matched"
        elif f.age is None or edu_ok is None:
            conclusion = "pending"
        elif f.needs and f.study_intent and language_result == "satisfied":
            conclusion = "matched"
        else:
            conclusion = "partial"
        programs = ["中德精英人才共建计划"] if conclusion in ("matched", "partial") else ([] if conclusion == "not_matched" else ["中德精英人才共建计划"])
        return {"conclusion": conclusion, "dimensions": dimensions, "matched_programs": programs, "summary": self._summary("中德", conclusion, f)}

    @staticmethod
    def _summary(product: str, conclusion: str, f: CustomerFacts) -> str:
        mapping = {"matched": "关键条件和意愿证据均已具备，可作为优先跟进对象。", "partial": "基础条件存在匹配，但重要条件仍需电话核实。", "pending": "关键年龄或学历信息不足，班型待信息核实后确认。", "not_matched": "存在明确硬性不符合条件，当前不建议推荐。"}
        return f"{product}项目：{mapping[conclusion]}"

    def _recommend(self, singapore: dict[str, Any], germany: dict[str, Any], f: CustomerFacts) -> list[dict[str, str]]:
        ranked: list[tuple[int, str, str]] = []
        for key, assessment in (("singapore", singapore), ("germany", germany)):
            if assessment["conclusion"] not in ("matched", "partial"): continue
            score = 2 if assessment["conclusion"] == "matched" else 1
            if key == "germany" and f.needs and any(word in f.needs for word in ("就业", "工作", "移民")): score += 1
            if key == "singapore" and f.education and any(word in f.education for word in ("初中", "高中", "专科", "本科")): score += 1
            reason = "年龄、学历与当前需求匹配" if assessment["conclusion"] == "matched" else "具备部分基础条件，但需补充意愿、经济或语言等信息"
            ranked.append((score, key, reason))
        return [{"project": key, "reason": reason} for _, key, reason in sorted(ranked, reverse=True)]

    @staticmethod
    def _missing_info(f: CustomerFacts) -> list[str]:
        items = []
        for value, label in ((f.education, "学历/在读阶段"), (f.needs, "升学或就业需求"), (f.study_intent, "留学意愿及意向国家"), (f.economy, "家庭经济状况"), (f.german_ability, "德语基础（中德项目）"), (f.closed_training, "是否接受线下封闭式实训（中德项目）"), (f.criminal_record, "有无犯罪记录（中德项目）")):
            if not value: items.append(label)
        return items

    @staticmethod
    def _overview(f: CustomerFacts, recommended: list[dict[str, str]]) -> str:
        identity = "，".join(x for x in (f.name, f.gender, f.age_text, f.education) if x) or "该客户"
        direction = "、".join(item["project"] for item in recommended) if recommended else "暂无可直接推荐项目"
        return f"{identity}。已提供信息中可关注的需求为：{f.needs or '待进一步了解'}。当前推荐方向：{direction}，建议结合缺失信息完成电话核实。"

    @staticmethod
    def _advice(f: CustomerFacts, missing: list[str], conflicts: list[str]) -> str:
        questions = "；".join(missing) if missing else "确认项目细节与后续报名安排"
        conflict = f"；另请人工核对冲突信息：{'；'.join(conflicts)}" if conflicts else ""
        return f"电话切入：先围绕客户已提及的{f.needs or '升学/就业规划'}了解目标，再介绍相应项目。重点核实：{questions}。中德项目必须确认是否接受线下封闭式实训；家庭经济自述仅作线索，需核实实际支付能力{conflict}"

    def _merge(self, group: list[tuple[int, AssessmentRequest]]) -> tuple[AssessmentRequest, list[str]]:
        """同号批内信息合并：拼接原文，并显式报告相互冲突字段。"""
        facts = [extract_facts(req.content, req.registration) for _, req in group]
        conflicts: list[str] = []
        for attr, label in (("name", "姓名"), ("gender", "性别"), ("age_text", "年龄"), ("education", "学历")):
            values = list(dict.fromkeys(str(getattr(item, attr)) for item in facts if getattr(item, attr)))
            if len(values) > 1: conflicts.append(f"{label}存在冲突：{' / '.join(values)}，请人工确认")
        return AssessmentRequest(content="\n".join(req.content for _, req in group), source_type="batch"), conflicts
