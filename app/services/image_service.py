import io
import random
import re
from datetime import datetime

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from PIL import Image as PILImage, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import defer

from app.db.models import Image


THUMBNAIL_SIZE = (160, 160)
THUMBNAIL_FORMAT = "WEBP"
THUMBNAIL_QUALITY = 80


def normalize(value: str) -> str:
    return re.sub(r"\s+", "_", value.strip().lower())


def _detect_media_type(data: bytes) -> str:
    try:
        with PILImage.open(io.BytesIO(data)) as img:
            fmt = (img.format or "").upper()
    except UnidentifiedImageError:
        return "application/octet-stream"

    mapping = {
        "JPEG": "image/jpeg",
        "JPG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
        "GIF": "image/gif",
        "BMP": "image/bmp",
        "TIFF": "image/tiff",
    }
    return mapping.get(fmt, "application/octet-stream")


def _generate_thumbnail_bytes(data: bytes) -> bytes:
    try:
        with PILImage.open(io.BytesIO(data)) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail(THUMBNAIL_SIZE)

            output = io.BytesIO()
            img.save(output, format=THUMBNAIL_FORMAT, quality=THUMBNAIL_QUALITY, method=6)
            return output.getvalue()
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="Unsupported or invalid image file")


def _stream_bytes(data: bytes, media_type: str, max_age: int) -> StreamingResponse:
    response = StreamingResponse(io.BytesIO(data), media_type=media_type)
    response.headers["Cache-Control"] = f"public, max-age={max_age}"
    return response


async def create_image(db, image, image_name, series_name, author, description):
    data = await image.read()

    if not data:
        raise HTTPException(status_code=400, detail="Empty image file")

    thumbnail_data = _generate_thumbnail_bytes(data)

    img = Image(
        image_name=image_name,
        image_data=data,
        thumbnail_data=thumbnail_data,
        series_name=series_name,
        author=author,
        description=description,
    )

    db.add(img)
    db.commit()
    db.refresh(img)

    return {"id": img.id}


def list_images(db, series_name=None, limit=None, offset=0):
    query = db.query(Image).options(
        defer(Image.image_data),
        defer(Image.thumbnail_data),
    )

    if series_name:
        query = query.filter(Image.series_name == series_name)

    query = query.order_by(Image.id.desc())

    has_more = False

    if limit is not None:
        records = query.offset(offset).limit(limit + 1).all()
        if len(records) > limit:
            has_more = True
            records = records[:limit]
    else:
        records = query.offset(offset).all()

    return {
        "items": [
            {
                "id": img.id,
                "image_name": img.image_name,
                "series_name": img.series_name,
                "author": img.author,
                "description": img.description,
            }
            for img in records
        ],
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
    }


def get_image_data(db, image_id):
    img = db.query(Image).filter(Image.id == image_id).first()

    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    media_type = _detect_media_type(img.image_data)
    return _stream_bytes(img.image_data, media_type, max_age=3600)


def get_image_thumb(db, image_id):
    img = db.query(Image).filter(Image.id == image_id).first()

    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    # Backfill thumbnails for old rows that were uploaded before thumbnail support existed
    if not getattr(img, "thumbnail_data", None):
        img.thumbnail_data = _generate_thumbnail_bytes(img.image_data)
        db.commit()
        db.refresh(img)

    return _stream_bytes(img.thumbnail_data, "image/webp", max_age=86400)


def random_images(db, limit=30):
    records = db.query(Image).options(
        defer(Image.image_data),
        defer(Image.thumbnail_data),
    ).all()

    random.shuffle(records)
    records = records[:limit]

    return [
        {
            "id": img.id,
            "image_name": img.image_name,
            "series_name": img.series_name,
            "author": img.author,
            "description": img.description,
        }
        for img in records
    ]


async def create_images_bulk(
    db,
    images,
    base_name,
    series_name,
    author,
    description,
):
    if not images or len(images) == 0:
        raise HTTPException(status_code=400, detail="No images provided")

    if not base_name:
        safe_author = normalize(author or "unknown")
        safe_series = normalize(series_name or "untitled")
        date_str = datetime.utcnow().strftime("%Y%m%d")
        base_name = f"{safe_author}_{safe_series}_{date_str}"
    else:
        base_name = normalize(base_name)

    created_names = []

    for index, image in enumerate(images, start=1):
        data = await image.read()

        if not data:
            raise HTTPException(status_code=400, detail=f"Empty file at index {index}")

        image_name = f"{base_name}-{index}"
        thumbnail_data = _generate_thumbnail_bytes(data)

        img = Image(
            image_name=image_name,
            image_data=data,
            thumbnail_data=thumbnail_data,
            series_name=series_name,
            author=author,
            description=description,
        )

        db.add(img)
        created_names.append(image_name)

    db.commit()

    return {
        "count": len(created_names),
        "base_name": base_name,
        "images": created_names,
    }


def delete_image(db, image_id):
    img = db.query(Image).filter(Image.id == image_id).first()

    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    db.delete(img)
    db.commit()

    return {"deleted": image_id}


def delete_all_images(db):
    deleted_count = db.query(Image).delete(synchronize_session=False)
    db.commit()

    return {
        "message": "All images deleted successfully",
        "deleted_count": deleted_count,
    }


def update_image_metadata(
    db,
    image_id,
    image_name=None,
    series_name=None,
    author=None,
    description=None,
):
    img = db.query(Image).filter(Image.id == image_id).first()

    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    if image_name is not None:
        img.image_name = image_name
    if series_name is not None:
        img.series_name = series_name
    if author is not None:
        img.author = author
    if description is not None:
        img.description = description

    db.commit()
    db.refresh(img)

    return {"updated": image_id}