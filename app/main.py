from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi import Depends
from app.api import images
from app.db.database import engine
from app.db.models import Base
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.auth import admin_auth
from pathlib import Path

Base.metadata.create_all(bind=engine)

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(images.router, prefix="/api")



@app.get("/")
def health():
    return {"status": "ok"}


@app.get("/admin", dependencies=[Depends(admin_auth)])
def admin():
    return FileResponse("app/static/admin.html")
