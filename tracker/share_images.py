"""隊伍分享的配圖：從原文抓第一張圖（多半是機器照片或 CAD），縮成小圖存成 data URI。

Artifact 網頁不能載入外部圖片，所以圖片要內嵌。存成文字 JSON（data/share_images.json），
才會被 backup.py 一起備份。只保留最近 IMG_DAYS 天的分享，網頁和備份都不會越來越大。
"""
from __future__ import annotations

import base64
import datetime as dt
import io
import json
import re
import sys
from pathlib import Path

from .fetch import PoliteFetcher
from .sources import first_image

IMG_DAYS = 30
MAX_SIDE = 560
MAX_BYTES = 15_000_000
CD_TOPIC = re.compile(r"^(https://www\.chiefdelphi\.com/t/[^/?#]+/\d+)")


def _load(p: Path, default):
    return json.loads(p.read_text("utf-8")) if p.exists() else default


def recent_shares(data_dir: Path, today: str) -> list[dict]:
    """最近 IMG_DAYS 天分析檔裡的所有分享。"""
    cut = (dt.date.fromisoformat(today) - dt.timedelta(days=IMG_DAYS)).isoformat()
    out = []
    for f in sorted((data_dir / "analysis").glob("20*.json")):
        if f.stem < cut:
            continue
        out += json.loads(f.read_text("utf-8")).get("team_shares") or []
    return out


def find_image_url(fetcher: PoliteFetcher, share: dict, pool: dict) -> str:
    """依序找：分享本身指定的 image → 候選池記錄的 → 原文網頁（Chief Delphi 取第一篇的圖，其他取 og:image）。

    註：Chief Delphi 的 robots.txt 禁止 /t/*/*.rss，所以讀討論串網頁本身。"""
    url = share["url"]
    hit = share.get("image") or (pool.get(url) or {}).get("image")
    if hit:
        return hit
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(fetcher.get(url).text, "html.parser")
    og = soup.find("meta", attrs={"property": "og:image"})
    og = (og.get("content") or "").strip() if og else ""
    if CD_TOPIC.match(url):
        # 討論串網頁：只用第一篇（作者本人的分享）裡的圖；沒有圖時 og:image 是論壇 logo，不要用
        post = soup.select_one("div.post, [itemprop=text]")
        img = first_image(str(post)) if post else ""
        sha = re.search(r"/([0-9a-f]{40})", img)
        return og if sha and sha.group(1) in og else img  # og:image 是同一張的較大版本
    return og


def to_thumb(raw: bytes) -> tuple[str, int, int]:
    from PIL import Image
    im = Image.open(io.BytesIO(raw))
    im.thumbnail((MAX_SIDE, MAX_SIDE))
    if im.mode != "RGB":
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.convert("RGBA").split()[-1])
        im = bg
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=70, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode(), im.width, im.height


def update_images(data_dir: Path, fetcher: PoliteFetcher, today: str) -> dict:
    """幫最近的分享補上縮圖；找不到圖的記成 none，不重複嘗試。清掉太舊的。"""
    path = data_dir / "share_images.json"
    index: dict = _load(path, {})
    pool = _load(data_dir / "share_pool.json", {})
    shares = recent_shares(data_dir, today)
    keep = {s["url"] for s in shares}
    stats = {"new": 0, "none": 0, "errors": 0}
    for s in shares:
        if s["url"] in index:
            continue
        try:
            src = find_image_url(fetcher, s, pool)
            if not src:
                index[s["url"]] = {"none": True}
                stats["none"] += 1
                continue
            r = fetcher.get(src)
            if len(r.content) > MAX_BYTES:
                raise ValueError("圖片太大")
            data, w, h = to_thumb(r.content)
            index[s["url"]] = {"src": src, "data": data, "w": w, "h": h}
            stats["new"] += 1
        except Exception as e:  # 單張失敗不影響網站建置；下次再試
            stats["errors"] += 1
            print(f"[分享配圖失敗] {s['url']}: {e}", file=sys.stderr)
    index = {u: v for u, v in index.items() if u in keep}
    path.write_text(json.dumps(index, ensure_ascii=False, indent=1), "utf-8")
    print(f"[完成] 分享配圖：新增 {stats['new']} 張、沒有圖 {stats['none']} 則、失敗 {stats['errors']} 則")
    return stats
