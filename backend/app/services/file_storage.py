import io
import uuid
from datetime import date
from enum import Enum

from minio import Minio
from minio.error import S3Error

from app.config import settings

MAX_FILE_SIZE = 20 * 1024 * 1024


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
    def __init__(self) -> None:
        self._client: Minio | None = None

    def _get_client(self) -> Minio:
        if self._client is None:
            self._client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=False,
            )
        return self._client

    def _ensure_bucket(self, client: Minio) -> None:
        bucket = settings.MINIO_BUCKET
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)

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
        ext = "." + original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
        return f"{module_str}/{today}/{unique}_{original_filename}"

    def upload(
        self,
        module: str | FileModule,
        filename: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        self._validate(filename, len(data))
        object_name = self._build_path(module, filename)

        client = self._get_client()
        self._ensure_bucket(client)

        stream = io.BytesIO(data)
        client.put_object(
            settings.MINIO_BUCKET,
            object_name,
            stream,
            length=len(data),
            content_type=content_type,
        )
        return object_name

    def get_presigned_url(self, object_name: str, expires_hours: int = 1) -> str:
        from datetime import timedelta
        client = self._get_client()
        return client.presigned_get_object(
            settings.MINIO_BUCKET,
            object_name,
            expires=timedelta(hours=expires_hours),
        )

    def download(self, object_name: str) -> bytes:
        client = self._get_client()
        try:
            response = client.get_object(settings.MINIO_BUCKET, object_name)
            return response.read()
        except S3Error as exc:
            raise FileStorageError(f"文件下载失败: {exc}") from exc
        finally:
            response.close()  # type: ignore[possibly-undefined]
            response.release_conn()  # type: ignore[possibly-undefined]

    def delete(self, object_name: str) -> None:
        client = self._get_client()
        client.remove_object(settings.MINIO_BUCKET, object_name)


file_storage = FileStorageService()
