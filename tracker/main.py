"""每日執行入口：python -m tracker.main"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

import requests
import yaml

from .analyze import analyze
from .fetch import PoliteFetcher
from .site import build_site
from .sources import COLLECTORS, classify, diff_snapshots, is_document_link, is_relevant

ROOT = Path(__file__).resolve().parent.parent
MAX_SEEN = 1000          # 每個來源最多記住幾個已看過的 id
MAX_LINES = 25           # 頁面變動最多列幾行


def load_json(p: Path, default):
    return json.loads(p.read_text("utf-8")) if p.exists() else default


def save_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), "utf-8")


def run(config_path: Path, data_dir: Path, report_dir: Path, today: str) -> dict:
    cfg = yaml.safe_load(config_path.read_text("utf-8"))
    kws, cats = cfg["relevance_keywords"], cfg["categories"]
    fetcher = PoliteFetcher(cfg["user_agent"], cfg.get("request_delay_seconds", 2),
                            cfg.get("timeout_seconds", 30))
    state = load_json(data_dir / "state.json", {"seen": {}})

    result = {"date": today, "items": [], "pages": [], "errors": [], "baselines": []}
    reported_urls: set[str] = set()   # 同一篇文章可能出現在多個 feed，只報一次
    for src in cfg["sources"]:
        sid = src["id"]
        try:
            items, snap = COLLECTORS[src["type"]](fetcher, src)
        except Exception as e:  # 單一來源失敗不影響其他來源
            result["errors"].append({"source": src["name"], "url": src["url"], "error": str(e)[:200]})
            print(f"[失敗] {src['name']}: {e}", file=sys.stderr)
            continue

        if items is not None:  # feed / discourse
            first_time = sid not in state["seen"]
            seen = set(state["seen"].get(sid, []))
            fresh = [i for i in items if i["id"] not in seen]
            if src.get("filter", "relevant") == "relevant":
                fresh = [i for i in fresh if is_relevant(f"{i['title']} {i['summary']}", kws)]
            fresh = [i for i in fresh if i["url"] not in reported_urls]
            for i in fresh:
                reported_urls.add(i["url"])
                i["source"] = src["name"]
                i["categories"] = classify(i["title"], cats, i["summary"])
                i["baseline"] = first_time
            result["items"].extend(fresh)
            if first_time:
                result["baselines"].append(src["name"])
            state["seen"][sid] = ([i["id"] for i in items] + list(state["seen"].get(sid, [])))[:MAX_SEEN]
            state["seen"][sid] = list(dict.fromkeys(state["seen"][sid]))
            print(f"[完成] {src['name']}: {len(items)} 筆，新的 2027 相關 {len(fresh)} 筆")

        if snap is not None:  # page
            snap_path = data_dir / "snapshots" / f"{sid}.json"
            d = diff_snapshots(load_json(snap_path, None), snap)
            save_json(snap_path, snap)
            if d["baseline"]:
                result["baselines"].append(src["name"])
                docs = {u: t for u, t in snap["links"].items()
                        if is_document_link(u) and is_relevant(f"{u} {t}", kws)}
                d["new_links"] = docs  # 第一次：列出目前已有的 2027 文件當參考
            if d["baseline"] or d["added"] or d["removed"] or d["new_links"] or d["gone_links"]:
                result["pages"].append({"source": src["name"], "url": src["url"], **d})
            print(f"[完成] {src['name']}: +{len(d['added'])} / -{len(d['removed'])} 行")

    save_json(data_dir / "state.json", state)
    save_json(data_dir / "daily" / f"{today}.json", result)
    md = render_markdown(result, kws, cats)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / f"{today}.md").write_text(md, "utf-8")
    (report_dir / "latest.md").write_text(md, "utf-8")
    update_index(report_dir)
    return result


# ---------------- 報告 ----------------
def render_markdown(r: dict, kws: list[str], cats: dict) -> str:
    out = [f"# FRC 2027 變更日報 — {r['date']}", ""]
    changed_pages = [p for p in r["pages"] if not p["baseline"]]
    out.append(f"**摘要：** {len(r['items'])} 則新消息、{len(changed_pages)} 個監控頁面有變動、"
               f"{len(r['errors'])} 個來源抓取失敗。")
    if r["baselines"]:
        out += ["", f"> ℹ️ 首次監控（建立基準）：{'、'.join(r['baselines'])}。"
                "這些來源今天列出的是「目前已存在」的內容，之後只會回報新變動。"]
    if not r["items"] and not r["pages"]:
        out += ["", "今天沒有偵測到任何 2027 相關變化。"]

    if r["items"]:
        out += ["", "## 📰 新消息（依分類）"]
        for cat in list(cats) + ["其他"]:
            group = [i for i in r["items"] if i["categories"][0] == cat]
            if not group:
                continue
            out += ["", f"### {cat}（{len(group)}）"]
            for i in group:
                tags = " ".join(f"`{c}`" for c in i["categories"][1:])
                date = i["date"]
                out.append(f"- **[{i['title']}]({i['url']})** — {i['source']} · {date} {tags}".rstrip())
                if i["summary"]:
                    out.append(f"  > {i['summary']}")

    if r["pages"]:
        out += ["", "## 🔍 監控頁面變動"]
        for p in r["pages"]:
            out += ["", f"### [{p['source']}]({p['url']})"]
            if p["baseline"]:
                out.append("已建立基準快照。")
                if p["new_links"]:
                    out.append(f"目前頁面上的 2027 相關文件（{len(p['new_links'])}）：")
            elif p["new_links"]:
                out.append(f"**新增連結（{len(p['new_links'])}）：**")
            for u, t in list(p["new_links"].items())[:40]:
                out.append(f"- [{t}]({u})")
            if p["gone_links"]:
                out.append(f"**移除的連結（{len(p['gone_links'])}）：**")
                out += [f"- ~~{t}~~ ({u})" for u, t in list(p["gone_links"].items())[:20]]
            if p["added"]:
                rel = [l for l in p["added"] if is_relevant(l, kws)]
                other = [l for l in p["added"] if l not in rel]
                out.append(f"**新增內容（{len(p['added'])} 行，含 2027 關鍵字的優先列出）：**")
                for l in (rel + other)[:MAX_LINES]:
                    out.append(f"- {'⭐ ' if l in rel else ''}{l[:300]}")
            if p["removed"]:
                out.append(f"**刪除內容（{len(p['removed'])} 行）：**")
                out += [f"- ~~{l[:300]}~~" for l in p["removed"][:10]]

    if r["errors"]:
        out += ["", "## ⚠️ 抓取失敗"]
        out += [f"- {e['source']}：{e['error']}" for e in r["errors"]]
    out += ["", "---", "*由 frc2027-tracker 自動產生。內容摘錄自原始來源（英文），請以官方文件為準。*", ""]
    return "\n".join(out)


def update_index(report_dir: Path) -> None:
    days = sorted((p.stem for p in report_dir.glob("20*.md")), reverse=True)
    lines = ["# FRC 2027 變更日報索引", "", "- [最新一期](latest.md)", ""]
    lines += [f"- [{d}]({d}.md)" for d in days]
    (report_dir / "README.md").write_text("\n".join(lines) + "\n", "utf-8")


def notify_discord(webhook: str, r: dict) -> None:
    """設定環境變數 DISCORD_WEBHOOK_URL 就會推播摘要（選用）。"""
    lines = [f"**FRC 2027 日報 {r['date']}**：{len(r['items'])} 則新消息、"
             f"{len([p for p in r['pages'] if not p['baseline']])} 個頁面變動"]
    for i in r["items"][:10]:
        lines.append(f"• [{i['categories'][0]}] {i['title']} <{i['url']}>")
    for p in r["pages"]:
        if not p["baseline"]:
            lines.append(f"• 頁面變動：{p['source']} <{p['url']}>")
    requests.post(webhook, json={"content": "\n".join(lines)[:1900]}, timeout=20)


def main() -> None:
    ap = argparse.ArgumentParser(description="FRC 2027 變更追蹤器")
    ap.add_argument("--config", default=ROOT / "config.yaml", type=Path)
    ap.add_argument("--data", default=ROOT / "data", type=Path)
    ap.add_argument("--reports", default=ROOT / "reports", type=Path)
    ap.add_argument("--site", default=ROOT / "site", type=Path)
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--site-only", action="store_true", help="不抓資料，只用現有資料重建網站")
    a = ap.parse_args()
    if a.site_only:
        build_site(a.data, a.site)
        print(f"網站已建立：{a.site / 'index.html'}")
        return
    r = run(a.config, a.data, a.reports, a.date)
    analyze(r, a.data / "analysis")
    build_site(a.data, a.site)
    print(f"網站已建立：{a.site / 'index.html'}")
    hook = os.environ.get("DISCORD_WEBHOOK_URL")
    has_news = r["items"] or any(not p["baseline"] for p in r["pages"])
    if hook and has_news:
        notify_discord(hook, r)
    print(f"報告已寫入 {a.reports / (a.date + '.md')}")


if __name__ == "__main__":
    main()
