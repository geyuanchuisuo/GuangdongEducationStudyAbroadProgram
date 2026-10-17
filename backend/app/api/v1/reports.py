from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_user_type
from app.core.response import success_response
from app.database import get_db
from app.models.user import User
from app.repositories.report_repo import ReportRepository
from app.schemas.report import ReportGenerateRequest, ReportOut
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["智能报告"])


def _get_service(db: AsyncSession = Depends(get_db)) -> ReportService:
    return ReportService(ReportRepository(db))


@router.get("", summary="报告列表")
async def list_reports(
    report_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_user_type("MANAGER", "ADMIN")),
    service: ReportService = Depends(_get_service),
):
    items, total = await service.list_reports(report_type, page, page_size)
    return success_response(data={
        "items": [ReportOut.model_validate(r) for r in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.post("/generate", summary="手动生成报告")
async def generate_report(
    data: ReportGenerateRequest,
    current_user: User = Depends(require_user_type("MANAGER", "ADMIN")),
    service: ReportService = Depends(_get_service),
):
    report = await service.generate(data.report_type, data.period_start, data.period_end, current_user.id)
    return success_response(data=ReportOut.model_validate(report), message="生成成功")


@router.get("/{report_id}", summary="报告详情")
async def get_report(
    report_id: int,
    current_user: User = Depends(require_user_type("MANAGER", "ADMIN")),
    service: ReportService = Depends(_get_service),
):
    report = await service.get_report(report_id)
    return success_response(data=ReportOut.model_validate(report))


@router.get("/{report_id}/customers", summary="客户下钻（脱敏）")
async def report_customers(
    report_id: int,
    current_user: User = Depends(require_user_type("MANAGER", "ADMIN")),
    service: ReportService = Depends(_get_service),
):
    items = await service.customer_drilldown(report_id)
    return success_response(data={"items": items})


@router.get("/{report_id}/psych_cases", summary="心理个案（按角色过滤）")
async def report_psych_cases(
    report_id: int,
    current_user: User = Depends(get_current_user),
    service: ReportService = Depends(_get_service),
):
    items = await service.psych_cases(report_id, current_user)
    return success_response(data={"items": items})


@router.get("/{report_id}/special_cases", summary="投诉特别案例（仅已复核）")
async def report_special_cases(
    report_id: int,
    current_user: User = Depends(require_user_type("MANAGER", "ADMIN")),
    service: ReportService = Depends(_get_service),
):
    items = await service.special_cases(report_id)
    return success_response(data={"items": items})


@router.get("/{report_id}/download", summary="下载脱敏 PDF")
async def download_report(
    report_id: int,
    current_user: User = Depends(require_user_type("MANAGER", "ADMIN")),
    service: ReportService = Depends(_get_service),
):
    pdf_bytes = await service.download_pdf(report_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report_{report_id}.pdf"'},
    )
