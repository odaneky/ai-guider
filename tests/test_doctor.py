"""Tests for doctor and templates."""

from guider.doctor import run_doctor
from guider.mission.context_profiles import detect_profile, filter_unknowns
from guider.mission.templates import get_template


class TestDoctor:
    def test_run_doctor(self, isolated_home) -> None:
        ok, results = run_doctor()
        assert len(results) >= 5
        checks = [r["check"] for r in results]
        assert "Python version" in checks
        assert "Database" in checks


class TestContextProfiles:
    def test_personal_profile_detected(self) -> None:
        assert detect_profile("Build a couple journey website") == "personal"

    def test_filters_auth_for_personal(self) -> None:
        unknowns = ["Authentication", "Visual style and mood"]
        filtered = filter_unknowns(unknowns, "personal")
        assert "Authentication" not in filtered
        assert "Visual style and mood" in filtered


class TestTemplates:
    def test_personal_site_template(self) -> None:
        t = get_template("personal-site")
        assert t is not None
        assert t["context_profile"] == "personal"
