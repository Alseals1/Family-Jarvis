from app.db.supabase import get_supabase_admin


def get_family_id_for_user(user_id: str) -> str | None:
    """Return the family_id for a user, or None if not yet onboarded."""
    admin = get_supabase_admin()
    result = (
        admin.table("family_members")
        .select("family_id")
        .eq("user_id", user_id)
        .eq("active", True)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]["family_id"]
    return None
