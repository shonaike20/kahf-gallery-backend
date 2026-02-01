import io
import random
from datetime import datetime
import re
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from app.db.models import Image

def normalize(value: str) -> str:
    return re.sub(r"\s+", "_", value.strip().lower())

async def create_image(db, image, image_name, series, author, description):
    data = await image.read()

    img = Image(
        image_name=image_name,
        image_data=data,
        series_name=series,
        author=author,
        description=description
    )

    db.add(img)
    db.commit()
    db.refresh(img)

    return {"id": img.id}


def list_images(db, series_name = None, limit=30, offset=0):
    query = db.query(Image)

    if series_name:
        query = query.filter(Image.series_name == series_name)

    images = query.offset(offset).limit(limit).all()


    return [
        {
            "id": img.id,
            "image_name": img.image_name,
            "series_name": img.series_name,
            "author": img.author,
            "description": img.description
        }
        for img in images
    ]

def get_image_data(db, image_id):
    img = db.query(Image).filter(Image.id == image_id).first()

    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    return StreamingResponse(
        io.BytesIO(img.image_data),
        media_type="image/jpeg"
    )
import random

def random_images(db, limit=30):
    images = db.query(Image).all()
    random.shuffle(images)
    images = images[:limit]

    return [
        {
            "id": img.id,
            "image_name": img.image_name,
            "series_name": img.series_name,
            "author": img.author,
            "description": img.description
        }
        for img in images
    ]

async def create_images_bulk(
    db,
    images,
    base_name,
    series_name,
    author,
    description
):
    if not images or len(images) == 0:
        raise HTTPException(status_code=400, detail="No images provided")

    # Derive base name if not provided
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

        # Optional: protect against empty files
        if not data:
            raise HTTPException(status_code=400, detail=f"Empty file at index {index}")

        image_name = f"{base_name}-{index}"

        img = Image(
            image_name=image_name,
            image_data=data,
            series_name=series_name,
            author=author,
            description=description
        )

        db.add(img)
        created_names.append(image_name)

    db.commit()

    return {
        "count": len(created_names),
        "base_name": base_name,
        "images": created_names
    }
