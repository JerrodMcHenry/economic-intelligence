"""Architectural guards for the MacroChipz Analyst (Increment #33).

Pure AST/source inspection -- no database, no network, no provider.

These are the tests that make the Analyst's safety claims true rather
than aspirational. The system instruction tells the model not to reach
for data it was not given; these tests make it impossible for the model
to reach anything at all, whatever the instruction says.

The central assertion is an import-graph fact: `app/services/analyst.py`
-- the only module that talks to a language model -- imports no
SQLAlchemy, no `app.db`, no repository, and receives no `Session`. So
"the LLM cannot touch canonical data" is checked structurally, not by
scanning prose for scary words.
"""

import ast
import inspect
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

MODEL_FACING = REPO_ROOT / "app/services/analyst.py"
CONTEXT_BUILDER = REPO_ROOT / "app/services/analyst_context.py"
PROMPT = REPO_ROOT / "app/services/analyst_prompt.py"
CONTRACTS = REPO_ROOT / "app/models/analyst.py"
ROUTE = REPO_ROOT / "app/api/analyst.py"

ANALYST_FILES = [CONTRACTS, CONTEXT_BUILDER, PROMPT, MODEL_FACING, ROUTE]


def _imported_module_names(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _forbids(imported: set[str], prefixes: tuple[str, ...]) -> list[str]:
    return [
        name
        for name in imported
        for prefix in prefixes
        if name == prefix or name.startswith(f"{prefix}.")
    ]


def _code_only(path: Path) -> str:
    """Source with docstrings removed, so a guard cannot be tripped by
    prose explaining the very thing it forbids."""
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
                if isinstance(node.body[0].value.value, str):
                    node.body.pop(0)
    return ast.unparse(tree)


def test_every_declared_file_exists():
    assert [str(p.relative_to(REPO_ROOT)) for p in ANALYST_FILES if not p.exists()] == []


# ---------------------------------------------------------------------
# The central boundary: the model-facing module cannot reach data
# ---------------------------------------------------------------------


def test_the_model_facing_module_cannot_reach_the_database():
    """`app/services/analyst.py` is the only module that contacts a
    language model. It imports nothing that could read or write
    canonical data, so no instruction, jailbreak, or model mistake can
    make it do so."""
    offenders = _forbids(
        _imported_module_names(MODEL_FACING),
        (
            "sqlalchemy",
            "app.db",
            "app.repositories",
            "app.domain",
            "app.clients",
            "app.services.inflation",
            "app.services.labor",
            "app.services.rates",
            "app.services.monitor_history",
            "app.services.replay",
            "app.services.release_processing",
            "app.services.maintenance",
            "app.services.analyst_context",
        ),
    )
    assert offenders == [], f"the model-facing module must not import {offenders}"


def test_the_model_facing_service_is_never_handed_a_session():
    """A `Session` parameter would undo the import guard above by
    handing the boundary a live connection at call time."""
    from app.services.analyst import AnalystService

    for name, method in inspect.getmembers(AnalystService, predicate=inspect.isfunction):
        if name.startswith("__"):
            continue
        annotations = inspect.signature(method).parameters
        for parameter in annotations.values():
            rendered = str(parameter.annotation)
            assert "Session" not in rendered, f"AnalystService.{name} accepts a Session ({parameter.name})"


def test_the_context_builder_never_imports_a_language_model():
    """Context assembly is ordinary deterministic code. It would behave
    identically if no model existed."""
    offenders = _forbids(_imported_module_names(CONTEXT_BUILDER), ("openai", "anthropic", "app.services.analyst"))
    assert offenders == []


def test_the_contracts_module_has_no_framework_provider_or_orm_dependency():
    offenders = _forbids(_imported_module_names(CONTRACTS), ("openai", "sqlalchemy", "fastapi", "app.db"))
    assert offenders == []


def test_the_prompt_module_is_text_only():
    """Instructions are data. A prompt module that imported services
    could start making decisions."""
    offenders = _forbids(
        _imported_module_names(PROMPT), ("openai", "sqlalchemy", "fastapi", "app.db", "app.repositories", "app.services")
    )
    assert offenders == []


# ---------------------------------------------------------------------
# No tools, no loop
# ---------------------------------------------------------------------


def test_no_tools_are_ever_offered_to_the_model():
    """ADR-014 kept tools read-only; #33 goes further and offers none at
    all. A tool the model cannot call cannot be called wrongly."""
    code = _code_only(MODEL_FACING)
    for fragment in ("tools=", "tool_choice", "function_call", "TOOL_SCHEMAS", "execute_tool"):
        assert fragment not in code, f"the Analyst must offer no tools; found {fragment!r}"


def test_exactly_one_model_generation_per_request():
    """Increment #9's autonomous orchestration failed its acceptance
    gate three times (ADR-018). One call, one answer -- and one call
    site, so a loop cannot be added without this failing."""
    code = _code_only(MODEL_FACING)
    assert code.count("responses.create") == 1
    assert "chat.completions" not in code


def test_no_loop_surrounds_the_provider_call():
    """A `while`/`for` containing the generation would be an autonomous
    round loop by another name."""
    tree = ast.parse(MODEL_FACING.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.While, ast.For, ast.AsyncFor)):
            body = ast.unparse(node)
            assert "responses.create" not in body, "the provider call must not sit inside a loop"


def test_no_round_or_iteration_budget_exists_because_there_are_no_rounds():
    code = _code_only(MODEL_FACING)
    for fragment in ("MAX_TOOL_ROUNDS", "MAX_DISCOVERY_ROUNDS", "round_count", "previous_response_id"):
        assert fragment not in code


