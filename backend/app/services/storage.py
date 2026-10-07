import hashlib
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.db.models import StoredFile
from app.services.base import BaseService


class FileStorageService(BaseService):
    def save_bytes(
        self,
        *,
        content: bytes,
        original_name: str,
        mime_type: str | None = None,
        owner_type: str | None = None,
        owner_id: int | None = None,
        base_dir: Path | None = None,
    ) -> StoredFile:
        if not content:
            raise ValueError("file is empty")
        if len(content) > settings.max_upload_bytes:
            raise ValueError(f"file exceeds limit: {settings.max_upload_bytes} bytes")

        digest = hashlib.sha256(content).hexdigest()
        safe_name = self.sanitize_filename(original_name)
        now = datetime.now()
        root = (base_dir or Path(settings.data_dir)).resolve()
        directory = root / "uploads" / f"{now:%Y}" / f"{now:%m}"
        directory.mkdir(parents=True, exist_ok=True)
        stored_path = directory / f"{uuid4().hex}_{safe_name}"
        stored_path.write_bytes(content)

        stored_file = StoredFile(
            original_name=original_name,
            stored_path=str(stored_path),
            mime_type=mime_type or "application/octet-stream",
            size_bytes=len(content),
            sha256=digest,
            owner_type=owner_type,
            owner_id=owner_id,
        )
        return self.uow.files.add(stored_file)

    @staticmethod
    def sanitize_filename(name: str) -> str:
        safe = Path(name or "upload.bin").name
        safe = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "_", safe)
        safe = safe.strip("._") or "upload.bin"
        return safe[:180]
