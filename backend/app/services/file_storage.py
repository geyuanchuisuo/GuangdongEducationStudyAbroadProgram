import io
import os
import re
import uuid
from datetime import date
from enum import Enum
from pathlib import Path
from urllib.parse import quote

from app.config import settings

MAX_FILE_SIZE = 20 * 1024 * 1024

# object_name 合法格式：module/YYYY-MM-DD/8位hex_文件名（文件名仅常见安全字符）
_OBJECT_NAME_RE = re.compile(r"^[a-z]+/\d{4}-\d{2}-\d{2}/[0-9a-f]{8}_[^/\\]+$")


class FileModule(str, Enum):
    CRM = "crm"
    CS = "cs"
    EMPLOYEE = "employee"
    STUDENT = "student"
    REPORT = "report"
    SYSTEM = "system"


ALLOWED_EXTENSIONS: dict[str, list[str]] = {
    "image": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
    "document": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"],
    "text": [".txt", ".csv", ".md"],
    "archive": [".zip"],
}

_ALL_ALLOWED = set()
for exts in ALLOWED_EXTENSIONS.values():
    _ALL_ALLOWED.update(exts)


class FileStorageError(Exception):
    pass


class FileStorageService:
    """文件存储服务（双后端）

    - local（默认，STORAGE_BACKEND=local）：落盘到 STORAGE_LOCAL_DIR，一期单机 Docker 零外部依赖
    - s3（STORAGE_BACKEND=s3）：MinIO 等 S3 兼容存储，二期生产/分布式部署可选
    """

    def __init__(self) -> None:
        self._client = None  # S3 客户端延迟初始化
        self._local_base: Path | None = None

    # ---------- 公共校验/路径 ----------

    def _validate(self, filename: str, file_size: int) -> str:
        if file_size > MAX_FILE_SIZE:
            raise FileStorageError(f"文件大小超过限制（最大 {MAX_FILE_SIZE // 1024 // 1024}MB）")

        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in _ALL_ALLOWED:
            raise FileStorageError(f"文件类型不允许: {ext}")
        return ext

    def _build_path(self, module: str | FileModule, original_filename: str) -> str:
        module_str = module.value if isinstance(module, FileModule) else module
        today = date.today().isoformat()
        unique = uuid.uuid4().hex[:8]
        # 清洗文件名：只保留基线名，剥离任何路径成分，防止文件名注入分隔符
        safe_name = os.path.basename(original_filename).replace("\\", "_").replace("/", "_")
        return f"{module_str}/{today}/{unique}_{safe_name}"

    @staticmethod
    def _validate_object_name(object_name: str) -> None:
        if not object_name or not _OBJECT_NAME_RE.match(object_name) or ".." in object_name:
            raise FileStorageError("非法的文件对象名")

    # ---------- local 后端 ----------

    def _local_base_dir(self) -> Path:
        if self._local_base is None:
            base = Path(settings.STORAGE_LOCAL_DIR).resolve()
            base.mkdir(parents=True, exist_ok=True)
            self._local_base = base
        return self._local_base

    def _local_path(self, object_name: str) -> Path:
        self._validate_object_name(object_name)
        base = self._local_base_dir()
        target = (base / object_name).resolve()
        # 双重保险：resolve 后必须仍位于存储根目录内
        if base not in target.parents and target != base:
            raise FileStorageError("非法的文件对象名")
        return target

    def _local_upload(self, object_name: str, data: bytes) -> None:
        target = self._local_path(object_name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def _local_download(self, object_name: str) -> bytes:
        target = self._local_path(object_name)
        if not target.is_file():
            raise FileStorageError("文件不存在")
        return target.read_bytes()

    def _local_delete(self, object_name: str) -> None:
        target = self._local_path(object_name)
        if target.is_file():
            target.unlink()

    # ---------- s3 后端（MinIO，二期可选） ----------

    def _get_client(self):
        if self._client is None:
            from minio import Minio  # 延迟导入：local 模式无需 minio 服务/依赖可用

            self._client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=False,
            )
        return self._client

    def _ensure_bucket(self, client) -> None:
        bucket = settings.MINIO_BUCKET
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)

    def _s3_upload(self, object_name: str, data: bytes, content_type: str) -> None:
        from minio.error import S3Error  # noqa: F401  (保留后端分支依赖说明)

        client = self._get_client()
        self._ensure_bucket(client)
        client.put_object(
            settings.MINIO_BUCKET,
            object_name,
            io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    def _s3_download(self, object_name: str) -> bytes:
        from minio.error import S3Error

        client = self._get_client()
        response = None
        try:
            response = client.get_object(settings.MINIO_BUCKET, object_name)
            return response.read()
        except S3Error as exc:
            raise FileStorageError(f"文件下载失败: {exc}") from exc
        finally:
            if response is not None:
                response.close()
                response.release_conn()

    def _s3_delete(self, object_name: str) -> None:
        client = self._get_client()
        client.remove_object(settings.MINIO_BUCKET, object_name)

    # ---------- 对外统一接口 ----------

    def upload(
        self,
        module: str | FileModule,
        filename: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        self._validate(filename, len(data))
        object_name = self._build_path(module, filename)
        if settings.STORAGE_BACKEND == "s3":
            self._s3_upload(object_name, data, content_type)
        else:
            self._local_upload(object_name, data)
        return object_name

    def get_presigned_url(self, object_name: str, expires_hours: int = 1) -> str:
        """返回下载地址。

        - s3：MinIO 预签名 URL（浏览器直连，有效期 expires_hours 小时）
        - local：后端鉴权下载端点相对路径（前端 axios 带 Bearer Token 请求，
          与平台内附件下载场景一致；local 模式无独立对象存储，不产生免登录 URL）
        """
        if settings.STORAGE_BACKEND == "s3":
            from datetime import timedelta

            client = self._get_client()
            return client.presigned_get_object(
                settings.MINIO_BUCKET,
                object_name,
                expires=timedelta(hours=expires_hours),
            )
        self._validate_object_name(object_name)
        return f"/api/v1/files/download?object_name={quote(object_name, safe='/_-')}"

    def download(self, object_name: str) -> bytes:
        if settings.STORAGE_BACKEND == "s3":
            return self._s3_download(object_name)
        return self._local_download(object_name)

    def delete(self, object_name: str) -> None:
        if settings.STORAGE_BACKEND == "s3":
            self._s3_delete(object_name)
        else:
            self._local_delete(object_name)


file_storage = FileStorageService()
