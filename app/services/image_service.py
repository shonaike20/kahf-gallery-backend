import asyncio
import io
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image as PILImage, ImageOps, UnidentifiedImageError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Image

# ── Storage directories ────────────────────────────────────────────────────────
# Derive uploads root from DATABASE_URL so local → ./uploads, Fly.io → /data/uploads
_db_url = os.getenv("DATABASE_URL", "sqlite:///./gallery.db")
_db_path_match = re.match(r"sqlite:///(.+\.db)", _db_url)
_db_dir = Path(_db_path_match.group(1)).parent if _db_path_match else Path(".")
_UPLOADS_BASE = Path(os.getenv("UPLOADS_DIR", str(_db_dir / "uploads")))

IMAGES_DIR = _UPLOADS_BASE / "images"
THUMBS_DIR = _UPLOADS_BASE / "thumbs"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
THUMBS_DIR.mkdir(parents=True, exist_ok=True)

# ── Constants ──────────────────────────────────────────────────────────────────

THUMBNAIL_SIZE    = (300, 300)
THUMBNAIL_QUALITY = 82
THUMBNAIL_FORMAT  = "WEBP"

_MIME_MAP = {
    "JPEG": "image/jpeg",
    "JPG":  "image/jpeg",
    "PNG":  "image/png",
    "WEBP": "image/webp",
    "GIF":  "image/gif",
    "BMP":  "image/bmp",
    "TIFF": "image/tiff",
}

_METADATA = [Image.id, Image.image_name, Image.series_name, Image.author, Image.description]


# ── Helpers ────────────────────────────────────────────────────────────────────

def normalize(value: str) -> str:
    return re.sub(r"\s+", "_", value.strip().lower())


def _detect_content_type(data: bytes) -> str:
    try:
        with PILImage.open(io.BytesIO(data)) as img:
            return _MIME_MAP.get((img.format or "").upper(), "application/octet-stream")
    except Exception:
        return "application/octet-stream"


def _generate_thumbnail(data: bytes) -> bytes:
    try:
        with PILImage.open(io.BytesIO(data)) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail(THUMBNAIL_SIZE)
            out = io.BytesIO()
            # method=4 is a good speed/quality balance (method=6 is slowest)
            img.save(out, format=THUMBNAIL_FORMAT, quality=THUMBNAIL_QUALITY, method=4)
            return out.getvalue()
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="Unsupported or invalid image file")


def _save_to_disk(data: bytes, file_name: str) -> None:
    """Write image bytes and generate + write thumbnail. Runs in a thread."""
    (IMAGES_DIR / file_name).write_bytes(data)
    thumb = _generate_thumbnail(data)
    (THUMBS_DIR / f"{file_name}.webp").write_bytes(thumb)


def _delete_files(file_name: str) -> None:
    for path in [IMAGES_DIR / file_name, THUMBS_DIR / f"{file_name}.webp"]:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def _cached_file_response(path: Path, media_type: str, max_age: int) -> FileResponse:
    return FileResponse(
        str(path),
        media_type=media_type,
        headers={"Cache-Control": f"public, max-age={max_age}"},
    )


def _streaming_blob(data: bytes, media_type: str, max_age: int) -> StreamingResponse:
    resp = StreamingResponse(io.BytesIO(data), media_type=media_type)
    resp.headers["Cache-Control"] = f"public, max-age={max_age}"
    return resp


def _row_to_dict(r) -> dict:
    return {
        "id": r.id,
        "image_name": r.image_name,
        "series_name": r.series_name,
        "author": r.author,
        "description": r.description,
    }


# ── Service functions ──────────────────────────────────────────────────────────

async def create_image(db: Session, image, image_name, series_name, author, description):
    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty image file")

    content_type = _detect_content_type(data)
    file_name    = str(uuid.uuid4())

    # PIL thumbnail generation is CPU-bound — run off the event loop
    await asyncio.to_thread(_save_to_disk, data, file_name)

    img = Image(
        image_name=image_name,
        content_type=content_type,
        file_name=file_name,
        series_name=series_name,
        author=author,
        description=description,
    )
    db.add(img)
    db.commit()
    db.refresh(img)
    return {"id": img.id}


def list_images(db: Session, series_name=None, author=None, limit=20, offset=0):
    query = db.query(*_METADATA)
    if series_name:
        query = query.filter(Image.series_name == series_name)
    if author:
        query = query.filter(Image.author == author)
    query = query.order_by(Image.id.desc())

    has_more = False
    if limit is not None:
        rows = query.offset(offset).limit(limit + 1).all()
        if len(rows) > limit:
            has_more = True
            rows = rows[:limit]
    else:
        rows = query.offset(offset).all()

    return {
        "items": [_row_to_dict(r) for r in rows],
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
    }


