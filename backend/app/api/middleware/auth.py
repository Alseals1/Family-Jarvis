import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.db.supabase import get_supabase_admin
from app.db.queries.family import get_family_id_for_user

logger = logging.getLogger(__name__)
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
    # Step 1: validate the JWT — this is the only thing that produces 401
    try:
        admin = get_supabase_admin()
        result = admin.auth.get_user(token)
        if result is None or result.user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("JWT validation failed: %s", e)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    # Step 2: look up family membership — DB errors here are not auth errors
    user_id = result.user.id
    family_id = None
    try:
        family_id = get_family_id_for_user(user_id)
    except Exception as e:
        logger.warning("family_id lookup failed for user %s: %s", user_id, e)
        # User is authenticated but not yet onboarded — family_id stays None

    return {
        "user_id": user_id,
        "email": result.user.email,
        "family_id": family_id,
    }