def test_the_analyst_does_not_reuse_the_frozen_increment_8_tool_service():
    """`app.services.ai` is the frozen 2008-era tool-calling path. #33
    deliberately starts from the preserved principles, not from that
    code."""
    for path in ANALYST_FILES:
        offenders = _forbids(_imported_module_names(path), ("app.services.ai",))
        assert offenders == [], f"{path.name} imports the frozen AI tool service"


# ---------------------------------------------------------------------
# No canonical writes
# ---------------------------------------------------------------------


@pytest.mark.parametrize("path", ANALYST_FILES, ids=lambda p: p.name)
def test_no_analyst_file_can_write_canonical_data(path):
    code = _code_only(path)
    for fragment in (
        "session.add",
        "session.delete",
        ".commit(",
        ".flush(",
        "add_recorded_monitor_result",
        "add_observation_update",
        "add_check_run",
        "write_observation",
        "ObservationVersionWriter",
        "create_series",
    ):
        assert fragment not in code, f"{path.name} must not write canonical data; found {fragment!r}"


def test_the_route_exposes_only_the_two_contracted_endpoints():
    from app.api.analyst import router

    assert sorted((route.path, tuple(sorted(route.methods))) for route in router.routes) == [
        ("/analyst/availability", ("GET",)),
        ("/analyst/explain", ("POST",)),
    ]


def test_the_route_never_offers_a_mutating_verb_beyond_the_single_post():
    source = ROUTE.read_text()
    for verb in ("@router.put(", "@router.patch(", "@router.delete("):
        assert verb not in source
    assert source.count("@router.post(") == 1


# ---------------------------------------------------------------------
# The trust boundary: a browser names a context, never supplies one
# ---------------------------------------------------------------------


def test_context_types_are_an_allow_list():
    from app.models.analyst import AnalystContextType

    assert set(AnalystContextType.__args__) == {"INFLATION", "LABOR", "RATES", "MONITOR_HISTORY"}


def test_a_client_cannot_supply_canonical_state_or_evidence():
    """The request contract is the trust boundary. If it carried a
    state, a value, or an evidence list, a client could make the Analyst
    explain an economy that does not exist."""
    from app.models.analyst import AnalystContextRef, AnalystExplainRequest

    assert set(AnalystExplainRequest.model_fields) == {"context", "question"}
    assert set(AnalystContextRef.model_fields) == {"type", "recorded_result_id", "monitor"}

    forbidden = {"state", "canonical_state", "evidence", "metrics", "value", "methodology", "packet", "context_packet"}
    for model in (AnalystExplainRequest, AnalystContextRef):
        assert not (set(model.model_fields) & forbidden)


def test_the_request_contract_rejects_unknown_fields():
    """Silently ignoring an unrecognised field is exactly where someone
    would try to smuggle state in."""
    from pydantic import ValidationError

    from app.models.analyst import AnalystExplainRequest

    with pytest.raises(ValidationError):
        AnalystExplainRequest.model_validate(
            {"context": {"type": "INFLATION"}, "question": "why?", "canonical_state": "HYPERINFLATION"}
        )
    with pytest.raises(ValidationError):
        AnalystExplainRequest.model_validate(
            {"context": {"type": "INFLATION", "state": "HYPERINFLATION"}, "question": "why?"}
        )


def test_the_packet_is_versioned_and_the_prompt_is_versioned():
    from app.models.analyst import ANALYST_CONTEXT_VERSION
    from app.services.analyst_prompt import ANALYST_PROMPT_VERSION

    assert ANALYST_CONTEXT_VERSION == "analyst_context_v1"
    # v1.1: the live baseline showed `macrochipz_analyst_v1` dropping the
    # reconstructed-input disclosure on reassuring historical answers, so
    # the instruction changed and the version moved with it. The baseline
    # version is deliberately never reused for changed behaviour -- the
    # recorded baseline results belong to it.
    assert ANALYST_PROMPT_VERSION == "macrochipz_analyst_v1.1"


def test_the_response_schema_is_static_not_rebuilt_per_request():
    """ADR-018's lesson: a dynamically shaped schema is a hint the model
    violated ~60% of the time. The schema stays fixed; validation is the
    enforcement."""
    from app.services import analyst_prompt

    assert isinstance(analyst_prompt.ANALYST_RESPONSE_SCHEMA, dict)
    code = _code_only(PROMPT)
    assert "def build_response_schema" not in code
    assert "enum" not in code, "evidence ids must not be injected into the schema as an enum"


# ---------------------------------------------------------------------
# Availability: the Analyst is optional
# ---------------------------------------------------------------------


def test_availability_is_a_plain_boolean_that_leaks_no_configuration(monkeypatch):
    from app.core.config import settings
    from app.models.analyst import AnalystAvailability

    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "openai_model", None)

    from app.api.analyst import get_analyst_availability

    result = get_analyst_availability()
    assert isinstance(result, AnalystAvailability)
    assert result.available is False
    assert result.reason == "NOT_CONFIGURED"
    # The reason vocabulary must not grow into a configuration report.
    assert set(AnalystAvailability.model_fields) == {"available", "reason"}


def test_no_secret_is_ever_placed_in_a_log_or_a_packet():
    """The key may only appear where the client is constructed."""
    for path in ANALYST_FILES:
        code = _code_only(path)
        if path == MODEL_FACING:
            assert code.count("openai_api_key") <= 2, "the key belongs at client construction only"
        else:
            assert "openai_api_key" not in code or path == ROUTE

    logging_block = _code_only(MODEL_FACING)
    start = logging_block.find("logger.info")
    extra = logging_block[start:]
    for forbidden in ("api_key", "question=", "answer=", "context_json", "raw_text"):
        assert forbidden not in extra, f"operational logging must not carry {forbidden!r}"
