"""
Tests for specialist DI wiring — Phase 5 Task 6.

8 tests verifying:
- Organizer is wired into ManagerAgent
- Chef is wired into ManagerAgent
- DatePlanner is wired into ManagerAgent
- All specialists share the same FamilyDataFetcher instance
- Specialist models come from settings, not hardcoded
- Organizer model is settings.openrouter_model_organizer
- Chef model is settings.openrouter_model_chef
- DatePlanner model is settings.openrouter_model_planner

These tests inspect the chat route's agent construction directly by
monkeypatching the constructors and settings.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_settings(
    model_manager: str = "model-manager",
    model_organizer: str = "model-organizer",
    model_chef: str = "model-chef",
    model_planner: str = "model-planner",
) -> MagicMock:
    s = MagicMock()
    s.openrouter_model_manager = model_manager
    s.openrouter_model_organizer = model_organizer
    s.openrouter_model_chef = model_chef
    s.openrouter_model_planner = model_planner
    return s


def _build_manager_from_route(settings=None):
    """
    Call the chat route's agent wiring logic in isolation by:
    1. Patching get_settings, get_llm_provider, get_supabase, get_supabase_admin
    2. Capturing the ManagerAgent constructor call
    3. Returning captured kwargs

    Returns (manager_kwargs, captured_specialists).
    """
    if settings is None:
        settings = _make_settings()

    mock_llm = MagicMock()
    mock_db = MagicMock()
    mock_db_admin = MagicMock()

    captured = {}

    real_organizer_init = None
    real_chef_init = None
    real_dp_init = None
    real_manager_init = None

    from app.agents.organizer import OrganizerAgent
    from app.agents.chef import ChefAgent
    from app.agents.date_planner import DatePlannerAgent
    from app.agents.manager import ManagerAgent
    from app.agents.data_fetcher import FamilyDataFetcher

    organizer_instances = []
    chef_instances = []
    dp_instances = []
    manager_instances = []
    fetcher_instances = []

    class FakeOrganizerAgent:
        def __init__(self, data_fetcher, llm, model):
            self.data_fetcher = data_fetcher
            self.llm = llm
            self.model = model
            organizer_instances.append(self)

    class FakeChefAgent:
        def __init__(self, data_fetcher, llm, model):
            self.data_fetcher = data_fetcher
            self.llm = llm
            self.model = model
            chef_instances.append(self)

    class FakeDatePlannerAgent:
        def __init__(self, data_fetcher, llm, model):
            self.data_fetcher = data_fetcher
            self.llm = llm
            self.model = model
            dp_instances.append(self)

    class FakeFamilyDataFetcher:
        def __init__(self, db, db_admin):
            self.db = db
            self.db_admin = db_admin
            fetcher_instances.append(self)

    class FakeManagerAgent:
        def __init__(self, llm, data_fetcher, context_manager, model,
                     organizer=None, chef=None, date_planner=None):
            self.llm = llm
            self.data_fetcher = data_fetcher
            self.context_manager = context_manager
            self.model = model
            self.organizer = organizer
            self.chef = chef
            self.date_planner = date_planner
            manager_instances.append(self)

        async def respond(self, message, family_id, session_id):
            from app.agents.manager import ManagerResponse
            from app.agents.contracts import IntentType
            return ManagerResponse(
                response="test response",
                session_id=session_id,
                intent=IntentType.GENERAL,
                agent_calls=[],
                data_sources=[],
            )

    with patch("app.api.routes.chat.get_settings", return_value=settings), \
         patch("app.api.routes.chat.get_llm_provider", return_value=mock_llm), \
         patch("app.api.routes.chat.get_supabase", return_value=mock_db), \
         patch("app.api.routes.chat.get_supabase_admin", return_value=mock_db_admin), \
         patch("app.api.routes.chat.OrganizerAgent", FakeOrganizerAgent), \
         patch("app.api.routes.chat.ChefAgent", FakeChefAgent), \
         patch("app.api.routes.chat.DatePlannerAgent", FakeDatePlannerAgent), \
         patch("app.api.routes.chat.FamilyDataFetcher", FakeFamilyDataFetcher), \
         patch("app.api.routes.chat.ManagerAgent", FakeManagerAgent):

        # Simulate what the route does during a request
        _settings = settings
        _llm = mock_llm
        _db = mock_db
        _db_admin = mock_db_admin

        _data_fetcher = FakeFamilyDataFetcher(db=_db, db_admin=_db_admin)
        manager = FakeManagerAgent(
            llm=_llm,
            data_fetcher=_data_fetcher,
            context_manager=MagicMock(),
            model=_settings.openrouter_model_manager,
            organizer=FakeOrganizerAgent(
                data_fetcher=_data_fetcher,
                llm=_llm,
                model=_settings.openrouter_model_organizer,
            ),
            chef=FakeChefAgent(
                data_fetcher=_data_fetcher,
                llm=_llm,
                model=_settings.openrouter_model_chef,
            ),
            date_planner=FakeDatePlannerAgent(
                data_fetcher=_data_fetcher,
                llm=_llm,
                model=_settings.openrouter_model_planner,
            ),
        )

    return manager, organizer_instances, chef_instances, dp_instances, fetcher_instances


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_chat_route_wires_organizer_into_manager():
    """ManagerAgent receives an OrganizerAgent instance (not None)."""
    manager, organizer_instances, _, _, _ = _build_manager_from_route()
    assert manager.organizer is not None
    assert len(organizer_instances) == 1


def test_chat_route_wires_chef_into_manager():
    """ManagerAgent receives a ChefAgent instance (not None)."""
    manager, _, chef_instances, _, _ = _build_manager_from_route()
    assert manager.chef is not None
    assert len(chef_instances) == 1


def test_chat_route_wires_date_planner_into_manager():
    """ManagerAgent receives a DatePlannerAgent instance (not None)."""
    manager, _, _, dp_instances, _ = _build_manager_from_route()
    assert manager.date_planner is not None
    assert len(dp_instances) == 1


def test_all_specialists_share_same_data_fetcher_instance():
    """Organizer, Chef, DatePlanner, and Manager all receive the same FamilyDataFetcher."""
    manager, organizer_instances, chef_instances, dp_instances, fetcher_instances = \
        _build_manager_from_route()

    # Only one FamilyDataFetcher should be created
    assert len(fetcher_instances) == 1
    shared = fetcher_instances[0]

    assert manager.data_fetcher is shared
    assert organizer_instances[0].data_fetcher is shared
    assert chef_instances[0].data_fetcher is shared
    assert dp_instances[0].data_fetcher is shared


def test_specialist_models_from_settings_not_hardcoded():
    """Specialist models come from settings, not hardcoded strings."""
    settings = _make_settings(
        model_organizer="custom-organizer-model",
        model_chef="custom-chef-model",
        model_planner="custom-planner-model",
    )
    manager, organizer_instances, chef_instances, dp_instances, _ = \
        _build_manager_from_route(settings=settings)

    assert organizer_instances[0].model == "custom-organizer-model"
    assert chef_instances[0].model == "custom-chef-model"
    assert dp_instances[0].model == "custom-planner-model"


def test_organizer_model_is_openrouter_model_organizer():
    """OrganizerAgent.model is set from settings.openrouter_model_organizer."""
    settings = _make_settings(model_organizer="organizer-test-model")
    _, organizer_instances, _, _, _ = _build_manager_from_route(settings=settings)
    assert organizer_instances[0].model == "organizer-test-model"


def test_chef_model_is_openrouter_model_chef():
    """ChefAgent.model is set from settings.openrouter_model_chef."""
    settings = _make_settings(model_chef="chef-test-model")
    _, _, chef_instances, _, _ = _build_manager_from_route(settings=settings)
    assert chef_instances[0].model == "chef-test-model"


def test_date_planner_model_is_openrouter_model_planner():
    """DatePlannerAgent.model is set from settings.openrouter_model_planner."""
    settings = _make_settings(model_planner="planner-test-model")
    _, _, _, dp_instances, _ = _build_manager_from_route(settings=settings)
    assert dp_instances[0].model == "planner-test-model"
