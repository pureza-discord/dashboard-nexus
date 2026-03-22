"""Unit tests for scraper core: normalizer and geo_resolver."""

import pytest

from server.modules.scraper_service.core.normalizer import (
    dedup_fingerprint,
    deduplicate,
    normalize_lead,
    normalize_leads,
)
from server.modules.scraper_service.core.geo_resolver import (
    GeoValidationError,
    expand_geo,
    validate_geo,
)


# ---------------------------------------------------------------------------
# Normalizer Tests
# ---------------------------------------------------------------------------

class TestNormalizer:
    def test_normalize_lead_basic(self):
        raw = {
            "nome_empresa": "Test Company",
            "telefone": "+55 11 99999-0000",
            "email": "test@example.com",
            "site": "https://example.com",
        }
        result = normalize_lead(raw, nicho="tech", pais="Brasil", cidade="São Paulo", source="google_maps")
        assert result["empresa"] == "Test Company"
        assert result["telefone"] == "+55 11 99999-0000"
        assert result["email"] == "test@example.com"
        assert result["site"] == "https://example.com"
        assert result["nicho"] == "tech"
        assert result["pais"] == "Brasil"
        assert result["origem"] == "google_maps"

    def test_normalize_lead_fallback_to_empresa(self):
        raw = {"empresa": "Direct Company Name"}
        result = normalize_lead(raw, nicho="food", pais="USA", cidade=None, source="mock")
        assert result["empresa"] == "Direct Company Name"

    def test_normalize_lead_unknown_default(self):
        raw = {}
        result = normalize_lead(raw, nicho="test", pais="BR", cidade=None, source="mock")
        assert result["empresa"] == "Unknown"

    def test_normalize_leads_batch(self):
        raws = [
            {"nome_empresa": "Company A", "telefone": "111"},
            {"nome_empresa": "Company B", "telefone": "222"},
        ]
        results = normalize_leads(raws, nicho="test", pais="BR", cidade="SP", source="mock")
        assert len(results) == 2
        assert results[0]["empresa"] == "Company A"
        assert results[1]["empresa"] == "Company B"


class TestDeduplication:
    def test_dedup_fingerprint_deterministic(self):
        lead = {"empresa": "ACME Corp", "telefone": "+1-555-1234", "site": "https://acme.com"}
        fp1 = dedup_fingerprint(lead)
        fp2 = dedup_fingerprint(lead)
        assert fp1 == fp2

    def test_dedup_fingerprint_different_companies(self):
        lead1 = {"empresa": "ACME Corp"}
        lead2 = {"empresa": "Beta Inc"}
        assert dedup_fingerprint(lead1) != dedup_fingerprint(lead2)

    def test_deduplicate_removes_exact_duplicates(self):
        leads = [
            {"empresa": "ACME", "telefone": "111", "site": "https://acme.com"},
            {"empresa": "ACME", "telefone": "111", "site": "https://acme.com"},
            {"empresa": "Beta", "telefone": "222", "site": "https://beta.com"},
        ]
        result = deduplicate(leads)
        assert len(result) == 2

    def test_deduplicate_keeps_different_companies(self):
        leads = [
            {"empresa": "A", "telefone": "1"},
            {"empresa": "B", "telefone": "2"},
            {"empresa": "C", "telefone": "3"},
        ]
        result = deduplicate(leads)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Geo Resolver Tests
# ---------------------------------------------------------------------------

class TestGeoValidation:
    def test_validate_geo_national_scope(self):
        pais, cidade = validate_geo("Brasil", None)
        assert pais == "Brasil"
        assert cidade is None

    def test_validate_geo_valid_city(self):
        pais, cidade = validate_geo("Brasil", "São Paulo")
        assert pais == "Brasil"
        assert cidade == "São Paulo"

    def test_validate_geo_mismatched_city(self):
        with pytest.raises(GeoValidationError):
            validate_geo("Brasil", "lisboa")

    def test_validate_geo_empty_country_raises(self):
        with pytest.raises(ValueError):
            validate_geo("", "Lisboa")

    def test_validate_geo_unknown_city_passes(self):
        # Unknown cities are allowed through
        pais, cidade = validate_geo("Brasil", "Smalltown XYZ")
        assert pais == "Brasil"
        assert cidade == "Smalltown XYZ"

    def test_validate_geo_empty_city_becomes_national(self):
        pais, cidade = validate_geo("USA", "")
        assert cidade is None


class TestGeoExpansion:
    def test_expand_specific_city(self):
        result = expand_geo(None, "São Paulo", "Brasil")
        assert result == ["São Paulo"]

    def test_expand_region_nordeste(self):
        result = expand_geo("nordeste", None, "Brasil")
        assert len(result) > 5
        assert "Recife" in result
        assert "Salvador" in result

    def test_expand_state_sp(self):
        result = expand_geo("sp", None, "Brasil")
        assert "São Paulo" in result
        assert "Campinas" in result

    def test_expand_national_scope(self):
        result = expand_geo(None, None, "Brasil")
        assert result == [None]
