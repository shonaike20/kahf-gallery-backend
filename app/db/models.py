from sqlalchemy import Column, Integer, Text, LargeBinary, String
from app.db.database import Base

class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    image_name = Column(String, nullable=False)
    image_data = Column(LargeBinary, nullable=False)
    thumbnail_data = Column(LargeBinary, nullable=True)  # <- add this
    series_name = Column(String, nullable=True)
    author = Column(String, nullable=True)
    description = Column(Text, nullable=True)