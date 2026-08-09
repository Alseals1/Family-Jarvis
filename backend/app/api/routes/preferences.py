from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from typing import Any, Optional
from app.api.middleware.auth import get_current_user
from app.db.supabase import get_supabase_admin

router = APIRouter(prefix="/api/family")


class PreferenceCreate(BaseModel):
    category: str
    key: str
    value: Any
    family_member_id: Optional[str] = None  # null = family-wide


class FoodPreferenceCreate(BaseModel):
    preference_type: str   # 'favorite' | 'dislike' | 'restriction' | 'allergy'
    item: str
    notes: Optional[str] = None
    family_member_id: Optional[str] = None


def _require_family(user: dict) -> str:
    fid = user.get("family_id")
    if not fid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Family not set up")
    return fid


# ── General Preferences ───────────────────────────────────────────────────

@router.get("/preferences")
async def list_preferences(
    category: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    family_id = _require_family(user)
    query = (
        get_supabase_admin()
        .table("preferences")
        .select("*")
        .eq("family_id", family_id)
    )
    if category:
        query = query.eq("category", category)
    return query.execute().data


@router.post("/preferences", status_code=status.HTTP_201_CREATED)
async def create_preference(body: PreferenceCreate, user: dict = Depends(get_current_user)):
    family_id = _require_family(user)
    row = {"family_id": family_id, **body.model_dump(exclude_none=True)}
    result = get_supabase_admin().table("preferences").insert(row).execute()
    return result.data[0]


@router.delete("/preferences/{pref_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_preference(pref_id: str, user: dict = Depends(get_current_user)):
    family_id = _require_family(user)
    result = (
        get_supabase_admin()
        .table("preferences")
        .delete()
        .eq("id", pref_id)
        .eq("family_id", family_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Preference not found")


# ── Food Preferences ──────────────────────────────────────────────────────

@router.get("/food")
async def list_food_preferences(
    preference_type: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    family_id = _require_family(user)
    query = (
        get_supabase_admin()
        .table("food_preferences")
        .select("*")
        .eq("family_id", family_id)
    )
    if preference_type:
        query = query.eq("preference_type", preference_type)
    return query.execute().data


@router.post("/food", status_code=status.HTTP_201_CREATED)
async def create_food_preference(
    body: FoodPreferenceCreate,
    user: dict = Depends(get_current_user),
):
    family_id = _require_family(user)
    row = {"family_id": family_id, **body.model_dump(exclude_none=True)}
    result = get_supabase_admin().table("food_preferences").insert(row).execute()
    return result.data[0]


@router.delete("/food/{food_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_food_preference(food_id: str, user: dict = Depends(get_current_user)):
    family_id = _require_family(user)
    result = (
        get_supabase_admin()
        .table("food_preferences")
        .delete()
        .eq("id", food_id)
        .eq("family_id", family_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Food preference not found")
