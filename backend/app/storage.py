import io
import uuid

from minio import Minio

from .config import settings

client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=False,
)

EXT_BY_TYPE = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
TYPE_BY_EXT = {v: k for k, v in EXT_BY_TYPE.items()}


def ensure_bucket():
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)


def put_image(data, content_type):
    key = f"{uuid.uuid4().hex}.{EXT_BY_TYPE[content_type]}"
    client.put_object(
        settings.minio_bucket,
        key,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return key


def get_image(key):
    obj = client.get_object(settings.minio_bucket, key)
    try:
        return obj.read()
    finally:
        obj.close()
        obj.release_conn()
