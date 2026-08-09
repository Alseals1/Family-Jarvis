from pathlib import Path
import re

MIGRATIONS_DIR = Path(__file__).parent.parent.parent.parent / "supabase/migrations"
SEED_DIR = Path(__file__).parent.parent.parent.parent / "supabase/seed"


def migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def test_migration_files_exist():
    files = migration_files()
    assert len(files) >= 4, f"Expected ≥4 migration files, found {len(files)}"


def test_migration_files_are_sequentially_numbered():
    files = migration_files()
    for i, f in enumerate(files, start=1):
        assert f.name.startswith(f"{i:03d}_"), f"Migration {f.name} not in sequence at position {i}"


def test_families_table_defined():
    sql = (MIGRATIONS_DIR / "001_create_families.sql").read_text()
    assert "CREATE TABLE families" in sql
    assert "family_id" not in sql  # families has no parent family_id


def test_family_members_references_families():
    sql = (MIGRATIONS_DIR / "002_create_family_members.sql").read_text()
    assert "CREATE TABLE family_members" in sql
    assert "REFERENCES families" in sql


def test_rls_enabled_for_core_tables():
    sql = (MIGRATIONS_DIR / "003_enable_rls.sql").read_text()
    assert "ALTER TABLE families" in sql and "ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE family_members" in sql and "ROW LEVEL SECURITY" in sql
    # Must include auth.uid() checks — not just blanket access
    assert "auth.uid()" in sql


def test_conversations_schema_exists():
    sql = (MIGRATIONS_DIR / "004_create_conversations.sql").read_text()
    assert "CREATE TABLE conversations" in sql
    assert "CREATE TABLE conversation_turns" in sql
    assert "ROW LEVEL SECURITY" in sql


def test_demo_seed_uses_only_demo_data():
    sql = (SEED_DIR / "demo-family.sql").read_text()
    assert "demo_mode" in sql
    assert "true" in sql
    # Must not have real-looking email domains
    real_domains = ["gmail.com", "yahoo.com", "outlook.com", "icloud.com"]
    for domain in real_domains:
        assert domain not in sql, f"Real email domain {domain} found in seed data"


def test_rls_does_not_grant_cross_family_access():
    sql = (MIGRATIONS_DIR / "003_enable_rls.sql").read_text()
    # All SELECT policies must scope to the user's own family
    policies = re.findall(r"CREATE POLICY.*?;", sql, re.DOTALL)
    for policy in policies:
        if "FOR SELECT" in policy:
            assert "auth.uid()" in policy, f"SELECT policy missing auth.uid() check:\n{policy}"


# ── Phase 2 migration tests ────────────────────────────────────────────────

PHASE2_TABLES = {
    "005": ("calendars", ["family_id", "family_member_id", "provider", "access_token_enc"]),
    "006": ("calendar_events", ["family_id", "calendar_id", "start_time", "end_time"]),
    "007": ("important_dates", ["family_id", "date_type", "recurs_yearly", "lead_days"]),
    "008": ("preferences", ["food_preferences"]),
    "009": ("memories", ["confirmed_to_user", "source"]),
    "010": ("trips", ["departure_date", "travelers"]),
    "011": ("relationships", ["date_history"]),
    "012": ("notifications", ["trigger_date", "delivered"]),
    "013": ("agent_tasks", ["task_type", "agent", "status"]),
}


def test_phase2_migration_files_exist():
    for num in range(5, 15):
        matches = list(MIGRATIONS_DIR.glob(f"{num:03d}_*.sql"))
        assert matches, f"Missing migration {num:03d}_*.sql"


def test_phase2_migration_count():
    files = migration_files()
    assert len(files) >= 14, f"Expected ≥14 migration files, found {len(files)}"


def test_phase2_tables_contain_expected_columns():
    for num, (primary_table, expected_tokens) in PHASE2_TABLES.items():
        path = next(MIGRATIONS_DIR.glob(f"{num}_*.sql"))
        sql = path.read_text()
        assert primary_table in sql, f"{path.name}: expected table/keyword '{primary_table}'"
        for token in expected_tokens:
            assert token in sql, f"{path.name}: expected column/token '{token}'"


def test_rls_phase2_enables_rls_on_all_tables():
    sql = (MIGRATIONS_DIR / "014_rls_phase2.sql").read_text()
    phase2_tables = [
        "calendars", "calendar_events", "important_dates",
        "preferences", "food_preferences", "memories",
        "trips", "relationships", "date_history",
        "notifications", "agent_tasks",
    ]
    for table in phase2_tables:
        assert f"ALTER TABLE {table}" in sql, f"RLS not enabled for {table}"
        assert "ROW LEVEL SECURITY" in sql


def test_rls_phase2_all_select_policies_check_auth_uid():
    sql = (MIGRATIONS_DIR / "014_rls_phase2.sql").read_text()
    policies = re.findall(r"CREATE POLICY.*?;", sql, re.DOTALL)
    assert len(policies) >= 11, f"Expected ≥11 RLS policies, found {len(policies)}"
    for policy in policies:
        if "FOR SELECT" in policy:
            assert "auth.uid()" in policy, f"SELECT policy missing auth.uid():\n{policy}"


def test_oauth_tokens_not_in_rls_select_policies():
    """OAuth token columns must never appear in SELECT policies — write-only via service role."""
    sql = (MIGRATIONS_DIR / "014_rls_phase2.sql").read_text()
    policies = re.findall(r"CREATE POLICY.*?;", sql, re.DOTALL)
    for policy in policies:
        if "FOR SELECT" in policy:
            assert "access_token_enc"  not in policy, "access_token_enc exposed in SELECT policy"
            assert "refresh_token_enc" not in policy, "refresh_token_enc exposed in SELECT policy"


def test_memories_source_constrained_to_explicit():
    sql = (MIGRATIONS_DIR / "009_create_memories.sql").read_text()
    assert "source = 'explicit'" in sql, "memories.source must be constrained to 'explicit' only"


def test_calendar_events_has_composite_time_index():
    sql = (MIGRATIONS_DIR / "006_create_calendar_events.sql").read_text()
    assert "start_time" in sql and "end_time" in sql
    assert "CREATE INDEX" in sql
