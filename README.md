# TOEIC Practice Platform (新制多益線上模擬測驗平台)

專為多益聽力與閱讀模擬練習與家教學生打造的免安裝、即開即練線上全真模考系統。

## 平台特色
- **10 回完整聽力模擬測驗**：每回包含 Part 1（照片描述）、Part 2（應答問題）、Part 3（簡短對話）、Part 4（簡短獨白）共 100 題。
- **10 回完整閱讀模擬測驗**：每回包含 Part 5（單句填空 30 題）、Part 6（短文填空 16 題）、Part 7（閱讀理解 54 題）共 100 題（Q101–Q200），附完整解析與篇章中譯。Part 7 使用 2026-11-18 交付複核後的題庫，單篇、雙篇與三篇文件均保留。
- **雲端音檔串流**：所有聽力音訊檔及題目圖片均託管於 Cloudflare R2，網頁載入迅速，節省頻寬與儲存空間。
- **即時自動評分**：提交後立即顯示各 Part 正確率、答對題數與百分比。
- **錯題快速檢視**：自動標記錯題，並可一鍵跳轉回原題查看題目、解析與正確解答。
- **進度自動儲存**：作答狀態即時保存於瀏覽器 LocalStorage，保留既有 Part 5／6 進度；Part 7 可獨立作答及交卷。三部分皆交卷後顯示全卷成果。不同瀏覽器與兩個站點的紀錄不互通。
- **靜態部署**：閱讀文字與解析直接包含在各回 HTML，無額外 API、資料庫或 Cloudflare 請求。聽力音檔與圖片繼續使用既有 R2，不受這次整合影響。

## 線上體驗
- GitHub Pages：https://roychihcheng.github.io/toeic-listening-practice/
- Vercel 站點：https://toeic-listening-practice.vercel.app/

## 更新閱讀題庫

需要 Python 3.12 或以上；產生網頁僅使用標準函式庫。輸入為核准的完整閱讀 SCORM ZIP（不是 Part 7 分卷），檔名 `TOEIC_Reading_Mock_Test_01.zip` 至 `TOEIC_Reading_Mock_Test_10.zip`。

```bash
python generate_reading_tests.py --source-dir "本機核准題庫資料夾"
python -m unittest discover -s tests -v
```

產生器會檢查各部分題號、四個選項及正解／解析一致性，輸出 `reading1.html` 至 `reading10.html`。可指定 `--output-dir` 先產生至別處檢查；不會改寫聽力頁面或來源 ZIP。正式部署只需推送產生的 HTML 與首頁至本專案 `main`，GitHub Pages 與 Vercel 沿用同一份靜態檔案。

若要把已產生的每一題與本機核准來源再次比對：

```bash
# Bash
TOEIC_SOURCE_DIR="本機核准題庫資料夾" python -m unittest discover -s tests -v
```

瀏覽器煙霧測試另需本機已安裝的 Python Playwright 與 Chromium：先啟動 `python -m http.server 8765 --bind 127.0.0.1`，再執行 `python tests/browser_smoke.py`。可用 `--base-url` 檢查正式站點。測試進度僅寫入隔離的測試瀏覽器，不影響學生紀錄。

此為練習網站：HTML 中含正解與解析，並非具防作弊能力的正式線上考場，也不回傳 LMS 成績。
