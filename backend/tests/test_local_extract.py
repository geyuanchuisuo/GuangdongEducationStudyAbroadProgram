"""v6.10.0：客服对话本地信息提取（v6.9.10 交付的兜底逻辑）测试入库——原 5/5 为临时脚本未留档。"""
from app.services.ai_service import AiService


def test_extract_name_age_education():
    slots = AiService._local_extract_merge({}, "我叫张三，今年17岁，高二在读")
    assert slots["name"] == "张三"
    assert slots["age"] == 17
    assert slots["education"] == "高二"


def test_no_overwrite_existing_fields():
    # 已有字段不覆盖，仅补缺
    slots = AiService._local_extract_merge({"name": "李四"}, "我叫张三，想去德国")
    assert slots["name"] == "李四"
    assert slots["study_intent"] == "德国"


def test_extract_gender_and_study_intent():
    slots = AiService._local_extract_merge({}, "我是男的，想去德国留学")
    assert slots["gender"] == "男"
    assert slots["study_intent"] == "德国"


def test_empty_message_returns_slots_unchanged():
    assert AiService._local_extract_merge({"age": 18}, "") == {"age": 18}


def test_no_match_adds_nothing():
    assert AiService._local_extract_merge({}, "今天天气不错") == {}


def test_normalize_slot_value():
    assert AiService._normalize_slot_value("age", "17") == 17
    assert AiService._normalize_slot_value("age", "abc") is None
    assert AiService._normalize_slot_value("gender", "未知") is None
    assert AiService._normalize_slot_value("gender", "女") == "女"
    assert AiService._normalize_slot_value("name", "  张三  ") == "张三"
