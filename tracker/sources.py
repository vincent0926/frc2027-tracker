"""各種來源的解析器。每個 collect_* 回傳 (items, snapshot)。

item 格式：{"id", "title", "url", "date", "summary"}
"""
from __future__ import annotations

import difflib
import html
import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .fetch import PoliteFetcher

ATOM = "{http://www.w3.org/2005/Atom}"


def _strip_html(s: str | None, limit: int = 400) -> str:
    if not s:
        return ""
    text = BeautifulSoup(html.unescape(s), "html.parser").get_text(" ")
    text = " ".join(text.split())
    return text[:limit] + ("…" if len(text) > limit else "")


# ---------------- RSS / Atom ----------------
def parse_feed(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    items = []
    if root.tag == f"{ATOM}feed":
        for e in root.findall(f"{ATOM}entry"):
            link = e.find(f"{ATOM}link")
            content = e.find(f"{ATOM}content")
            if content is None:
                content = e.find(f"{ATOM}summary")
            items.append({
                "id": (e.findtext(f"{ATOM}id") or "").strip(),
                "title": (e.findtext(f"{ATOM}title") or "").strip(),
                "url": link.get("href") if link is not None else "",
                "date": (e.findtext(f"{ATOM}updated") or "").strip(),
                "summary": _strip_html(content.text if content is not None else ""),
            })
    else:  # RSS 2.0
        for it in root.iter("item"):
            link = (it.findtext("link") or "").strip()
            items.append({
                "id": (it.findtext("guid") or link).strip(),
                "title": (it.findtext("title") or "").strip(),
                "url": link,
                "date": (it.findtext("pubDate") or "").strip(),
                "summary": _strip_html(it.findtext("description")),
            })
    return items


def collect_feed(f: PoliteFetcher, src: dict) -> tuple[list[dict], None]:
    return parse_feed(f.get(src["url"]).text), None


# ---------------- 網頁快照 ----------------
NOISE_TAGS = ["script", "style", "noscript", "nav", "header", "footer", "svg", "form"]


def page_snapshot(html_text: str, base_url: str, selector: str | None = None,
                  ignore_links: list[str] | None = None) -> dict:
    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(NOISE_TAGS):
        tag.decompose()
    root = (soup.select_one(selector) if selector else None) or soup.body or soup
    lines = []
    for line in root.get_text("\n").splitlines():
        line = " ".join(line.split())
        if len(line) >= 3 and (not lines or lines[-1] != line):
            lines.append(line)
    links = {}
    for a in root.find_all("a", href=True):
        text = " ".join(a.get_text(" ").split())
        href = urljoin(base_url, a["href"]).split("#")[0]
        if text and href.startswith("http") and not any(x in href for x in ignore_links or []):
            links[href] = text
    return {"lines": lines, "links": links}


def diff_snapshots(old: dict | None, new: dict) -> dict:
    """比對兩份快照，回傳新增/刪除的文字行與連結。"""
    if old is None:
        return {"baseline": True, "added": [], "removed": [], "new_links": {}, "gone_links": {}}
    added, removed = [], []
    for op in difflib.ndiff(old["lines"], new["lines"]):
        if op.startswith("+ "):
            added.append(op[2:])
        elif op.startswith("- "):
            removed.append(op[2:])
    old_links, new_links = old.get("links", {}), new.get("links", {})
    return {
        "baseline": False,
        "added": added,
        "removed": removed,
        "new_links": {u: t for u, t in new_links.items() if u not in old_links},
        "gone_links": {u: t for u, t in old_links.items() if u not in new_links},
    }


def collect_page(f: PoliteFetcher, src: dict) -> tuple[None, dict]:
    r = f.get(src["url"])
    return None, page_snapshot(r.text, r.url, src.get("selector"), src.get("ignore_links"))


COLLECTORS = {
    "feed": collect_feed,
    "page": collect_page,
}


def is_relevant(text: str, keywords: list[str]) -> bool:
    low = text.lower()
    return any(k.lower() in low for k in keywords)


def _match(text: str, categories: dict[str, list[str]]) -> list[str]:
    low = " " + text.lower() + " "
    return [name for name, kws in categories.items() if any(k.lower() in low for k in kws)]


def classify(title: str, categories: dict[str, list[str]], summary: str = "") -> list[str]:
    """先看標題；標題判斷不出來才看內文摘要（內文常有不相干的字，容易誤判）。"""
    return _match(title, categories) or _match(summary, categories) or ["其他"]


_PDF = re.compile(r"\.(pdf|docx?|xlsx?|zip)(\?|$)", re.I)


def is_document_link(url: str) -> bool:
    return bool(_PDF.search(url))
