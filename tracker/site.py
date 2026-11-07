"""把 data/daily + data/analysis 組成一個單檔靜態網站（site/index.html）。"""
from __future__ import annotations

import json
from pathlib import Path

TEMPLATE = Path(__file__).with_name("site_template.html")
MAX_DAYS = 90  # 網站保留最近幾天


def collect_days(data_dir: Path) -> list[dict]:
    days = []
    for f in sorted((data_dir / "daily").glob("20*.json"), reverse=True)[:MAX_DAYS]:
        a = data_dir / "analysis" / f.name
        days.append({
            "date": f.stem,
            "result": json.loads(f.read_text("utf-8")),
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
