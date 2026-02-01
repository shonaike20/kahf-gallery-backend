from fastapi import FastAPI
from app.api import images
from app.db.database import engine
from app.db.models import Base
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(images.router, prefix="/api")

@app.get("/")
def health():
    return {"status": "ok"}


@app.get("/admin", response_class=HTMLResponse)
def admin():
    return Path("app/static/admin.html").read_text()
