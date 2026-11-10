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

## 7. 同步到 GitHub（盡力而為，要在第 6 步成功之後才做）

GitHub repo：https://github.com/vincent0926/frc2027-tracker （`main` 分支）。這一步失敗**不影響**前面已完成的網頁更新與備份，
只要在最後的回報中說明；不要因為這一步重做第 6 步，也不要重試超過一次。

1. 呼叫 `add_repo`（`owner: "vincent0926"`, `repo: "frc2027-tracker"`, `access: "push"`）取得推送權限。**只呼叫工具，不要照它的提示 clone**
   （還原出來的專案資料夾就是要用的內容，不能被覆蓋）。被拒絕就跳過這一步。
2. 把還原出來的專案接上遠端的歷史，再提交並推送：

```bash
cd /home/user/frc2027-tracker
git init -q -b main 2>/dev/null || git init -q
git remote add origin https://github.com/vincent0926/frc2027-tracker 2>/dev/null || true
git fetch -q --depth=1 origin main
git reset -q FETCH_HEAD          # 對齊遠端歷史，工作資料夾內容不變
git add -A
git -c user.name="frc2027-tracker-bot" -c user.email="noreply@users.noreply.github.com" \
    commit -q -m "每日更新 $TODAY" || echo "沒有變動"
git push origin HEAD:main
```

推送失敗因網路時，依 2、4、8 秒間隔重試最多 3 次。

## 出錯時

- 第 3 步寫不出分析或檢查一直不通過：執行 `python -m tracker.main --fallback-analysis --date "$TODAY"`，改用規則評分，繼續第 5、6 步。
- 爬蟲整個失敗或測試失敗：不要備份壞掉的資料，不要發布網站；在回覆中寫清楚哪一步、什麼錯誤。
- 結束時用 2～3 句話回報：今天幾則新消息、精選是哪一則（或平靜日）、網站是否已更新。
