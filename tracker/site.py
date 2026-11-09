"""把 data/daily + data/analysis 組成一個單檔靜態網站（site/index.html）。"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .analyze import item_level
from .events import event_zh

TEMPLATE = Path(__file__).with_name("site_template.html")
MAX_DAYS = 90  # 網站保留最近幾天


def source_kind(item: dict) -> tuple[str, str]:
    """回傳（來源類型, 簡短來源名稱），像新聞網站標示出處那樣。"""
    src, title = item.get("source", ""), item.get("title", "")
    if src.startswith("FIRST 官方"):
        return "官方", "FIRST 官方部落格"
    if src.startswith("WPILib 文件"):
        return "官方", "WPILib 文件"
    if "Releases" in src:
        return "軟體發布", src.replace(" GitHub Releases", "").replace(" Releases", "")
    if re.match(r"\[(FRC|FIRST|FTC|WPILib|FRC/FTC|FTC/FRC)[^\]]*Blog\]", title, re.I):
        return "官方轉貼", "Chief Delphi"
    if re.match(r"\[(CTRE|REV)\]", title) or (re.search(r"product|announcements", title, re.I) and not title.startswith("FIRST")):
        return "廠商", "Chief Delphi"
    return "社群", "Chief Delphi"


def collect_days(data_dir: Path) -> list[dict]:
    days = []
    for f in sorted((data_dir / "daily").glob("20*.json"), reverse=True)[:MAX_DAYS]:
        a = data_dir / "analysis" / f.name
        result = json.loads(f.read_text("utf-8"))
        for it in result.get("items", []):
            it["level"] = item_level(it, f.stem)
            it["kind"], it["src"] = source_kind(it)
        for ev in result.get("events", []):
            ev["zh"] = event_zh(ev["label"])
        days.append({
            "date": f.stem,
            "result": result,
            "analysis": json.loads(a.read_text("utf-8")) if a.exists() else None,
        })
    return days


# ---------------- SystemCore 專頁 ----------------
SC_RE = re.compile(r"systemcore|system core|motioncore|future robot controller|2027 control system", re.I)
SC_TOPICS = [
    ("價格與供貨", r"pric|purchase|black tote|storefront|availab|budget|cost|free of charge"),
    ("硬體與接線", r"electrical|\bcan\b|can bus|\bleds?\b|wir(e|ing)|molex|status (light|signal)|power|hardware|i2c|\bports?\b"),
    ("軟體與程式", r"wpilib|\bcode\b|firmware|toolchain|\bgit\b|blocks|driver ?station|\bds\b|sendable|ntcore|advantagescope|ipk|\bhal\b|program"),
    ("規則", r"\brules?\b|\blegal\b"),
    ("測試回報", r"alpha|beta|testing"),
]


def collect_systemcore(data_dir: Path) -> dict:
    """彙整所有日期中與 SystemCore 有關的訊息（不受網站 90 天限制），加上主題標籤。"""
    items: dict[str, dict] = {}
    for f in sorted((data_dir / "daily").glob("20*.json")):
        day = f.stem
        a = data_dir / "analysis" / f.name
        zh = (json.loads(a.read_text("utf-8")).get("items_zh") or {}) if a.exists() else {}
        for it in json.loads(f.read_text("utf-8")).get("items", []):
            text = f"{it['title']} {it.get('summary', '')}"
            if not SC_RE.search(text):
                continue
            # 測試 repo 的 commit 只收新出現的，首次監控時的舊紀錄不列（避免洗版）
            if it.get("source", "").startswith("SystemCoreTesting") and it.get("baseline"):
                continue
            entry = items.setdefault(it["url"], {
                "url": it["url"], "title": it["title"], "summary": it.get("summary", "")[:220],
                "date": it.get("date", ""), "first_seen": day, "baseline": it.get("baseline", False),
                "tags": [name for name, pat in SC_TOPICS if re.search(pat, text, re.I)] or ["其他"],
            })
            entry["kind"], entry["src"] = source_kind(it)
            if it["url"] in zh:
                entry["zh"] = zh[it["url"]]
    curated_path = data_dir / "systemcore.json"
    curated = json.loads(curated_path.read_text("utf-8")) if curated_path.exists() else None
    return {"curated": curated,
            "items": sorted(items.values(), key=lambda x: x["date"], reverse=True),
            "topics": [name for name, _ in SC_TOPICS]}


def render_fragment(days: list[dict], systemcore: dict | None = None) -> str:
    # 防止資料內容提早結束 <script>
    payload = json.dumps({"days": days, "systemcore": systemcore}, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.read_text("utf-8").replace("/*__DATA__*/", payload)


def build_site(data_dir: Path, site_dir: Path) -> Path:
    frag = render_fragment(collect_days(data_dir), collect_systemcore(data_dir))
    site_dir.mkdir(parents=True, exist_ok=True)
    # GitHub Pages 用完整 HTML；fragment.html 給 Claude Artifact 預覽用
    (site_dir / "fragment.html").write_text(frag, "utf-8")
    page = ('<!doctype html>\n<html lang="zh-Hant">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '</head>\n<body>\n' + frag + '\n</body>\n</html>\n')
    out = site_dir / "index.html"
    out.write_text(page, "utf-8")
    return out
