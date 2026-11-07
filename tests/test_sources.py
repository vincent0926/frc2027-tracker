from tracker.sources import classify, diff_snapshots, is_relevant, page_snapshot, parse_feed

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
<item><title>2027 Kickoff info</title><link>https://a/1</link><guid>g1</guid>
<pubDate>Fri, 30 Oct 2026 15:53:39 GMT</pubDate><description>&lt;p&gt;Hello &lt;b&gt;teams&lt;/b&gt;&lt;/p&gt;</description></item>
</channel></rss>"""

ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><id>tag:1</id><title>v2027.1.1-beta-1</title><link href="https://gh/r/1"/>
<updated>2026-11-01T00:00:00Z</updated><content type="html">&lt;p&gt;SystemCore fixes&lt;/p&gt;</content></entry></feed>"""


def test_parse_rss():
    [i] = parse_feed(RSS)
    assert i["id"] == "g1" and i["url"] == "https://a/1" and i["summary"] == "Hello teams"


def test_parse_atom():
    [i] = parse_feed(ATOM)
    assert i["title"] == "v2027.1.1-beta-1" and i["url"] == "https://gh/r/1"
    assert "SystemCore" in i["summary"]


def test_relevance_and_classify():
    assert is_relevant("New SYSTEMCORE image", ["2027", "systemcore"])
    assert not is_relevant("2026 recap", ["2027"])
    cats = {"軟體更新": ["wpilib"], "行政/賽事": ["registration"]}
    assert classify("WPILib 2027 beta", cats) == ["軟體更新"]
    assert classify("Hello", cats, "open registration now") == ["行政/賽事"]
    assert classify("random", cats) == ["其他"]


def test_page_diff():
    html1 = '<html><body><nav>menu</nav><p>Game Manual v1</p><a href="/m.pdf">Manual</a></body></html>'
    html2 = '<html><body><nav>menu</nav><p>Game Manual v2</p><a href="/m.pdf">Manual</a>' \
            '<a href="/tu1.pdf">Team Update 01</a></body></html>'
    s1, s2 = page_snapshot(html1, "https://x/"), page_snapshot(html2, "https://x/")
    assert "menu" not in s1["lines"]  # nav 被移除
    assert diff_snapshots(None, s1)["baseline"]
    d = diff_snapshots(s1, s2)
    assert d["added"] == ["Game Manual v2", "Team Update 01"] and d["removed"] == ["Game Manual v1"]
    assert d["new_links"] == {"https://x/tu1.pdf": "Team Update 01"}
