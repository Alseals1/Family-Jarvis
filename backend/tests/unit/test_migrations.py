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
