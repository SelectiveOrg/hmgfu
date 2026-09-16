"""95.78 D5 — the weather widget never fetched any weather.

Live session 523b0720: asked for a widget that shows the weather, the agent wrote a page whose value is
a constant, `temp: 18, // Converting 64F to approx 18C`, under a comment reading "In production, you'd
use: await fetch('https://api.openweathermap.org/...appid=YOUR_API_KEY')". It then reported "I've
finished building your weather widget". Writing the file IS real work, so the say-do gate had nothing
to catch, and the user found out by comparing it with their phone.

Invariant: an artefact shipped with its own placeholders left in is disclosed as unfinished. The
detection reads the text that was written, and the disclosure is appended by the harness, so it does
not depend on the model choosing to mention it.

Tradeoff, stated: the markers are a short list of code idioms (TODO, mock, YOUR_API_KEY, "in
production"…), documented in the roadmap and visible in the module. The alternative — running the
artefact to see whether it does what it claims — is a much larger change, and this one catches the case
that actually happened without touching the model's wording.
"""

from __future__ import annotations

import json

from hmgfu.artefacts import disclosure, placeholders_in
from hmgfu.receipts import ReceiptStore, observe_effects

THE_REAL_PAGE = """<!DOCTYPE html><html><script>
    async function getWeather() {
        // In production, you'd use: await fetch('https://api.openweathermap.org/data/2.5/weather?q=Valencia&appid=YOUR_API_KEY')
        const mockData = { temp: 18, humidity: 70 };
        document.getElementById('temp').innerText = `${mockData.temp}°C`;
    }
</script></html>"""

A_REAL_PAGE = """<!DOCTYPE html><html><script>
    async function getWeather() {
        const r = await fetch('https://api.open-meteo.com/v1/forecast?latitude=39.47&longitude=-0.38&current=temperature_2m');
        const d = await r.json();
        document.getElementById('temp').innerText = `${d.current.temperature_2m}°C`;
    }
</script></html>"""


def test_the_page_that_pretends_is_recognised():
    found = placeholders_in(THE_REAL_PAGE)
    assert found, "the mock data and the API-key placeholder are both unresolved"
    assert any("mock" in f.lower() for f in found)


def test_the_page_that_works_is_not_flagged():
    assert placeholders_in(A_REAL_PAGE) == []
    assert placeholders_in("") == []
    assert placeholders_in("<p>The production line runs at 40 units per hour.</p>") == [], \
        "a word that merely appears in prose is not a placeholder"


def test_the_receipt_records_what_was_shipped(tmp_path):
    target = tmp_path / "weather_widget_final.html"
    target.write_text(THE_REAL_PAGE, encoding="utf-8")
    eff = observe_effects("write_file", {"path": "weather_widget_final.html", "content": THE_REAL_PAGE},
                          json.dumps({"path": str(target), "bytes": len(THE_REAL_PAGE)}), str(tmp_path))
    assert eff["files"][0]["placeholders"], eff


def test_the_reply_discloses_it(tmp_path):
    st = ReceiptStore(str(tmp_path / "r.db"))
    rid = st.open("s", 5, "write_file", {"path": "weather_widget_final.html"}, "write", "user_request", 0)
    st.close(rid, "ok", "written", {"files": [{"path": "weather_widget_final.html", "sha256": "x",
                                               "placeholders": ["mockData", "YOUR_API_KEY"]}]})

    class _Engine:
        receipts = st
        _turn_session = "s"
        _turn_seq = 5

    note = disclosure(_Engine(), "s", 5)
    assert "weather_widget_final.html" in note
    assert "mockData" in note or "YOUR_API_KEY" in note
    assert "not" in note.lower(), "it says plainly that the artefact is not finished"


def test_nothing_is_disclosed_when_the_work_is_real(tmp_path):
    st = ReceiptStore(str(tmp_path / "r.db"))
    rid = st.open("s", 5, "write_file", {"path": "ok.html"}, "write", "user_request", 0)
    st.close(rid, "ok", "written", {"files": [{"path": "ok.html", "sha256": "x"}]})

    class _Engine:
        receipts = st
        _turn_session = "s"
        _turn_seq = 5

    assert disclosure(_Engine(), "s", 5) == ""
