# FRC 2027 變更追蹤器

每天自動從網路抓取 **FRC 2027 賽季**的各種變化（軟體更新、硬體/控制系統、規則手冊、行政/賽事公告），
和前一天比對後產生：

- **網站「FRC 2027 情報站」**（[`site/index.html`](site/index.html)，自動部署到 GitHub Pages）
  - 今日最有價值的一則（含理由與隊伍可以做的事）
  - 今日重點整理（依分類）
  - 全部訊息（分類篩選、搜尋、切換日期）、監控頁面的變動
- **中文日報** Markdown（[`reports/`](reports/)）

## 監控來源

| 類型 | 來源 | 抓什麼 |
|---|---|---|
| 官方 | FIRST 官方部落格 RSS、FRC 分類頁 | 官方公告 |
| 官方 | FRC Season Materials 頁面 | 新的 Game Manual、Team Update、規則文件、賽季行事曆 |
| 軟體 | WPILib「New for 2027」文件 | 2027 軟體變更內容 |
| 軟體 | WPILib / CTRE / REV / PhotonVision / AdvantageKit 的 GitHub Releases | 新版本 |
| 社群 | Chief Delphi：最新討論、#2027、#systemcore、#frc-blog 及 11 個技術標籤 | 社群討論、廠商公告、官方 blog 轉貼 |

所有來源都在 [`config.yaml`](config.yaml)，要新增就照格式加一筆。

## 運作方式

1. **抓取**：`tracker/fetch.py` 用誠實的 User-Agent、遵守 robots.txt、每次請求間隔 2 秒。
2. **比對**：
   - RSS/Atom feed：記錄看過的文章 id（`data/state.json`），只報新的。
   - 網頁：存快照（`data/snapshots/`），用 `difflib` 找出新增/刪除的文字行與連結。
3. **篩選**：只保留含 `2027`、`SystemCore`、`BIOCORE` 等關鍵字的內容。
4. **分類**：依標題關鍵字分到 隊伍建造紀錄 / 軟體 / 硬體 / 規則 / 行政。
5. **報告**：寫成 `reports/YYYY-MM-DD.md`，`reports/latest.md` 永遠是最新一期。
6. **分析**（`tracker/analyze.py`）：挑出最有價值的一則並寫重點整理，存到 `data/analysis/日期.json`。
   - 有設定 `ANTHROPIC_API_KEY`：由 Claude 閱讀當天所有訊息後挑選，用繁體中文寫理由與整理。
   - 沒有設定：用規則評分（官方來源 > 廠商 > 社群；規則、手冊、Team Update、價格、截止日加分；建造紀錄、猜測減分；越新越高分）。
   - 該日的分析檔已存在就不覆蓋，所以可以手動修改。
   - Claude 也會替「重要」「值得看」的訊息寫新聞式中文標題與一句導讀（`items_zh`），網站會優先顯示中文、原文標題放小字。
7. **網站**（`tracker/site.py`）：把最近 90 天的資料嵌進單一 HTML 檔，不需要伺服器。

> 第一次執行某個來源時會「建立基準」，列出目前已存在的內容；之後只回報新變動。

## 本機執行

```bash
pip install -r requirements.txt
python -m tracker.main
python -m pytest tests     # 跑測試
python -m tracker.main --site-only   # 只用現有資料重建網站
```

產生的網站在 `site/index.html`，直接用瀏覽器打開就能看。

## 每天自動執行（GitHub Actions）

1. 把這個資料夾推到你自己的 GitHub repo。
2. 到 repo 的 **Settings → Pages**，把 Source 設成 **GitHub Actions**。
3. `.github/workflows/daily.yml` 會在每天台灣時間 07:17 自動執行：爬取 → 分析 → 建網站 → commit 回 repo → 部署到 Pages。
   網址會是 `https://<你的帳號>.github.io/<repo 名稱>/`。
4. 想立即測試：到 repo 的 **Actions → FRC 2027 每日追蹤 → Run workflow**。
5. （建議）讓 Claude 挑精選、寫整理：在 **Settings → Secrets and variables → Actions** 新增
   `ANTHROPIC_API_KEY`。每天呼叫一次 Claude Opus 5.5，並開啟了 server-side fallback
   （Claude 若拒絕回答，API 會自動改用其他模型重跑）；沒設定就用規則評分。
6. （選用）想在 Discord 收到通知：新增 `DISCORD_WEBHOOK_URL`，有新消息時會推播摘要。

## 注意

- Chief Delphi 的 robots.txt 禁止爬 `/search` 和分類頁 `/c/...`，所以本系統只用允許的 `latest.rss` 與標籤 RSS。
- 報告摘錄自原始英文來源，請以官方文件為準。
