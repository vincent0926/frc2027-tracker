"""每日分析：挑出「最有價值的一則」並寫當天重點整理。

- 有 ANTHROPIC_API_KEY：請 Claude 閱讀當天所有項目後挑選、用中文整理。
- 沒有 key（或呼叫失敗）：用規則評分（來源權重 + 關鍵字 + 新鮮度）挑選。
- data/analysis/<日期>.json 已存在時不覆蓋（可以手寫/人工修正）。
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

MODEL = "claude-opus-5-5"

# 來源權重：官方 > 廠商/軟體 > 社群
SOURCE_WEIGHT = {"FIRST 官方": 6, "Season Materials": 8, "WPILib 文件": 6, "frc-blog": 5,
                 "Releases": 4, "Chief Delphi": 1}
KEYWORD_WEIGHT = {
    "team update": 7, "game manual": 7, "rule": 5, "legal": 4, "preview": 3, "deadline": 3,
    "registration": 3, "pricing": 3, "price": 2, "fee": 3, "systemcore": 3, "release": 2,
    "beta": 2, "kickoff": 3, "breaking": 3, "removes": 2, "change": 2,
    "build thread": -4, "open alliance": -3, "guesses": -3, "predictions": -3, "help": -1,
}


def _source_weight(name: str) -> int:
    return max((w for k, w in SOURCE_WEIGHT.items() if k in name), default=0)


def _age_days(date: str, today: str) -> int | None:
    try:
        return (dt.date.fromisoformat(today) - dt.date.fromisoformat(date[:10])).days
    except ValueError:
        return None


def score_item(item: dict, today: str) -> float:
    text = f"{item['title']} {item.get('summary', '')}".lower()
    s = _source_weight(item["source"])
    s += sum(w for k, w in KEYWORD_WEIGHT.items() if k in text)
    if "2027" in item["title"]:
        s += 2
    age = _age_days(item.get("date", ""), today)
    if age is not None:
        s += 4 if age <= 2 else 2 if age <= 7 else 0 if age <= 30 else -3
    return s


def page_items(result: dict) -> list[dict]:
    """把「頁面有變動」轉成可評分的項目（新文件連結最重要）。"""
    out = []
    for p in result["pages"]:
        if p["baseline"]:
            continue
        n_links, n_add = len(p["new_links"]), len(p["added"])
        if not (n_links or n_add):
            continue
        first = next(iter(p["new_links"].values()), None) or (p["added"][0] if p["added"] else "")
        out.append({"title": f"頁面更新：{p['source']}（{first[:60]}）", "url": p["url"],
                    "source": p["source"], "date": result["date"],
                    "summary": "；".join(list(p["new_links"].values())[:5] + p["added"][:5]),
                    "categories": ["規則/比賽手冊"], "baseline": False,
                    "_bonus": 10 + 3 * n_links})
    return out


def heuristic_analysis(result: dict) -> dict:
    today = result["date"]
    cands = [i for i in result["items"]] + page_items(result)
    if not cands:
        return {"method": "heuristic", "top_pick": None,
                "headline": "今天沒有新的 2027 相關消息。", "highlights": []}
    scored = sorted(cands, key=lambda i: score_item(i, today) + i.get("_bonus", 0), reverse=True)
    top = scored[0]
    groups: dict[str, list[dict]] = {}
    for i in scored:
        groups.setdefault(i["categories"][0], []).append(i)
    highlights = [{"category": c, "text": f"{len(g)} 則，較重要的有：" + "、".join(f"「{x['title']}」" for x in g[:3])}
                  for c, g in groups.items()]
    return {
        "method": "heuristic",
        "top_pick": {"url": top["url"], "title": top["title"], "source": top["source"],
                     "reason": "依來源可信度（官方優先）、關鍵字（規則、手冊、Team Update、價格、截止日）"
                               "與發布時間自動評分，這則分數最高。設定 ANTHROPIC_API_KEY 可改由 Claude 判讀並寫出理由。"},
        "headline": f"今天共 {len(cands)} 則 2027 相關消息，分布在 {len(groups)} 個分類。",
        "highlights": highlights,
    }


# ---------------- Claude ----------------
SCHEMA = {
    "type": "object",
    "properties": {
        "top_pick_url": {"type": "string"},
        "top_pick_reason": {"type": "string"},
        "headline": {"type": "string"},
        "highlights": {"type": "array", "items": {
            "type": "object",
            "properties": {"category": {"type": "string"}, "text": {"type": "string"}},
            "required": ["category", "text"], "additionalProperties": False}},
        "action_items": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["top_pick_url", "top_pick_reason", "headline", "highlights", "action_items"],
    "additionalProperties": False,
}

SYSTEM = """你是 FRC（FIRST Robotics Competition）隊伍的情報分析員，讀者是台灣高中隊伍的學生與導師。
你會收到爬蟲今天抓到、和 2027 賽季有關的項目（標題、來源、日期、摘要，多為英文）。請：
1. 挑出對隊伍「最有價值」的一則：優先考慮會影響規則、採購、軟體升級、截止日期或比賽策略的官方或第一手資訊；
   社群猜測、隊伍建造紀錄、舊聞價值較低。top_pick_url 必須是清單中某一則的 url，原樣複製。
2. top_pick_reason：用 2–4 句繁體中文說明它講了什麼、為什麼重要、隊伍該做什麼。
3. headline：一句話總結今天。
4. highlights：依分類（軟體更新、硬體/控制系統、規則/比賽手冊、行政/賽事、其他）寫重點，每類 1–3 句繁體中文，
   要寫具體內容，不要只列標題；沒有內容的分類省略。
5. action_items：0–4 條隊伍可以馬上做的事。
專有名詞（SystemCore、WPILib、REVLib、Team Update 等）保留英文。只根據提供的資料，不要編造。"""


def claude_analysis(result: dict) -> dict:
    import anthropic  # 只有要用 Claude 時才需要安裝

    cands = result["items"] + page_items(result)
    lines = [f"今天日期：{result['date']}", ""]
    for i in cands:
        old = "（首次監控時已存在的舊內容）" if i.get("baseline") else ""
        lines.append(f"- [{i['categories'][0]}] {i['title']} {old}\n  來源：{i['source']}｜日期：{i.get('date', '')}"
                     f"｜url：{i['url']}\n  摘要：{i.get('summary', '')}")
    client = anthropic.Anthropic()
    resp = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": "\n".join(lines)}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("Claude 拒絕了這次分析")
    text = next(b.text for b in resp.content if b.type == "text")
    data = json.loads(text)
    pick = next((i for i in cands if i["url"] == data["top_pick_url"]), cands[0])
    return {
        "method": "claude",
        "model": MODEL,
        "top_pick": {"url": pick["url"], "title": pick["title"], "source": pick["source"],
                     "reason": data["top_pick_reason"]},
        "headline": data["headline"],
        "highlights": data["highlights"],
        "action_items": data["action_items"],
    }


def analyze(result: dict, out_dir: Path) -> dict:
    path = out_dir / f"{result['date']}.json"
    if path.exists():  # 已有分析（例如人工撰寫）就沿用
        return json.loads(path.read_text("utf-8"))
    has_content = result["items"] or page_items(result)
    analysis = None
    if has_content and os.environ.get("ANTHROPIC_API_KEY"):
        try:
            analysis = claude_analysis(result)
        except Exception as e:  # API 出錯時退回規則評分，網站照常更新
            print(f"[分析] Claude 分析失敗，改用規則評分：{e}", file=sys.stderr)
    analysis = analysis or heuristic_analysis(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(analysis, ensure_ascii=False, indent=1), "utf-8")
    return analysis
