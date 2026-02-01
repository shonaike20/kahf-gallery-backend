from fastapi import APIRouter, UploadFile, Form, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.image_service import (
    create_image,
    list_images,
    get_image_data,
    random_images,
    create_images_bulk
)

router = APIRouter(prefix="/images", tags=["Images"])

@router.post("/")
async def upload_image(
    image: UploadFile,
    image_name: str = Form(...),
    series_name: str = Form(None),
    author: str = Form(None),
    description: str = Form(None),
    db: Session = Depends(get_db)
):
    return await create_image(
        db, image, image_name, series_name, author, description
    )


@router.get("/")
def fetch_images(
    #optional filter by series
    series_name: str | None = None,
    limit: int = 30,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    return list_images(db, series_name, limit, offset)

@router.get("/{image_id}/data")
def fetch_image_data(image_id: int, db: Session = Depends(get_db)):
    return get_image_data(db, image_id)

@router.get("/random")
def fetch_random_images(
    limit: int = 30,
    db: Session = Depends(get_db)
):
    return random_images(db, limit)

@router.post("/bulk")
async def bulk_upload_images(
    images: list[UploadFile],
    base_name: str | None = Form(None),
    series_name: str = Form(None),
    author: str = Form(None),
    description: str = Form(None),
    db: Session = Depends(get_db)
):
    return await create_images_bulk(
        db,
        images,
        base_name,
        series_name,
        author,
        description
    )