# 每日更新流程（給排程執行的 Claude）

每天台灣時間早上約 7 點，排程會開一個新的 Claude 工作階段，照這份文件更新「FRC 2027 情報站」。
全程不需要問使用者問題；遇到無法處理的狀況，照「出錯時」一節處理。

- 網站（Claude Artifact，已分享給隊伍）：https://claude.ai/artifact/S3zmGKK82y9653mdFuYLom
- 日期一律用台灣時間：`TODAY=$(TZ=Asia/Taipei date +%F)`

## 1. 準備

```bash
pip install -q -r requirements.txt
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

欄位：

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
- 只根據資料內容撰寫，不要編造。官方文章摘要不夠時，可以用網頁讀取工具讀原文（使用者代理請用 `frc2027-tracker/0.1`，遵守 robots.txt）。
- 用繁體中文；SystemCore、WPILib、REVLib 等專有名詞保留英文。

寫完後檢查：

```bash
python -m tracker.main --check-analysis --date "$TODAY"
```

有錯就修到通過為止。

## 4. SystemCore 專頁（有新官方資訊時才做）

如果今天有新的 SystemCore 官方資訊（FIRST 部落格、WPILib 文件、SystemCoreTesting repo 的相容表或已知問題有變動），
更新 `data/systemcore.json` 對應的區塊（facts、stats、vendors、gotchas、checklist…），每一條都要附來源網址，
並把 `updated` 改成今天。沒有新官方資訊就不要動這個檔案。

## 5. 建立網站並保存

```bash
python -m tracker.main --site-only
git add -A
git commit -m "每日更新 $TODAY"
git push origin main
```

push 因網路失敗時，依 2、4、8、16 秒間隔重試最多 4 次。

## 6. 更新分享的網頁

1. 用 Artifact 工具的 `read` 讀一次上面的網站網址（發布前必須先讀過）。
2. 用 `publish`，`url` 填上面的網站網址、`file_path` 填 `site/fragment.html`，不要帶 `icon`。

## 出錯時

- 第 3 步寫不出分析或檢查一直不通過：執行 `python -m tracker.main --fallback-analysis --date "$TODAY"`，改用規則評分，繼續第 5、6 步。
- 爬蟲整個失敗或測試失敗：不要 commit 壞掉的資料，不要發布網站；在回覆中寫清楚哪一步、什麼錯誤。
- 結束時用 2～3 句話回報：今天幾則新消息、精選是哪一則（或平靜日）、網站是否已更新。
