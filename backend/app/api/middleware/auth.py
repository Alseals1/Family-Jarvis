from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.db.supabase import get_supabase_admin

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Verifies the Supabase JWT and returns the authenticated user.
    family_id is NOT extracted here — it requires a DB lookup added in Phase 2.
    """
    token = credentials.credentials
    try:
        admin = get_supabase_admin()
        result = admin.auth.get_user(token)
        if result is None or result.user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return {"user_id": result.user.id, "email": result.user.email}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
