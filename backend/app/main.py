import re
import secrets

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from minio.error import S3Error
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import storage
from .config import settings
from .db import Product, get_session

MAX_IMAGE_BYTES = 10 * 1024 * 1024
KEY_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")

app = FastAPI(title="Catalog API")


class ProductOut(BaseModel):
    id: int
    title: str
    image_url: str


def to_out(p: Product) -> ProductOut:
    return ProductOut(id=p.id, title=p.title, image_url=f"/api/images/{p.image_key}")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/products", response_model=list[ProductOut])
async def list_products(session: AsyncSession = Depends(get_session)):
    rows = await session.scalars(select(Product).order_by(Product.id.desc()))
    return [to_out(p) for p in rows]


@app.post("/api/products", response_model=ProductOut, status_code=201)
async def create_product(
    title: str = Form(..., min_length=1, max_length=255),
    image: UploadFile = File(...),
    x_internal_token: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
):
    if not x_internal_token or not secrets.compare_digest(
        x_internal_token, settings.internal_token
    ):
        raise HTTPException(status_code=403, detail="forbidden")

    content_type = image.content_type or ""
    if content_type not in storage.EXT_BY_TYPE:
        raise HTTPException(status_code=415, detail="unsupported image type")

    data = await image.read()
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="bad image size")

    key = await run_in_threadpool(storage.put_image, data, content_type)
    product = Product(title=title.strip(), image_key=key)
    session.add(product)
    await session.commit()
    return to_out(product)


@app.get("/api/images/{key}")
async def get_image(key: str):
    if not KEY_RE.match(key):
        raise HTTPException(status_code=404)
    try:
        data = await run_in_threadpool(storage.get_image, key)
    except S3Error:
        raise HTTPException(status_code=404)
    media_type = storage.TYPE_BY_EXT[key.rsplit(".", 1)[1]]
    return Response(
        content=data,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
