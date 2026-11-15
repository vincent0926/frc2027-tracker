# 每日更新流程（給排程執行的 Claude）

每天台灣時間早上約 7 點，排程會開一個**全新的** Claude 工作階段，照這份文件更新「FRC 2027 情報站」。
全程不需要問使用者問題；遇到無法處理的狀況，照「出錯時」一節處理。

- 網站（Claude Artifact，已分享給隊伍）：https://claude.ai/artifact/S3zmGKK82y9653mdFuYLom
- 專案的長期保存：這個 Artifact 的附加檔案 `backup/project.json`（整個專案打包成一個 JSON）
- 日期一律用台灣時間：`TODAY=$(TZ=Asia/Taipei date +%F)`

## 0. 還原專案（全新的工作階段第一步）

新的工作階段裡沒有專案，先從 Artifact 的備份檔還原：

1. Artifact 工具 `read`，`url` 填上面的網站網址、`path` 填 `backup/project.json`，結果會告訴你存到哪個本機路徑。
2. 還原（把 `BACKUP` 換成上一步的路徑）：

```bash
mkdir -p /home/user/frc2027-tracker && cd /home/user/frc2027-tracker
BACKUP="<上一步的本機路徑>" python3 -c "
import json, os, pathlib
b = json.load(open(os.environ['BACKUP'], encoding='utf-8'))
root = pathlib.Path('/home/user/frc2027-tracker').resolve()
for rel, text in b['files'].items():
    f = (root / rel).resolve()
    assert root in f.parents, rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(text, encoding='utf-8')
print(len(b['files']), 'files restored')
"
pip install -q requests beautifulsoup4 PyYAML pytest
```

備份讀不到或還原失敗時，**不要**重新從頭建立專案（會丟掉歷史資料）；在回覆中說明，等使用者處理。

## 1. 測試

```bash
cd /home/user/frc2027-tracker
python -m pytest -q tests
```

測試失敗就停止，照「出錯時」處理。

## 2. 爬取

```bash
python -m tracker.main --date "$TODAY" --skip-analysis
```

- 會更新 `data/daily/$TODAY.json`、`data/state.json`、`data/snapshots/`、`reports/`。
- 有些來源抓取失敗是正常的（例如網路暫時不通），會記在當天資料的 `errors` 裡，不用處理。

## 3. 撰寫當天分析（由你判讀）

讀 `data/daily/$TODAY.json`，寫 `data/analysis/$TODAY.json`。
格式參考 `data/analysis/2026-11-07.json`（有精選的一天）與 `2026-11-08.json`（平靜日）。

| 欄位 | 內容 |
|---|---|
| `method` | `"claude"` |
| `model` | `"每日排程"` |
| `tldr` | 1～3 條，每條 25 字內，最重要的放第一條。14 天內到期的截止日（見 `events`）也算重要 |
| `top_pick` | 最有價值的一則：`url`（必須原樣複製當天 `items` 裡的網址）、`title`（原文標題）、`source`、`summary`（40 字內一句話）、`points`（3～6 條具體重點）、`impact`（只能用：機構、電控、程式、行政/報名、策略） |
| `quiet` | 當天沒有夠重要的新消息時設 `true`，並把 `top_pick` 設成 `null` |
| `headline` | 一句話總結今天 |
| `highlights` | 每個有內容的分類：`category`、`importance`（high／medium／low）、`points`（1～3 條，35 字內） |
| `action_items` | 0～4 條隊伍可以馬上做的事，有期限寫日期 |
| `items_zh` | 「重要」「值得看」的訊息的中文標題與導讀：`{網址: {"title": 20 字內, "blurb": 50 字內}}` |

判讀原則：

- 只看 `baseline` 為 false 的新訊息；官方來源、規則、採購、軟體升級、截止日優先；社群猜測、建造紀錄、舊聞價值低。
- 只根據資料內容撰寫，不要編造。官方文章摘要不夠時，可以讀原文（使用者代理請用 `frc2027-tracker/0.1`，遵守 robots.txt）。
- 用繁體中文；SystemCore、WPILib、REVLib 等專有名詞保留英文。

