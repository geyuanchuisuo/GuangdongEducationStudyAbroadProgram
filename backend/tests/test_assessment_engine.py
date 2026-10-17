from app.assessment.engine import CustomerAssessmentEngine
from app.assessment.schemas import AssessmentRequest


engine = CustomerAssessmentEngine()


def test_missing_phone_is_invalid_phone():
    result = engine.assess_one(AssessmentRequest(content="姓名张三，19岁，本科毕业，想去新加坡留学"))
    assert result.status == "invalid_phone"
    assert result.assessments is None


def test_invalid_input_stops_assessment():
    result = engine.assess_one(AssessmentRequest(content="欢迎点击广告链接，今日特价"))
    assert result.status == "invalid_input"
    assert result.recommended_projects is None


def test_registration_is_assessed_without_guessing_optional_fields():
    result = engine.assess_one(AssessmentRequest(
        content="注册信息",
        source_type="registration",
        registration={"姓名": "李四", "联系方式": "13800138000", "年龄": "22", "学历": "本科毕业", "职业需求": "希望获得稳定工作", "德语能力": "零基础"},
    ))
    assert result.status == "valid"
    assert result.assessments["singapore"]["conclusion"] == "partial"
    assert result.assessments["germany"]["conclusion"] == "partial"
    assert "家庭经济状况" in result.missing_info


def test_explicit_intent_field_extracts_country_and_study_plan():
    result = engine.assess_one(AssessmentRequest(
        content="姓名：张三；手机号：13800138000；年龄：22岁；学历：本科毕业；意向：新加坡留学，希望提升就业竞争力，毕业后尽快工作。"
    ))
    intent_dimension = next(
        item for item in result.assessments["singapore"]["dimensions"]
        if item["dimension"] == "留学意愿"
    )
    assert intent_dimension["result"] == "satisfied"
    assert "新加坡留学" in intent_dimension["evidence"]
    assert "留学意愿及意向国家" not in result.missing_info


def test_germany_hard_line_for_underage():
    result = engine.assess_one(AssessmentRequest(content="姓名王五，手机号13900139000，17岁，高中毕业，想去德国就业"))
    assert result.assessments["germany"]["conclusion"] == "not_matched"


def test_batch_same_phone_merges_and_reports_conflict():
    results = engine.assess_batch([
        AssessmentRequest(content="姓名张三，电话13800138000，22岁，本科毕业，想去新加坡"),
        AssessmentRequest(content="姓名李四，电话13800138000，希望提升就业竞争力"),
    ])
    assert len(results) == 1
    assert results[0].index == 1
    assert results[0].conflicts == ["姓名存在冲突：张三 / 李四，请人工确认"]
