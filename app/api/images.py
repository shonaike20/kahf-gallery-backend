from fastapi import APIRouter, UploadFile, Form, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.auth import admin_auth
from app.services.image_service import (
    create_image,
    list_images,
    get_image_data,
    random_images,
    create_images_bulk,
    delete_image,
    update_image_metadata
)

router = APIRouter(prefix="/images", tags=["Images"])

@router.post("", dependencies=[Depends(admin_auth)])
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

@router.post("/bulk", dependencies=[Depends(admin_auth)])
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

@router.delete("/{image_id}", dependencies=[Depends(admin_auth)])
def delete_image_api(
    image_id: int,
    db: Session = Depends(get_db)
):
    return delete_image(db, image_id)

@router.put("/{image_id}", dependencies=[Depends(admin_auth)])
def update_image_api(
    image_id: int,
    image_name: str = Form(None),
    series_name: str = Form(None),
    author: str = Form(None),
    description: str = Form(None),
    db: Session = Depends(get_db)
):
    return update_image_metadata(
        db,
        image_id,
        image_name,
        series_name,
        author,
        description
    )
