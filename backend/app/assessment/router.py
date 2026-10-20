import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import require_user_type
from app.core.exceptions import ValidationError
from app.core.response import success_response

from .engine import CustomerAssessmentEngine
from .file_parsers import SUPPORTED_SUFFIXES, extract_text
from .schemas import AssessmentRequest, BatchAssessmentRequest

router = APIRouter(prefix="/crm/assessments", tags=["客户研判"])
engine = CustomerAssessmentEngine()


@router.post("/text")
async def assess_text(
    request: AssessmentRequest,
    _current_user=Depends(require_user_type("EMPLOYEE", "MANAGER")),
):
    """文本、客服对话或上游已解析的文件文本的单条研判。"""
    return success_response(data=engine.assess_one(request).model_dump())


@router.post("/file")
async def assess_file(
    file: UploadFile = File(...),
    _current_user=Depends(require_user_type("EMPLOYEE", "MANAGER")),
):
    """文件研判：后端 extract_text 提取全文后走文本研判引擎。"""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValidationError(f"不支持的文件类型：{suffix or '未知'}，支持 {','.join(SUPPORTED_SUFFIXES)}")
    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        text = extract_text(tmp_path)
    except Exception as exc:
        # v6.11.58：损坏/伪装文件（如改扩展名的假 docx → BadZipFile）不再崩为 50001，
        # 统一走业务异常（40002），前端拦截器自动弹出友好提示
        raise ValidationError(f"文件内容无法解析（可能已损坏或与扩展名不符）：{exc}") from exc
    finally:
        os.unlink(tmp_path)
    if not text.strip():
        raise ValidationError("文件内容为空或无法提取文字")
    return success_response(
        # v6.11.32：文件渠道标记为 file_text，使提取器可启用面向简历文档的规则（如姓名独占首行）
        data=engine.assess_one(AssessmentRequest(source_type="file_text", content=text)).model_dump(),
        message="文件研判完成",
    )


@router.post("/batch")
async def assess_batch(
    request: BatchAssessmentRequest,
    _current_user=Depends(require_user_type("EMPLOYEE", "MANAGER")),
):
    """批量研判；批内同手机号自动整合，仅返回一条研判记录。"""
    return success_response(data=[record.model_dump() for record in engine.assess_batch(request.records)])
