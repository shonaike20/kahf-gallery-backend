import os
from fastapi import Depends, HTTPException, status, Request


def admin_auth(request: Request):
    if request.cookies.get("admin_session") != "authenticated":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )
    return True