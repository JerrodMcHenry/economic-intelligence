"""Visual evidence for intelligence objects (Increment #40C).

`TimeSeriesVisualEvidence` exists so a surface can SHOW the movement an
object describes without going and fetching the data itself. These
tests hold the contract to the properties that make that safe: bounded,
selection-only, canonical identity and units, and honest about a short
record.

Pure-domain and pure-contract only -- no database, no network.
"""

from datetime import date, timedelta

import pytest

from app.domain.rates import RateObservation, recent_session_observations
from app.models.intelligence import (
    INTELLIGENCE_CONTRACT_VERSION,
    RatesMovementIntelligence,
    RatesMovementPayload,
    TimeSeriesVisualEvidence,
    VisualEvidencePoint,
)


#: Day 1 is 2026-01-01; `missing` is given in the same day numbering, so
#: a test can say "the provider published nothing on day 4".
_DAY_ONE = date(2026, 1, 1)


def _on(day: int) -> date:
    return _DAY_ONE + timedelta(days=day - 1)


def series(days: int, *, start: int = 1, missing: set[int] | None = None) -> list[RateObservation]:
    missing = missing or set()
    return [
        RateObservation(
            observation_date=_on(day),
            value=None if day in missing else 4.0 + day / 100,
        )
        for day in range(start, start + days)
    ]


class TestWindowSelection:
    def test_returns_at_most_the_requested_number_of_sessions(self):
        selected = recent_session_observations(series(200), 63, _on(200))
        assert len(selected) == 63

    def test_returns_the_LATEST_sessions_not_the_earliest(self):
        selected = recent_session_observations(series(10), 3, date(2026, 1, 10))
        assert [obs.observation_date.day for obs in selected] == [8, 9, 10]

    def test_is_chronologically_ascending(self):
        selected = recent_session_observations(series(30), 63, _on(30))
        assert selected == sorted(selected, key=lambda obs: obs.observation_date)

    def test_never_includes_an_observation_after_the_effective_date(self):
        selected = recent_session_observations(series(10), 63, date(2026, 1, 6))
        assert max(obs.observation_date for obs in selected) == date(2026, 1, 6)

    def test_ends_exactly_at_the_effective_date_when_one_exists(self):
        selected = recent_session_observations(series(10), 63, date(2026, 1, 7))
        assert selected[-1].observation_date == date(2026, 1, 7)

    def test_input_order_is_not_trusted(self):
        shuffled = list(reversed(series(10)))
        assert recent_session_observations(shuffled, 3, date(2026, 1, 10)) == recent_session_observations(
            series(10), 3, date(2026, 1, 10)
        )

    def test_is_deterministic(self):
        observations = series(100)
        first = recent_session_observations(observations, 63, _on(100))
        second = recent_session_observations(observations, 63, _on(100))
        assert first == second

    def test_rejects_a_nonsensical_window(self):
        with pytest.raises(ValueError):
            recent_session_observations(series(10), 0, date(2026, 1, 10))


class TestHonestyAboutGaps:
    def test_drops_unpublished_values_rather_than_interpolating(self):
        selected = recent_session_observations(series(10, missing={4, 5}), 63, date(2026, 1, 10))
        days = [obs.observation_date.day for obs in selected]
        assert 4 not in days and 5 not in days
        # The surrounding values are untouched -- nothing was smoothed
        # across the gap, and no value was carried forward into it.
        assert [obs.value for obs in selected] == [4.0 + d / 100 for d in days]

    def test_a_short_record_returns_what_exists_rather_than_padding(self):
        selected = recent_session_observations(series(5), 63, date(2026, 1, 5))
        assert len(selected) == 5

    def test_no_usable_history_is_empty_not_an_error(self):
        assert recent_session_observations(series(5, missing={1, 2, 3, 4, 5}), 63, date(2026, 1, 5)) == []


class TestContractShape:
    def build(self, points: int = 63) -> TimeSeriesVisualEvidence:
        return TimeSeriesVisualEvidence(
            concept_id="UST_NOMINAL_10Y",
            unit="Percent",
            requested_sessions=63,
            available_sessions=points,
            points=[
                VisualEvidencePoint(observation_date=date(2026, 1, 1), value=4.51)
                for _ in range(points)
            ],
        )

    def test_carries_source_neutral_concept_identity_not_a_provider_series_id(self):
        evidence = self.build()
        # #38: the concept id, never Treasury's own field name.
        assert evidence.concept_id == "UST_NOMINAL_10Y"
        assert "TREASURY" not in evidence.model_dump_json()

    def test_carries_the_canonical_unit(self):
        assert self.build().unit == "Percent"

    def test_reports_the_real_count_beside_the_requested_one(self):
        short = self.build(points=12)
        assert short.requested_sessions == 63
        assert short.available_sessions == 12

    def test_carries_no_presentation_configuration_whatsoever(self):
        payload = self.build().model_dump()
        forbidden = {
            "color", "colour", "width", "height", "pixels", "axis", "ticks",
            "stroke", "fill", "theme", "component", "chart", "style", "label",
        }
        assert forbidden.isdisjoint(payload.keys())
        assert forbidden.isdisjoint(payload["points"][0].keys())

    def test_a_point_carries_only_a_date_and_a_value(self):
        assert set(VisualEvidencePoint(observation_date=date(2026, 1, 1), value=4.5).model_dump()) == {
            "observation_date",
            "value",
        }


