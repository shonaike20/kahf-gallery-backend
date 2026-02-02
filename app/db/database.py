from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

#prod db toggle
# DATABASE_URL = "sqlite:////data/gallery.db"

DATABASE_URL = "sqlite:///./gallery.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
