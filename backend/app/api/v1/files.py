from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response

from app.api.deps import get_current_user
from app.core.exceptions import BusinessError
from app.core.response import success_response
from app.models.user import User
from app.services.file_storage import FileStorageError, file_storage

router = APIRouter(prefix="/files", tags=["文件存储"])


@router.post("/upload", summary="上传文件")
async def upload_file(
    module: str = Form(..., description="模块: crm/cs/employee/student/report/system"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    data = await file.read()
    try:
        object_name = file_storage.upload(
            module,
            file.filename or "unnamed",
            data,
            file.content_type or "application/octet-stream",
        )
        file_url = file_storage.get_presigned_url(object_name)
    except FileStorageError as exc:
        raise BusinessError(code=50003, message=str(exc))
    return success_response(
        data={"object_name": object_name, "file_url": file_url},
        message="上传成功",
    )


@router.get("/download", summary="下载文件")
async def download_file(
    object_name: str = Query(..., description="文件对象名"),
    current_user: User = Depends(get_current_user),
):
    try:
        data = file_storage.download(object_name)
    except FileStorageError as exc:
        raise BusinessError(code=50003, message=str(exc))

    filename = object_name.rsplit("/", 1)[-1]
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    return Response(content=data, media_type="application/octet-stream", headers=headers)


@router.get("/presigned", summary="获取预签名下载URL")
async def get_presigned_url(
    object_name: str = Query(..., description="文件对象名"),
    current_user: User = Depends(get_current_user),
):
    try:
        file_url = file_storage.get_presigned_url(object_name)
    except Exception as exc:  # MinIO 未启动/对象不存在等统一按文件服务异常返回
        raise BusinessError(code=50003, message=f"获取下载链接失败: {exc}")
    return success_response(data={"object_name": object_name, "file_url": file_url})
