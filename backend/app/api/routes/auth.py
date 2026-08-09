from fastapi import APIRouter, Depends
from app.api.middleware.auth import get_current_user

router = APIRouter(prefix="/api/auth")


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    return user