class TestAdditiveVersioning:
    """The field is optional, so an `intelligence_v1` consumer written
    before #40C still parses every object. That is why the contract
    version is deliberately NOT bumped."""

    def payload(self, **overrides) -> RatesMovementPayload:
        base = dict(
            series_title="10-Year Treasury Par Yield (Nominal)",
            latest_value=5.01,
            changes=[],
            historical_percentile_rank=None,
            historical_magnitude_percentile_rank=None,
            historical_observation_count=0,
        )
        base.update(overrides)
        return RatesMovementPayload(**base)

    def test_payload_is_valid_without_visual_evidence(self):
        assert self.payload().visual_evidence is None

    def test_contract_version_is_unchanged(self):
        assert INTELLIGENCE_CONTRACT_VERSION == "intelligence_v1"

    def test_an_object_carrying_visual_evidence_still_declares_v1(self):
        obj = RatesMovementIntelligence(
            id="rates:UST_NOMINAL_10Y:2026-09-18",
            world="rates",
            concepts=["UST_NOMINAL_10Y"],
            effective_period=date(2026, 9, 18),
            recorded_at="2026-09-20T00:00:00Z",
            published_at=None,
            knowledge_basis="OBSERVED",
            basis="METHODOLOGY_DERIVED",
            methodology=None,
            evidence=[],
            relations=[],
            limitations=[],
            payload=self.payload(
                visual_evidence=TimeSeriesVisualEvidence(
                    concept_id="UST_NOMINAL_10Y",
                    unit="Percent",
                    requested_sessions=63,
                    available_sessions=1,
                    points=[VisualEvidencePoint(observation_date=date(2026, 9, 18), value=5.01)],
                )
            ),
        )
        assert obj.contract_version == "intelligence_v1"


class TestNoProviderDependency:
    """Generate-on-read must never reach a provider (#40C).

    Checked STATICALLY, by parsing imports, rather than by mocking a
    client at runtime: a module that cannot import an HTTP client or a
    provider client cannot call one, on any code path, including ones
    no test exercises. This is the same technique
    `tests/integration/test_transaction_and_safety.py` uses, and it is
    why this test deliberately does NOT import `httpx` itself.
    """

    #: Everything the RATES_MOVEMENT read path touches to produce
    #: visual evidence.
    READ_PATH = (
        "app/domain/rates.py",
        "app/services/rates.py",
        "app/services/intelligence/builder.py",
        "app/repositories/rates_repository.py",
        "app/models/intelligence.py",
    )

    FORBIDDEN_PREFIXES = ("httpx", "requests", "urllib.request", "aiohttp", "app.clients", "openai", "anthropic")

    def imported_modules(self, relative_path: str) -> set[str]:
        import ast
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        tree = ast.parse((root / relative_path).read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names.add(node.module)
        return names

    def test_the_read_path_imports_no_http_or_provider_client(self):
        violations = []
        for relative_path in self.READ_PATH:
            for module in self.imported_modules(relative_path):
                if any(module == p or module.startswith(p + ".") for p in self.FORBIDDEN_PREFIXES):
                    violations.append(f"{relative_path}: imports '{module}'")
        assert violations == [], "the intelligence read path can reach a provider:\n" + "\n".join(violations)

    def test_the_rates_service_reads_only_through_its_repository(self):
        imports = self.imported_modules("app/services/rates.py")
        assert "app.repositories.rates_repository" in imports
        assert not any(name.startswith("app.services.rates_ingestion") for name in imports), (
            "the read path must not import the ingestion service"
        )

    def test_the_guard_covers_the_module_that_actually_builds_the_evidence(self):
        """Fails loudly if the builder is renamed or moved, rather than
        silently guarding nothing."""
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        for relative_path in self.READ_PATH:
            assert (root / relative_path).exists(), f"{relative_path} no longer exists"
        assert "_rates_visual_evidence" in (root / "app/services/intelligence/builder.py").read_text()
