from fastapi import APIRouter, Depends, HTTPException, status
from app.api.middleware.auth import get_current_user
from app.db.supabase import get_supabase_admin
from app.models.family import FamilyMemberCreate, FamilyMemberUpdate

router = APIRouter(prefix="/api/family/members")


def _require_family(user: dict) -> str:
    family_id = user.get("family_id")
    if not family_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Family not set up")
    return family_id


@router.get("")
async def list_members(user: dict = Depends(get_current_user)):
    family_id = _require_family(user)
    result = (
        get_supabase_admin()
        .table("family_members")
        .select("*")
        .eq("family_id", family_id)
        .eq("active", True)
        .execute()
    )
    return result.data


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_member(body: FamilyMemberCreate, user: dict = Depends(get_current_user)):
    family_id = _require_family(user)
    row = {
        "family_id": family_id,   # always from JWT, never from body
        **body.model_dump(exclude_none=True),
    }
    if "birthday" in row and row["birthday"]:
        row["birthday"] = str(row["birthday"])
    result = get_supabase_admin().table("family_members").insert(row).execute()
    return result.data[0]


@router.get("/{member_id}")
async def get_member(member_id: str, user: dict = Depends(get_current_user)):
    family_id = _require_family(user)
    result = (
        get_supabase_admin()
        .table("family_members")
        .select("*")
        .eq("id", member_id)
        .eq("family_id", family_id)   # ensures cross-family read is impossible
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Member not found")
    return result.data[0]


@router.patch("/{member_id}")
async def update_member(
    member_id: str,
    body: FamilyMemberUpdate,
    user: dict = Depends(get_current_user),
):
    family_id = _require_family(user)
    updates = body.model_dump(exclude_none=True)
    if "birthday" in updates and updates["birthday"]:
        updates["birthday"] = str(updates["birthday"])
    result = (
        get_supabase_admin()
        .table("family_members")
        .update(updates)
        .eq("id", member_id)
        .eq("family_id", family_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Member not found")
    return result.data[0]


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(member_id: str, user: dict = Depends(get_current_user)):
    """Soft-delete: sets active=False. No hard deletes in MVP."""
    family_id = _require_family(user)
    result = (
        get_supabase_admin()
        .table("family_members")
        .update({"active": False})
        .eq("id", member_id)
        .eq("family_id", family_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Member not found")
