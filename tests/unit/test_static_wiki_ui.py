from pathlib import Path


def test_static_wiki_ui_is_evidence_shell_not_stub_page():
    root = Path(__file__).resolve().parents[2]
    html = (root / "src/static/wiki/index.html").read_text(encoding="utf-8")
    lower = html.lower()

    assert "recent pages stub" not in lower
    assert "// stub" not in lower
    assert "mock" not in lower
    assert "todo" not in lower
    assert "Evidence Bundle" in html
    assert "Killer Demo" in html
    assert "Launch Room" in html
    assert "Wiki API not mounted" in html
    assert "fabricated pages" in html
