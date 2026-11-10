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


def test_quiet_day_with_deadline():
    r = dict(RESULT, date="2026-11-08",
             items=[_item("FRC 247 and FRC 445 Looking for Mentors", "Chief Delphi 最新討論", "2026-11-07")],
             events=[{"date": "2026-11-17", "label": "Kit and Kickoff Registration Closes"},
                     {"date": "2026-11-17", "label": "Drive Base & Black Tote Opt Out Closes"},
                     {"date": "2027-01-09", "label": "2027 FIRST Robotics Competition Kickoff"}])
    a = heuristic_analysis(r)
    assert a["quiet"] and a["top_pick"] is None
    assert a["tldr"][0] == "11/17 截止：Kit 與 Kickoff 報名、底盤／Black Tote 退訂（剩 9 天）"


def test_calendar_events_and_names():
    from tracker.events import event_zh
    from tracker.sources import extract_calendar_events
    html = ('<a href="https://calendar.google.com/calendar/render?action=TEMPLATE&amp;text=Official+Q%26amp%3BA+Opens'
            '&amp;dates=20270113T120000/20270421T120000">Add</a>'
            '<a href="https://calendar.google.com/calendar/render?action=TEMPLATE&amp;text=Digital+Animation+Award+Closes'
            '&amp;dates=20261020T120000/20270112T235900">Add</a>')
    evs = extract_calendar_events(html)
    assert evs == [{"date": "2027-01-12", "label": "Digital Animation Award Closes"},
                   {"date": "2027-01-13", "label": "Official Q&A Opens"}]
    assert event_zh("Week 3 Competition Events") == "第 3 週賽事"
    assert event_zh("Volunteer Registration Opens") == ""


def test_collect_systemcore_aggregates_and_tags(tmp_path):
    from tracker.site import collect_systemcore
    data = tmp_path / "data"
    (data / "daily").mkdir(parents=True)
    d1 = dict(RESULT, items=[_item("Looking for Systemcore pricing details", "Chief Delphi 標籤 #systemcore", "2026-09-06"),
                             _item("Motor count", "Chief Delphi", "2026-09-01")])
    d2 = dict(RESULT, date="2026-11-08",
              items=[_item("Getting LEDs working on SystemCore", "Chief Delphi", "2026-11-08")])
    (data / "daily" / "2026-11-07.json").write_text(json.dumps(d1), "utf-8")
    (data / "daily" / "2026-11-08.json").write_text(json.dumps(d2), "utf-8")
    sc = collect_systemcore(data)
    assert [i["title"] for i in sc["items"]] == ["Getting LEDs working on SystemCore", "Looking for Systemcore pricing details"]
    assert sc["items"][1]["tags"] == ["價格與供貨"] and "硬體與接線" in sc["items"][0]["tags"]
    assert sc["curated"] is None


def test_validate_analysis():
    from tracker.analyze import validate_analysis
    ok = {"tldr": ["a"], "headline": "h", "action_items": [],
          "highlights": [{"category": "其他", "importance": "low", "points": ["x"]}],
          "top_pick": {"url": "https://x/Motor count", "title": "t", "source": "s", "summary": "s",
                       "points": [], "impact": ["電控"]},
          "items_zh": {"https://x/Motor count": {"title": "t", "blurb": "b"}}}
    r = dict(RESULT, items=[_item("Motor count", "Chief Delphi", "2026-11-07")])
    assert validate_analysis(ok, r) == []
    bad = dict(ok, top_pick=dict(ok["top_pick"], url="https://made-up", impact=["廚房"]), tldr=[])
    errs = validate_analysis(bad, r)
    assert len(errs) == 3
    assert validate_analysis(dict(ok, top_pick=None), r) == ["top_pick 為空時必須設定 quiet: true"]


def test_merge_same_day_keeps_earlier_items():
    from tracker.main import merge_same_day
    old = dict(RESULT, pages=[{"source": "A", "baseline": False, "url": "u"}], baselines=["X"])
    new = dict(RESULT, items=[RESULT["items"][0]], pages=[], baselines=["Y"])
    m = merge_same_day(old, new)
    assert len(m["items"]) == 3 and m["pages"][0]["source"] == "A" and m["baselines"] == ["X", "Y"]


def test_source_kind_for_git_sources():
    from tracker.site import source_kind
    assert source_kind({"source": "SystemCoreTesting（官方測試 repo：相容表）", "title": "x"}) == ("官方", "SystemCoreTesting")
    assert source_kind({"source": "WPILib 新版本", "title": "x"}) == ("軟體發布", "WPILib")
    assert source_kind({"source": "Chief Delphi #2027", "title": "Motor count"}) == ("社群", "Chief Delphi")
    assert source_kind({"source": "某個新來源", "title": "x"}) == ("社群", "某個新來源")


def test_backup_roundtrip_and_path_safety(tmp_path):
    import pytest
    from tracker.backup import pack, unpack
    src = tmp_path / "src"
    (src / "data" / "daily").mkdir(parents=True)
    (src / "data" / "daily" / "2026-11-10.json").write_text('{"中文": 1}', "utf-8")
    (src / "config.yaml").write_text("a: 1\n", "utf-8")
    (src / "tracker").mkdir()
    (src / "tracker" / "__pycache__").mkdir()
    (src / "tracker" / "__pycache__" / "x.pyc").write_bytes(b"\xff\xfe")
    b = pack(src)
    assert sorted(b["files"]) == ["config.yaml", "data/daily/2026-11-10.json"]
    dst = tmp_path / "dst"
    assert unpack(b, dst) == 2
    assert (dst / "data" / "daily" / "2026-11-10.json").read_text("utf-8") == '{"中文": 1}'
    with pytest.raises(ValueError):
        unpack({"files": {"../evil.txt": "x"}}, dst)
