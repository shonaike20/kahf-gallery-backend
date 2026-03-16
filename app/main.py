import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, Depends, Form, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import images
from app.db.database import engine, run_migrations
from app.db.models import Base
from app.auth import admin_auth

Base.metadata.create_all(bind=engine)
run_migrations()

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI()
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(images.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def gallery_landing():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/browse")
def gallery_browse():
    return FileResponse(str(STATIC_DIR / "browse.html"))


@app.get("/series")
def gallery_series():
    return FileResponse(str(STATIC_DIR / "series.html"))


@app.get("/login")
def login_page():
    return FileResponse(str(STATIC_DIR / "login.html"))


@app.post("/login")
def login(
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
):
    correct_user = os.getenv("ADMIN_USER", "")
    correct_pass = os.getenv("ADMIN_PASSWORD", "")

    if username == correct_user and password == correct_pass:
        resp = RedirectResponse(url="/admin", status_code=302)
        resp.set_cookie("admin_session", "authenticated", httponly=True, samesite="strict")
        return resp

    return RedirectResponse(url="/login?error=1", status_code=302)


@app.post("/logout")
def logout():
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie("admin_session")
    return resp


@app.get("/admin", dependencies=[Depends(admin_auth)])
def admin():
    return FileResponse(str(STATIC_DIR / "admin.html"))