def get_image_data(db: Session, image_id: int):
    row = (
        db.query(Image.file_name, Image.content_type, Image.image_data)
        .filter(Image.id == image_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Image not found")

    # New file-based path — OS sendfile, ETags, Range requests for free
    if row.file_name:
        path = IMAGES_DIR / row.file_name
        if path.exists():
            return _cached_file_response(path, row.content_type or "image/jpeg", max_age=3600)

    # Legacy BLOB fallback
    if row.image_data:
        return _streaming_blob(row.image_data, row.content_type or "image/jpeg", max_age=3600)

    raise HTTPException(status_code=404, detail="Image data not found")


def get_image_thumb(db: Session, image_id: int):
    row = (
        db.query(Image.file_name, Image.thumbnail_data)
        .filter(Image.id == image_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Image not found")

    # New file-based path
    if row.file_name:
        path = THUMBS_DIR / f"{row.file_name}.webp"
        if path.exists():
            return _cached_file_response(path, "image/webp", max_age=86400)

    # Legacy: has thumbnail BLOB
    if row.thumbnail_data:
        return _streaming_blob(row.thumbnail_data, "image/webp", max_age=86400)

    # Legacy: no thumbnail — generate from full image on demand (separate query to avoid loading
    # image_data unless absolutely necessary)
    full = db.query(Image.image_data).filter(Image.id == image_id).first()
    if full and full.image_data:
        thumb = _generate_thumbnail(full.image_data)
        return _streaming_blob(thumb, "image/webp", max_age=86400)

    raise HTTPException(status_code=404, detail="Thumbnail not found")


def random_images(db: Session, limit: int = 30):
    # ORDER BY RANDOM() in SQL — no full table load + Python shuffle
    rows = db.query(*_METADATA).order_by(func.random()).limit(limit).all()
    return {"items": [_row_to_dict(r) for r in rows]}


def list_series(db: Session):
    """Return all distinct (series_name, author) pairs with image count and a cover image id."""
    # Subquery: for each (series_name, author) group get the lowest image id as cover
    groups = (
        db.query(
            Image.series_name,
            Image.author,
            func.count(Image.id).label("image_count"),
            func.min(Image.id).label("cover_image_id"),
        )
        .filter(Image.series_name.isnot(None))
        .group_by(Image.series_name, Image.author)
        .order_by(Image.series_name)
        .all()
    )

    return [
        {
            "series_name": g.series_name,
            "author": g.author,
            "image_count": g.image_count,
            "cover_image_id": g.cover_image_id,
        }
        for g in groups
    ]


async def create_images_bulk(db: Session, images, base_name, series_name, author, description):
    if not images:
        raise HTTPException(status_code=400, detail="No images provided")

    if not base_name:
        safe_author = normalize(author or "unknown")
        safe_series = normalize(series_name or "untitled")
        date_str    = datetime.utcnow().strftime("%Y%m%d")
        base_name   = f"{safe_author}_{safe_series}_{date_str}"
    else:
        base_name = normalize(base_name)

    # Read all files before any processing
    payloads = []
    for index, image in enumerate(images, start=1):
        data = await image.read()
        if not data:
            raise HTTPException(status_code=400, detail=f"Empty file at index {index}")
        payloads.append(data)

    # Process thumbnails with bounded concurrency to cap memory usage.
    # Running all PIL tasks at once on a single-CPU VM spikes RAM and can
    # exceed the proxy's 60s timeout; a semaphore of 4 keeps throughput high
    # while bounding peak memory to ~4 images in-flight at once.
    _sem = asyncio.Semaphore(4)

    async def _process(data: bytes, image_name: str) -> Image:
        async with _sem:
            file_name    = str(uuid.uuid4())
            content_type = _detect_content_type(data)
            await asyncio.to_thread(_save_to_disk, data, file_name)
            return Image(
                image_name=image_name,
                content_type=content_type,
                file_name=file_name,
                series_name=series_name,
                author=author,
                description=description,
            )

    img_objs = await asyncio.gather(
        *[_process(data, f"{base_name}-{i}") for i, data in enumerate(payloads, start=1)]
    )

    for img in img_objs:
        db.add(img)
    db.commit()

    return {
        "count": len(img_objs),
        "base_name": base_name,
        "images": [img.image_name for img in img_objs],
    }


def delete_image(db: Session, image_id: int):
    img = db.query(Image).filter(Image.id == image_id).first()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    if img.file_name:
        _delete_files(img.file_name)

    db.delete(img)
    db.commit()
    return {"deleted": image_id}


def delete_all_images(db: Session):
    rows = db.query(Image.file_name).all()
    for row in rows:
        if row.file_name:
            _delete_files(row.file_name)

    deleted_count = db.query(Image).delete(synchronize_session=False)
    db.commit()
    return {"message": "All images deleted successfully", "deleted_count": deleted_count}


def update_image_metadata(db: Session, image_id, image_name=None, series_name=None, author=None, description=None):
    img = db.query(Image).filter(Image.id == image_id).first()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    if image_name  is not None: img.image_name  = image_name
    if series_name is not None: img.series_name = series_name
    if author      is not None: img.author      = author
    if description is not None: img.description = description

    db.commit()
    return {"updated": image_id}
