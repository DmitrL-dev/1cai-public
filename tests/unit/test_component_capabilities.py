"""Components report support explicitly and refuse before side effects (PORT-GATE-01)."""
import pytest

from rentgen_core import capabilities, gui

EXPECTED = {
    "win32": {"local_gui": False, "observer_service": True, "native_execution": True, "companion_editor": True},
    "linux": {"local_gui": True, "observer_service": False, "native_execution": False, "companion_editor": False},
    "darwin": {"local_gui": False, "observer_service": False, "native_execution": False, "companion_editor": False},
}


@pytest.mark.parametrize("platform", sorted(EXPECTED))
def test_component_matrix_is_explicit_with_reasons(monkeypatch, platform):
    monkeypatch.setattr(capabilities, "_platform", platform)
    components = capabilities.capability_report()["components"]
    assert {name: row["supported"] for name, row in components.items()} == EXPECTED[platform]
    for row in components.values():
        assert (row["reason"] is None) is row["supported"]
    assert capabilities.component_status("unreviewed") == {
        "supported": False,
        "reason": "No reviewed component contract exists",
    }


@pytest.mark.parametrize("platform", ["win32", "darwin"])
def test_local_gui_refuses_before_reading_inputs(monkeypatch, tmp_path, platform):
    monkeypatch.setattr(capabilities, "_platform", platform)
    missing = tmp_path / "absent"
    with pytest.raises(SystemExit) as error:
        gui.main([
            "--registry", str(missing / "registry.sqlite3"),
            "--identity-profile", str(missing / "identity.json"),
            "--input-core", str(missing / "rentgen-input-core"),
            "--project", "00000000-0000-4000-8000-000000000001",
            "--input-core-sha256", "a" * 64,
        ])
    assert error.value.code == 2
    assert not missing.exists()
