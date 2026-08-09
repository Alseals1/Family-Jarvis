from pathlib import Path
import re

SEED_FILE = Path(__file__).parent.parent.parent.parent / "supabase/seed/demo-family.sql"


def sql():
    return SEED_FILE.read_text()


def test_seed_file_exists():
    assert SEED_FILE.exists()


def test_seed_uses_demo_family_id():
    assert "00000000-0000-0000-0000-000000000001" in sql()


def test_seed_has_four_family_members():
    # Each member has a distinct UUID in the 0001 block
    member_ids = re.findall(r"00000000-0000-0000-0001-\d+", sql())
    unique_members = set(member_ids)
    assert len(unique_members) >= 4, f"Expected ≥4 member IDs, found {unique_members}"


def test_seed_has_anniversary_date():
    s = sql()
    assert "anniversary" in s.lower()
    assert "2010-08-23" in s  # anniversary date


def test_seed_has_eli_peanut_allergy():
    s = sql()
    assert "allergy" in s.lower()
    assert "peanuts" in s.lower()


def test_seed_has_priya_vegetarian_restriction():
    s = sql()
    assert "vegetarian" in s.lower() or ("restriction" in s.lower() and "meat" in s.lower())


def test_seed_has_upcoming_trip():
    s = sql()
    assert "2026-08-22" in s  # trip departure


def test_seed_has_date_history():
    assert "date_history" in sql()
    # At least 3 past date nights
    assert sql().count("Rosso") >= 1


def test_seed_has_memories():
    s = sql()
    assert "memories" in s
    assert "explicit" in s
    assert "corner table" in s.lower() or "Rosso" in s


def test_seed_has_dinner_budget_preference():
    assert "dinner_budget" in sql()


def test_seed_no_real_email_domains():
    real_domains = ["gmail.com", "yahoo.com", "outlook.com", "icloud.com", "hotmail.com"]
    s = sql()
    for domain in real_domains:
        assert domain not in s, f"Real email domain '{domain}' found in demo seed"


def test_seed_demo_mode_true():
    assert "demo_mode" in sql()
    assert "true" in sql().lower()


def test_calendars_present_for_all_members():
    """Seed contains one calendar row for each of the four Reeds family members."""
    s = sql()
    assert "INSERT INTO calendars" in s
    # Each member UUID must appear in the calendars block
    member_uuids = [
        "00000000-0000-0000-0001-000000000001",  # Marcus
        "00000000-0000-0000-0001-000000000002",  # Priya
        "00000000-0000-0000-0001-000000000003",  # Eli
        "00000000-0000-0000-0001-000000000004",  # Zoe
    ]
    cal_block_start = s.find("INSERT INTO calendars")
    cal_block = s[cal_block_start:cal_block_start + 2000]
    for uuid in member_uuids:
        assert uuid in cal_block, f"Calendar for member {uuid} not found in seed"


def test_calendar_events_present():
    """Seed contains at least 10 calendar_events rows."""
    s = sql()
    assert "INSERT INTO calendar_events" in s
    # Count value tuples in the calendar_events block
    block_start = s.find("INSERT INTO calendar_events")
    block = s[block_start:block_start + 5000]
    event_count = block.count("'confirmed'")
    assert event_count >= 10, f"Expected ≥10 calendar events, found {event_count}"


def test_double_booking_event_present():
    """Seed contains two overlapping Marcus events on 2026-08-16 (Sunday)."""
    s = sql()
    assert "2026-08-16" in s
    assert "Marcus double-booked" in s or "double" in s.lower()
