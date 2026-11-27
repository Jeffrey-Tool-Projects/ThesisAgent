# ThesisAgents 全專案程式碼審查

2026-11-27，審查基準為 `dev` 的 `96df260`。**結論為需修正。** 優先處理升級時刪除使用者檔案、論文與 PDF 配錯、識別碼重用、簡報覆寫，以及發布版本與通過 CI 的版本不一致。本次列出 18 項待修問題，其中 6 項列為高優先。文末保留 10 月的報告及其後續結案紀錄。

## 高優先問題

| 編號 | 觸發條件、證據與影響 | 建議修正與驗收方式 |
|---|---|---|
| R01　升級刪除使用者檔案 | Windows 安裝程式只憑目錄名稱與兩個執行檔認定目錄歸它管理，升級時逐項遞迴刪除其中所有名稱未以 `unins` 開頭的項目。使用者若在該目錄保存 PDF、資料庫或匯出結果，升級會一併刪除。由安裝腳本確認。[thesisagents.iss，第 81、97–105 行](packaging/windows/thesisagents.iss#L97) | 依舊版安裝清單移除程式檔。用含舊 DLL、使用者資料庫及子目錄 PDF 的安裝目錄做升級測試，驗證只移除舊 DLL。 |
| R02　重用輸出目錄會配錯 PDF | 下載器只在本批次內處理 BibTeX 鍵碰撞，且把同名非空檔直接判為已下載。離線測試先在共用目錄留下 A 的檔案，再單獨下載同鍵的 B，結果為 `on_disk`，讀回仍是 A 的內容。逐篇簡報的 PDF 門檻因此也會放行 B。[pdf_download.py，第 164–172、194–198 行](thesisagents/core/pdf_download.py#L164) | 將檔案對應到持久的論文身分，命中快取時核對歸屬。應測試分批下載、對調兩篇順序及升級後的既有目錄。 |
| R03　去重會合併有相異 DOI 的論文 | 離線建立 A、B 兩篇各有 DOI 的論文，再加入缺 DOI 的 C。C 的標題、作者、年份吻合 A，arXiv ID 吻合 B。去重最後只保留一筆，同時帶有 A 的 DOI 與 B 的 arXiv ID。在暫存 SQLite 館藏先匯入 A、B，再匯入 C，也從兩列變成一列。這兩個識別碼都可能存在，匯出前各自驗證仍無法辨認配錯。[store.py，第 437、460–475 行](thesisagents/library/store.py#L437)、[dedup.py，第 108–117、169–171 行](thesisagents/core/dedup.py#L108) | 合併前對所有候選者檢查強識別碼衝突，強識別碼匹配優先於標題匹配。用不同的輸入順序驗證兩個 DOI 都保留、兩篇資料各自正確。 |
| R04　舊的館藏編號可編輯另一篇論文 | `papers.id` 使用 SQLite 的 `INTEGER PRIMARY KEY`，新增資料時未指定 ID。暫存館藏實測先刪除編號 1 的 Alpha，再匯入 Beta。Beta 取得編號 1，以舊編號寫給 Alpha 的筆記實際出現在 Beta。持有舊編號的 CLI 或 MCP 使用者亦可能刪錯論文。[schema.py，第 98–99 行](thesisagents/library/schema.py#L98)、[store.py，第 430 行](thesisagents/library/store.py#L430)、[curation_tools.py，第 85–93 行](thesisagents/mcp/curation_tools.py#L85) | 資料庫應配置不重用的公開編號，並考量現有 schema 的升級。測試刪除最大編號後再匯入，確認以舊編號更新或刪除時回報查無資料。 |
| R05　引用鍵碰撞也會覆寫逐篇簡報 | 同作者同年三篇標題依序為 `Gene A`、`Gene C`、`GeneB study`，實測後兩篇都得到 `doe2025geneb`。產鍵函式只計算原始鍵出現次數，未保留已配出的完整鍵。CLI 又直接採用這些鍵作為逐篇簡報檔名，三篇實際匯出後只剩兩個 PPTX，重開共用檔名的簡報，其封面是第三篇。[bibtex.py，第 43–53 行](thesisagents/exporters/bibtex.py#L43)、[cli.py，第 833–845 行](thesisagents/cli.py#L833) | 統一配置引用鍵與輸出檔名，逐一核對最終值是否已配出。以三篇同時匯出，驗證三個唯一引用鍵、三份簡報檔與各自的標題。 |
| R06　通過 CI 的提交與發布內容可能不同 | 發布流程收到提交 A 的 CI 成功事件後 checkout `main`。如果此時 `main` 已前進到 B，版本更新、建置便以 B 為基礎，B 的 CI 可能仍在執行。由工作流程的事件條件、checkout 與推送步驟確認。[release.yml，第 50、67、80、134 行](.github/workflows/release.yml#L67) | checkout 通過 CI 的 `workflow_run.head_sha`，發版前確認遠端分支仍指向該提交，並保留非快轉推送的拒絕機制。用 A 成功、B 已推送但仍在測試的事件順序驗收。 |

## 其他會改變結果或使用者狀態的問題

| 編號 | 證據與影響 | 修正與回歸測試 |
|---|---|---|
| R07　取得 PDF 的方式因入口而異 | CLI 先做摘要，再下載 PDF。遠端摘要直接呼叫 HTTP，出版商拒絕請求時會回傳原論文，即使同一次執行稍後透過 Chrome 成功取得全文，仍缺少摘要。MCP 的全文讀取也進入同一 HTTP 函式。[cli.py，第 600–607 行](thesisagents/cli.py#L600)、[pipeline.py，第 432–435 行](thesisagents/core/pipeline.py#L432)、[pdf.py，第 43–45 行](thesisagents/intelligence/pdf.py#L43) | 摘要優先讀取已取得的 PDF，遠端取得共用同一套出版商路由。以模擬的瀏覽器下載成功結果驗證 CLI 與 MCP 能讀到文字。 |
| R08　PDF 大小上限無法限制下載時的記憶體 | HTTP 路徑先用 `get` 讀完整個回應，才檢查內容長度。即使最後拒絕檔案，每個平行下載仍可能先持有整份過大內容。[pdf_download.py，第 314、326–327 行](thesisagents/core/pdf_download.py#L314)、[pdf.py，第 45、56–57 行](thesisagents/intelligence/pdf.py#L45) | 以串流累計解碼後的位元組數，超限立即關閉。用無長度標頭的離線分段回應測試沒有繼續讀取後續區塊。 |
| R09　混合匯出遺漏沒有 PDF 的搜尋結果 | 查詢同時要求 PPTX 和 XLSX／BibTeX 時，CLI 把能下載 PDF 的子集合傳給所有其他匯出器。若全數下載失敗則提前返回，不會寫出總表。以四篇輸入、三篇可下載的結果執行逐篇匯出，讀回 XLSX 只有三列論文，與總表應保留完整搜尋結果的約定衝突。[cli.py，第 809–829 行](thesisagents/cli.py#L809) | 用原始集合寫總表，只對逐篇簡報套用下載條件。以「兩篇中一篇可下載」及「全不可下載」驗證總表筆數與簡報數。 |
| R10　六個來源提前移除年份不明的論文 | 核心年份篩選保留未知年份，但 arXiv、DBLP、DOAJ、Europe PMC、HAL 與 CORE 的本地篩選會先剔除它們，同一篇可能因來源不同而消失，也失去與其他來源合併補全年份的機會。[pipeline.py，第 342 行](thesisagents/core/pipeline.py#L342)、[arxiv/fetcher.py，第 48、111 行](thesisagents/sources/arxiv/fetcher.py#L111)、[dblp/parser.py，第 51 行](thesisagents/sources/dblp/parser.py#L51) | 各來源的本地篩選共用年份規則。對六個來源各用缺年份 fixture，驗證有年份下限時仍能進入核心合併流程。 |
| R11　文獻匯入失敗後仍留下資料 | CLI 與 MCP 先提交論文和執行紀錄，再驗證並寫入標籤。用暫存 BibTeX 透過 MCP 工具函式匯入一篇且傳入空白標籤，實際回報 `ValueError`，重開資料庫仍看得到新論文與本次執行紀錄。重試會增加另一筆紀錄。[curation_tools.py，第 106–110 行](thesisagents/mcp/curation_tools.py#L106)、[cli_library_edit.py，第 233–236 行](thesisagents/cli_library_edit.py#L233) | 用現有的 `Library.together()` 包住匯入與加標籤，成功提交後才印結果。回歸測試同時斷言論文、標籤及執行紀錄數。 |
| R12　搜尋進行中仍可再按 Enter 啟動工作 | GUI 停用搜尋按鈕後，查詢欄的 Enter 仍直接連到啟動方法。方法未檢查忙碌狀態，兩個背景工作可先後覆寫目前的工作物件，舊查詢較晚完成時可蓋掉新結果或提早開放操作。[search.py，第 167、593、640、701–723 行](thesisagents/gui/pages/search.py#L593) | 所有入口共用忙碌檢查，或讓完成訊號核對目前的工作身分。以延遲工作及兩次 Enter 驗證結果與取消按鈕所屬的查詢。 |
| R13　新增投影片的文字框超出頁面 | 在只有封面的 7.5 吋高簡報新增內文頁，重新開啟實際產出的 PPTX，文字框從 2.8 吋延伸到 8.2 吋。框底超過 7.05 吋頁尾界線，也超過投影片底端，長文可能被裁掉。[pptx_edit.py，第 38、186 行](thesisagents/exporters/pptx_edit.py#L186) | 依實際頁高與頁尾保留區計算可用高度，對只有封面的簡報透過新增頁入口測試所有內容形狀的底部位置。 |
| R14　關閉摘要後部分格式仍輸出原文 | 使用相同論文及 `include_abstract=False` 實際匯出，Markdown 中找不到摘要標記，BibTeX、CSL JSON 與一般 JSON 卻仍含該字串。CLI 的 `--no-abstract` 說明未標示這些例外。[cli.py，第 254–256 行](thesisagents/cli.py#L254)、[bibtex.py，第 85 行](thesisagents/exporters/bibtex.py#L85)、[csljson.py，第 85 行](thesisagents/exporters/csljson.py#L85)、[json_export.py，第 27 行](thesisagents/exporters/json_export.py#L27) | 對各格式套用同一選項。用唯一摘要標記測試輸出內容，包含同批匯出多種格式的情況。 |
| R15　解除安裝移除原已存在的 PATH | 新增 PATH 是可選項，若路徑已存在，安裝程式會略過新增。解除安裝仍會移除符合的項目，沒有紀錄該項是否由本次安裝加入。[thesisagents.iss，第 69、122–138 行](packaging/windows/thesisagents.iss#L122) | 持久記錄安裝程式對 PATH 的修改。測試原有、由安裝新增、未勾選三種情形，驗證解除安裝後保留使用者原設定。 |
| R16　重複結果讓前 K 名的評估偏高 | 評估器先對整份排名去重才取前 K 名。實測排名 `[A, A, B]`、兩篇皆相關、K = 2，輸出 precision 與 recall 都是 1.0，實際前兩個位置只涵蓋一篇相關論文。內建收集器會去重，此問題影響直接傳入重複排名的評估檔。[search_quality.py，第 37–44 行](thesisagents/evaluation/search_quality.py#L37) | 明訂輸入契約並拒絕重複 ID，或保留名次且讓重複命中計零。測試第三名不能補入前兩名計分。 |
| R17　桌面更新提示可能早於安裝檔 | GUI 以 PyPI 版本決定是否提示更新，下載按鈕卻開啟 GitHub 最新正式版。流程先發布 PyPI，才建置並公開 Windows 安裝檔。在建置中或建置失敗時，按鈕可導向舊版。[updates.py，第 61–67 行](thesisagents/core/updates.py#L61)、[update_check.py，第 74 行](thesisagents/gui/update_check.py#L74)、[release.yml，第 197、228、464 行](.github/workflows/release.yml#L197) | 桌面安裝版以已公開且包含安裝檔的版本為準。用套件庫已更新、GitHub 尚未公開新版的狀態測試通知及下載連結。 |
| R18　同來源的並行搜尋分別取得完整速率額度 | 每次搜尋都重新載入 fetcher，每個實例建立一個裝滿初始額度的 token bucket。例如兩個 MCP 搜尋可各自立即送出第一個 Semantic Scholar 請求，無法共同遵守設定的每秒一次、burst 一次。[pipeline.py，第 115 行](thesisagents/core/pipeline.py#L115)、[base.py，第 40、73 行](thesisagents/fetchers/base.py#L40)、[fetcher.py，第 41、93 行](thesisagents/sources/semantic_scholar/fetcher.py#L93) | 依上游服務共享配額，並考量 GUI 工作者使用不同事件迴圈。用可控制的時鐘及兩個搜尋呼叫核對送出時間。 |

## 審查涵蓋與驗證

以 Git 追蹤的 434 個檔案為盤點範圍，311 個 Python 檔案全部通過語法解析，其中套件 180 個、測試 106 個、腳本 23 個，資產與文件各 1 個。人工審查沿著下列入口追蹤實際呼叫與資料流。腳本與工作流程採重點查閱，沒有逐一執行歷史稿件的改寫腳本。

| 範圍 | 核對內容 |
|---|---|
| 搜尋與下載 | CLI、15 個來源外掛的請求與篩選、去重、速率限制、瀏覽器分流、PDF 快取及文字擷取。 |
| 館藏與評估 | SQLite 識別碼、匯入與交易邊界、篩選紀錄、儲存的查詢、PRISMA 計數、離線排名指標。 |
| 輸出與互動 | 逐篇簡報和總表的資料選取、引用鍵、摘要選項、簡報編輯、GUI 搜尋工作生命週期、MCP 工具入口。 |
| 交付 | 設定與使用說明、CI、版本更新、Windows 安裝及解除安裝、桌面更新提示。 |

在暫存目錄實際操作 PDF 快取、BibTeX 匯入、SQLite 刪除後再新增，以及簡報與文獻格式匯出。GUI 測試以離屏視窗連續送出兩個 Enter，攔截執行緒池提交，實際收到兩個工作。另用含文字的單頁 PDF 跑 CLI 的本機輕量模式，程序成功結束，重新開啟的簡報有 5 頁，BibTeX 包含指定標題。MCP 伺服器在本機列出 25 個工具。

在基準提交的乾淨封存副本上，以系統 Python 3.14 與 setuptools 84.0.0 離線建置 wheel。檢查成品包含套件的 180 個 Python 檔、桌面圖示，以及 CLI、GUI、MCP 三個啟動入口。

| 專案檢查 | 本機結果 |
|---|---|
| `.venv/Scripts/python.exe -m pytest tests/ -q` | Windows、Python 3.14.7、Qt 離屏模式。首輪 2,070 項通過、1 項失敗。Windows 字型測試的子程序達到 60 秒逾時，該項單獨重跑通過。[test_app_fonts.py，第 51–69 行](tests/gui/test_app_fonts.py#L51) |
| `.venv/Scripts/python.exe -X utf8 -m pytest tests/ -q` | 同一工作樹完整重跑，2,071 項全數通過，0 項略過，耗時 252.47 秒。 |
| `.venv/Scripts/python.exe -m ruff check .` | 通過。 |
| `.venv/Scripts/python.exe -m bandit -c pyproject.toml -r thesisagents/` | 依專案設定掃描套件，0 項發現，0 個檔案略過。 |

本次未連線執行學術搜尋、學校 VPN 或付費牆下載，未呼叫模型服務，亦未執行正式發布或升級既有安裝。R01、R06、R15、R17 的判斷來自安裝及發布程式碼。投影片的驗證依實際檔案結構與幾何位置，未做 PowerPoint 視覺驗收。

## 2026-10-22 歷史審核紀錄

<details>
<summary>以下保留當時的發現、原始結論，以及 2026-11-26 補登的五項結案狀態。</summary>


## 審核者

- 審核者：工作區程式審核
- 日期：2026-10-22
- 對象：`ThesisAgents`（工作樹熱點：論文搜尋與簡報產生）
- 結論：需修正（2026-11-26 起五項發現皆已關閉）

## 審核規範

共通規範在工作區 repo [JE-Chen/Codes](https://github.com/JE-Chen/Codes) 的 `docs/code-review-standard.md`。下面留下 2026-10-22 這次審核所用的條款，讓審核紀錄的依據對得上那一次。之後的審核以工作區那份為準。本專案更嚴的條款仍以本節與本專案的 `CLAUDE.md` 為準。

本次依下列 10 條審核。更嚴的專案門檻從嚴。

1. 設計：分層、失敗隔離、擴充點是否與 `architecture.md` 一致。
2. 可讀性：圈複雜度不超過 15、函式不超過 80 行、巢狀不超過 4、參數不超過 7、行寬不超過 120。專案若更嚴，以專案為準。
3. 錯誤處理：失敗要有邊界，不可裸吞例外。
4. 死碼：未使用的常數、分支與註解不得冒充已實作的行為。
5. 型別與 docstring：公開邊界要有型別與說明，且說明須與程式一致。
6. 安全：外部 HTTP、金鑰來源與是否寫死、命令注入、檔案路徑穿越。
7. 測試：風險路徑要有對應測試，且測試不能只覆蓋正例。
8. 效能：連線池、速率與併發是否會打爆上游或本機。
9. §6 契約：`architecture.md` 第 6 節的跨專案邊界不得被靜默打破。
10. 文件同步：環境變數、傳輸方式與行為描述須與程式一致。

嚴重度分缺陷、建議、備註。通過指沒有未關閉缺陷。有條件通過指沒有立即損害。需修正指仍有未關閉缺陷。

## 審核紀錄

### 方法

閱讀 `architecture.md`、`CLAUDE.md` 的專案概觀與網路／瀏覽器規則、`progress.md` 前 80 行，以及 `docs/configuration.md` 的環境變數表。在 `thesisagents/` 套件原始碼搜尋 `eval(`、`exec(`、`shell=True`、`pickle`、`yaml.load`、`verify=False`、裸 `except:`、`subprocess`、`api_key`、`password`、`token`，並排除 `tests/`、`docs/_build/`、`__pycache__/`。命中後逐檔閱讀 `fetchers/http.py`、`fetchers/webrunner_browser.py`、`fetchers/webrunner_pdf.py`、`fetchers/rate_limit.py`、`utils/path_safety.py`、`core/pdf_download.py`、`core/pdf_cookies.py`、`core/oa_resolver.py`、`core/identifiers.py`、`core/query.py`、`intelligence/pdf.py`、`intelligence/summarise.py`、`gui/pages/settings.py`、`mcp/server.py`、`exporters/pptx_edit.py`，以及各來源 fetcher 的金鑰與請求組裝。說明文件中的省略號占位不當成可用金鑰。未改其他檔、未執行測試、未啟動程式、未呼叫外部 API。

### 總評

搜尋與匯出的分層清楚：外部 HTTP 集中在 `get_client`，付費牆頁面另走可見 Chrome，匯出檔名有 slug，相對路徑有 `resolve_safe`。套件內沒有寫死的可用金鑰，也沒有命令注入。未關閉的問題是付費牆主機判斷用字串後綴，仿冒網域會被送進可能帶著使用者 Chrome 設定檔的瀏覽器。另有速率註解與實作不符，以及 PDF 第二跳缺少內網位址界限。

### 發現

#### CR-01

- 嚴重度：缺陷
- 位置：`thesisagents/fetchers/webrunner_pdf.py` 第 50 至 69 行、第 83 至 88 行。呼叫點在 `thesisagents/core/pdf_download.py` 第 140 至 142 行。瀏覽器選項在 `thesisagents/fetchers/webrunner_browser.py` 第 76 至 93 行。
- 說明：`should_use_webrunner` 用 `host.endswith(suffix)` 判斷付費牆。後綴沒有要求點邊界，因此 `evilieee.org` 會命中 `ieee.org`，`notacm.org` 會命中 `acm.org`，`notwiley.com`、`notoup.com`、`fakescience.org` 等同理。`pdf_url` 來自 OpenAlex、Semantic Scholar、Unpaywall、CORE，或 MCP `download_pdfs` 的呼叫端，不是固定主機清單。命中後 `download_via_browser` 會以可見 Chrome 開啟該 URL。若設定了 `THESISAGENTS_CHROME_PROFILE_DIR`，這個視窗使用使用者的 Chrome 設定檔，而且 `make_driver` 加上 `--no-sandbox`，PDF 下載偏好又把 Safe Browsing 設為關閉。瀏覽器本身的 cookie 網域比對仍有點邊界，不表示出版商 cookie 一定會被送到仿冒主機。風險是攻擊頁面跑在該設定檔與放寬過的 Chrome 裡。
- 依據：安全（外部 HTTP 與瀏覽器載入的主機範圍）。`architecture.md` 第 6 節要求外部服務只經 `fetchers/http.py` 或可見 Chrome 輔助，主機分類錯誤會把不該走 Chrome 的 URL 送進去。`tests/test_webrunner_pdf.py` 只斷言正例出版商與少數開放主機，沒有仿冒後綴的反例。
- 狀態：已關閉（2026-11-26，U-20261126-02）：比對改為網域本身或其子網域，並補仿冒網域的反例測試。
- 建議：比對改為主機等於後綴，或主機以「點加後綴」結尾。為 `notieee.org` 這類名稱補反例測試。設定檔路徑只在通過比對後才套用。

#### CR-02

- 嚴重度：建議
- 位置：`thesisagents/core/pdf_download.py` 第 1 至 14 行與第 61 至 76、163 行。`thesisagents/core/oa_resolver.py` 第 61 至 68、193 至 207、241 至 253、286 至 300 行。`thesisagents/intelligence/pdf.py` 第 1 至 6、35 至 45 行。`thesisagents/fetchers/http.py` 第 70 至 76 行。`thesisagents/core/constants.py` 第 8 至 10 行。
- 說明：檔案註解寫 PDF 下載與 PDF 文字擷取沿用各來源的 token bucket。bucket 實際只在各 `sources/*/fetcher.py` 送搜尋請求前呼叫 `acquire`。`get_client` 只做 HTTPS 傳輸、逾時與連線池，`AsyncHTTPTransport(retries=0)`。`HTTP_MAX_RETRIES` 與 `HTTP_BACKOFF_BASE_SECONDS` 沒有其他讀取點，屬死碼。OA 解析另用 `unpaywall`、`semantic_scholar_oa`、`core_ac_uk` 三個 client 鍵，併發上限 5，不進入 Semantic Scholar 搜尋那條每秒 1 次的 bucket。PDF 下載併發上限 4，同樣不取得 bucket。`docs/configuration.md` 寫有金鑰時 Semantic Scholar 可到每秒 10 次、NCBI 可到每秒 10 次，對應 fetcher 仍固定每秒 1 次與每秒 3 次。這兩處程式比文件保守，不會因此超速。超速風險在 OA 與 PDF 這兩條旁路。
- 依據：死碼、文件與 docstring 不一致、效能與上游禮貌使用。搜尋路徑的 429 仍由 `core/pipeline.py` 做有限次退避，故不列為缺陷。
- 狀態：已關閉（2026-11-26，U-20261126-02）：更正註解與文件數字、刪除未使用的重試常數，PDF 下載加上每個主機最多 2 個併發。OA 解析的 Semantic Scholar 查詢維持現狀，它只在 Unpaywall 查無結果後執行，併發上限 5，遇 429 會改用其他來源。
- 建議：讓 PDF、OA 與文字擷取走與該上游相同的 bucket，或改寫註解，刪除未使用的重試常數。文件上的每秒 10 次若尚未實作，應改成與 `RateLimit` 相同的數字。

#### CR-03

- 嚴重度：建議
- 位置：`thesisagents/core/pdf_download.py` 第 171 至 178、196 至 211、249 至 266 行。`thesisagents/intelligence/pdf.py` 第 35 至 45 行。`thesisagents/mcp/server.py` 的 `fetch_pdf_text`（約第 231 至 245 行）。
- 說明：第一個 `pdf_url` 若不是付費牆主機，以及 HTML 裡 `citation_pdf_url` 的第二跳，都直接 `client.get`。第二跳用 `urljoin` 接上頁面給的位址，不再呼叫 `should_use_webrunner`。`HttpsOnlyTransport` 會拒絕非 HTTPS，包含重新導向後的非 HTTPS，這一點已讀過 `fetchers/http.py` 第 27 至 34 行。傳輸層不拒絕 loopback、鏈路本機或私有網段上的 HTTPS。cookie 只在 `pdf_cookies._domain_matches` 認為網域相符時附加，比對有前導點，沒有 CR-01 那種無點邊界的後綴錯誤。這不能阻止對使用者本機能連上的內網 HTTPS 服務發請求。MCP `fetch_pdf_text` 的 URL 由呼叫端給定，範圍相同。
- 依據：安全（外部 HTTP 的目標範圍）。公開 OA 主機不應整表封鎖，故不升為缺陷。
- 狀態：已關閉（2026-11-26，U-20261126-02）：傳輸層拒絕本機與私有網段的位址（含重新導向後），第二跳的付費牆網址改走 Chrome。只檢查位址字面值，不檢查名稱解析結果，因為學校代理伺服器常有私有位址。
- 建議：在送出前拒絕非 HTTPS，以及 loopback、鏈路本機與私有網段。第二跳若主機屬於付費牆清單，應與第一跳使用同一條瀏覽器路徑。

#### CR-04

- 嚴重度：建議
- 位置：`thesisagents/fetchers/webrunner_browser.py` 第 76 至 93 行。`thesisagents/sources/scholar/webrunner_backend.py` 第 97 至 114 行的 `_build_chrome_args` 同樣列出 `--no-sandbox`，實際啟動仍走 `make_driver`。
- 說明：每一個 Chrome 都加上 `--no-sandbox`。PDF 下載把 `safebrowsing.enabled` 設為 False。兩處都沒有說明為何使用者桌面上的可見視窗也要關掉沙箱與 Safe Browsing。此視窗會開啟出版商頁面，並在設定了 `THESISAGENTS_CHROME_PROFILE_DIR` 時載入該設定檔。CR-01 修正主機比對之後，這項放寬仍然存在。
- 依據：安全（瀏覽器載入外部頁面時的隔離）。未看到 `shell=True` 或把使用者字串拼進 shell，故不把這項寫成命令注入。
- 狀態：已關閉（2026-11-26，U-20261126-02）：`--no-sandbox` 只在 Linux root 使用，PDF 下載不再關閉 Safe Browsing，Scholar 的重複參數清單已刪除。
- 建議：桌面路徑不要加 `--no-sandbox`，除非有註明僅限無法使用沙箱的環境。PDF 下載不要關掉 Safe Browsing。若必須保留，在 `make_driver` 的 docstring 寫明失敗模式與適用範圍。

#### CR-05

- 嚴重度：備註
- 位置：`thesisagents/fetchers/http.py` 第 61 至 67 行。`docs/configuration.md` 環境變數表中 `THESISAGENTS_CONTACT_EMAIL` 那一列（約第 37 行）。
- 說明：預設 User-Agent 寫死「set THESISAGENTS_CONTACT」。程式與 `docs/configuration.md`、`architecture.md` 使用的名稱是 `THESISAGENTS_CONTACT_EMAIL`，而且 User-Agent 並不讀取該變數。郵件實際由 OpenAlex、Crossref、ACM 的 `mailto`、PubMed 的 `email` 查詢參數，以及 Unpaywall 的 `email` 參數送出。同一列文件把 NCBI 的 `tool` 與 `email` 寫成標頭。`thesisagents/sources/pubmed/fetcher.py` 第 98 至 102 行把它們放在查詢參數，這與 E-utilities 的用法一致，是文件用詞錯誤，不是多送了一份金鑰。
- 依據：文件同步。不外洩金鑰，也不改變 HTTPS 限制。
- 狀態：已關閉（2026-11-26，U-20261126-02）：User-Agent 不再提到錯誤的變數名稱，文件改為查詢參數。
- 建議：User-Agent 改為真實的變數名稱，或在有設定聯絡郵件時放入郵件。文件改為查詢參數。

沒有其他已確認的缺陷。命令注入、寫死可用金鑰、路徑穿越未成立，見下方已核對。

### 已核對

- 金鑰來源：Anthropic、Semantic Scholar、NCBI、IEEE、Springer、Crossref Plus、CORE 都在使用當下從環境變數讀取。GUI 的 `thesisagents/gui/pages/settings.py` 把同一批值存進本機 QSettings，啟動時寫回 `os.environ`。`docs/configuration.md` 已寫明 Windows 登錄、macOS plist 與 Linux ini 的位置，介面文案也寫本機儲存。這是明文使用者設定，不是原始碼裡的可用金鑰。空字串會清掉環境變數。說明文件裡的 Anthropic 範例是省略號占位，不當缺陷。
- 金鑰放置：Semantic Scholar 與 OA 的 S2 查詢使用 `x-api-key`。CORE 與 Crossref Plus 使用標頭。Anthropic 金鑰交給官方客戶端。IEEE、Springer、NCBI 依上游介面把金鑰放在查詢參數。套件日誌沒有主動印出這些值。4xx 會把回應本文前 256 字元放進例外。本次未看到上游一定會把查詢字串回顯，故不列缺陷。
- 傳輸：套件內的 `httpx` 呼叫都經過 `get_client`。`HttpsOnlyTransport` 拒絕非 `https`。`follow_redirects=True` 時，後續請求仍經過同一層包裝。未看到 `verify=False`、`requests`、`urlopen`。arXiv 與 PubMed 的 XML 使用 `defusedxml`。
- 命令注入：套件內沒有 `subprocess`、`shell=True`、`os.system`、`pickle`、`yaml.load` 或裸 `except:`。`gui/app.py` 的 `app.exec()` 是 Qt 事件迴圈。IEEE 的 `execute_async_script` 把 URL 與 JSON 當引數傳入，沒有把使用者關鍵字拼進腳本文字。Scholar 查詢使用 `urlencode`。Chrome 參數是固定清單，設定檔路徑是單一 `add_argument`，不是 shell。`scripts/migrate_sources_into_package.py` 的 `subprocess.run` 接收字串清單且不在安裝套件內，不列缺陷。
- 路徑：`resolve_safe` 拒絕絕對路徑、`..` 與解析後逃出根目錄的符號連結。匯出檔名經 `safe_filename`，斜線與 `..` 進不了檔名。`ensure_export_dir` 允許呼叫端指定的輸出目錄，這是 CLI 與 MCP 的輸出位置，不是把相對路徑拼進根目錄。`pptx_edit` 依呼叫端給的路徑開關簡報，屬本機編輯工具的設計。
- 輸入：關鍵字經 `normalize_query` 去掉控制字元並限制長度。DOI、PMID、arXiv、IEEE 編號在 `identifiers.py` 有格式判斷後才分派。
- 錯誤處理：廣泛的 `except Exception` 多半帶 `BLE001` 與邊界理由（單一來源失敗不拖垮整批、PDF 與 OA 為盡力而為）。不是裸 `except:`。
- §6：沒有依賴工作區的 WebRunner 套件。Selenium 由 `webrunner_browser.py` 每個呼叫各開一個 Chrome。除 CR-01 的主機分類外，外部服務仍只經共用 HTTP client 或該瀏覽器輔助。
- `progress.md` 前 80 行只有未完成的評測集與 Nuitka 快取兩項，與本次熱點無直接衝突。

### 未涵蓋

- 未執行 pytest、ruff、bandit，也未逐函式計算圈複雜度與行數。`thesisagents/exporters/pptx.py` 體積大，不在本次 HTTP 與路徑熱點的逐行範圍。
- 未對照已安裝的 httpx 是否在標頭含換行時拒絕請求，因此不對 cookie 值拼進 `Cookie` 標頭下結論。
- 未審查 `docs/_build/`、測試假金鑰、以及 `scripts/` 裡簡報維護腳本的簡報內容。
- 未連線驗證各上游是否在錯誤本文回顯查詢字串。

### 本專案加嚴

`pyproject.toml` 的 ruff 行寬是 100，McCabe 上限是 10，都嚴於本規範的 120 與 15。本次未跑 linter，不宣稱全套件達標。網路與路徑另有專案自己的約定：全部 HTTP 走 `get_client`、付費牆走可見 Chrome、匯出檔名走 `safe_filename`。CR-01 與 CR-02 就是對照這些約定後的差距。

### 結論

需修正。發現 5 則：缺陷 1（CR-01，未關閉）、建議 3（CR-02、CR-03、CR-04）、備註 1（CR-05）。沒有寫死的可用金鑰，套件內也沒有命令注入或已成立的路徑穿越。CR-01 未關，故不能通過，也不能有條件通過。

</details>
