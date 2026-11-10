"""把整個專案打包成單一 JSON（備份），或從備份還原。

用途：排程每天開一個全新的 Claude 工作階段，專案要能從備份完整還原。
  python -m tracker.backup pack OUT.json
  python -m tracker.backup unpack IN.json [目的資料夾]
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCLUDE = ["tracker", "tests", "docs", ".github", "data", "reports",
           "config.yaml", "requirements.txt", "README.md", ".gitignore"]
SKIP_PARTS = {"__pycache__", ".pytest_cache"}
MAX_FILE = 5_000_000


def pack(root: Path = ROOT) -> dict:
    files: dict[str, str] = {}
    for name in INCLUDE:
        base = root / name
        paths = [base] if base.is_file() else sorted(base.rglob("*")) if base.is_dir() else []
        for f in paths:
            if not f.is_file() or SKIP_PARTS & set(f.parts) or f.stat().st_size > MAX_FILE:
                continue
            try:
                files[f.relative_to(root).as_posix()] = f.read_text("utf-8")
            except UnicodeDecodeError:
                continue
    return {"version": 1, "created": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "files": files}


def unpack(bundle: dict, dest: Path) -> int:
    dest = dest.resolve()
    for rel, text in bundle["files"].items():
        target = (dest / rel).resolve()
        if dest not in target.parents:  # 擋掉 ../ 之類的路徑
            raise ValueError(f"不安全的路徑：{rel}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, "utf-8")
    return len(bundle["files"])


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == "pack":
        out = Path(sys.argv[2])
        b = pack()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(b, ensure_ascii=False), "utf-8")
        print(f"已備份 {len(b['files'])} 個檔案、{out.stat().st_size // 1024} KB → {out}")
    elif len(sys.argv) >= 3 and sys.argv[1] == "unpack":
        dest = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT
        n = unpack(json.loads(Path(sys.argv[2]).read_text("utf-8")), dest)
        print(f"已還原 {n} 個檔案 → {dest}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
