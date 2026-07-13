# core/services/storage.py
"""
Thin wrapper around Supabase Storage for the async upload pipeline.

Why object storage instead of the local FileField path the old synchronous
pipeline used: the Celery worker that processes a file may not be the same
machine (or container) as the Django web process that accepted the HTTP
upload. A local disk path written by the web process is not guaranteed to
be visible to the worker. Object storage is the shared medium between them.

This does not remove the existing customers_file / products_file /
coupons_file FileFields — those stay for audit/history exactly as before.
This module is used specifically for the copy the Celery task reads from,
addressed by storage_key rather than by local path.
"""

import os
import tempfile
import uuid
from contextlib import contextmanager

from django.conf import settings
from supabase import create_client


def _client():
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


UPLOAD_BUCKET = getattr(settings, "SUPABASE_UPLOAD_BUCKET", "upload-staging")


def upload_fileobj_to_storage(fileobj, tenant_id: int, upload_type: str, filename: str) -> str:
    """
    Streams an uploaded file to Supabase Storage and returns the storage key.

    fileobj: a Django UploadedFile (request.FILES['...']) — file-like, may be
             InMemoryUploadedFile or TemporaryUploadedFile depending on size.
    """
    ext = os.path.splitext(filename)[1] or ".xlsx"
    storage_key = f"{tenant_id}/{upload_type}/{uuid.uuid4()}{ext}"

    client = _client()
    fileobj.seek(0)
    # Supabase's storage client accepts bytes; for very large files Django
    # will have already spooled to a TemporaryUploadedFile on disk, so this
    # read is bounded by chunked upload behavior on the client's side, not
    # held twice in memory here.
    client.storage.from_(UPLOAD_BUCKET).upload(
        path=storage_key,
        file=fileobj.read(),
        file_options={"content-type": fileobj.content_type or "application/octet-stream"},
    )
    return storage_key


@contextmanager
def download_to_tempfile(storage_key: str):
    """
    Downloads a file from Supabase Storage into a local temp file for the
    Celery worker to process, and guarantees cleanup afterward regardless
    of success or failure.

    Usage:
        with download_to_tempfile(job.storage_key) as local_path:
            ... process local_path ...
    """
    client = _client()
    suffix = os.path.splitext(storage_key)[1] or ".xlsx"
    fd, local_path = tempfile.mkstemp(suffix=suffix)
    try:
        data = client.storage.from_(UPLOAD_BUCKET).download(storage_key)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        yield local_path
    finally:
        try:
            os.remove(local_path)
        except OSError:
            pass


def delete_from_storage(storage_key: str) -> None:
    """Best-effort cleanup once a job has finished (success or failure)."""
    try:
        _client().storage.from_(UPLOAD_BUCKET).remove([storage_key])
    except Exception:
        # Cleanup failures should never break the pipeline or hide the
        # real result of the job — log and move on.
        pass
