import json

from tracker.analyze import analyze, heuristic_analysis
from tracker.site import build_site


def _item(title, source, date, cat="其他", baseline=False, url=None):
    return {"id": title, "title": title, "url": url or f"https://x/{title}", "date": date,
            "summary": "", "source": source, "categories": [cat], "baseline": baseline}


RESULT = {
    "date": "2026-11-07",
    "items": [
        _item("FRC 157 2027 Build Thread | Open Alliance", "Chief Delphi 標籤 #2027", "2026-11-06", "隊伍建造紀錄"),
        _item("2027 Event & Robot Rule Preview", "FIRST 官方部落格 (RSS)", "2026-11-05", "規則/比賽手冊"),
        _item("Guesses for FRC 2027?", "Chief Delphi 最新討論", "2026-11-07"),
    ],
    "pages": [], "errors": [], "baselines": [],
}


def test_heuristic_prefers_official_rules():
    a = heuristic_analysis(RESULT)
    assert a["top_pick"]["title"] == "2027 Event & Robot Rule Preview"
    assert {h["category"] for h in a["highlights"]} == {"隊伍建造紀錄", "規則/比賽手冊", "其他"}


def test_page_change_beats_community_posts():
    r = dict(RESULT, pages=[{"source": "FRC Season Materials", "url": "https://first/season", "baseline": False,
                             "added": ["Team Update 01"], "removed": [],
                             "new_links": {"https://f/frc2027/TU01.pdf": "Team Update 01"}, "gone_links": {}}])
    assert heuristic_analysis(r)["top_pick"]["url"] == "https://first/season"


def test_existing_analysis_not_overwritten(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    (tmp_path / "2026-11-07.json").write_text(json.dumps({"method": "manual"}), "utf-8")
    assert analyze(RESULT, tmp_path) == {"method": "manual"}


def test_site_escapes_script_close(tmp_path):
    data = tmp_path / "data"
    (data / "daily").mkdir(parents=True)
    evil = dict(RESULT, items=[_item("</script><img src=x onerror=alert(1)>", "s", "2026-11-07")])
    (data / "daily" / "2026-11-07.json").write_text(json.dumps(evil), "utf-8")
    html = build_site(data, tmp_path / "site").read_text("utf-8")
    assert "</script><img" not in html and "<\\/script><img" in html
    assert html.startswith("<!doctype html>")