寫完後檢查，有錯就修到通過為止：

```bash
python -m tracker.main --check-analysis --date "$TODAY"
```

## 3b. 隊伍分享（每天 2 則）

不限 2027，任何 FRC 主題都可以：機構設計、程式設計、電控、公關行銷、策略、隊務經營等。爬取時已經自動更新候選池，先列出候選：

```bash
python -m tracker.main --share-candidates --date "$TODAY"
```

1. 從候選中挑 **2 則**，盡量不同主題。優先選隊伍親自分享的實作經驗、開源 CAD／程式、技術手冊、教學、公關行銷／募款／評審經驗；
   不要選求助、徵人、借東西、買賣、廠商廣告。已經分享過的不會出現在候選裡。
2. 讀原文第一篇再寫介紹：`https://www.chiefdelphi.com/raw/<文章編號>/1`（文章網址最後那串數字；使用者代理用 `frc2027-tracker/0.1`）。
3. 寫進當天分析檔的 `team_shares`（清單，最多 2 則；合格候選不足時可以少於 2 則）：

| 欄位 | 內容 |
|---|---|
| `url`、`title`、`source`、`team`、`date` | 原樣從候選複製（`title` 是原文標題） |
| `topic` | 只能用：機構設計、程式設計、電控、公關行銷、策略、隊務經營、綜合 |
| `title_zh` | 中文標題，25 字內，直接講出分享的東西 |
| `summary_zh` | 2～3 句介紹：哪支隊伍、分享了什麼、有什麼特別 |
| `takeaways` | 2～3 條「可以學到」的具體重點，每條 35 字內，只寫原文裡有的內容 |

範例見 `data/analysis/2026-11-15.json`。寫完一樣用 `--check-analysis` 檢查（會確認網址在候選池裡、沒有重複分享）。

## 4. SystemCore 專頁（有新官方資訊時才做）

如果今天有新的 SystemCore 官方資訊（FIRST 部落格、WPILib 文件、SystemCoreTesting repo 的相容表或已知問題有變動），
更新 `data/systemcore.json` 對應的區塊（facts、stats、vendors、gotchas、checklist…），每一條都要附來源網址，
並把 `updated` 改成今天。沒有新官方資訊就不要動這個檔案。

## 5. 建立網站

```bash
python -m tracker.main --site-only
```

## 6. 備份並更新分享的網頁

1. 打包專案：`python -m tracker.backup pack /home/user/frc2027-backup/project.json`
2. 用 Artifact 工具的 `read` 讀一次網站網址（發布前必須先讀過）。
3. 用 Artifact 工具的 `publish`：`url` 填網站網址、`file_path` 填 `/home/user/frc2027-tracker/site/fragment.html`、不要帶 `icon`，
   `files` 填 `{"backup/project.json": {"from": "/home/user/frc2027-backup/project.json", "contentType": "application/json"}}`。
   **備份檔和網頁要在同一次發布，不能只更新網頁**，否則下一次還原會拿到舊資料。

## 7. GitHub（排程不做）

排程開的新工作階段沒有 https://github.com/vincent0926/frc2027-tracker 的推送權限（推送會被代理擋下 403），
所以排程**不要**嘗試同步 GitHub。GitHub 那份副本由使用者在互動工作階段裡手動同步；專案的正式保存位置是 Artifact 的 `backup/project.json`。

## 出錯時

- 第 3 步寫不出分析或檢查一直不通過：執行 `python -m tracker.main --fallback-analysis --date "$TODAY"`，改用規則評分，繼續第 5、6 步。
- 爬蟲整個失敗或測試失敗：不要備份壞掉的資料，不要發布網站；在回覆中寫清楚哪一步、什麼錯誤。
- 結束時用 2～3 句話回報：今天幾則新消息、精選是哪一則（或平靜日）、網站是否已更新。
