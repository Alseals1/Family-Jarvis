from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.db.supabase import get_supabase_admin
from app.db.queries.family import get_family_id_for_user

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Verifies the Supabase JWT and returns the authenticated user.
    family_id is looked up from family_members — null if not yet onboarded.
    family_id always comes from DB, never from the request body.
    """
    token = credentials.credentials
    try:
        admin = get_supabase_admin()
        result = admin.auth.get_user(token)
        if result is None or result.user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        user_id = result.user.id
        family_id = get_family_id_for_user(user_id)

        return {
            "user_id": user_id,
            "email": result.user.email,
            "family_id": family_id,  # None if not onboarded
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
