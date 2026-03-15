import os
from pathlib import Path

from dotenv import load_dotenv

# Explicitly load .env from the project root (one level above this file)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

print("ENV PATH:", _env_path)
print("ADMIN_USER:", os.getenv("ADMIN_USER"))
print("ADMIN_PASSWORD:", os.getenv("ADMIN_PASSWORD"))

from fastapi import FastAPI, Depends, Form, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import images
from app.db.database import engine
from app.db.models import Base
from app.auth import admin_auth

Base.metadata.create_all(bind=engine)

# Absolute path to app/static - works regardless of where uvicorn is run from
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI()
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(images.router, prefix="/api")


@app.get("/")
def health():
    return {"status": "ok"}


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
        resp.set_cookie(
            "admin_session",
            "authenticated",
            httponly=True,
            samesite="strict",
        )
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