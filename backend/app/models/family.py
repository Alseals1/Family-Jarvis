from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional


class FamilyMemberCreate(BaseModel):
    name: str
    relationship: str
    birthday: Optional[date] = None
    email: Optional[str] = None


class FamilyMemberUpdate(BaseModel):
    name: Optional[str] = None
    relationship: Optional[str] = None
    birthday: Optional[date] = None
    email: Optional[str] = None
    active: Optional[bool] = None


class FamilyMemberResponse(BaseModel):
    id: str
    family_id: str
    name: str
    relationship: str
    birthday: Optional[date] = None
    email: Optional[str] = None
    active: bool
    created_at: datetime
