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


def render_fragment(days: list[dict]) -> str:
    # 防止資料內容提早結束 <script>
    payload = json.dumps({"days": days}, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.read_text("utf-8").replace("/*__DATA__*/", payload)


def build_site(data_dir: Path, site_dir: Path) -> Path:
    frag = render_fragment(collect_days(data_dir))
    site_dir.mkdir(parents=True, exist_ok=True)
    # GitHub Pages 用完整 HTML；fragment.html 給 Claude Artifact 預覽用
    (site_dir / "fragment.html").write_text(frag, "utf-8")
    page = ('<!doctype html>\n<html lang="zh-Hant">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '</head>\n<body>\n' + frag + '\n</body>\n</html>\n')
    out = site_dir / "index.html"
    out.write_text(page, "utf-8")
    return out
