from pathlib import Path

BACKEND_ROOT = Path(__file__).parent.parent.parent
REPO_ROOT = BACKEND_ROOT.parent

APP_PACKAGES = [
    "app",
    "app/api",
    "app/api/routes",
    "app/api/middleware",
    "app/agents",
    "app/providers",
    "app/providers/llm",
    "app/providers/calendar",
    "app/providers/voice",
    "app/db",
    "app/db/queries",
    "app/logic",
    "app/jobs",
    "app/models",
]


def test_app_packages_have_init():
    for pkg in APP_PACKAGES:
        init = BACKEND_ROOT / pkg / "__init__.py"
        assert init.exists(), f"Missing __init__.py in backend/{pkg}/"


def test_test_directories_exist():
    assert (BACKEND_ROOT / "tests/unit").is_dir()
    assert (BACKEND_ROOT / "tests/integration").is_dir()


def test_supabase_directories_exist():
    assert (REPO_ROOT / "supabase/migrations").is_dir()
    assert (REPO_ROOT / "supabase/seed").is_dir()
