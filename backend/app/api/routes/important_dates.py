from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from typing import Optional
from app.api.middleware.auth import get_current_user
from app.db.supabase import get_supabase_admin

router = APIRouter(prefix="/api/family/dates")


class ImportantDateCreate(BaseModel):
    label: str
    date_type: str
    date: date
    family_member_id: Optional[str] = None
    recurs_yearly: bool = True
    notes: Optional[str] = None
    lead_days: int = 14


class ImportantDateUpdate(BaseModel):
    label: Optional[str] = None
    date: Optional[date] = None
    recurs_yearly: Optional[bool] = None
    notes: Optional[str] = None
    lead_days: Optional[int] = None


def _require_family(user: dict) -> str:
    fid = user.get("family_id")
    if not fid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Family not set up")
    return fid


def _next_occurrence(d: date, today: date) -> date:
    """Return the next occurrence of a yearly date on or after today."""
    candidate = d.replace(year=today.year)
    if candidate < today:
        candidate = candidate.replace(year=today.year + 1)
    return candidate


@router.get("")
async def list_dates(
    date_type: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    family_id = _require_family(user)
    query = (
        get_supabase_admin()
        .table("important_dates")
        .select("*")
        .eq("family_id", family_id)
    )
    if date_type:
        query = query.eq("date_type", date_type)
    return query.execute().data


@router.get("/upcoming")
async def upcoming_dates(
    days: int = Query(30, ge=1, le=365),
    user: dict = Depends(get_current_user),
):
    """Return dates with their next occurrence falling within the next N days."""
    family_id = _require_family(user)
    all_dates = (
        get_supabase_admin()
        .table("important_dates")
        .select("*")
        .eq("family_id", family_id)
        .execute()
        .data
    )
    today = date.today()
    cutoff = date.fromordinal(today.toordinal() + days)
    upcoming = []
    for d in all_dates:
        raw = date.fromisoformat(d["date"])
        next_occ = _next_occurrence(raw, today) if d.get("recurs_yearly") else raw
        if today <= next_occ <= cutoff:
            upcoming.append({**d, "next_occurrence": next_occ.isoformat()})
    upcoming.sort(key=lambda x: x["next_occurrence"])
    return upcoming


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_date(body: ImportantDateCreate, user: dict = Depends(get_current_user)):
    family_id = _require_family(user)
    row = {
        "family_id": family_id,
        **body.model_dump(exclude_none=True),
        "date": str(body.date),
    }
    result = get_supabase_admin().table("important_dates").insert(row).execute()
    return result.data[0]


@router.patch("/{date_id}")
async def update_date(
    date_id: str,
    body: ImportantDateUpdate,
    user: dict = Depends(get_current_user),
):
    family_id = _require_family(user)
    updates = body.model_dump(exclude_none=True)
    if "date" in updates:
        updates["date"] = str(updates["date"])
    result = (
        get_supabase_admin()
        .table("important_dates")
        .update(updates)
        .eq("id", date_id)
        .eq("family_id", family_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Date not found")
    return result.data[0]


@router.delete("/{date_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_date(date_id: str, user: dict = Depends(get_current_user)):
    family_id = _require_family(user)
    result = (
        get_supabase_admin()
        .table("important_dates")
        .delete()
        .eq("id", date_id)
        .eq("family_id", family_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Date not found")
