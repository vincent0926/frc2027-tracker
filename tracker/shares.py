"""隊伍分享：每天從 Chief Delphi 各技術主題收集候選文章，排程每天挑 2 則放上網站。

- 不限 2027，任何 FRC 主題都可以（機構、程式、電控、公關行銷、策略、隊務經營…）。
- 候選池 data/share_pool.json 保留最近 POOL_DAYS 天的文章，新文章少的日子也有得選。
- 已經放上網站的分享（任何一天分析檔裡的 team_shares）不會再被選。
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

from .fetch import PoliteFetcher
from .sources import collect_feed

SHARE_TOPICS = ["機構設計", "程式設計", "電控", "公關行銷", "策略", "隊務經營", "綜合"]
POOL_DAYS = 60
POOL_MAX = 400

# 標題／摘要裡出現這些字代表「有內容可學」
GOOD = {
    "tech binder": 6, "technical binder": 6, "whitepaper": 4, "white paper": 4, "build thread": 3, "build blog": 3,
    "open alliance": 2, "code release": 4, "cad release": 4, "release": 1, "github": 2, "onshape": 1, "cad": 2,
    "guide": 3, "tutorial": 3, "how we": 3, "how to": 2, "lessons": 3, "reveal": 2, "design": 1, "breakdown": 3,
    "outreach": 2, "impact": 1, "sponsor": 2, "marketing": 2, "fundraising": 2, "branding": 2, "scouting": 2,
    "strategy": 1, "simulator": 2, "library": 2, "tool": 1, "research": 2, "wiring": 1, "swerve": 1,
}
# 問問題、徵人、買賣、廣告類的貼文，通常不是「分享」
BAD = {
    "looking for": -4, "help": -2, "borrow": -5, "wanted": -4, "for sale": -5, "selling": -5, "hiring": -5,
    "job": -3, "seeking": -3, "new products": -3, "announcement": -1, "survey": -2, "poll": -2, "vs": -1,
}
TEAM_RE = re.compile(r"(?:\bteam|\bfrc)\s*#?\s*(\d{2,5})\b|^\s*(\d{2,5})\b", re.I)
POSTS_RE = re.compile(r"(\d+)\s+posts?\b")


def _load(p: Path, default):
    return json.loads(p.read_text("utf-8")) if p.exists() else default


def team_of(title: str) -> str:
    m = TEAM_RE.search(title or "")
    return f"FRC {m.group(1) or m.group(2)}" if m else ""


def _age(date: str, today: str) -> int | None:
    try:
        return (dt.date.fromisoformat(today) - dt.date.fromisoformat((date or "")[:10])).days
    except ValueError:
        return None


def used_urls(data_dir: Path, exclude_date: str | None = None) -> set[str]:
    """所有分析檔裡已經放上網站的分享。"""
    out: set[str] = set()
    for f in (data_dir / "analysis").glob("20*.json"):
        if exclude_date and f.stem == exclude_date:
            continue
        for s in json.loads(f.read_text("utf-8")).get("team_shares") or []:
            out.add(s.get("url", ""))
    return out


def score_share(item: dict, today: str) -> float:
    title = item.get("title", "").lower()
    text = f"{title} {item.get('summary', '')}".lower()
    s = sum(w for k, w in GOOD.items() if k in text)
    s += sum(w for k, w in BAD.items() if re.search(r"\b" + re.escape(k) + r"\b", title))
    if title.rstrip().endswith("?"):
        s -= 3
    if item.get("team"):
        s += 3
    m = POSTS_RE.search(item.get("summary", ""))
    if m:
        s += min(3, int(m.group(1)) / 15)
    age = _age(item.get("date", ""), today)
    if age is not None:
        s += 2 if age <= 7 else 1 if age <= 30 else 0
    return round(s, 2)


def update_pool(cfg: dict, fetcher: PoliteFetcher, data_dir: Path, today: str) -> dict:
    """抓所有分享來源，把新文章加進候選池，並清掉太舊的。"""
    path = data_dir / "share_pool.json"
    pool: dict[str, dict] = _load(path, {})
    used = used_urls(data_dir)
    stats = {"new": 0, "errors": []}
    added: set[str] = set()
    for src in cfg.get("share_sources", []):
        try:
            items, _ = collect_feed(fetcher, src)
        except Exception as e:  # 單一來源失敗不影響其他
            stats["errors"].append({"source": src["name"], "url": src["url"], "error": str(e)[:200]})
            print(f"[分享來源失敗] {src['name']}: {e}", file=sys.stderr)
            continue
        for i in items:
            url = i["url"]
            if not url or url in used:
                continue
            if url in pool:  # 同一篇出現在多個來源：「綜合」讓位給較具體的主題
                if pool[url]["topic"] == "綜合" and src["topic"] != "綜合":
                    pool[url]["topic"] = src["topic"]
                continue
            pool[url] = {"url": url, "title": i["title"], "date": i.get("date", ""), "summary": i.get("summary", ""),
                         "topic": src["topic"], "source": src["name"], "team": team_of(i["title"]), "first_seen": today}
            added.add(url)
    # 清掉太舊的，太多時只留分數高的
    for url in list(pool):
        age = _age(pool[url].get("date") or pool[url]["first_seen"], today)
        if age is not None and age > POOL_DAYS:
            del pool[url]
    if len(pool) > POOL_MAX:
        keep = sorted(pool.values(), key=lambda x: score_share(x, today), reverse=True)[:POOL_MAX]
        pool = {x["url"]: x for x in keep}
    stats["new"] = len(added & set(pool))  # 只算清理後真正留下的新文章
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pool, ensure_ascii=False, indent=1), "utf-8")
    print(f"[完成] 隊伍分享候選池：新增 {stats['new']} 篇，共 {len(pool)} 篇")
    return stats


def candidates(data_dir: Path, today: str, n: int = 40) -> list[dict]:
    pool = _load(data_dir / "share_pool.json", {})
    used = used_urls(data_dir, exclude_date=today)
    cands = [dict(x, score=score_share(x, today)) for x in pool.values() if x["url"] not in used]
    return sorted(cands, key=lambda x: x["score"], reverse=True)[:n]


def pick_shares(cands: list[dict], k: int = 2) -> list[dict]:
    """規則評分版：取分數最高的，盡量不同主題。"""
    good = [c for c in cands if c["score"] > 0]  # cands 已依分數排序
    picked: list[dict] = []
    for c in good:  # 先每個主題各取最高分
        if len(picked) < k and c["topic"] not in {p["topic"] for p in picked}:
            picked.append(c)
    for c in good:  # 主題不夠分散時，用剩下的高分補滿
        if len(picked) < k and c not in picked:
            picked.append(c)
    return [{"url": c["url"], "title": c["title"], "source": c["source"], "topic": c["topic"], "team": c.get("team", ""),
             "date": c.get("date", ""), "summary": c.get("summary", "")[:280],
             "title_zh": "", "summary_zh": "", "takeaways": []} for c in picked]


def validate_shares(shares: list, pool_urls: set[str], used: set[str]) -> list[str]:
    errs = []
    if not isinstance(shares, list) or len(shares) > 2:
        return ["team_shares 必須是最多 2 則的清單"]
    seen = set()
    for s in shares:
        u = s.get("url", "")
        if u not in pool_urls:
            errs.append(f"team_shares 的網址不在候選池中：{u}")
        if u in used:
            errs.append(f"team_shares 這篇之前已經分享過：{u}")
        if u in seen:
            errs.append(f"team_shares 重複：{u}")
        seen.add(u)
        if s.get("topic") not in SHARE_TOPICS:
            errs.append(f"team_shares 的主題不合法：{s.get('topic')}（只能用 {'、'.join(SHARE_TOPICS)}）")
        if not s.get("title"):
            errs.append("team_shares 缺少原文標題 title")
        if s.get("title_zh") and not s.get("summary_zh"):
            errs.append(f"team_shares 有中文標題卻沒有 summary_zh：{u}")
    return errs
