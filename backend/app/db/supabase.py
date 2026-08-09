from functools import lru_cache
from supabase import create_client, Client
from app.config import get_settings


@lru_cache
def get_supabase() -> Client:
    """Anon-key client — subject to RLS. Use for user-context queries."""
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_anon_key)


@lru_cache
def get_supabase_admin() -> Client:
    """Service-role client — bypasses RLS. Backend/jobs use only. Never expose."""
    s = get_settings()
    return create_client(s.supabase_url, s.supabase_service_role_key)
