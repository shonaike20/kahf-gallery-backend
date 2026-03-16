from sqlalchemy import Column, Integer, Text, LargeBinary, String
from app.db.database import Base


class Image(Base):
    __tablename__ = "images"

    id             = Column(Integer, primary_key=True, index=True)
    image_name     = Column(String,      nullable=False)
    content_type   = Column(String,      nullable=False, default="image/jpeg")
    file_name      = Column(String,      nullable=True)   # UUID filename on disk (new records)
    image_data     = Column(LargeBinary, nullable=True)   # legacy BLOB
    thumbnail_data = Column(LargeBinary, nullable=True)   # legacy BLOB
    series_name    = Column(String,      nullable=True)
    author         = Column(String,      nullable=True)
    description    = Column(Text,        nullable=True)
