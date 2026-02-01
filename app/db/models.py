from sqlalchemy import Column, Integer, Text, LargeBinary, String
from app.db.database import Base

class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    image_name = Column(String, nullable=False)
    image_data = Column(LargeBinary, nullable=False)
    series_name = Column(String)
    author = Column(String)
    description = Column(Text)