"""GUI label translations across all 14 supported languages.

Separate from ``thesisagents/exporters/i18n.py`` so the slide-deck
i18n table (which the test suite enforces 14-language coverage for)
and the UI labels can evolve independently — but the language set
is intentionally identical so users see one consistent menu.

Adding a new key: extend ``_LABELS`` with one entry. The test in
``tests/gui/test_i18n.py`` enforces every key has every language;
that catches a missing translation at PR time, not at runtime.
"""

from __future__ import annotations

from typing import Final

DEFAULT_LANGUAGE: Final[str] = "en"
SUPPORTED_LANGUAGES: Final[tuple[str, ...]] = (
    "en",
    "zh-tw",
    "zh-cn",
    "ja",
    "es",
    "fr",
    "de",
    "ko",
    "pt",
    "ru",
    "it",
    "vi",
    "hi",
    "id",
)

# Display name of the Material 3 GUI style. It is a product name that stays
# the same in every language, so the settings label for every locale reads
# it from here instead of repeating the literal per language.
_MATERIAL_3_STYLE_NAME: Final[str] = "Material 3"

# Human-readable language name to display in the UI language dropdown.
LANGUAGE_DISPLAY_NAMES: Final[dict[str, str]] = {
    "en": "English",
    "zh-tw": "繁體中文",
    "zh-cn": "简体中文",
    "ja": "日本語",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "ko": "한국어",
    "pt": "Português",
    "ru": "Русский",
    "it": "Italiano",
    "vi": "Tiếng Việt",
    "hi": "हिन्दी",
    "id": "Bahasa Indonesia",
}

_LABELS: Final[dict[str, dict[str, str]]] = {
    # Window + nav ----------------------------------------------------
    "app.title": {
        "en": "ThesisAgents",
        "zh-tw": "ThesisAgents",
        "zh-cn": "ThesisAgents",
        "ja": "ThesisAgents",
        "es": "ThesisAgents",
        "fr": "ThesisAgents",
        "de": "ThesisAgents",
        "ko": "ThesisAgents",
        "pt": "ThesisAgents",
        "ru": "ThesisAgents",
        "it": "ThesisAgents",
        "vi": "ThesisAgents",
        "hi": "ThesisAgents",
        "id": "ThesisAgents",
    },
    "nav.search": {
        "en": "Search",
        "zh-tw": "搜尋",
        "zh-cn": "搜索",
        "ja": "検索",
        "es": "Buscar",
        "fr": "Rechercher",
        "de": "Suchen",
        "ko": "검색",
        "pt": "Pesquisar",
        "ru": "Поиск",
        "it": "Cerca",
        "vi": "Tìm kiếm",
        "hi": "खोज",
        "id": "Cari",
    },
    "nav.enrich": {
        "en": "Enrich",
        "zh-tw": "豐富化",
        "zh-cn": "丰富化",
        "ja": "強化",
        "es": "Enriquecer",
        "fr": "Enrichir",
        "de": "Anreichern",
        "ko": "보강",
        "pt": "Enriquecer",
        "ru": "Обогащение",
        "it": "Arricchisci",
        "vi": "Làm giàu",
        "hi": "समृद्ध करें",
        "id": "Perkaya",
    },
    "nav.deck": {
        "en": "Deck",
        "zh-tw": "投影片",
        "zh-cn": "幻灯片",
        "ja": "スライド",
        "es": "Diapositivas",
        "fr": "Diapos",
        "de": "Folien",
        "ko": "슬라이드",
        "pt": "Slides",
        "ru": "Слайды",
        "it": "Diapositive",
        "vi": "Slide",
        "hi": "स्लाइड",
        "id": "Slide",
    },
    "nav.settings": {
        "en": "Settings",
        "zh-tw": "設定",
        "zh-cn": "设置",
        "ja": "設定",
        "es": "Ajustes",
        "fr": "Paramètres",
        "de": "Einstellungen",
        "ko": "설정",
        "pt": "Configurações",
        "ru": "Настройки",
        "it": "Impostazioni",
        "vi": "Cài đặt",
        "hi": "सेटिंग्स",
        "id": "Pengaturan",
    },
    # Search page — inputs --------------------------------------------
    "search.query_label": {
        "en": "Query",
        "zh-tw": "查詢關鍵字",
        "zh-cn": "查询关键词",
        "ja": "検索キーワード",
        "es": "Consulta",
        "fr": "Requête",
        "de": "Suchbegriff",
        "ko": "검색어",
        "pt": "Consulta",
        "ru": "Запрос",
        "it": "Query",
        "vi": "Truy vấn",
        "hi": "क्वेरी",
        "id": "Kueri",
    },
    "search.query_placeholder": {
        "en": "e.g. transformer attention",
        "zh-tw": "例如:transformer attention",
        "zh-cn": "例如:transformer attention",
        "ja": "例:transformer attention",
        "es": "p. ej. transformer attention",
        "fr": "p. ex. transformer attention",
        "de": "z. B. transformer attention",
        "ko": "예: transformer attention",
        "pt": "p. ex. transformer attention",
        "ru": "напр. transformer attention",
        "it": "es. transformer attention",
        "vi": "vd. transformer attention",
        "hi": "उदा. transformer attention",
        "id": "mis. transformer attention",
    },
    "search.sources_label": {
        "en": "Sources",
        "zh-tw": "資料來源",
        "zh-cn": "数据来源",
        "ja": "ソース",
        "es": "Fuentes",
        "fr": "Sources",
        "de": "Quellen",
        "ko": "출처",
        "pt": "Fontes",
        "ru": "Источники",
        "it": "Fonti",
        "vi": "Nguồn",  # NOSONAR translation, matching words in other keys are not one constant
        "hi": "स्रोत",  # NOSONAR translation, matching words in other keys are not one constant
        "id": "Sumber",
    },
    "search.language_label": {
        "en": "Slide language",
        "zh-tw": "投影片語言",
        "zh-cn": "幻灯片语言",
        "ja": "スライドの言語",
        "es": "Idioma de las diapositivas",
        "fr": "Langue des diapositives",
        "de": "Foliensprache",
        "ko": "슬라이드 언어",
        "pt": "Idioma dos slides",
        "ru": "Язык слайдов",
        "it": "Lingua delle diapositive",
        "vi": "Ngôn ngữ slide",
        "hi": "स्लाइड भाषा",
        "id": "Bahasa slide",
    },
    "search.max_results_label": {
        "en": "Max results per source",
        "zh-tw": "每個來源的最多結果數",
        "zh-cn": "每个来源的最多结果数",
        "ja": "ソースごとの最大結果数",
        "es": "Resultados máximos por fuente",
        "fr": "Résultats maximum par source",
        "de": "Maximale Ergebnisse pro Quelle",
        "ko": "출처당 최대 결과 수",
        "pt": "Resultados máximos por fonte",
        "ru": "Макс. результатов на источник",
        "it": "Risultati massimi per fonte",
        "vi": "Số kết quả tối đa mỗi nguồn",
        "hi": "प्रति स्रोत अधिकतम परिणाम",
        "id": "Hasil maks per sumber",
    },
    "search.top_tier_only": {
        "en": "Top-tier venues only",
        "zh-tw": "僅頂級會議 / 期刊",
        "zh-cn": "仅顶级会议 / 期刊",
        "ja": "トップ会議 / 学術誌のみ",
        "es": "Solo eventos de primer nivel",
        "fr": "Conférences / revues de premier plan uniquement",
        "de": "Nur Top-Tier-Veranstaltungsorte",
        "ko": "최상위 학회 / 저널만",
        "pt": "Apenas eventos de primeiro nível",
        "ru": "Только топовые конференции / журналы",
        "it": "Solo sedi di alto livello",
        "vi": "Chỉ hội thảo / tạp chí hàng đầu",
        "hi": "केवल शीर्ष श्रेणी के स्थान",
        "id": "Hanya tempat papan atas",
    },
    "search.year_from": {
        "en": "Year from",
        "zh-tw": "起始年份",
        "zh-cn": "起始年份",
        "ja": "開始年",
        "es": "Año desde",
        "fr": "Année de début",
        "de": "Jahr ab",
        "ko": "시작 연도",
        "pt": "Ano de",
        "ru": "Год с",
        "it": "Anno da",
        "vi": "Năm từ",
        "hi": "वर्ष से",
        "id": "Tahun dari",
    },
    "search.year_to": {
        "en": "Year to",
        "zh-tw": "結束年份",
        "zh-cn": "结束年份",
        "ja": "終了年",
        "es": "Año hasta",
        "fr": "Année de fin",
        "de": "Jahr bis",
        "ko": "종료 연도",
        "pt": "Ano até",
        "ru": "Год по",
        "it": "Anno a",
        "vi": "Năm đến",
        "hi": "वर्ष तक",
        "id": "Tahun sampai",
    },
    "search.search_button": {
        "en": "Search",
        "zh-tw": "搜尋",
        "zh-cn": "搜索",
        "ja": "検索",
        "es": "Buscar",
        "fr": "Rechercher",
        "de": "Suchen",
        "ko": "검색",
        "pt": "Pesquisar",
        "ru": "Искать",
        "it": "Cerca",
        "vi": "Tìm kiếm",
        "hi": "खोजें",  # NOSONAR translation, matching words in other keys are not one constant
        "id": "Cari",
    },
    "search.export_button": {
        "en": "Export…",
        "zh-tw": "匯出…",
        "zh-cn": "导出…",
        "ja": "エクスポート…",
        "es": "Exportar…",
        "fr": "Exporter…",
        "de": "Exportieren…",
        "ko": "내보내기…",
        "pt": "Exportar…",
        "ru": "Экспорт…",  # NOSONAR translation, matching words in other keys are not one constant
        "it": "Esporta…",
        "vi": "Xuất…",
        "hi": "निर्यात…",
        "id": "Ekspor…",
    },
    "search.export_dialog_title": {
        "en": "Choose export directory",
        "zh-tw": "選擇匯出資料夾",
        "zh-cn": "选择导出文件夹",
        "ja": "エクスポート先のフォルダを選択",
        "es": "Elija el directorio de exportación",
        "fr": "Choisir le dossier d'exportation",
        "de": "Exportverzeichnis auswählen",
        "ko": "내보내기 폴더 선택",
        "pt": "Escolha a pasta de exportação",
        "ru": "Выберите папку для экспорта",
        "it": "Scegli la cartella di esportazione",
        "vi": "Chọn thư mục xuất",
        "hi": "निर्यात फ़ोल्डर चुनें",
        "id": "Pilih folder ekspor",
    },
    # Search page — status / errors -----------------------------------
    "search.status_idle": {
        "en": "Idle.",
        "zh-tw": "閒置中。",
        "zh-cn": "空闲。",
        "ja": "待機中。",
        "es": "Inactivo.",
        "fr": "Inactif.",
        "de": "Bereit.",
        "ko": "대기 중.",
        "pt": "Ocioso.",
        "ru": "Ожидание.",
        "it": "Inattivo.",
        "vi": "Chờ.",
        "hi": "निष्क्रिय।",
        "id": "Diam.",
    },
    "search.status_running": {
        "en": "Searching…",
        "zh-tw": "搜尋中…",
        "zh-cn": "搜索中…",
        "ja": "検索中…",
        "es": "Buscando…",
        "fr": "Recherche…",
        "de": "Suche läuft…",
        "ko": "검색 중…",
        "pt": "Pesquisando…",
        "ru": "Идёт поиск…",
        "it": "Ricerca in corso…",
        "vi": "Đang tìm…",
        "hi": "खोज रहे हैं…",
        "id": "Mencari…",
    },
    "search.status_done": {
        "en": "Found {count} paper(s).",
        "zh-tw": "找到 {count} 篇論文。",
        "zh-cn": "找到 {count} 篇论文。",
        "ja": "{count} 件の論文が見つかりました。",
        "es": "Se encontraron {count} artículo(s).",
        "fr": "{count} article(s) trouvé(s).",
        "de": "{count} Paper gefunden.",
        "ko": "{count}개의 논문을 찾았습니다.",
        "pt": "{count} artigo(s) encontrado(s).",
        "ru": "Найдено статей: {count}.",
        "it": "Trovati {count} articolo/i.",
        "vi": "Tìm thấy {count} bài báo.",
        "hi": "{count} शोधपत्र मिले।",
        "id": "Ditemukan {count} makalah.",
    },
    # Appended to the line above: what each source returned for this query,
    # e.g. "Sources: arxiv 23, openalex 25, ieee (failed)". The three words
    # below mark a source that contributed nothing for a reason other than
    # "no match".
    "search.sources_summary": {
        "en": "Sources: {summary}",
        "zh-tw": "來源: {summary}",
        "zh-cn": "来源: {summary}",
        "ja": "ソース: {summary}",
        "es": "Fuentes: {summary}",
        "fr": "Sources : {summary}",
        "de": "Quellen: {summary}",
        "ko": "소스: {summary}",
        "pt": "Fontes: {summary}",
        "ru": "Источники: {summary}",
        "it": "Fonti: {summary}",
        "vi": "Nguồn: {summary}",
        "hi": "स्रोत: {summary}",
        "id": "Sumber: {summary}",
    },
    "search.source_failed": {
        "en": "failed",
        "zh-tw": "失敗",
        "zh-cn": "失败",
        "ja": "失敗",
        "es": "falló",
        "fr": "échec",
        "de": "fehlgeschlagen",
        "ko": "실패",
        "pt": "falhou",
        "ru": "ошибка",
        "it": "fallita",
        "vi": "lỗi",
        "hi": "विफल",
        "id": "gagal",
    },
    "search.source_rate_limited": {
        "en": "rate limited",
        "zh-tw": "被限流",
        "zh-cn": "被限流",
        "ja": "レート制限",
        "es": "límite de peticiones",
        "fr": "débit limité",
        "de": "Ratenlimit",
        "ko": "요청 제한",
        "pt": "limite de requisições",
        "ru": "лимит запросов",
        "it": "limite di richieste",
        "vi": "bị giới hạn tốc độ",
        "hi": "rate limit",
        "id": "kena batas laju",
    },
    "search.source_disabled": {
        "en": "disabled",
        "zh-tw": "未啟用",
        "zh-cn": "未启用",
        "ja": "無効",
        "es": "desactivada",
        "fr": "désactivée",
        "de": "deaktiviert",
        "ko": "비활성",
        "pt": "desativada",
        "ru": "отключён",
        "it": "disattivata",
        "vi": "đã tắt",
        "hi": "बंद",
        "id": "nonaktif",
    },
    "search.snowball_label": {
        "en": "Citation snowball",
        "zh-tw": "引用滾雪球",
        "zh-cn": "引用滚雪球",
        "ja": "引用スノーボール",
        "es": "Bola de nieve por citas",
        "fr": "Boule de neige par citations",
        "de": "Zitations-Schneeball",
        "ko": "인용 스노볼",
        "pt": "Bola de neve por citações",
        "ru": "Снежный ком по цитированиям",
        "it": "Palla di neve per citazioni",
        "vi": "Lăn cầu tuyết theo trích dẫn",
        "hi": "Citation snowball",
        "id": "Bola salju sitasi",
    },
    "search.snowball_off": {
        "en": "Off",
        "zh-tw": "關閉",
        "zh-cn": "关闭",
        "ja": "オフ",
        "es": "Desactivada",
        "fr": "Désactivée",
        "de": "Aus",
        "ko": "끔",
        "pt": "Desativada",
        "ru": "Выключено",
        "it": "Disattivata",
        "vi": "Tắt",
        "hi": "बंद",
        "id": "Mati",
    },
    "search.snowball_references": {
        "en": "References (what the top results cite)",
        "zh-tw": "參考文獻 (前幾筆結果引用的文獻)",
        "zh-cn": "参考文献 (前几条结果引用的文献)",
        "ja": "参考文献 (上位の結果が引用する文献)",
        "es": "Referencias (lo que citan los primeros resultados)",
        "fr": "Références (ce que citent les premiers résultats)",
        "de": "Referenzen (was die obersten Ergebnisse zitieren)",
        "ko": "참고문헌 (상위 결과가 인용한 문헌)",
        "pt": "Referências (o que os primeiros resultados citam)",
        "ru": "Ссылки (что цитируют верхние результаты)",
        "it": "Riferimenti (ciò che citano i primi risultati)",
        "vi": "Tài liệu tham khảo (những gì các kết quả đầu trích dẫn)",
        "hi": "References (शीर्ष परिणाम जिन्हें cite करते हैं)",
        "id": "Referensi (yang disitasi hasil teratas)",
    },
    "search.snowball_cited_by": {
        "en": "Cited by (what cites them)",
        "zh-tw": "被引用 (引用它們的文獻)",
        "zh-cn": "被引用 (引用它们的文献)",
        "ja": "被引用 (それらを引用する文献)",
        "es": "Citado por (lo que los cita)",
        "fr": "Cité par (ce qui les cite)",
        "de": "Zitiert von (was sie zitiert)",
        "ko": "피인용 (그것들을 인용한 문헌)",
        "pt": "Citado por (o que os cita)",
        "ru": "Цитируется (что цитирует их)",
        "it": "Citato da (ciò che li cita)",
        "vi": "Được trích dẫn bởi (những gì trích dẫn chúng)",
        "hi": "Cited by (जो उन्हें cite करते हैं)",
        "id": "Disitasi oleh (yang menyitasi mereka)",
    },
    "search.snowball_both": {
        "en": "Both directions",
        "zh-tw": "兩個方向",
        "zh-cn": "两个方向",
        "ja": "両方向",
        "es": "Ambas direcciones",
        "fr": "Les deux sens",
        "de": "Beide Richtungen",
        "ko": "양방향",
        "pt": "Ambas as direções",
        "ru": "Оба направления",
        "it": "Entrambe le direzioni",
        "vi": "Cả hai chiều",
        "hi": "दोनों दिशाएँ",
        "id": "Kedua arah",
    },
    "search.snowball_summary": {
        "en": "Snowball: {count} new.",
        "zh-tw": "滾雪球: 新增 {count} 篇。",
        "zh-cn": "滚雪球: 新增 {count} 篇。",
        "ja": "スノーボール: 新規 {count} 件。",
        "es": "Bola de nieve: {count} nuevos.",
        "fr": "Boule de neige : {count} nouveaux.",
        "de": "Schneeball: {count} neu.",
        "ko": "스노볼: 새 논문 {count}편.",
        "pt": "Bola de neve: {count} novos.",
        "ru": "Снежный ком: новых {count}.",
        "it": "Palla di neve: {count} nuovi.",
        "vi": "Lăn cầu tuyết: {count} bài mới.",
        "hi": "Snowball: {count} नए।",
        "id": "Bola salju: {count} baru.",
    },
    "search.library_label": {
        "en": "Library",
        "zh-tw": "文獻庫",
        "zh-cn": "文献库",
        "ja": "ライブラリ",
        "es": "Biblioteca",
        "fr": "Bibliothèque",
        "de": "Bibliothek",
        "ko": "라이브러리",
        "pt": "Biblioteca",
        "ru": "Библиотека",
        "it": "Biblioteca",
        "vi": "Thư viện",
        "hi": "Library",
        "id": "Pustaka",
    },
    "search.library_placeholder": {
        "en": "Library file (optional), e.g. thesis.db",
        "zh-tw": "文獻庫檔案 (選填),例如 thesis.db",
        "zh-cn": "文献库文件 (可选),例如 thesis.db",
        "ja": "ライブラリファイル (任意)、例: thesis.db",
        "es": "Archivo de biblioteca (opcional), p. ej. thesis.db",
        "fr": "Fichier de bibliothèque (facultatif), p. ex. thesis.db",
        "de": "Bibliotheksdatei (optional), z. B. thesis.db",
        "ko": "라이브러리 파일 (선택), 예: thesis.db",
        "pt": "Arquivo de biblioteca (opcional), p. ex. thesis.db",
        "ru": "Файл библиотеки (необязательно), например thesis.db",
        "it": "File della biblioteca (facoltativo), es. thesis.db",
        "vi": "Tệp thư viện (tùy chọn), ví dụ thesis.db",
        "hi": "Library file (वैकल्पिक), जैसे thesis.db",
        "id": "File pustaka (opsional), mis. thesis.db",
    },
    "search.library_browse": {
        "en": "Browse…",  # NOSONAR translation, matching words in other keys are not one constant
        "zh-tw": "瀏覽…",
        "zh-cn": "浏览…",
        "ja": "参照…",
        "es": "Examinar…",  # NOSONAR translation, matching words in other keys are not one constant
        "fr": (
            "Parcourir…"  # NOSONAR translation, matching words in other keys are not one constant
        ),
        "de": (
            "Durchsuchen…"  # NOSONAR translation, matching words in other keys are not one constant
        ),
        "ko": "찾아보기…",  # NOSONAR translation, matching words in other keys are not one constant
        "pt": "Procurar…",  # NOSONAR translation, matching words in other keys are not one constant
        "ru": "Обзор…",  # NOSONAR translation, matching words in other keys are not one constant
        "it": "Sfoglia…",  # NOSONAR translation, matching words in other keys are not one constant
        "vi": "Duyệt…",  # NOSONAR translation, matching words in other keys are not one constant
        "hi": "Browse…",
        "id": "Telusuri…",  # NOSONAR translation, matching words in other keys are not one constant
    },
    "search.library_dialog_title": {
        "en": "Choose a library file",
        "zh-tw": "選擇文獻庫檔案",
        "zh-cn": "选择文献库文件",
        "ja": "ライブラリファイルを選択",
        "es": "Elegir un archivo de biblioteca",
        "fr": "Choisir un fichier de bibliothèque",
        "de": "Bibliotheksdatei wählen",
        "ko": "라이브러리 파일 선택",
        "pt": "Escolher um arquivo de biblioteca",
        "ru": "Выберите файл библиотеки",
        "it": "Scegli un file della biblioteca",
        "vi": "Chọn tệp thư viện",
        "hi": "Library file चुनें",
        "id": "Pilih file pustaka",
    },
    "search.library_add": {
        "en": "Add results to the library",
        "zh-tw": "把結果加入文獻庫",
        "zh-cn": "把结果加入文献库",
        "ja": "結果をライブラリに追加",
        "es": "Añadir los resultados a la biblioteca",
        "fr": "Ajouter les résultats à la bibliothèque",
        "de": "Ergebnisse zur Bibliothek hinzufügen",
        "ko": "결과를 라이브러리에 추가",
        "pt": "Adicionar os resultados à biblioteca",
        "ru": "Добавлять результаты в библиотеку",
        "it": "Aggiungi i risultati alla biblioteca",
        "vi": "Thêm kết quả vào thư viện",
        "hi": "Results को library में जोड़ें",
        "id": "Tambahkan hasil ke pustaka",
    },
    "search.library_search_button": {
        "en": "Search library",
        "zh-tw": "搜尋文獻庫",
        "zh-cn": "搜索文献库",
        "ja": "ライブラリを検索",
        "es": "Buscar en la biblioteca",
        "fr": "Chercher dans la bibliothèque",
        "de": "Bibliothek durchsuchen",
        "ko": "라이브러리 검색",
        "pt": "Buscar na biblioteca",
        "ru": "Искать в библиотеке",
        "it": "Cerca nella biblioteca",
        "vi": "Tìm trong thư viện",
        "hi": "Library में खोजें",
        "id": "Cari di pustaka",
    },
    "search.library_added": {
        "en": "Library: {added} added, {merged} already there.",
        "zh-tw": "文獻庫: 新增 {added} 篇,已有 {merged} 篇。",
        "zh-cn": "文献库: 新增 {added} 篇,已有 {merged} 篇。",
        "ja": "ライブラリ: 追加 {added} 件、既存 {merged} 件。",
        "es": "Biblioteca: {added} añadidos, {merged} ya estaban.",
        "fr": "Bibliothèque : {added} ajoutés, {merged} déjà présents.",
        "de": "Bibliothek: {added} hinzugefügt, {merged} schon vorhanden.",
        "ko": "라이브러리: {added}편 추가, {merged}편은 이미 있음.",
        "pt": "Biblioteca: {added} adicionados, {merged} já estavam.",
        "ru": "Библиотека: добавлено {added}, уже было {merged}.",
        "it": "Biblioteca: {added} aggiunti, {merged} già presenti.",
        "vi": "Thư viện: thêm {added}, đã có {merged}.",
        "hi": "Library: {added} जोड़े गए, {merged} पहले से मौजूद।",
        "id": "Pustaka: {added} ditambahkan, {merged} sudah ada.",
    },
    "search.library_found": {
        "en": "{count} of {total} library papers.",
        "zh-tw": "文獻庫 {total} 篇中的 {count} 篇。",
        "zh-cn": "文献库 {total} 篇中的 {count} 篇。",
        "ja": "ライブラリ {total} 件中 {count} 件。",
        "es": "{count} de {total} artículos de la biblioteca.",
        "fr": "{count} articles sur {total} dans la bibliothèque.",
        "de": "{count} von {total} Papers der Bibliothek.",
        "ko": "라이브러리 {total}편 중 {count}편.",
        "pt": "{count} de {total} artigos da biblioteca.",
        "ru": "{count} из {total} статей библиотеки.",
        "it": "{count} di {total} articoli della biblioteca.",
        "vi": "{count} trên {total} bài trong thư viện.",
        "hi": "Library के {total} में से {count} papers।",
        "id": "{count} dari {total} makalah di pustaka.",
    },
    "search.error_no_library": {
        "en": "Enter a library file first.",
        "zh-tw": "請先填入文獻庫檔案。",
        "zh-cn": "请先填入文献库文件。",
        "ja": "先にライブラリファイルを指定してください。",
        "es": "Indique primero un archivo de biblioteca.",
        "fr": "Indiquez d'abord un fichier de bibliothèque.",
        "de": "Bitte zuerst eine Bibliotheksdatei angeben.",
        "ko": "먼저 라이브러리 파일을 지정하세요.",
        "pt": "Informe primeiro um arquivo de biblioteca.",
        "ru": "Сначала укажите файл библиотеки.",
        "it": "Indica prima un file della biblioteca.",
        "vi": "Hãy nhập tệp thư viện trước.",
        "hi": "पहले library file दर्ज करें।",
        "id": "Isi file pustaka terlebih dahulu.",
    },
    "search.status_export_running": {
        "en": "Exporting…",
        "zh-tw": "正在匯出…",
        "zh-cn": "正在导出…",
        "ja": "エクスポート中…",
        "es": (
            "Exportando…"  # NOSONAR translation, matching words in other keys are not one constant
        ),
        "fr": "Exportation…",
        "de": "Exportiere…",
        "ko": "내보내는 중…",
        "pt": "Exportando…",
        "ru": "Экспорт…",
        "it": "Esportazione…",
        "vi": "Đang xuất…",
        "hi": "निर्यात हो रहा है…",
        "id": "Mengekspor…",
    },
    "search.status_export_done": {
        "en": "Exported to {path}",
        "zh-tw": "已匯出至 {path}",
        "zh-cn": "已导出至 {path}",
        "ja": "{path} へエクスポートしました",
        "es": "Exportado a {path}",
        "fr": "Exporté vers {path}",
        "de": "Exportiert nach {path}",
        "ko": "{path}로 내보냈습니다",
        "pt": "Exportado para {path}",
        "ru": "Экспортировано в {path}",
        "it": "Esportato in {path}",
        "vi": "Đã xuất tới {path}",
        "hi": "{path} में निर्यात किया गया",
        "id": "Diekspor ke {path}",
    },
    "search.error_empty_query": {
        "en": "Enter a query first.",
        "zh-tw": "請先輸入查詢關鍵字。",
        "zh-cn": "请先输入查询关键词。",
        "ja": "まず検索キーワードを入力してください。",
        "es": "Introduzca primero una consulta.",
        "fr": "Saisissez d'abord une requête.",
        "de": "Bitte zuerst einen Suchbegriff eingeben.",
        "ko": "먼저 검색어를 입력하세요.",
        "pt": "Digite uma consulta primeiro.",
        "ru": "Сначала введите запрос.",
        "it": "Inserisci prima una query.",
        "vi": "Vui lòng nhập truy vấn trước.",
        "hi": "पहले एक क्वेरी दर्ज करें।",
        "id": "Masukkan kueri terlebih dahulu.",
    },
    "search.error_no_results": {
        "en": "No results to export. Run a search first.",
        "zh-tw": "沒有可匯出的結果,請先執行搜尋。",
        "zh-cn": "没有可导出的结果,请先执行搜索。",
        "ja": "エクスポートする結果がありません。先に検索してください。",
        "es": "No hay resultados para exportar. Ejecute una búsqueda primero.",
        "fr": "Aucun résultat à exporter. Lancez d'abord une recherche.",
        "de": "Keine Ergebnisse zum Exportieren. Bitte zuerst suchen.",
        "ko": "내보낼 결과가 없습니다. 먼저 검색하세요.",
        "pt": "Nenhum resultado para exportar. Faça uma pesquisa primeiro.",
        "ru": "Нет результатов для экспорта. Сначала выполните поиск.",
        "it": "Nessun risultato da esportare. Esegui prima una ricerca.",
        "vi": "Không có kết quả để xuất. Hãy tìm kiếm trước.",
        "hi": "निर्यात के लिए कोई परिणाम नहीं। पहले खोजें।",
        "id": "Tidak ada hasil untuk diekspor. Lakukan pencarian terlebih dahulu.",
    },
    "search.error_generic": {
        "en": "Error: {error}",
        "zh-tw": "錯誤:{error}",
        "zh-cn": "错误:{error}",
        "ja": "エラー: {error}",
        "es": "Error: {error}",
        "fr": "Erreur : {error}",
        "de": "Fehler: {error}",
        "ko": "오류: {error}",
        "pt": "Erro: {error}",
        "ru": "Ошибка: {error}",
        "it": "Errore: {error}",
        "vi": "Lỗi: {error}",
        "hi": "त्रुटि: {error}",
        "id": "Galat: {error}",
    },
    # Results table columns -------------------------------------------
    "results.col_title": {
        "en": "Title",
        "zh-tw": "標題",
        "zh-cn": "标题",
        "ja": "タイトル",
        "es": "Título",  # NOSONAR translation, matching words in other keys are not one constant
        "fr": "Titre",
        "de": "Titel",
        "ko": "제목",
        "pt": "Título",
        "ru": "Заголовок",
        "it": "Titolo",
        "vi": "Tiêu đề",
        "hi": "शीर्षक",
        "id": "Judul",
    },
    "results.col_authors": {
        "en": "Authors",
        "zh-tw": "作者",
        "zh-cn": "作者",
        "ja": "著者",
        "es": "Autores",
        "fr": "Auteurs",
        "de": "Autoren",
        "ko": "저자",
        "pt": "Autores",
        "ru": "Авторы",
        "it": "Autori",
        "vi": "Tác giả",
        "hi": "लेखक",
        "id": "Penulis",
    },
    "results.col_year": {
        "en": "Year",
        "zh-tw": "年份",
        "zh-cn": "年份",
        "ja": "年",
        "es": "Año",
        "fr": "Année",
        "de": "Jahr",
        "ko": "연도",
        "pt": "Ano",
        "ru": "Год",
        "it": "Anno",
        "vi": "Năm",
        "hi": "वर्ष",
        "id": "Tahun",
    },
    "results.col_source": {
        "en": "Source",
        "zh-tw": "來源",
        "zh-cn": "来源",
        "ja": "ソース",
        "es": "Fuente",
        "fr": "Source",
        "de": "Quelle",
        "ko": "출처",
        "pt": "Fonte",
        "ru": "Источник",
        "it": "Fonte",
        "vi": "Nguồn",
        "hi": "स्रोत",
        "id": "Sumber",
    },
    "results.col_doi": {
        "en": "DOI",
        "zh-tw": "DOI",
        "zh-cn": "DOI",
        "ja": "DOI",
        "es": "DOI",
        "fr": "DOI",
        "de": "DOI",
        "ko": "DOI",
        "pt": "DOI",
        "ru": "DOI",
        "it": "DOI",
        "vi": "DOI",
        "hi": "DOI",
        "id": "DOI",
    },
    "results.col_citations": {
        "en": "Citations",
        "zh-tw": "引用數",
        "zh-cn": "引用数",
        "ja": "引用数",
        "es": "Citas",
        "fr": "Citations",
        "de": "Zitate",
        "ko": "인용 수",
        "pt": "Citações",
        "ru": "Цитирования",
        "it": "Citazioni",
        "vi": "Số trích dẫn",
        "hi": "उद्धरण",
        "id": "Sitasi",
    },
    # Advisory pruning recommendation for each search result. The three
    # values below fill this column. Hovering a row shows the score breakdown.
    "results.col_suggestion": {
        "en": "Suggestion",
        "zh-tw": "建議",
        "zh-cn": "建议",
        "ja": "提案",
        "es": "Sugerencia",
        "fr": "Suggestion",
        "de": "Empfehlung",
        "ko": "제안",
        "pt": "Sugestão",
        "ru": "Рекомендация",
        "it": "Suggerimento",
        "vi": "Gợi ý",
        "hi": "सुझाव",
        "id": "Saran",
    },
    "results.suggestion_keep": {
        "en": "keep",
        "zh-tw": "保留",
        "zh-cn": "保留",
        "ja": "残す",
        "es": "conservar",
        "fr": "garder",
        "de": "behalten",
        "ko": "유지",
        "pt": "manter",
        "ru": "оставить",
        "it": "tenere",
        "vi": "giữ",
        "hi": "रखें",
        "id": "simpan",
    },
    "results.suggestion_review": {
        "en": "review",
        "zh-tw": "再看一次",
        "zh-cn": "再看一次",
        "ja": "要確認",
        "es": "revisar",
        "fr": "à revoir",
        "de": "prüfen",
        "ko": "검토",
        "pt": "rever",
        "ru": "проверить",
        "it": "rivedere",
        "vi": "xem lại",
        "hi": "दोबारा देखें",
        "id": "tinjau",
    },
    "results.suggestion_prune": {
        "en": "prune",
        "zh-tw": "可移除",
        "zh-cn": "可移除",
        "ja": "除外候補",
        "es": "descartar",
        "fr": "à écarter",
        "de": "aussortieren",
        "ko": "제외 후보",
        "pt": "descartar",
        "ru": "убрать",
        "it": "scartare",
        "vi": "nên bỏ",
        "hi": "हटा सकते हैं",
        "id": "buang",
    },
    # Enrich / Deck placeholder ---------------------------------------
    "placeholder.coming_soon_title": {
        "en": "Coming soon",
        "zh-tw": "即將推出",
        "zh-cn": "即将推出",
        "ja": "近日公開",
        "es": "Próximamente",
        "fr": "Bientôt disponible",
        "de": "Demnächst",
        "ko": "곧 출시",
        "pt": "Em breve",
        "ru": "Скоро",
        "it": "Prossimamente",
        "vi": "Sắp ra mắt",
        "hi": "जल्द आ रहा है",
        "id": "Segera hadir",
    },
    "placeholder.enrich_body": {
        "en": (
            "Per-paper PDF + LLM enrichment will land here. For now, "
            "set ANTHROPIC_API_KEY in Settings, run a search, then "
            "export — the CLI will auto-enrich each paper that has a "
            "downloadable PDF."
        ),
        "zh-tw": (
            "單篇論文的 PDF + LLM 豐富化會放在這個分頁。目前請先到「設定」"
            "輸入 ANTHROPIC_API_KEY,執行搜尋後再匯出 — CLI 會自動豐富每篇"
            "有可下載 PDF 的論文。"
        ),
        "zh-cn": (
            "单篇论文的 PDF + LLM 丰富化会放在这个分页。目前请先到「设置」"
            "输入 ANTHROPIC_API_KEY,执行搜索后再导出 — CLI 会自动丰富每篇"
            "有可下载 PDF 的论文。"
        ),
        "ja": (
            "論文ごとの PDF + LLM 強化はここに搭載予定です。当面は「設定」で "
            "ANTHROPIC_API_KEY を入力し、検索を実行してからエクスポートして"
            "ください — CLI が PDF を取得できる論文ごとに自動で強化します。"
        ),
        "es": (
            "El enriquecimiento por artículo con PDF + LLM llegará aquí. "
            "Por ahora, configure ANTHROPIC_API_KEY en Ajustes, ejecute "
            "una búsqueda y luego exporte — la CLI enriquecerá "
            "automáticamente cada artículo con un PDF descargable."
        ),
        "fr": (
            "L'enrichissement article par article (PDF + LLM) sera "
            "disponible ici. Pour l'instant, définissez ANTHROPIC_API_KEY "
            "dans Paramètres, lancez une recherche puis exportez — la CLI "
            "enrichira automatiquement chaque article avec un PDF "
            "téléchargeable."
        ),
        "de": (
            "Pro-Paper-Anreicherung mit PDF + LLM kommt hierher. Bis dahin "
            "ANTHROPIC_API_KEY in Einstellungen setzen, suchen und "
            "exportieren — die CLI reichert jedes Paper mit "
            "herunterladbarem PDF automatisch an."
        ),
        "ko": (
            "논문별 PDF + LLM 보강이 곧 여기에 추가됩니다. 지금은 설정에서 "
            "ANTHROPIC_API_KEY를 입력하고 검색을 실행한 뒤 내보내기를 "
            "하세요 — CLI가 PDF를 다운로드할 수 있는 각 논문을 자동으로 "
            "보강합니다."
        ),
        "pt": (
            "O enriquecimento por artigo com PDF + LLM chegará aqui. Por "
            "enquanto, defina ANTHROPIC_API_KEY em Configurações, execute "
            "uma pesquisa e exporte — a CLI enriquecerá automaticamente "
            "cada artigo com PDF baixável."
        ),
        "ru": (
            "Постатейное обогащение PDF + LLM появится здесь. Пока "
            "укажите ANTHROPIC_API_KEY в Настройках, выполните поиск и "
            "экспортируйте — CLI автоматически обогатит каждую статью с "
            "загружаемым PDF."
        ),
        "it": (
            "L'arricchimento per articolo con PDF + LLM arriverà qui. Per "
            "ora, imposta ANTHROPIC_API_KEY in Impostazioni, esegui una "
            "ricerca e poi esporta — la CLI arricchirà automaticamente "
            "ogni articolo con un PDF scaricabile."
        ),
        "vi": (
            "Tính năng làm giàu từng bài (PDF + LLM) sẽ có ở đây. Hiện "
            "tại, hãy đặt ANTHROPIC_API_KEY trong Cài đặt, chạy tìm kiếm "
            "rồi xuất — CLI sẽ tự động làm giàu mỗi bài có PDF tải được."
        ),
        "hi": (
            "प्रति-शोधपत्र PDF + LLM समृद्धि यहाँ आएगी। अभी के लिए, "
            "सेटिंग्स में ANTHROPIC_API_KEY सेट करें, खोजें और निर्यात "
            "करें — CLI डाउनलोड योग्य PDF वाले प्रत्येक शोधपत्र को "
            "स्वचालित रूप से समृद्ध करेगा।"
        ),
        "id": (
            "Pengayaan per-makalah dengan PDF + LLM akan hadir di sini. "
            "Untuk saat ini, setel ANTHROPIC_API_KEY di Pengaturan, "
            "jalankan pencarian, lalu ekspor — CLI akan otomatis memperkaya "
            "setiap makalah yang PDF-nya bisa diunduh."
        ),
    },
    "placeholder.deck_body": {
        "en": (
            "Slide-deck inspector / editor will land here. The MCP "
            "server already exposes pptx_inspect / pptx_update_slide / "
            "pptx_reorder_slides / pptx_delete_slide / pptx_add_slide; "
            "this page will wire them to a Qt list view."
        ),
        "zh-tw": (
            "投影片檢視 / 編輯介面會放在這個分頁。MCP 伺服器已經提供 "
            "pptx_inspect / pptx_update_slide / pptx_reorder_slides / "
            "pptx_delete_slide / pptx_add_slide,這頁會把它們接到 Qt list view。"
        ),
        "zh-cn": (
            "幻灯片查看 / 编辑界面会放在这个分页。MCP 服务器已经提供 "
            "pptx_inspect / pptx_update_slide / pptx_reorder_slides / "
            "pptx_delete_slide / pptx_add_slide,这页会把它们接到 Qt list view。"
        ),
        "ja": (
            "スライドの検査 / 編集 UI はここに搭載予定です。MCP サーバーは "
            "すでに pptx_inspect / pptx_update_slide / pptx_reorder_slides / "
            "pptx_delete_slide / pptx_add_slide を公開しており、このページでは "
            "それらを Qt の list view に接続します。"
        ),
        "es": (
            "El inspector / editor de diapositivas llegará aquí. El "
            "servidor MCP ya expone pptx_inspect / pptx_update_slide / "
            "pptx_reorder_slides / pptx_delete_slide / pptx_add_slide; "
            "esta página los conectará a una vista de lista Qt."
        ),
        "fr": (
            "L'inspecteur / éditeur de diapositives sera disponible ici. "
            "Le serveur MCP expose déjà pptx_inspect / pptx_update_slide / "
            "pptx_reorder_slides / pptx_delete_slide / pptx_add_slide ; "
            "cette page les reliera à une vue liste Qt."
        ),
        "de": (
            "Folien-Inspektor / -Editor kommt hierher. Der MCP-Server "
            "stellt bereits pptx_inspect / pptx_update_slide / "
            "pptx_reorder_slides / pptx_delete_slide / pptx_add_slide "
            "bereit; diese Seite verdrahtet sie mit einer Qt-Listenansicht."
        ),
        "ko": (
            "슬라이드 검사 / 편집기가 곧 여기에 추가됩니다. MCP 서버는 이미 "
            "pptx_inspect / pptx_update_slide / pptx_reorder_slides / "
            "pptx_delete_slide / pptx_add_slide를 제공하고, 이 페이지는 "
            "이를 Qt 리스트 뷰에 연결합니다."
        ),
        "pt": (
            "O inspector / editor de slides chegará aqui. O servidor MCP "
            "já expõe pptx_inspect / pptx_update_slide / "
            "pptx_reorder_slides / pptx_delete_slide / pptx_add_slide; "
            "esta página os ligará a uma view de lista Qt."
        ),
        "ru": (
            "Инспектор / редактор слайдов появится здесь. MCP-сервер уже "
            "предоставляет pptx_inspect / pptx_update_slide / "
            "pptx_reorder_slides / pptx_delete_slide / pptx_add_slide; "
            "эта страница подключит их к Qt-списку."
        ),
        "it": (
            "L'ispettore / editor di diapositive arriverà qui. Il server "
            "MCP espone già pptx_inspect / pptx_update_slide / "
            "pptx_reorder_slides / pptx_delete_slide / pptx_add_slide; "
            "questa pagina li collegherà a una vista lista Qt."
        ),
        "vi": (
            "Trình kiểm tra / chỉnh sửa slide sẽ có ở đây. Máy chủ MCP đã "
            "cung cấp pptx_inspect / pptx_update_slide / "
            "pptx_reorder_slides / pptx_delete_slide / pptx_add_slide; "
            "trang này sẽ kết nối chúng với Qt list view."
        ),
        "hi": (
            "स्लाइड डेक निरीक्षक / संपादक यहाँ आएगा। MCP सर्वर पहले से "
            "pptx_inspect / pptx_update_slide / pptx_reorder_slides / "
            "pptx_delete_slide / pptx_add_slide उपलब्ध कराता है; यह पेज "
            "उन्हें Qt list view से जोड़ेगा।"
        ),
        "id": (
            "Inspektur / editor slide akan hadir di sini. Server MCP "
            "sudah menyediakan pptx_inspect / pptx_update_slide / "
            "pptx_reorder_slides / pptx_delete_slide / pptx_add_slide; "
            "halaman ini akan menghubungkannya ke list view Qt."
        ),
    },
    # Settings page ---------------------------------------------------
    "settings.title": {
        "en": "Settings",
        "zh-tw": "設定",
        "zh-cn": "设置",
        "ja": "設定",
        "es": "Ajustes",
        "fr": "Paramètres",
        "de": "Einstellungen",
        "ko": "설정",
        "pt": "Configurações",
        "ru": "Настройки",
        "it": "Impostazioni",
        "vi": "Cài đặt",
        "hi": "सेटिंग्स",
        "id": "Pengaturan",
    },
    "settings.ui_language": {
        "en": "Interface language",
        "zh-tw": "介面語言",
        "zh-cn": "界面语言",
        "ja": "インターフェース言語",
        "es": "Idioma de la interfaz",
        "fr": "Langue de l'interface",
        "de": "Oberflächensprache",
        "ko": "인터페이스 언어",
        "pt": "Idioma da interface",
        "ru": "Язык интерфейса",
        "it": "Lingua dell'interfaccia",
        "vi": "Ngôn ngữ giao diện",
        "hi": "इंटरफ़ेस भाषा",
        "id": "Bahasa antarmuka",
    },
    "settings.api_keys_group": {
        "en": "API keys (stored locally via QSettings)",
        "zh-tw": "API 金鑰(透過 QSettings 儲存在本機)",
        "zh-cn": "API 密钥(通过 QSettings 存储在本机)",
        "ja": "API キー(QSettings でローカル保存)",
        "es": "Claves de API (guardadas localmente vía QSettings)",
        "fr": "Clés API (stockées localement via QSettings)",
        "de": "API-Schlüssel (lokal via QSettings gespeichert)",
        "ko": "API 키 (QSettings로 로컬 저장)",
        "pt": "Chaves de API (armazenadas localmente via QSettings)",
        "ru": "Ключи API (хранятся локально через QSettings)",
        "it": "Chiavi API (memorizzate localmente tramite QSettings)",
        "vi": "Khóa API (lưu cục bộ qua QSettings)",
        "hi": "API कुंजियाँ (QSettings के माध्यम से स्थानीय रूप से संग्रहीत)",
        "id": "Kunci API (disimpan lokal lewat QSettings)",
    },
    "settings.anthropic_key": {
        "en": "Anthropic API key",
        "zh-tw": "Anthropic API 金鑰",
        "zh-cn": "Anthropic API 密钥",
        "ja": "Anthropic API キー",
        "es": "Clave de API de Anthropic",
        "fr": "Clé API Anthropic",
        "de": "Anthropic-API-Schlüssel",
        "ko": "Anthropic API 키",
        "pt": "Chave de API da Anthropic",
        "ru": "API-ключ Anthropic",
        "it": "Chiave API Anthropic",
        "vi": "Khóa API Anthropic",
        "hi": "Anthropic API कुंजी",
        "id": "Kunci API Anthropic",
    },
    "settings.s2_key": {
        "en": "Semantic Scholar API key (optional)",
        "zh-tw": "Semantic Scholar API 金鑰(選填)",
        "zh-cn": "Semantic Scholar API 密钥(可选)",
        "ja": "Semantic Scholar API キー(任意)",
        "es": "Clave de API de Semantic Scholar (opcional)",
        "fr": "Clé API Semantic Scholar (facultative)",
        "de": "Semantic-Scholar-API-Schlüssel (optional)",
        "ko": "Semantic Scholar API 키 (선택)",
        "pt": "Chave de API do Semantic Scholar (opcional)",
        "ru": "API-ключ Semantic Scholar (необяз.)",
        "it": "Chiave API Semantic Scholar (opzionale)",
        "vi": "Khóa API Semantic Scholar (tùy chọn)",
        "hi": "Semantic Scholar API कुंजी (वैकल्पिक)",
        "id": "Kunci API Semantic Scholar (opsional)",
    },
    "settings.ncbi_key": {
        "en": "NCBI / PubMed API key (optional)",
        "zh-tw": "NCBI / PubMed API 金鑰(選填)",
        "zh-cn": "NCBI / PubMed API 密钥(可选)",
        "ja": "NCBI / PubMed API キー(任意)",
        "es": "Clave de API de NCBI / PubMed (opcional)",
        "fr": "Clé API NCBI / PubMed (facultative)",
        "de": "NCBI- / PubMed-API-Schlüssel (optional)",
        "ko": "NCBI / PubMed API 키 (선택)",
        "pt": "Chave de API do NCBI / PubMed (opcional)",
        "ru": "API-ключ NCBI / PubMed (необяз.)",
        "it": "Chiave API NCBI / PubMed (opzionale)",
        "vi": "Khóa API NCBI / PubMed (tùy chọn)",
        "hi": "NCBI / PubMed API कुंजी (वैकल्पिक)",
        "id": "Kunci API NCBI / PubMed (opsional)",
    },
    "settings.ieee_key": {
        "en": "IEEE Xplore API key (optional)",
        "zh-tw": "IEEE Xplore API 金鑰(選填)",
        "zh-cn": "IEEE Xplore API 密钥(可选)",
        "ja": "IEEE Xplore API キー(任意)",
        "es": "Clave de API de IEEE Xplore (opcional)",
        "fr": "Clé API IEEE Xplore (facultative)",
        "de": "IEEE-Xplore-API-Schlüssel (optional)",
        "ko": "IEEE Xplore API 키 (선택)",
        "pt": "Chave de API do IEEE Xplore (opcional)",
        "ru": "API-ключ IEEE Xplore (необяз.)",
        "it": "Chiave API IEEE Xplore (opzionale)",
        "vi": "Khóa API IEEE Xplore (tùy chọn)",
        "hi": "IEEE Xplore API कुंजी (वैकल्पिक)",
        "id": "Kunci API IEEE Xplore (opsional)",
    },
    "settings.springer_key": {
        "en": "Springer Nature API key (optional)",
        "zh-tw": "Springer Nature API 金鑰(選填)",
        "zh-cn": "Springer Nature API 密钥(可选)",
        "ja": "Springer Nature API キー(任意)",
        "es": "Clave de API de Springer Nature (opcional)",
        "fr": "Clé API Springer Nature (facultative)",
        "de": "Springer-Nature-API-Schlüssel (optional)",
        "ko": "Springer Nature API 키 (선택)",
        "pt": "Chave de API do Springer Nature (opcional)",
        "ru": "API-ключ Springer Nature (необяз.)",
        "it": "Chiave API Springer Nature (opzionale)",
        "vi": "Khóa API Springer Nature (tùy chọn)",
        "hi": "Springer Nature API कुंजी (वैकल्पिक)",
        "id": "Kunci API Springer Nature (opsional)",
    },
    "settings.crossref_token": {
        "en": "Crossref Plus token (optional)",
        "zh-tw": "Crossref Plus token(選填)",
        "zh-cn": "Crossref Plus token(可选)",
        "ja": "Crossref Plus トークン(任意)",
        "es": "Token de Crossref Plus (opcional)",
        "fr": "Jeton Crossref Plus (facultatif)",
        "de": "Crossref-Plus-Token (optional)",
        "ko": "Crossref Plus 토큰 (선택)",
        "pt": "Token do Crossref Plus (opcional)",
        "ru": "Токен Crossref Plus (необяз.)",
        "it": "Token Crossref Plus (opzionale)",
        "vi": "Token Crossref Plus (tùy chọn)",
        "hi": "Crossref Plus टोकन (वैकल्पिक)",
        "id": "Token Crossref Plus (opsional)",
    },
    "settings.contact_email": {
        "en": "Contact email (Crossref polite pool)",
        "zh-tw": "聯絡 email(Crossref polite pool)",
        "zh-cn": "联系 email(Crossref polite pool)",
        "ja": "連絡先メール(Crossref polite pool)",
        "es": "Correo de contacto (Crossref polite pool)",
        "fr": "E-mail de contact (Crossref polite pool)",
        "de": "Kontakt-E-Mail (Crossref Polite Pool)",
        "ko": "연락 이메일 (Crossref polite pool)",
        "pt": "E-mail de contato (Crossref polite pool)",
        "ru": "Контактный e-mail (Crossref polite pool)",
        "it": "Email di contatto (Crossref polite pool)",
        "vi": "Email liên hệ (Crossref polite pool)",
        "hi": "संपर्क ईमेल (Crossref polite pool)",
        "id": "Email kontak (Crossref polite pool)",
    },
    "settings.cookies_file": {
        "en": "PDF cookies file (Netscape format)",
        "zh-tw": "PDF cookies 檔案(Netscape 格式)",
        "zh-cn": "PDF cookies 文件(Netscape 格式)",
        "ja": "PDF cookies ファイル(Netscape 形式)",
        "es": "Archivo de cookies PDF (formato Netscape)",
        "fr": "Fichier de cookies PDF (format Netscape)",
        "de": "PDF-Cookies-Datei (Netscape-Format)",
        "ko": "PDF cookies 파일 (Netscape 형식)",
        "pt": "Arquivo de cookies PDF (formato Netscape)",
        "ru": "Файл cookies для PDF (формат Netscape)",
        "it": "File cookies PDF (formato Netscape)",
        "vi": "Tệp cookies PDF (định dạng Netscape)",
        "hi": "PDF कुकीज़ फ़ाइल (Netscape फॉर्मेट)",
        "id": "Berkas cookies PDF (format Netscape)",
    },
    "settings.browse_button": {
        "en": "Browse…",
        "zh-tw": "瀏覽…",
        "zh-cn": "浏览…",
        "ja": "参照…",
        "es": "Examinar…",
        "fr": "Parcourir…",
        "de": "Durchsuchen…",
        "ko": "찾아보기…",
        "pt": "Procurar…",
        "ru": "Обзор…",
        "it": "Sfoglia…",
        "vi": "Duyệt…",
        "hi": "ब्राउज़ करें…",
        "id": "Telusuri…",
    },
    "settings.save_button": {
        "en": "Save",
        "zh-tw": "儲存",
        "zh-cn": "保存",
        "ja": "保存",
        "es": "Guardar",
        "fr": "Enregistrer",
        "de": "Speichern",
        "ko": "저장",
        "pt": "Salvar",
        "ru": "Сохранить",
        "it": "Salva",
        "vi": "Lưu",
        "hi": "सहेजें",
        "id": "Simpan",
    },
    "settings.saved_message": {
        "en": "Settings saved and applied.",
        "zh-tw": "設定已儲存並套用。",
        "zh-cn": "设置已保存并应用。",
        "ja": "設定を保存して反映しました。",
        "es": "Ajustes guardados y aplicados.",
        "fr": "Paramètres enregistrés et appliqués.",
        "de": "Einstellungen gespeichert und angewendet.",
        "ko": "설정을 저장하고 적용했습니다.",
        "pt": "Configurações salvas e aplicadas.",
        "ru": "Настройки сохранены и применены.",
        "it": "Impostazioni salvate e applicate.",
        "vi": "Đã lưu và áp dụng cài đặt.",
        "hi": "सेटिंग्स सहेजी और लागू की गईं।",
        "id": "Pengaturan disimpan dan diterapkan.",
    },
    "settings.cookies_dialog_title": {
        "en": "Choose cookies file",
        "zh-tw": "選擇 cookies 檔案",
        "zh-cn": "选择 cookies 文件",
        "ja": "cookies ファイルを選択",
        "es": "Elija el archivo de cookies",
        "fr": "Choisir le fichier de cookies",
        "de": "Cookies-Datei auswählen",
        "ko": "cookies 파일 선택",
        "pt": "Escolha o arquivo de cookies",
        "ru": "Выберите файл cookies",
        "it": "Scegli il file cookies",
        "vi": "Chọn tệp cookies",
        "hi": "कुकीज़ फ़ाइल चुनें",
        "id": "Pilih berkas cookies",
    },
    "settings.core_key": {
        "en": "CORE.ac.uk API key (OA resolver)",
        "zh-tw": "CORE.ac.uk API 金鑰(OA 解析器)",
        "zh-cn": "CORE.ac.uk API 密钥(OA 解析器)",
        "ja": "CORE.ac.uk API キー(OA リゾルバ)",
        "es": "Clave API de CORE.ac.uk (resolver OA)",
        "fr": "Clé API CORE.ac.uk (résolveur OA)",
        "de": "CORE.ac.uk API-Schlüssel (OA-Resolver)",
        "ko": "CORE.ac.uk API 키 (OA 리졸버)",
        "pt": "Chave de API CORE.ac.uk (resolvedor OA)",
        "ru": "Ключ API CORE.ac.uk (резолвер OA)",
        "it": "Chiave API CORE.ac.uk (risolutore OA)",
        "vi": "Khóa API CORE.ac.uk (bộ phân giải OA)",
        "hi": "CORE.ac.uk API कुंजी (OA रिज़ॉल्वर)",
        "id": "Kunci API CORE.ac.uk (resolver OA)",
    },
    "settings.chrome_profile_dir": {
        "en": "Chrome profile directory (Scholar / IEEE / paywalled PDFs)",
        "zh-tw": "Chrome 設定檔資料夾 (Scholar / IEEE / 付費 PDF)",
        "zh-cn": "Chrome 配置文件目录 (Scholar / IEEE / 付费 PDF)",
        "ja": "Chrome プロファイルディレクトリ (Scholar / IEEE / 有料 PDF)",
        "es": "Directorio de perfil de Chrome (Scholar / IEEE / PDFs de pago)",
        "fr": "Répertoire de profil Chrome (Scholar / IEEE / PDFs payants)",
        "de": "Chrome-Profilverzeichnis (Scholar / IEEE / kostenpflichtige PDFs)",
        "ko": "Chrome 프로필 디렉터리 (Scholar / IEEE / 유료 PDF)",
        "pt": "Diretório do perfil do Chrome (Scholar / IEEE / PDFs pagos)",
        "ru": "Каталог профиля Chrome (Scholar / IEEE / платные PDF)",
        "it": "Directory del profilo Chrome (Scholar / IEEE / PDF a pagamento)",
        "vi": "Thư mục hồ sơ Chrome (Scholar / IEEE / PDF trả phí)",
        "hi": "Chrome प्रोफ़ाइल निर्देशिका (Scholar / IEEE / पेड PDF)",
        "id": "Direktori profil Chrome (Scholar / IEEE / PDF berbayar)",
    },
    "settings.chrome_profile_dialog_title": {
        "en": "Choose Chrome profile directory",
        "zh-tw": "選擇 Chrome 設定檔資料夾",
        "zh-cn": "选择 Chrome 配置文件目录",
        "ja": "Chrome プロファイルディレクトリを選択",
        "es": "Elija el directorio de perfil de Chrome",
        "fr": "Choisir le répertoire de profil Chrome",
        "de": "Chrome-Profilverzeichnis auswählen",
        "ko": "Chrome 프로필 디렉터리 선택",
        "pt": "Escolha o diretório do perfil do Chrome",
        "ru": "Выберите каталог профиля Chrome",
        "it": "Scegli la directory del profilo Chrome",
        "vi": "Chọn thư mục hồ sơ Chrome",
        "hi": "Chrome प्रोफ़ाइल निर्देशिका चुनें",
        "id": "Pilih direktori profil Chrome",
    },
    # --- EnrichPage --------------------------------------------------
    "enrich.settings_group": {
        "en": "Enrichment settings",
        "zh-tw": "Enrich 設定",
        "zh-cn": "Enrich 设置",
        "ja": "Enrich 設定",
        "es": "Ajustes de Enrich",
        "fr": "Paramètres Enrich",
        "de": "Enrich-Einstellungen",
        "ko": "Enrich 설정",
        "pt": "Configurações do Enrich",
        "ru": "Настройки Enrich",
        "it": "Impostazioni Enrich",
        "vi": "Cài đặt Enrich",
        "hi": "Enrich सेटिंग्स",
        "id": "Pengaturan Enrich",
    },
    "enrich.language_label": {
        "en": "Summary language",
        "zh-tw": "摘要語言",
        "zh-cn": "摘要语言",
        "ja": "要約の言語",
        "es": "Idioma del resumen",
        "fr": "Langue du résumé",
        "de": "Sprache der Zusammenfassung",
        "ko": "요약 언어",
        "pt": "Idioma do resumo",
        "ru": "Язык резюме",
        "it": "Lingua del riassunto",
        "vi": "Ngôn ngữ bản tóm tắt",
        "hi": "सारांश की भाषा",
        "id": "Bahasa ringkasan",
    },
    "enrich.model_label": {
        "en": "Anthropic model (override)",
        "zh-tw": "Anthropic 模型(覆寫)",
        "zh-cn": "Anthropic 模型(覆盖)",
        "ja": "Anthropic モデル(上書き)",
        "es": "Modelo Anthropic (anulación)",
        "fr": "Modèle Anthropic (override)",
        "de": "Anthropic-Modell (Override)",
        "ko": "Anthropic 모델 (재정의)",
        "pt": "Modelo Anthropic (substituição)",
        "ru": "Модель Anthropic (переопределение)",
        "it": "Modello Anthropic (override)",
        "vi": "Mô hình Anthropic (ghi đè)",
        "hi": "Anthropic मॉडल (ओवरराइड)",
        "id": "Model Anthropic (override)",
    },
    "enrich.enrich_button": {
        "en": "Enrich",
        "zh-tw": "Enrich",
        "zh-cn": "Enrich",
        "ja": "Enrich",
        "es": "Enriquecer",
        "fr": "Enrichir",
        "de": "Anreichern",
        "ko": "Enrich",
        "pt": "Enriquecer",
        "ru": "Обогатить",
        "it": "Arricchisci",
        "vi": "Enrich",
        "hi": "Enrich",
        "id": "Perkaya",
    },
    "enrich.column_title": {
        "en": "Title",
        "zh-tw": "標題",
        "zh-cn": "标题",
        "ja": "タイトル",
        "es": "Título",
        "fr": "Titre",
        "de": "Titel",
        "ko": "제목",
        "pt": "Título",
        "ru": "Название",
        "it": "Titolo",
        "vi": "Tiêu đề",
        "hi": "शीर्षक",
        "id": "Judul",
    },
    "enrich.column_pdf": {
        "en": "PDF",
        "zh-tw": "PDF",
        "zh-cn": "PDF",
        "ja": "PDF",
        "es": "PDF",
        "fr": "PDF",
        "de": "PDF",
        "ko": "PDF",
        "pt": "PDF",
        "ru": "PDF",
        "it": "PDF",
        "vi": "PDF",
        "hi": "PDF",
        "id": "PDF",
    },
    "enrich.column_status": {
        "en": "Status",
        "zh-tw": "狀態",
        "zh-cn": "状态",
        "ja": "状態",
        "es": "Estado",
        "fr": "Statut",
        "de": "Status",
        "ko": "상태",
        "pt": "Estado",
        "ru": "Состояние",
        "it": "Stato",
        "vi": "Trạng thái",
        "hi": "स्थिति",
        "id": "Status",
    },
    "enrich.row_pending": {
        "en": "pending",
        "zh-tw": "等待中",
        "zh-cn": "等待中",
        "ja": "待機中",
        "es": "pendiente",
        "fr": "en attente",
        "de": "ausstehend",
        "ko": "대기 중",
        "pt": "pendente",
        "ru": "ожидание",
        "it": "in attesa",
        "vi": "đang chờ",
        "hi": "लंबित",
        "id": "menunggu",
    },
    "enrich.row_done": {
        "en": "ok",
        "zh-tw": "完成",
        "zh-cn": "完成",
        "ja": "完了",
        "es": "ok",
        "fr": "ok",
        "de": "ok",
        "ko": "완료",
        "pt": "ok",
        "ru": "ок",
        "it": "ok",
        "vi": "xong",
        "hi": "हो गया",
        "id": "selesai",
    },
    "enrich.row_skipped": {
        "en": "skipped (no PDF)",
        "zh-tw": "已跳過(無 PDF)",
        "zh-cn": "已跳过(无 PDF)",
        "ja": "スキップ(PDF なし)",
        "es": "omitido (sin PDF)",
        "fr": "ignoré (pas de PDF)",
        "de": "übersprungen (kein PDF)",
        "ko": "건너뜀 (PDF 없음)",
        "pt": "ignorado (sem PDF)",
        "ru": "пропущено (нет PDF)",
        "it": "saltato (nessun PDF)",
        "vi": "đã bỏ qua (không có PDF)",
        "hi": "छोड़ा गया (PDF नहीं)",
        "id": "dilewati (tanpa PDF)",
    },
    "enrich.row_failed": {
        "en": "failed: {error}",
        "zh-tw": "失敗: {error}",
        "zh-cn": "失败: {error}",
        "ja": "失敗: {error}",
        "es": "falló: {error}",
        "fr": "échec : {error}",
        "de": "fehlgeschlagen: {error}",
        "ko": "실패: {error}",
        "pt": "falhou: {error}",
        "ru": "ошибка: {error}",
        "it": "fallito: {error}",
        "vi": "thất bại: {error}",
        "hi": "विफल: {error}",
        "id": "gagal: {error}",
    },
    "enrich.status_no_collection": {
        "en": "Run a search first; results populate this tab.",
        "zh-tw": "請先在 Search 分頁搜尋,結果會帶到這裡。",
        "zh-cn": "请先在 Search 分页搜索,结果会带到这里。",
        "ja": "まず Search タブで検索してください。結果がここに表示されます。",
        "es": "Ejecute primero una búsqueda; los resultados aparecerán aquí.",
        "fr": "Lancez d'abord une recherche ; les résultats apparaîtront ici.",
        "de": "Erst eine Suche ausführen; die Ergebnisse erscheinen hier.",
        "ko": "먼저 Search 탭에서 검색하세요. 결과가 여기에 표시됩니다.",
        "pt": "Execute uma busca primeiro; os resultados aparecerão aqui.",
        "ru": "Сначала выполните поиск; результаты появятся здесь.",
        "it": "Esegui prima una ricerca; i risultati appariranno qui.",
        "vi": "Hãy tìm kiếm trước; kết quả sẽ xuất hiện ở đây.",
        "hi": "पहले एक search करें; परिणाम यहाँ दिखेंगे।",
        "id": "Jalankan pencarian dulu; hasil muncul di sini.",
    },
    "enrich.status_ready": {
        "en": "Ready: {count} papers.",
        "zh-tw": "就緒: {count} 篇論文。",
        "zh-cn": "就绪: {count} 篇论文。",
        "ja": "準備完了: {count} 件。",
        "es": "Listo: {count} artículos.",
        "fr": "Prêt : {count} articles.",
        "de": "Bereit: {count} Arbeiten.",
        "ko": "준비됨: {count}편.",
        "pt": "Pronto: {count} artigos.",
        "ru": "Готово: {count} статей.",
        "it": "Pronto: {count} articoli.",
        "vi": "Sẵn sàng: {count} bài.",
        "hi": "तैयार: {count} पेपर।",
        "id": "Siap: {count} makalah.",
    },
    "enrich.status_running": {
        "en": "Enriching… {done}/{total}",
        "zh-tw": (
            "Enrich 中… {done}/{total}"  # NOSONAR zh-tw zh-cn ja translations match, not a constant
        ),
        "zh-cn": "Enrich 中… {done}/{total}",
        "ja": "Enrich 中… {done}/{total}",
        "es": "Enriqueciendo… {done}/{total}",
        "fr": "Enrichissement… {done}/{total}",
        "de": "Anreicherung läuft… {done}/{total}",
        "ko": "Enrich 중… {done}/{total}",
        "pt": "Enriquecendo… {done}/{total}",
        "ru": "Обогащение… {done}/{total}",
        "it": "Arricchimento… {done}/{total}",
        "vi": "Đang enrich… {done}/{total}",
        "hi": "Enrich हो रहा… {done}/{total}",
        "id": "Memperkaya… {done}/{total}",
    },
    "enrich.status_done": {
        "en": "Done: {successes}/{total} enriched.",
        "zh-tw": "完成: {successes}/{total} 已 enrich。",
        "zh-cn": "完成: {successes}/{total} 已 enrich。",
        "ja": "完了: {successes}/{total} を enrich。",
        "es": "Hecho: {successes}/{total} enriquecidos.",
        "fr": "Terminé : {successes}/{total} enrichis.",
        "de": "Fertig: {successes}/{total} angereichert.",
        "ko": "완료: {successes}/{total} enrich 됨.",
        "pt": "Concluído: {successes}/{total} enriquecidos.",
        "ru": "Готово: {successes}/{total} обогащено.",
        "it": "Fatto: {successes}/{total} arricchiti.",
        "vi": "Xong: {successes}/{total} đã enrich.",
        "hi": "हो गया: {successes}/{total} enrich।",
        "id": "Selesai: {successes}/{total} diperkaya.",
    },
    "enrich.error_no_collection": {
        "en": "No collection to enrich.",
        "zh-tw": "沒有可 enrich 的結果集。",
        "zh-cn": "没有可 enrich 的结果集。",
        "ja": "Enrich する結果がありません。",
        "es": "Sin colección que enriquecer.",
        "fr": "Aucune collection à enrichir.",
        "de": "Keine Sammlung zum Anreichern.",
        "ko": "Enrich 할 결과가 없습니다.",
        "pt": "Sem coleção para enriquecer.",
        "ru": "Нет коллекции для обогащения.",
        "it": "Nessuna collezione da arricchire.",
        "vi": "Không có bộ kết quả để enrich.",
        "hi": "Enrich करने के लिए कोई संग्रह नहीं।",
        "id": "Tidak ada koleksi untuk diperkaya.",
    },
    "enrich.error_no_key": {
        "en": "ANTHROPIC_API_KEY is not set — open Settings to add it.",
        "zh-tw": "未設 ANTHROPIC_API_KEY — 請到 Settings 分頁設定。",
        "zh-cn": "未设 ANTHROPIC_API_KEY — 请到 Settings 分页设置。",
        "ja": "ANTHROPIC_API_KEY 未設定 — Settings タブで追加してください。",
        "es": "ANTHROPIC_API_KEY no está configurado: añádalo en Settings.",
        "fr": "ANTHROPIC_API_KEY non défini — ajoutez-le dans Settings.",
        "de": "ANTHROPIC_API_KEY ist nicht gesetzt — in Settings ergänzen.",
        "ko": "ANTHROPIC_API_KEY 미설정 — Settings 탭에서 추가하세요.",
        "pt": "ANTHROPIC_API_KEY não definido — adicione em Settings.",
        "ru": "ANTHROPIC_API_KEY не задан — добавьте в Settings.",
        "it": "ANTHROPIC_API_KEY non impostato — aggiungilo in Settings.",
        "vi": "Chưa đặt ANTHROPIC_API_KEY — thêm vào tab Settings.",
        "hi": "ANTHROPIC_API_KEY सेट नहीं — Settings में जोड़ें।",
        "id": "ANTHROPIC_API_KEY belum diatur — tambah di Settings.",
    },
    # --- DeckPage ----------------------------------------------------
    "deck.output_group": {
        "en": "Output",
        "zh-tw": "輸出",
        "zh-cn": "输出",
        "ja": "出力",
        "es": "Salida",
        "fr": "Sortie",
        "de": "Ausgabe",
        "ko": "출력",
        "pt": "Saída",
        "ru": "Вывод",
        "it": "Output",
        "vi": "Đầu ra",
        "hi": "Output",
        "id": "Keluaran",
    },
    "deck.out_dir_label": {
        "en": "Output directory",
        "zh-tw": "輸出資料夾",
        "zh-cn": "输出目录",
        "ja": "出力ディレクトリ",
        "es": "Carpeta de salida",
        "fr": "Répertoire de sortie",
        "de": "Ausgabeordner",
        "ko": "출력 디렉터리",
        "pt": "Diretório de saída",
        "ru": "Каталог вывода",
        "it": "Directory di output",
        "vi": "Thư mục đầu ra",
        "hi": "Output निर्देशिका",
        "id": "Direktori keluaran",
    },
    "deck.browse_button": {
        "en": "Browse…",
        "zh-tw": "瀏覽…",
        "zh-cn": "浏览…",
        "ja": "参照…",
        "es": "Examinar…",
        "fr": "Parcourir…",
        "de": "Durchsuchen…",
        "ko": "찾아보기…",
        "pt": "Procurar…",
        "ru": "Обзор…",
        "it": "Sfoglia…",
        "vi": "Duyệt…",
        "hi": "ब्राउज़…",
        "id": "Telusuri…",
    },
    "deck.out_dir_dialog_title": {
        "en": "Choose output directory",
        "zh-tw": "選擇輸出資料夾",
        "zh-cn": "选择输出目录",
        "ja": "出力ディレクトリを選択",
        "es": "Elija la carpeta de salida",
        "fr": "Choisir le répertoire de sortie",
        "de": "Ausgabeordner auswählen",
        "ko": "출력 디렉터리 선택",
        "pt": "Escolha o diretório de saída",
        "ru": "Выберите каталог вывода",
        "it": "Scegli la directory di output",
        "vi": "Chọn thư mục đầu ra",
        "hi": "Output निर्देशिका चुनें",
        "id": "Pilih direktori keluaran",
    },
    "deck.filename_stem_label": {
        "en": "Filename stem (optional)",
        "zh-tw": "檔名(選填)",
        "zh-cn": "文件名(选填)",
        "ja": "ファイル名(任意)",
        "es": "Nombre de archivo (opcional)",
        "fr": "Nom de fichier (optionnel)",
        "de": "Dateiname (optional)",
        "ko": "파일 이름 (선택)",
        "pt": "Nome do arquivo (opcional)",
        "ru": "Имя файла (опционально)",
        "it": "Nome file (opzionale)",
        "vi": "Tên tệp (tuỳ chọn)",
        "hi": "फ़ाइल नाम (वैकल्पिक)",
        "id": "Nama berkas (opsional)",
    },
    "deck.filename_stem_placeholder": {
        "en": "auto-generated from query + timestamp",
        "zh-tw": "自動由查詢字串 + 時間戳產生",
        "zh-cn": "自动由查询 + 时间戳生成",
        "ja": "クエリ + タイムスタンプから自動生成",
        "es": "auto desde la consulta + marca de tiempo",
        "fr": "auto à partir de la requête + horodatage",
        "de": "automatisch aus Anfrage + Zeitstempel",
        "ko": "쿼리 + 타임스탬프에서 자동 생성",
        "pt": "auto a partir da consulta + timestamp",
        "ru": "авто из запроса + метки времени",
        "it": "auto da query + timestamp",
        "vi": "tự động từ truy vấn + thời gian",
        "hi": "query + timestamp से auto",
        "id": "otomatis dari query + timestamp",
    },
    "deck.language_label": {
        "en": "Deck language",
        "zh-tw": "投影片語言",
        "zh-cn": "幻灯片语言",
        "ja": "スライドの言語",
        "es": "Idioma de la presentación",
        "fr": "Langue de la présentation",
        "de": "Foliensprache",
        "ko": "슬라이드 언어",
        "pt": "Idioma do deck",
        "ru": "Язык слайдов",
        "it": "Lingua del deck",
        "vi": "Ngôn ngữ slide",
        "hi": "Deck की भाषा",
        "id": "Bahasa deck",
    },
    "deck.format_group": {
        "en": "Formats",
        "zh-tw": "輸出格式",
        "zh-cn": "输出格式",
        "ja": "出力フォーマット",
        "es": "Formatos",
        "fr": "Formats",
        "de": "Formate",
        "ko": "포맷",
        "pt": "Formatos",
        "ru": "Форматы",
        "it": "Formati",
        "vi": "Định dạng",
        "hi": "Formats",
        "id": "Format",
    },
    "deck.format_pptx": {
        "en": "PPTX", "zh-tw": "PPTX", "zh-cn": "PPTX", "ja": "PPTX",
        "es": "PPTX", "fr": "PPTX", "de": "PPTX", "ko": "PPTX",
        "pt": "PPTX", "ru": "PPTX", "it": "PPTX", "vi": "PPTX",
        "hi": "PPTX", "id": "PPTX",
    },
    "deck.format_xlsx": {
        "en": "XLSX", "zh-tw": "XLSX", "zh-cn": "XLSX", "ja": "XLSX",
        "es": "XLSX", "fr": "XLSX", "de": "XLSX", "ko": "XLSX",
        "pt": "XLSX", "ru": "XLSX", "it": "XLSX", "vi": "XLSX",
        "hi": "XLSX", "id": "XLSX",
    },
    "deck.format_bib": {
        "en": "BibTeX", "zh-tw": "BibTeX", "zh-cn": "BibTeX", "ja": "BibTeX",
        "es": "BibTeX", "fr": "BibTeX", "de": "BibTeX", "ko": "BibTeX",
        "pt": "BibTeX", "ru": "BibTeX", "it": "BibTeX", "vi": "BibTeX",
        "hi": "BibTeX", "id": "BibTeX",
    },
    "deck.format_md": {
        "en": "Markdown", "zh-tw": "Markdown", "zh-cn": "Markdown", "ja": "Markdown",
        "es": "Markdown", "fr": "Markdown", "de": "Markdown", "ko": "Markdown",
        "pt": "Markdown", "ru": "Markdown", "it": "Markdown", "vi": "Markdown",
        "hi": "Markdown", "id": "Markdown",
    },
    "deck.format_json": {
        "en": "JSON", "zh-tw": "JSON", "zh-cn": "JSON", "ja": "JSON",
        "es": "JSON", "fr": "JSON", "de": "JSON", "ko": "JSON",
        "pt": "JSON", "ru": "JSON", "it": "JSON", "vi": "JSON",
        "hi": "JSON", "id": "JSON",
    },
    "deck.format_ris": {
        "en": "RIS", "zh-tw": "RIS", "zh-cn": "RIS", "ja": "RIS",
        "es": "RIS", "fr": "RIS", "de": "RIS", "ko": "RIS",
        "pt": "RIS", "ru": "RIS", "it": "RIS", "vi": "RIS",
        "hi": "RIS", "id": "RIS",
    },
    "deck.format_csv": {
        "en": "CSV", "zh-tw": "CSV", "zh-cn": "CSV", "ja": "CSV",
        "es": "CSV", "fr": "CSV", "de": "CSV", "ko": "CSV",
        "pt": "CSV", "ru": "CSV", "it": "CSV", "vi": "CSV",
        "hi": "CSV", "id": "CSV",
    },
    "deck.format_csl": {
        "en": "CSL-JSON", "zh-tw": "CSL-JSON", "zh-cn": "CSL-JSON", "ja": "CSL-JSON",
        "es": "CSL-JSON", "fr": "CSL-JSON", "de": "CSL-JSON", "ko": "CSL-JSON",
        "pt": "CSL-JSON", "ru": "CSL-JSON", "it": "CSL-JSON", "vi": "CSL-JSON",
        "hi": "CSL-JSON", "id": "CSL-JSON",
    },
    "deck.options_group": {
        "en": "Options",
        "zh-tw": "選項",
        "zh-cn": "选项",
        "ja": "オプション",
        "es": "Opciones",
        "fr": "Options",
        "de": "Optionen",
        "ko": "옵션",
        "pt": "Opções",
        "ru": "Опции",
        "it": "Opzioni",
        "vi": "Tuỳ chọn",
        "hi": "विकल्प",
        "id": "Opsi",
    },
    "deck.max_slides_label": {
        "en": "Max slides per paper",
        "zh-tw": "每篇最多投影片",
        "zh-cn": "每篇最多幻灯片",
        "ja": "論文あたりの最大スライド数",
        "es": "Diapositivas máx. por artículo",
        "fr": "Max diapos par article",
        "de": "Max. Folien pro Arbeit",
        "ko": "논문당 최대 슬라이드",
        "pt": "Slides máx. por artigo",
        "ru": "Макс. слайдов на статью",
        "it": "Slide max per articolo",
        "vi": "Slide tối đa mỗi bài",
        "hi": "प्रति paper अधिकतम slides",
        "id": "Slide maks per makalah",
    },
    "deck.unlimited": {
        "en": "unlimited",
        "zh-tw": "無上限",
        "zh-cn": "无上限",
        "ja": "無制限",
        "es": "ilimitado",
        "fr": "illimité",
        "de": "unbegrenzt",
        "ko": "무제한",
        "pt": "ilimitado",
        "ru": "без предела",
        "it": "illimitato",
        "vi": "không giới hạn",
        "hi": "असीमित",
        "id": "tanpa batas",
    },
    "deck.include_abstract_label": {
        "en": "Include abstract slides",
        "zh-tw": "包含摘要投影片",
        "zh-cn": "包含摘要幻灯片",
        "ja": "アブストラクトを含める",
        "es": "Incluir diapositivas de resumen",
        "fr": "Inclure les diapos de résumé",
        "de": "Abstract-Folien einschließen",
        "ko": "초록 슬라이드 포함",
        "pt": "Incluir slides de resumo",
        "ru": "Включать слайды с аннотацией",
        "it": "Includi le slide del riassunto",
        "vi": "Bao gồm slide abstract",
        "hi": "Abstract slides शामिल करें",
        "id": "Sertakan slide abstrak",
    },
    "deck.dark_mode_label": {
        "en": "Dark mode (dark background; light navy-band deck is default)",
        "zh-tw": "暗色模式(深色背景,預設為淺色藍帶版面)",
        "zh-cn": "暗色模式(深色背景,默认为浅色蓝带版面)",
        "ja": "ダークモード(暗い背景,既定はライトの紺帯デッキ)",
        "es": "Modo oscuro (fondo oscuro; claro es el predeterminado)",
        "fr": "Mode sombre (fond sombre ; le clair est par défaut)",
        "de": "Dunkler Modus (dunkler Hintergrund; hell ist Standard)",
        "ko": "다크 모드 (어두운 배경, 기본은 라이트)",
        "pt": "Modo escuro (fundo escuro; claro é o padrão)",
        "ru": "Тёмный режим (тёмный фон; по умолчанию светлый)",
        "it": "Modalità scura (sfondo scuro; chiaro è il default)",
        "vi": "Chế độ tối (nền tối; mặc định là sáng)",
        "hi": "Dark mode (गहरी पृष्ठभूमि; डिफ़ॉल्ट light है)",
        "id": "Mode gelap (latar gelap; default terang)",
    },
    # Export preflight toggle. Checked by default: an unchecked box exports
    # DOIs / URLs unverified, which is only meant for working offline.
    "deck.verify_identifiers_label": {
        "en": "Verify DOIs and URLs before export (uncheck when offline)",
        "zh-tw": "匯出前驗證 DOI 與網址(離線時請取消勾選)",
        "zh-cn": "导出前验证 DOI 与网址(离线时请取消勾选)",
        "ja": "エクスポート前に DOI と URL を検証(オフライン時は外す)",
        "es": "Verificar DOI y URL antes de exportar (desmarcar sin conexión)",
        "fr": "Vérifier les DOI et URL avant l'export (décocher hors ligne)",
        "de": "DOIs und URLs vor dem Export prüfen (offline abwählen)",
        "ko": "내보내기 전에 DOI 와 URL 검증 (오프라인이면 해제)",
        "pt": "Verificar DOIs e URLs antes de exportar (desmarcar offline)",
        "ru": "Проверять DOI и URL перед экспортом (снять без сети)",
        "it": "Verifica DOI e URL prima dell'esportazione (deseleziona offline)",
        "vi": "Kiểm tra DOI và URL trước khi xuất (bỏ chọn khi ngoại tuyến)",
        "hi": "Export से पहले DOI और URL जाँचें (offline हों तो हटाएँ)",
        "id": "Verifikasi DOI dan URL sebelum ekspor (hapus centang saat offline)",
    },
    "deck.template_label": {
        "en": "Template (.pptx)",
        "zh-tw": "範本 (.pptx)",
        "zh-cn": "模板 (.pptx)",
        "ja": "テンプレート (.pptx)",
        "es": "Plantilla (.pptx)",
        "fr": "Modèle (.pptx)",
        "de": "Vorlage (.pptx)",
        "ko": "템플릿 (.pptx)",
        "pt": "Modelo (.pptx)",
        "ru": "Шаблон (.pptx)",
        "it": "Modello (.pptx)",
        "vi": "Mẫu (.pptx)",
        "hi": "Template (.pptx)",
        "id": "Templat (.pptx)",
    },
    "deck.template_config_label": {
        "en": "Template config",
        "zh-tw": "範本設定檔",
        "zh-cn": "模板配置文件",
        "ja": "テンプレート設定",
        "es": "Configuración de plantilla",
        "fr": "Configuration du modèle",
        "de": "Vorlagenkonfiguration",
        "ko": "템플릿 설정",
        "pt": "Configuração do modelo",
        "ru": "Настройки шаблона",
        "it": "Configurazione del modello",
        "vi": "Cấu hình mẫu",
        "hi": "Template config",
        "id": "Konfigurasi templat",
    },
    "deck.template_placeholder": {
        "en": "Built-in design when empty",
        "zh-tw": "留空則使用內建樣式",
        "zh-cn": "留空则使用内置样式",
        "ja": "空欄の場合は組み込みデザイン",
        "es": "Diseño integrado si se deja vacío",
        "fr": "Habillage intégré si vide",
        "de": "Leer: eingebautes Design",
        "ko": "비워 두면 기본 디자인",
        "pt": "Design embutido se vazio",
        "ru": "Если пусто, встроенное оформление",
        "it": "Design integrato se vuoto",
        "vi": "Để trống sẽ dùng thiết kế có sẵn",
        "hi": "खाली हो तो built-in design",
        "id": "Desain bawaan bila kosong",
    },
    "deck.template_config_placeholder": {
        "en": "Optional .toml / .json",
        "zh-tw": "選填的 .toml / .json",
        "zh-cn": "可选的 .toml / .json",
        "ja": "任意の .toml / .json",
        "es": ".toml / .json opcional",
        "fr": ".toml / .json facultatif",
        "de": "Optionale .toml / .json",
        "ko": "선택 사항 .toml / .json",
        "pt": ".toml / .json opcional",
        "ru": "Необязательный .toml / .json",
        "it": ".toml / .json facoltativo",
        "vi": ".toml / .json tùy chọn",
        "hi": "वैकल्पिक .toml / .json",
        "id": ".toml / .json opsional",
    },
    "deck.template_dialog_title": {
        "en": "Choose a PowerPoint template",
        "zh-tw": "選擇 PowerPoint 範本",
        "zh-cn": "选择 PowerPoint 模板",
        "ja": "PowerPoint テンプレートを選択",
        "es": "Elegir una plantilla de PowerPoint",
        "fr": "Choisir un modèle PowerPoint",
        "de": "PowerPoint-Vorlage wählen",
        "ko": "PowerPoint 템플릿 선택",
        "pt": "Escolher um modelo do PowerPoint",
        "ru": "Выберите шаблон PowerPoint",
        "it": "Scegli un modello PowerPoint",
        "vi": "Chọn mẫu PowerPoint",
        "hi": "PowerPoint template चुनें",
        "id": "Pilih templat PowerPoint",
    },
    "deck.template_config_dialog_title": {
        "en": "Choose a template config",
        "zh-tw": "選擇範本設定檔",
        "zh-cn": "选择模板配置文件",
        "ja": "テンプレート設定を選択",
        "es": "Elegir una configuración de plantilla",
        "fr": "Choisir une configuration de modèle",
        "de": "Vorlagenkonfiguration wählen",
        "ko": "템플릿 설정 선택",
        "pt": "Escolher uma configuração de modelo",
        "ru": "Выберите файл настроек шаблона",
        "it": "Scegli una configurazione del modello",
        "vi": "Chọn cấu hình mẫu",
        "hi": "Template config चुनें",
        "id": "Pilih konfigurasi templat",
    },
    "deck.export_button": {
        "en": "Export",
        "zh-tw": "輸出",
        "zh-cn": "导出",
        "ja": "エクスポート",
        "es": "Exportar",
        "fr": "Exporter",
        "de": "Exportieren",
        "ko": "내보내기",
        "pt": "Exportar",
        "ru": "Экспорт",
        "it": "Esporta",
        "vi": "Xuất",
        "hi": "Export",
        "id": "Ekspor",
    },
    "deck.open_folder_button": {
        "en": "Open folder",
        "zh-tw": "開啟資料夾",
        "zh-cn": "打开文件夹",
        "ja": "フォルダを開く",
        "es": "Abrir carpeta",
        "fr": "Ouvrir le dossier",
        "de": "Ordner öffnen",
        "ko": "폴더 열기",
        "pt": "Abrir pasta",
        "ru": "Открыть папку",
        "it": "Apri cartella",
        "vi": "Mở thư mục",
        "hi": "Folder खोलें",
        "id": "Buka folder",
    },
    "deck.column_format": {
        "en": "Format",
        "zh-tw": "格式",
        "zh-cn": "格式",
        "ja": "フォーマット",
        "es": "Formato",
        "fr": "Format",
        "de": "Format",
        "ko": "포맷",
        "pt": "Formato",
        "ru": "Формат",
        "it": "Formato",
        "vi": "Định dạng",
        "hi": "Format",
        "id": "Format",
    },
    "deck.column_path": {
        "en": "Path",
        "zh-tw": "路徑",
        "zh-cn": "路径",
        "ja": "パス",
        "es": "Ruta",
        "fr": "Chemin",
        "de": "Pfad",
        "ko": "경로",
        "pt": "Caminho",
        "ru": "Путь",
        "it": "Percorso",
        "vi": "Đường dẫn",
        "hi": "Path",
        "id": "Path",
    },
    "deck.status_no_collection": {
        "en": "Run a search first; the result populates this tab.",
        "zh-tw": "請先搜尋,結果會帶到這裡。",
        "zh-cn": "请先搜索,结果会带到这里。",
        "ja": "まず検索してください。結果がここに表示されます。",
        "es": "Ejecute primero una búsqueda; el resultado aparecerá aquí.",
        "fr": "Lancez d'abord une recherche ; le résultat apparaîtra ici.",
        "de": "Erst eine Suche ausführen; das Ergebnis erscheint hier.",
        "ko": "먼저 검색하세요. 결과가 여기에 표시됩니다.",
        "pt": "Execute uma busca primeiro; o resultado aparecerá aqui.",
        "ru": "Сначала выполните поиск; результат появится здесь.",
        "it": "Esegui prima una ricerca; il risultato appare qui.",
        "vi": "Hãy tìm trước; kết quả sẽ xuất hiện ở đây.",
        "hi": "पहले search करें; परिणाम यहाँ दिखेगा।",
        "id": "Jalankan pencarian dulu; hasil muncul di sini.",
    },
    "deck.status_ready_raw": {
        "en": "Ready: {count} papers (lightweight tier).",
        "zh-tw": "就緒: {count} 篇(輕量版)。",
        "zh-cn": "就绪: {count} 篇(轻量版)。",
        "ja": "準備完了: {count} 件(ライトモード)。",
        "es": "Listo: {count} artículos (modo ligero).",
        "fr": "Prêt : {count} articles (mode léger).",
        "de": "Bereit: {count} Arbeiten (Lightweight-Modus).",
        "ko": "준비됨: {count}편 (lightweight).",
        "pt": "Pronto: {count} artigos (modo leve).",
        "ru": "Готово: {count} статей (лёгкий режим).",
        "it": "Pronto: {count} articoli (modalità leggera).",
        "vi": "Sẵn sàng: {count} bài (lightweight).",
        "hi": "तैयार: {count} पेपर (lightweight)।",
        "id": "Siap: {count} makalah (ringan).",
    },
    "deck.status_ready_enriched": {
        "en": "Ready: {count} papers (enriched / thesis-style).",
        "zh-tw": "就緒: {count} 篇(已 enrich / 論文版)。",
        "zh-cn": "就绪: {count} 篇(已 enrich / 论文版)。",
        "ja": "準備完了: {count} 件(enrich 済み / thesis モード)。",
        "es": "Listo: {count} artículos (enriquecidos / tesis).",
        "fr": "Prêt : {count} articles (enrichis / mode thèse).",
        "de": "Bereit: {count} Arbeiten (angereichert / Thesis-Modus).",
        "ko": "준비됨: {count}편 (enrich, thesis).",
        "pt": "Pronto: {count} artigos (enriquecidos / tese).",
        "ru": "Готово: {count} статей (обогащено / thesis).",
        "it": "Pronto: {count} articoli (arricchiti / tesi).",
        "vi": "Sẵn sàng: {count} bài (đã enrich / thesis).",
        "hi": "तैयार: {count} पेपर (enrich, thesis)।",
        "id": "Siap: {count} makalah (diperkaya / thesis).",
    },
    "deck.status_running": {
        "en": "Exporting…",
        "zh-tw": "輸出中…",
        "zh-cn": "导出中…",
        "ja": "エクスポート中…",
        "es": "Exportando…",
        "fr": "Export en cours…",
        "de": "Export läuft…",
        "ko": "내보내는 중…",
        "pt": "Exportando…",
        "ru": "Экспорт…",
        "it": "Esportazione…",
        "vi": "Đang xuất…",
        "hi": "Export हो रहा…",
        "id": "Mengekspor…",
    },
    "deck.status_done": {
        "en": "Wrote {count} file(s).",
        "zh-tw": "完成,輸出 {count} 個檔案。",
        "zh-cn": "完成,导出 {count} 个文件。",
        "ja": "完了。{count} 件出力。",
        "es": "Hecho: {count} archivo(s) escrito(s).",
        "fr": "Terminé : {count} fichier(s) écrit(s).",
        "de": "Fertig: {count} Datei(en) geschrieben.",
        "ko": "완료: {count}개 파일 작성됨.",
        "pt": "Concluído: {count} arquivo(s) gravado(s).",
        "ru": "Готово: записано {count} файл(ов).",
        "it": "Fatto: {count} file scritti.",
        "vi": "Xong: ghi {count} tệp.",
        "hi": "हो गया: {count} फ़ाइलें लिखीं।",
        "id": "Selesai: menulis {count} berkas.",
    },
    "deck.error_no_collection": {
        "en": "No collection loaded.",
        "zh-tw": "尚未載入結果集。",
        "zh-cn": "尚未加载结果集。",
        "ja": "結果セットがありません。",
        "es": "Sin colección cargada.",
        "fr": "Aucune collection chargée.",
        "de": "Keine Sammlung geladen.",
        "ko": "결과 컬렉션 없음.",
        "pt": "Sem coleção carregada.",
        "ru": "Коллекция не загружена.",
        "it": "Nessuna collezione caricata.",
        "vi": "Chưa nạp bộ kết quả.",
        "hi": "कोई संग्रह नहीं।",
        "id": "Belum ada koleksi.",
    },
    "deck.error_no_formats": {
        "en": "Select at least one format.",
        "zh-tw": "至少要選一種格式。",
        "zh-cn": "至少要选一种格式。",
        "ja": "少なくとも 1 つのフォーマットを選択。",
        "es": "Seleccione al menos un formato.",
        "fr": "Sélectionnez au moins un format.",
        "de": "Mindestens ein Format wählen.",
        "ko": "포맷을 최소 하나 선택하세요.",
        "pt": "Selecione pelo menos um formato.",
        "ru": "Выберите хотя бы один формат.",
        "it": "Seleziona almeno un formato.",
        "vi": "Chọn ít nhất một định dạng.",
        "hi": "कम से कम एक format चुनें।",
        "id": "Pilih setidaknya satu format.",
    },
    "deck.error_no_out_dir": {
        "en": "Output directory cannot be empty.",
        "zh-tw": "輸出資料夾不能空白。",
        "zh-cn": "输出目录不能为空。",
        "ja": "出力ディレクトリは必須です。",
        "es": "La carpeta de salida no puede estar vacía.",
        "fr": "Le répertoire de sortie est obligatoire.",
        "de": "Ausgabeordner darf nicht leer sein.",
        "ko": "출력 디렉터리는 필수입니다.",
        "pt": "Diretório de saída obrigatório.",
        "ru": "Каталог вывода обязателен.",
        "it": "La directory di output è obbligatoria.",
        "vi": "Thư mục đầu ra không được trống.",
        "hi": "Output निर्देशिका आवश्यक।",
        "id": "Direktori keluaran wajib.",
    },
    "deck.error_no_output": {
        "en": "Export produced no files.",
        "zh-tw": "輸出沒有產生任何檔案。",
        "zh-cn": "导出未生成任何文件。",
        "ja": "ファイルは出力されませんでした。",
        "es": "La exportación no generó archivos.",
        "fr": "L'export n'a produit aucun fichier.",
        "de": "Export hat keine Dateien erzeugt.",
        "ko": "내보내기 결과 파일 없음.",
        "pt": "A exportação não gerou arquivos.",
        "ru": "Экспорт не создал файлов.",
        "it": "L'esportazione non ha prodotto file.",
        "vi": "Xuất không tạo ra tệp nào.",
        "hi": "Export से कोई फ़ाइल नहीं बनी।",
        "id": "Ekspor tidak menghasilkan berkas.",
    },
    "deck.error_generic": {
        "en": "Export failed: {error}",
        "zh-tw": "輸出失敗: {error}",
        "zh-cn": "导出失败: {error}",
        "ja": "エクスポート失敗: {error}",
        "es": "Falló la exportación: {error}",
        "fr": "Échec de l'export : {error}",
        "de": "Export fehlgeschlagen: {error}",
        "ko": "내보내기 실패: {error}",
        "pt": "Falha na exportação: {error}",
        "ru": "Ошибка экспорта: {error}",
        "it": "Esportazione fallita: {error}",
        "vi": "Xuất thất bại: {error}",
        "hi": "Export विफल: {error}",
        "id": "Ekspor gagal: {error}",
    },
    # Shell: sidebar, status bar, page subtitles ----------------------
    "nav.toggle": {
        "en": "Collapse or expand the sidebar",
        "zh-tw": "收合或展開側邊欄",
        "zh-cn": "收起或展开侧边栏",
        "ja": "サイドバーを折りたたむ／展開する",
        "es": "Contraer o expandir la barra lateral",
        "fr": "Réduire ou développer la barre latérale",
        "de": "Seitenleiste ein- oder ausklappen",
        "ko": "사이드바 접기/펼치기",
        "pt": "Recolher ou expandir a barra lateral",
        "ru": "Свернуть или развернуть боковую панель",
        "it": "Comprimi o espandi la barra laterale",
        "vi": "Thu gọn hoặc mở rộng thanh bên",
        "hi": "साइडबार को छोटा या बड़ा करें",
        "id": "Ciutkan atau bentangkan bilah samping",
    },
    "status.busy": {
        "en": "Working…",
        "zh-tw": "處理中…",
        "zh-cn": "处理中…",
        "ja": "処理中…",
        "es": "Procesando…",
        "fr": "Traitement en cours…",
        "de": "Wird bearbeitet …",
        "ko": "처리 중…",
        "pt": "Processando…",
        "ru": "Выполняется…",
        "it": "Elaborazione in corso…",
        "vi": "Đang xử lý…",
        "hi": "काम जारी है…",
        "id": "Sedang memproses…",
    },
    "page.search_subtitle": {
        "en": (
            "Find papers across the academic sources, follow their citations, and keep them in a "
            "library."
        ),
        "zh-tw": "跨學術來源搜尋論文，可沿引用延伸，並存入文獻庫。",
        "zh-cn": "跨学术来源搜索论文，可沿引用扩展，并存入文献库。",
        "ja": "複数の学術ソースから論文を検索し、引用をたどってライブラリに保存します。",
        "es": (
            "Busque artículos en las fuentes académicas, siga sus citas y guárdelos en una "
            "biblioteca."
        ),
        "fr": (
            "Recherchez des articles dans les sources académiques, suivez leurs citations et "
            "gardez-les dans une bibliothèque."
        ),
        "de": (
            "Artikel in den Fachquellen suchen, ihren Zitationen folgen und in einer Bibliothek "
            "ablegen."
        ),
        "ko": "여러 학술 소스에서 논문을 검색하고, 인용을 따라가며, 라이브러리에 보관합니다.",
        "pt": (
            "Pesquise artigos nas fontes acadêmicas, siga suas citações e guarde-os em uma "
            "biblioteca."
        ),
        "ru": (
            "Ищите статьи в академических источниках, переходите по цитированиям и сохраняйте их в "
            "библиотеке."
        ),
        "it": (
            "Cerca articoli nelle fonti accademiche, segui le loro citazioni e conservali in una "
            "biblioteca."
        ),
        "vi": "Tìm bài báo trên các nguồn học thuật, lần theo trích dẫn và lưu chúng vào thư viện.",
        "hi": (
            "अकादमिक स्रोतों में शोध-पत्र खोजें, उनके उद्धरणों का अनुसरण करें और उन्हें लाइब्रेरी "
            "में रखें।"
        ),
        "id": (
            "Cari makalah di berbagai sumber akademik, telusuri sitasinya, dan simpan di pustaka."
        ),
    },
    "page.enrich_subtitle": {
        "en": (
            "Read each paper's PDF and write a thesis-structured summary, with an Anthropic API "
            "key from Settings or by handing the papers to an LLM agent."
        ),
        "zh-tw": (
            "讀取每篇論文的 PDF，產生依論文章節編排的摘要。可使用「設定」中的 Anthropic API 金鑰，"
            "或把論文交給 LLM 代理處理。"
        ),
        "zh-cn": (
            "读取每篇论文的 PDF，生成按论文章节编排的摘要。可使用“设置”中的 Anthropic API 密钥，"
            "或把论文交给 LLM 代理处理。"
        ),
        "ja": (
            "各論文の PDF を読み、論文の章立てに沿った要約を作成します。設定の Anthropic API "
            "キーを使うか、論文を LLM エージェントに渡します。"
        ),
        "es": (
            "Lee el PDF de cada artículo y redacta un resumen con estructura de tesis, con una "
            "clave de API de Anthropic en Ajustes o pasando los artículos a un agente LLM."
        ),
        "fr": (
            "Lit le PDF de chaque article et rédige un résumé structuré comme une thèse, avec une "
            "clé API Anthropic dans les Paramètres ou en confiant les articles à un agent LLM."
        ),
        "de": (
            "Liest das PDF jedes Artikels und schreibt eine Zusammenfassung im Aufbau einer "
            "Abschlussarbeit, mit einem Anthropic-API-Schlüssel aus den Einstellungen oder über "
            "einen LLM-Agenten."
        ),
        "ko": (
            "각 논문의 PDF를 읽고 학위논문 구조에 맞춘 요약을 작성합니다. 설정의 Anthropic API "
            "키를 쓰거나 논문을 LLM 에이전트에게 넘깁니다."
        ),
        "pt": (
            "Lê o PDF de cada artigo e escreve um resumo com estrutura de tese, com uma chave de "
            "API da Anthropic em Configurações ou passando os artigos a um agente LLM."
        ),
        "ru": (
            "Читает PDF каждой статьи и составляет резюме по структуре диссертации, с ключом API "
            "Anthropic из настроек или через LLM-агента."
        ),
        "it": (
            "Legge il PDF di ogni articolo e scrive un riassunto con la struttura di una tesi, con "
            "una chiave API Anthropic nelle Impostazioni o affidando gli articoli a un agente LLM."
        ),
        "vi": (
            "Đọc PDF của từng bài báo và viết bản tóm tắt theo cấu trúc luận văn, bằng khóa API "
            "Anthropic trong Cài đặt hoặc giao các bài báo cho một tác tử LLM."
        ),
        "hi": (
            "हर शोध-पत्र की PDF पढ़कर थीसिस-संरचना वाला सारांश लिखता है, सेटिंग्स की Anthropic API "
            "कुंजी से या शोध-पत्र किसी LLM एजेंट को सौंपकर।"
        ),
        "id": (
            "Membaca PDF setiap makalah dan menulis ringkasan berstruktur tesis, dengan kunci API "
            "Anthropic di Pengaturan atau dengan menyerahkan makalah ke agen LLM."
        ),
    },
    "page.deck_subtitle": {
        "en": "Pick the output formats and deck options, then write the files.",
        "zh-tw": "選擇輸出格式與投影片選項，然後寫出檔案。",
        "zh-cn": "选择输出格式与幻灯片选项，然后写出文件。",
        "ja": "出力形式とスライドのオプションを選び、ファイルを書き出します。",
        "es": (
            "Elija los formatos de salida y las opciones de diapositivas, y luego escriba los "
            "archivos."
        ),
        "fr": (
            "Choisissez les formats de sortie et les options des diapos, puis écrivez les fichiers."
        ),
        "de": "Ausgabeformate und Folienoptionen wählen, dann die Dateien schreiben.",
        "ko": "출력 형식과 슬라이드 옵션을 고른 뒤 파일을 저장합니다.",
        "pt": (
            "Escolha os formatos de saída e as opções dos slides e, em seguida, grave os arquivos."
        ),
        "ru": "Выберите форматы вывода и параметры слайдов, затем запишите файлы.",
        "it": "Scegli i formati di output e le opzioni delle diapositive, poi scrivi i file.",
        "vi": "Chọn định dạng đầu ra và tùy chọn slide, sau đó ghi tệp.",
        "hi": "आउटपुट फ़ॉर्मैट और स्लाइड विकल्प चुनें, फिर फ़ाइलें लिखें।",
        "id": "Pilih format keluaran dan opsi slide, lalu tulis berkasnya.",
    },
    "page.settings_subtitle": {
        "en": (
            "API keys, browser access, interface language and theme. Everything is stored on this "
            "computer only."
        ),
        "zh-tw": "API 金鑰、瀏覽器存取、介面語言與主題。所有設定只儲存在這台電腦。",
        "zh-cn": "API 密钥、浏览器访问、界面语言与主题。所有设置只保存在这台电脑。",
        "ja": (
            "API キー、ブラウザーアクセス、表示言語とテーマ。"
            "すべてこのコンピューターにのみ保存されます。"
        ),
        "es": (
            "Claves de API, acceso del navegador, idioma de la interfaz y tema. Todo se guarda "
            "solo en este equipo."
        ),
        "fr": (
            "Clés API, accès navigateur, langue de l'interface et thème. Tout est enregistré sur "
            "cet ordinateur uniquement."
        ),
        "de": (
            "API-Schlüssel, Browserzugriff, Oberflächensprache und Design. Alles wird nur auf "
            "diesem Computer gespeichert."
        ),
        "ko": (
            "API 키, 브라우저 접근, 인터페이스 언어와 테마. 모든 설정은 이 컴퓨터에만 저장됩니다."
        ),
        "pt": (
            "Chaves de API, acesso do navegador, idioma da interface e tema. Tudo fica salvo "
            "apenas neste computador."
        ),
        "ru": (
            "Ключи API, доступ браузера, язык интерфейса и тема. Всё хранится только на этом "
            "компьютере."
        ),
        "it": (
            "Chiavi API, accesso del browser, lingua dell'interfaccia e tema. Tutto è salvato solo "
            "su questo computer."
        ),
        "vi": (
            "Khóa API, truy cập trình duyệt, ngôn ngữ giao diện và chủ đề. Mọi thứ chỉ được lưu "
            "trên máy tính này."
        ),
        "hi": (
            "API कुंजियाँ, ब्राउज़र पहुँच, इंटरफ़ेस भाषा और थीम। सब कुछ केवल इसी कंप्यूटर पर सहेजा "
            "जाता है।"
        ),
        "id": (
            "Kunci API, akses peramban, bahasa antarmuka, dan tema. Semuanya hanya disimpan di "
            "komputer ini."
        ),
    },
    # Card titles -------------------------------------------------------
    "search.card_query": {
        "en": "What to search",
        "zh-tw": "搜尋內容",
        "zh-cn": "搜索内容",
        "ja": "検索内容",
        "es": "Qué buscar",
        "fr": "Que rechercher",
        "de": "Suchanfrage",
        "ko": "검색 내용",
        "pt": "O que pesquisar",
        "ru": "Что искать",
        "it": "Cosa cercare",
        "vi": "Tìm gì",
        "hi": "क्या खोजें",
        "id": "Apa yang dicari",
    },
    "search.card_filters": {
        "en": "Filters",
        "zh-tw": "篩選條件",
        "zh-cn": "筛选条件",
        "ja": "絞り込み",
        "es": "Filtros",
        "fr": "Filtres",
        "de": "Filter",
        "ko": "필터",
        "pt": "Filtros",
        "ru": "Фильтры",
        "it": "Filtri",
        "vi": "Bộ lọc",
        "hi": "फ़िल्टर",
        "id": "Filter",
    },
    "search.card_library": {
        "en": "Snowball and library",
        "zh-tw": "引用滾雪球與文獻庫",
        "zh-cn": "引用滚雪球与文献库",
        "ja": "引用スノーボールとライブラリ",
        "es": "Bola de nieve y biblioteca",
        "fr": "Boule de neige et bibliothèque",
        "de": "Schneeball und Bibliothek",
        "ko": "인용 스노볼과 라이브러리",
        "pt": "Bola de neve e biblioteca",
        "ru": "Снежный ком и библиотека",
        "it": "Palla di neve e biblioteca",
        "vi": "Lăn cầu tuyết và thư viện",
        "hi": "Citation snowball और लाइब्रेरी",
        "id": "Bola salju dan pustaka",
    },
    "search.results_title": {
        "en": "Results",
        "zh-tw": "搜尋結果",
        "zh-cn": "搜索结果",
        "ja": "検索結果",
        "es": "Resultados",
        "fr": "Résultats",
        "de": "Ergebnisse",
        "ko": "결과",
        "pt": "Resultados",
        "ru": "Результаты",
        "it": "Risultati",
        "vi": "Kết quả",
        "hi": "परिणाम",
        "id": "Hasil",
    },
    "settings.card_browser": {
        "en": "Browser and PDF access",
        "zh-tw": "瀏覽器與 PDF 存取",
        "zh-cn": "浏览器与 PDF 访问",
        "ja": "ブラウザーと PDF へのアクセス",
        "es": "Navegador y acceso a PDF",
        "fr": "Navigateur et accès aux PDF",
        "de": "Browser und PDF-Zugriff",
        "ko": "브라우저 및 PDF 접근",
        "pt": "Navegador e acesso a PDF",
        "ru": "Браузер и доступ к PDF",
        "it": "Browser e accesso ai PDF",
        "vi": "Trình duyệt và truy cập PDF",
        "hi": "ब्राउज़र और PDF पहुँच",
        "id": "Peramban dan akses PDF",
    },
    # Theme ---------------------------------------------------------------
    "settings.theme_label": {
        "en": "Theme",
        "zh-tw": "主題",
        "zh-cn": "主题",
        "ja": "テーマ",
        "es": "Tema",
        "fr": "Thème",
        "de": "Design",
        "ko": "테마",
        "pt": "Tema",
        "ru": "Тема",
        "it": "Tema",
        "vi": "Chủ đề",
        "hi": "थीम",
        "id": "Tema",
    },
    "settings.theme_system": {
        "en": "Follow the system",
        "zh-tw": "跟隨系統",
        "zh-cn": "跟随系统",
        "ja": "システムに合わせる",
        "es": "Seguir el sistema",
        "fr": "Suivre le système",
        "de": "Wie System",
        "ko": "시스템 설정 따르기",
        "pt": "Seguir o sistema",
        "ru": "Как в системе",
        "it": "Segui il sistema",
        "vi": "Theo hệ thống",
        "hi": "सिस्टम के अनुसार",
        "id": "Ikuti sistem",
    },
    "settings.theme_light": {
        "en": "Light",
        "zh-tw": "淺色",
        "zh-cn": "浅色",
        "ja": "ライト",
        "es": "Claro",
        "fr": "Clair",
        "de": "Hell",
        "ko": "라이트",
        "pt": "Claro",
        "ru": "Светлая",
        "it": "Chiaro",
        "vi": "Sáng",
        "hi": "लाइट",
        "id": "Terang",
    },
    "settings.theme_dark": {
        "en": "Dark",
        "zh-tw": "深色",
        "zh-cn": "深色",
        "ja": "ダーク",
        "es": "Oscuro",
        "fr": "Sombre",
        "de": "Dunkel",
        "ko": "다크",
        "pt": "Escuro",
        "ru": "Тёмная",
        "it": "Scuro",
        "vi": "Tối",
        "hi": "डार्क",
        "id": "Gelap",
    },
    # Style -------------------------------------------------------------
    "settings.style_label": {
        "en": "Style",
        "zh-tw": "介面風格",
        "zh-cn": "界面风格",
        "ja": "スタイル",
        "es": "Estilo",
        "fr": "Style",
        "de": "Stil",
        "ko": "스타일",
        "pt": "Estilo",
        "ru": "Стиль",
        "it": "Stile",
        "vi": "Phong cách",
        "hi": "शैली",
        "id": "Gaya",
    },
    "settings.style_classic": {
        "en": "Classic (navy, matches the decks)",
        "zh-tw": "經典(海軍藍，與投影片一致)",
        "zh-cn": "经典(海军蓝，与幻灯片一致)",
        "ja": "クラシック(ネイビー、スライドと統一)",
        "es": "Clásico (azul marino, como las diapositivas)",
        "fr": "Classique (bleu marine, comme les diapos)",
        "de": "Klassisch (Marineblau, wie die Folien)",
        "ko": "클래식 (네이비, 슬라이드와 통일)",
        "pt": "Clássico (azul-marinho, como os slides)",
        "ru": "Классический (тёмно-синий, как слайды)",
        "it": "Classico (blu navy, come le diapositive)",
        "vi": "Cổ điển (xanh navy, giống slide)",
        "hi": "क्लासिक (नेवी, स्लाइड जैसा)",
        "id": "Klasik (biru dongker, serasi dengan slide)",
    },
    # A style name, the same word in every language, so one constant
    # fills every locale instead of fourteen copies of the literal.
    "settings.style_material": dict.fromkeys(SUPPORTED_LANGUAGES, _MATERIAL_3_STYLE_NAME),
    # Font size ---------------------------------------------------------
    "settings.font_size_label": {
        "en": "Font size",
        "zh-tw": "字體大小",
        "zh-cn": "字体大小",
        "ja": "文字サイズ",
        "es": "Tamaño de letra",
        "fr": "Taille du texte",
        "de": "Schriftgröße",
        "ko": "글자 크기",
        "pt": "Tamanho da fonte",
        "ru": "Размер шрифта",
        "it": "Dimensione del testo",
        "vi": "Cỡ chữ",
        "hi": "फ़ॉन्ट आकार",
        "id": "Ukuran font",
    },
    "settings.font_size_reset": {
        "en": "Reset",
        "zh-tw": "還原預設",
        "zh-cn": "恢复默认",
        "ja": "既定に戻す",
        "es": "Restablecer",
        "fr": "Réinitialiser",
        "de": "Zurücksetzen",
        "ko": "기본값 복원",
        "pt": "Redefinir",
        "ru": "Сбросить",
        "it": "Ripristina",
        "vi": "Đặt lại",
        "hi": "रीसेट करें",
        "id": "Atur ulang",
    },
    "settings.font_size_hint": {
        "en": "Applied at once. Ctrl++ larger, Ctrl+- smaller, Ctrl+0 default.",
        "zh-tw": "立即套用。Ctrl++ 放大，Ctrl+- 縮小，Ctrl+0 還原預設。",
        "zh-cn": "立即应用。Ctrl++ 放大，Ctrl+- 缩小，Ctrl+0 恢复默认。",
        "ja": "すぐに反映されます。Ctrl++ で拡大、Ctrl+- で縮小、Ctrl+0 で既定に戻ります。",
        "es": "Se aplica al instante. Ctrl++ agranda, Ctrl+- reduce, Ctrl+0 restablece.",
        "fr": "S'applique aussitôt. Ctrl++ agrandit, Ctrl+- réduit, Ctrl+0 réinitialise.",
        "de": "Gilt sofort. Strg++ größer, Strg+- kleiner, Strg+0 Standard.",
        "ko": "바로 적용됩니다. Ctrl++ 크게, Ctrl+- 작게, Ctrl+0 기본값.",
        "pt": "Aplicado na hora. Ctrl++ aumenta, Ctrl+- diminui, Ctrl+0 volta ao padrão.",
        "ru": "Применяется сразу. Ctrl++ крупнее, Ctrl+- мельче, Ctrl+0 по умолчанию.",
        "it": "Applicata subito. Ctrl++ ingrandisce, Ctrl+- riduce, Ctrl+0 ripristina.",
        "vi": "Áp dụng ngay. Ctrl++ phóng to, Ctrl+- thu nhỏ, Ctrl+0 về mặc định.",
        "hi": "तुरंत लागू होता है। Ctrl++ बड़ा, Ctrl+- छोटा, Ctrl+0 डिफ़ॉल्ट।",
        "id": "Langsung diterapkan. Ctrl++ memperbesar, Ctrl+- memperkecil, Ctrl+0 default.",
    },
    # Stage A: cancel, snowball bounds, results filter / ticks / menu --
    "action.cancel": {
        "en": "Cancel",
        "zh-tw": "取消",
        "zh-cn": "取消",
        "ja": "キャンセル",
        "es": "Cancelar",
        "fr": "Annuler",
        "de": "Abbrechen",
        "ko": "취소",
        "pt": "Cancelar",
        "ru": "Отмена",
        "it": "Annulla",
        "vi": "Hủy",
        "hi": "रद्द करें",
        "id": "Batal",
    },
    "search.status_cancelled": {
        "en": "Search cancelled. The previous results are kept.",
        "zh-tw": "已取消搜尋，保留先前的結果。",
        "zh-cn": "已取消搜索，保留之前的结果。",
        "ja": "検索をキャンセルしました。前回の結果はそのままです。",
        "es": "Búsqueda cancelada. Se conservan los resultados anteriores.",
        "fr": "Recherche annulée. Les résultats précédents sont conservés.",
        "de": "Suche abgebrochen. Die bisherigen Ergebnisse bleiben erhalten.",
        "ko": "검색을 취소했습니다. 이전 결과는 그대로 유지됩니다.",
        "pt": "Pesquisa cancelada. Os resultados anteriores foram mantidos.",
        "ru": "Поиск отменён. Предыдущие результаты сохранены.",
        "it": "Ricerca annullata. I risultati precedenti restano.",
        "vi": "Đã hủy tìm kiếm. Kết quả trước đó được giữ lại.",
        "hi": "खोज रद्द की गई। पिछले परिणाम बने रहेंगे।",
        "id": "Pencarian dibatalkan. Hasil sebelumnya tetap disimpan.",
    },
    "search.snowball_advanced": {
        "en": "Advanced snowball settings",
        "zh-tw": "進階滾雪球設定",
        "zh-cn": "高级滚雪球设置",
        "ja": "スノーボールの詳細設定",
        "es": "Ajustes avanzados de bola de nieve",
        "fr": "Réglages avancés de la boule de neige",
        "de": "Erweiterte Schneeball-Einstellungen",
        "ko": "스노볼 고급 설정",
        "pt": "Configurações avançadas da bola de neve",
        "ru": "Расширенные настройки снежного кома",
        "it": "Impostazioni avanzate della palla di neve",
        "vi": "Cài đặt lăn cầu tuyết nâng cao",
        "hi": "उन्नत snowball सेटिंग्स",
        "id": "Pengaturan lanjutan bola salju",
    },
    "search.snowball_seeds": {
        "en": "Top results to expand",
        "zh-tw": "延伸前幾筆結果",
        "zh-cn": "扩展前几条结果",
        "ja": "展開する上位の結果数",
        "es": "Primeros resultados a expandir",
        "fr": "Premiers résultats à étendre",
        "de": "Zu erweiternde Top-Ergebnisse",
        "ko": "확장할 상위 결과 수",
        "pt": "Primeiros resultados a expandir",
        "ru": "Сколько первых результатов расширять",
        "it": "Primi risultati da espandere",
        "vi": "Số kết quả đầu cần mở rộng",
        "hi": "विस्तार के लिए शीर्ष परिणाम",
        "id": "Hasil teratas yang diperluas",
    },
    "search.snowball_depth": {
        "en": "Steps from each result",
        "zh-tw": "每筆結果延伸的層數",
        "zh-cn": "每条结果扩展的层数",
        "ja": "各結果からたどる段数",
        "es": "Pasos desde cada resultado",
        "fr": "Étapes depuis chaque résultat",
        "de": "Schritte ab jedem Ergebnis",
        "ko": "각 결과에서 따라갈 단계 수",
        "pt": "Passos a partir de cada resultado",
        "ru": "Шагов от каждого результата",
        "it": "Passi da ogni risultato",
        "vi": "Số bước từ mỗi kết quả",
        "hi": "हर परिणाम से चरण",
        "id": "Langkah dari setiap hasil",
    },
    "search.snowball_max_per_seed": {
        "en": "Papers per result and direction",
        "zh-tw": "每筆結果、每個方向的論文數",
        "zh-cn": "每条结果、每个方向的论文数",
        "ja": "結果・方向ごとの論文数",
        "es": "Artículos por resultado y dirección",
        "fr": "Articles par résultat et direction",
        "de": "Artikel pro Ergebnis und Richtung",
        "ko": "결과·방향별 논문 수",
        "pt": "Artigos por resultado e direção",
        "ru": "Статей на результат и направление",
        "it": "Articoli per risultato e direzione",
        "vi": "Số bài báo mỗi kết quả và hướng",
        "hi": "प्रति परिणाम और दिशा शोध-पत्र",
        "id": "Makalah per hasil dan arah",
    },
    "search.snowball_max_total": {
        "en": "New papers in all (at most)",
        "zh-tw": "新增論文總數上限",
        "zh-cn": "新增论文总数上限",
        "ja": "追加する論文の上限",
        "es": "Máximo de artículos nuevos en total",
        "fr": "Nouveaux articles au total (au plus)",
        "de": "Neue Artikel insgesamt (höchstens)",
        "ko": "새 논문 총수 (최대)",
        "pt": "Máximo de artigos novos no total",
        "ru": "Всего новых статей (не более)",
        "it": "Nuovi articoli in tutto (al massimo)",
        "vi": "Tổng số bài báo mới (tối đa)",
        "hi": "कुल नए शोध-पत्र (अधिकतम)",
        "id": "Total makalah baru (paling banyak)",
    },
    "search.snowball_min_relevance": {
        "en": "Minimum relevance (0 to 1, dash = off)",
        "zh-tw": "最低相關度(0 到 1，— 表示不限)",
        "zh-cn": "最低相关度(0 到 1，— 表示不限)",
        "ja": "最低関連度(0〜1、— は制限なし)",
        "es": "Relevancia mínima (0 a 1, guion = sin límite)",
        "fr": "Pertinence minimale (0 à 1, tiret = aucune)",
        "de": "Mindestrelevanz (0 bis 1, Strich = aus)",
        "ko": "최소 관련도 (0~1, — 는 제한 없음)",
        "pt": "Relevância mínima (0 a 1, traço = sem limite)",
        "ru": "Минимальная релевантность (0–1, прочерк = без порога)",
        "it": "Rilevanza minima (da 0 a 1, trattino = nessuna)",
        "vi": "Độ liên quan tối thiểu (0 đến 1, gạch = không giới hạn)",
        "hi": "न्यूनतम प्रासंगिकता (0 से 1, डैश = बंद)",
        "id": "Relevansi minimum (0 sampai 1, tanda pisah = mati)",
    },
    "search.filter_placeholder": {
        "en": "Filter by title, author, venue or DOI",
        "zh-tw": "依標題、作者、出處或 DOI 篩選",
        "zh-cn": "按标题、作者、出处或 DOI 筛选",
        "ja": "タイトル・著者・掲載誌・DOI で絞り込み",
        "es": "Filtrar por título, autor, publicación o DOI",
        "fr": "Filtrer par titre, auteur, revue ou DOI",
        "de": "Nach Titel, Autor, Publikationsort oder DOI filtern",
        "ko": "제목·저자·게재처·DOI로 필터",
        "pt": "Filtrar por título, autor, veículo ou DOI",
        "ru": "Фильтр по названию, автору, изданию или DOI",
        "it": "Filtra per titolo, autore, sede o DOI",
        "vi": "Lọc theo tiêu đề, tác giả, nơi đăng hoặc DOI",
        "hi": "शीर्षक, लेखक, प्रकाशन स्थल या DOI से फ़िल्टर करें",
        "id": "Saring menurut judul, penulis, publikasi, atau DOI",
    },
    "search.filter_all_sources": {
        "en": "All sources",
        "zh-tw": "所有來源",
        "zh-cn": "所有来源",
        "ja": "すべてのソース",
        "es": "Todas las fuentes",
        "fr": "Toutes les sources",
        "de": "Alle Quellen",
        "ko": "모든 소스",
        "pt": "Todas as fontes",
        "ru": "Все источники",
        "it": "Tutte le fonti",
        "vi": "Tất cả nguồn",
        "hi": "सभी स्रोत",
        "id": "Semua sumber",
    },
    "search.tick_shown": {
        "en": "Tick shown",
        "zh-tw": "勾選顯示的",
        "zh-cn": "勾选显示的",
        "ja": "表示中を選択",
        "es": "Marcar visibles",
        "fr": "Cocher les visibles",
        "de": "Angezeigte anhaken",
        "ko": "표시된 항목 선택",
        "pt": "Marcar visíveis",
        "ru": "Отметить видимые",
        "it": "Seleziona visibili",
        "vi": "Chọn mục đang hiện",
        "hi": "दिखाए गए चुनें",
        "id": "Centang yang tampil",
    },
    "search.untick_shown": {
        "en": "Untick shown",
        "zh-tw": "取消勾選顯示的",
        "zh-cn": "取消勾选显示的",
        "ja": "表示中の選択を解除",
        "es": "Desmarcar visibles",
        "fr": "Décocher les visibles",
        "de": "Angezeigte abwählen",
        "ko": "표시된 항목 선택 해제",
        "pt": "Desmarcar visíveis",
        "ru": "Снять отметку с видимых",
        "it": "Deseleziona visibili",
        "vi": "Bỏ chọn mục đang hiện",
        "hi": "दिखाए गए अचयनित करें",
        "id": "Hapus centang yang tampil",
    },
    "search.selection_count": {
        "en": "{checked} of {total} ticked",
        "zh-tw": "已勾選 {checked} / {total}",
        "zh-cn": "已勾选 {checked} / {total}",
        "ja": "{total} 件中 {checked} 件を選択",
        "es": "{checked} de {total} marcados",
        "fr": "{checked} sur {total} cochés",
        "de": "{checked} von {total} angehakt",
        "ko": "{total}개 중 {checked}개 선택",
        "pt": "{checked} de {total} marcados",
        "ru": "Отмечено {checked} из {total}",
        "it": "{checked} di {total} selezionati",
        "vi": "Đã chọn {checked}/{total}",
        "hi": "{total} में से {checked} चुने गए",
        "id": "{checked} dari {total} dicentang",
    },
    "search.menu_open_page": {
        "en": "Open paper page",
        "zh-tw": "開啟論文頁面",
        "zh-cn": "打开论文页面",
        "ja": "論文ページを開く",
        "es": "Abrir la página del artículo",
        "fr": "Ouvrir la page de l'article",
        "de": "Artikelseite öffnen",
        "ko": "논문 페이지 열기",
        "pt": "Abrir a página do artigo",
        "ru": "Открыть страницу статьи",
        "it": "Apri la pagina dell'articolo",
        "vi": "Mở trang bài báo",
        "hi": "शोध-पत्र का पेज खोलें",
        "id": "Buka halaman makalah",
    },
    "search.menu_open_pdf": {
        "en": "Open PDF",
        "zh-tw": "開啟 PDF",
        "zh-cn": "打开 PDF",
        "ja": "PDF を開く",
        "es": "Abrir el PDF",
        "fr": "Ouvrir le PDF",
        "de": "PDF öffnen",
        "ko": "PDF 열기",
        "pt": "Abrir o PDF",
        "ru": "Открыть PDF",
        "it": "Apri il PDF",
        "vi": "Mở PDF",
        "hi": "PDF खोलें",
        "id": "Buka PDF",
    },
    "search.menu_copy_doi": {
        "en": "Copy DOI",
        "zh-tw": "複製 DOI",
        "zh-cn": "复制 DOI",
        "ja": "DOI をコピー",
        "es": "Copiar el DOI",
        "fr": "Copier le DOI",
        "de": "DOI kopieren",
        "ko": "DOI 복사",
        "pt": "Copiar o DOI",
        "ru": "Копировать DOI",
        "it": "Copia il DOI",
        "vi": "Sao chép DOI",
        "hi": "DOI कॉपी करें",
        "id": "Salin DOI",
    },
    "search.menu_copy_bibtex": {
        "en": "Copy BibTeX",
        "zh-tw": "複製 BibTeX",
        "zh-cn": "复制 BibTeX",
        "ja": "BibTeX をコピー",
        "es": "Copiar BibTeX",
        "fr": "Copier le BibTeX",
        "de": "BibTeX kopieren",
        "ko": "BibTeX 복사",
        "pt": "Copiar BibTeX",
        "ru": "Копировать BibTeX",
        "it": "Copia BibTeX",
        "vi": "Sao chép BibTeX",
        "hi": "BibTeX कॉपी करें",
        "id": "Salin BibTeX",
    },
    "enrich.row_cancelled": {
        "en": "not run (stopped)",
        "zh-tw": "未執行(已停止)",
        "zh-cn": "未执行(已停止)",
        "ja": "未実行(停止)",
        "es": "no procesado (detenido)",
        "fr": "non traité (arrêté)",
        "de": "nicht ausgeführt (gestoppt)",
        "ko": "실행 안 함 (중지됨)",
        "pt": "não processado (interrompido)",
        "ru": "не выполнено (остановлено)",
        "it": "non eseguito (interrotto)",
        "vi": "chưa chạy (đã dừng)",
        "hi": "नहीं चला (रोका गया)",
        "id": "tidak dijalankan (dihentikan)",
    },
    "enrich.status_cancelled": {
        "en": "Stopped after {done} of {total} papers. The rest keep their search record.",
        "zh-tw": "已在 {total} 篇中的第 {done} 篇後停止，其餘論文保留搜尋時的資料。",
        "zh-cn": "已在 {total} 篇中的第 {done} 篇后停止，其余论文保留搜索时的数据。",
        "ja": "{total} 件中 {done} 件で停止しました。残りは検索時の情報のままです。",
        "es": (
            "Detenido tras {done} de {total} artículos. El resto conserva su registro de búsqueda."
        ),
        "fr": (
            "Arrêté après {done} articles sur {total}. Les autres gardent leur fiche de recherche."
        ),
        "de": (
            "Nach {done} von {total} Artikeln gestoppt. Die übrigen behalten ihren Suchdatensatz."
        ),
        "ko": "{total}편 중 {done}편 이후 중지했습니다. 나머지는 검색 시 정보를 유지합니다.",
        "pt": (
            "Interrompido após {done} de {total} artigos. Os demais mantêm o registro da pesquisa."
        ),
        "ru": "Остановлено после {done} из {total} статей. Остальные сохраняют данные поиска.",
        "it": (
            "Interrotto dopo {done} di {total} articoli. Gli altri mantengono il record di ricerca."
        ),
        "vi": "Đã dừng sau {done}/{total} bài báo. Các bài còn lại giữ dữ liệu tìm kiếm.",
        "hi": "{total} में से {done} शोध-पत्रों के बाद रोका गया। बाकी अपना खोज रिकॉर्ड रखते हैं।",
        "id": "Dihentikan setelah {done} dari {total} makalah. Sisanya menyimpan data pencarian.",
    },
    # Library page --------------------------------------------------------
    "nav.library": {
        "en": "Library",
        "zh-tw": "文獻庫",
        "zh-cn": "文献库",
        "ja": "ライブラリ",
        "es": "Biblioteca",
        "fr": "Bibliothèque",
        "de": "Bibliothek",
        "ko": "라이브러리",
        "pt": "Biblioteca",
        "ru": "Библиотека",
        "it": "Biblioteca",
        "vi": "Thư viện",
        "hi": "लाइब्रेरी",
        "id": "Pustaka",
    },
    "page.library_subtitle": {
        "en": (
            "Browse a library file: what it holds, the searches that filled it, and the citation "
            "links between its papers. Read only."
        ),
        "zh-tw": "瀏覽文獻庫檔案：收錄的論文、累積它的歷次搜尋，以及論文之間的引用關係。唯讀。",
        "zh-cn": "浏览文献库文件：收录的论文、积累它的历次搜索，以及论文之间的引用关系。只读。",
        "ja": (
            "ライブラリファイルを閲覧します。収録論文、それを集めた検索、"
            "論文間の引用関係を表示します。読み取り専用です。"
        ),
        "es": (
            "Explore un archivo de biblioteca: lo que contiene, las búsquedas que lo llenaron y "
            "los enlaces de citas entre sus artículos. Solo lectura."
        ),
        "fr": (
            "Parcourez un fichier de bibliothèque : son contenu, les recherches qui l'ont rempli "
            "et les liens de citation entre ses articles. Lecture seule."
        ),
        "de": (
            "Eine Bibliotheksdatei durchsehen: ihren Inhalt, die Suchen, die sie gefüllt haben, "
            "und die Zitationen zwischen ihren Artikeln. Nur lesend."
        ),
        "ko": (
            "라이브러리 파일을 살펴봅니다. 담긴 논문, 이를 채운 검색들, 논문 간 인용 관계를 보여 "
            "줍니다. 읽기 전용입니다."
        ),
        "pt": (
            "Explore um arquivo de biblioteca: o que ele contém, as pesquisas que o preencheram e "
            "os vínculos de citação entre os artigos. Somente leitura."
        ),
        "ru": (
            "Просмотр файла библиотеки: что в нём хранится, какие поиски его наполнили и как "
            "статьи цитируют друг друга. Только чтение."
        ),
        "it": (
            "Consulta un file di biblioteca: cosa contiene, le ricerche che l'hanno riempito e i "
            "legami di citazione tra gli articoli. Sola lettura."
        ),
        "vi": (
            "Duyệt một tệp thư viện: nội dung, các lần tìm kiếm đã bổ sung vào nó và liên kết "
            "trích dẫn giữa các bài báo. Chỉ đọc."
        ),
        "hi": (
            "लाइब्रेरी फ़ाइल देखें: उसमें क्या है, किन खोजों ने उसे भरा, और उसके शोध-पत्रों के बीच "
            "उद्धरण संबंध। केवल पढ़ने के लिए।"
        ),
        "id": (
            "Jelajahi berkas pustaka: isinya, pencarian yang mengisinya, dan tautan sitasi "
            "antarmakalah. Hanya baca."
        ),
    },
    "library.card_file": {
        "en": "Library file",
        "zh-tw": "文獻庫檔案",
        "zh-cn": "文献库文件",
        "ja": "ライブラリファイル",
        "es": "Archivo de biblioteca",
        "fr": "Fichier de bibliothèque",
        "de": "Bibliotheksdatei",
        "ko": "라이브러리 파일",
        "pt": "Arquivo da biblioteca",
        "ru": "Файл библиотеки",
        "it": "File della biblioteca",
        "vi": "Tệp thư viện",
        "hi": "लाइब्रेरी फ़ाइल",
        "id": "Berkas pustaka",
    },
    "library.query_placeholder": {
        "en": "Find in the library (empty lists every paper)",
        "zh-tw": "在文獻庫中搜尋(留空則列出全部論文)",
        "zh-cn": "在文献库中搜索(留空则列出全部论文)",
        "ja": "ライブラリ内を検索(空欄ですべての論文)",
        "es": "Buscar en la biblioteca (vacío muestra todos los artículos)",
        "fr": "Chercher dans la bibliothèque (vide : tous les articles)",
        "de": "In der Bibliothek suchen (leer zeigt alle Artikel)",
        "ko": "라이브러리에서 찾기 (비워 두면 전체 논문)",
        "pt": "Procurar na biblioteca (vazio lista todos os artigos)",
        "ru": "Поиск в библиотеке (пусто: все статьи)",
        "it": "Cerca nella biblioteca (vuoto elenca tutti gli articoli)",
        "vi": "Tìm trong thư viện (để trống để liệt kê mọi bài báo)",
        "hi": "लाइब्रेरी में खोजें (खाली छोड़ने पर सभी शोध-पत्र)",
        "id": "Cari di pustaka (kosong menampilkan semua makalah)",
    },
    "library.card_overview": {
        "en": "Overview",
        "zh-tw": "概況",
        "zh-cn": "概况",
        "ja": "概要",
        "es": "Resumen",
        "fr": "Vue d'ensemble",
        "de": "Überblick",
        "ko": "개요",
        "pt": "Visão geral",
        "ru": "Обзор",
        "it": "Panoramica",
        "vi": "Tổng quan",
        "hi": "सारांश",
        "id": "Ikhtisar",
    },
    "library.stat_papers": {
        "en": "Papers",
        "zh-tw": "論文",
        "zh-cn": "论文",
        "ja": "論文",
        "es": "Artículos",  # NOSONAR translation, matching words in other keys are not one constant
        "fr": "Articles",
        "de": "Artikel",
        "ko": "논문",
        "pt": "Artigos",
        "ru": "Статьи",
        "it": "Articoli",
        "vi": "Bài báo",  # NOSONAR translation, matching words in other keys are not one constant
        "hi": "शोध-पत्र",  # NOSONAR translation, matching words in other keys are not one constant
        "id": "Makalah",
    },
    "library.stat_runs": {
        "en": "Searches",
        "zh-tw": "搜尋次數",
        "zh-cn": "搜索次数",
        "ja": "検索回数",
        "es": "Búsquedas",
        "fr": "Recherches",
        "de": "Suchen",
        "ko": "검색 횟수",
        "pt": "Pesquisas",
        "ru": "Поиски",
        "it": "Ricerche",
        "vi": "Lần tìm kiếm",
        "hi": "खोजें",
        "id": "Pencarian",
    },
    "library.stat_relations": {
        "en": "Citation links",
        "zh-tw": "引用關係",
        "zh-cn": "引用关系",
        "ja": "引用リンク",
        "es": "Enlaces de citas",
        "fr": "Liens de citation",
        "de": "Zitationen",
        "ko": "인용 관계",
        "pt": "Vínculos de citação",
        "ru": "Связи цитирования",
        "it": "Legami di citazione",
        "vi": "Liên kết trích dẫn",
        "hi": "उद्धरण संबंध",
        "id": "Tautan sitasi",
    },
    "library.stat_years": {
        "en": "Years",
        "zh-tw": "年份範圍",
        "zh-cn": "年份范围",
        "ja": "年",
        "es": "Años",
        "fr": "Années",
        "de": "Jahre",
        "ko": "연도",
        "pt": "Anos",
        "ru": "Годы",
        "it": "Anni",
        "vi": "Năm",
        "hi": "वर्ष",
        "id": "Tahun",
    },
    "library.stat_sources": {
        "en": "Papers per source",
        "zh-tw": "各來源論文數",
        "zh-cn": "各来源论文数",
        "ja": "ソース別の論文数",
        "es": "Artículos por fuente",
        "fr": "Articles par source",
        "de": "Artikel je Quelle",
        "ko": "소스별 논문 수",
        "pt": "Artigos por fonte",
        "ru": "Статей по источникам",
        "it": "Articoli per fonte",
        "vi": "Bài báo theo nguồn",
        "hi": "प्रति स्रोत शोध-पत्र",
        "id": "Makalah per sumber",
    },
    "library.stat_checks": {
        "en": "Identifier checks",
        "zh-tw": "識別碼檢查",
        "zh-cn": "标识符检查",
        "ja": "識別子の確認",
        "es": "Comprobaciones de identificadores",
        "fr": "Vérifications d'identifiants",
        "de": "Kennungsprüfungen",
        "ko": "식별자 검사",
        "pt": "Verificações de identificadores",
        "ru": "Проверки идентификаторов",
        "it": "Verifiche degli identificatori",
        "vi": "Kiểm tra định danh",
        "hi": "पहचानकर्ता जाँच",
        "id": "Pemeriksaan pengenal",
    },
    "library.open_button": {
        "en": "Open library",
        "zh-tw": "開啟文獻庫",
        "zh-cn": "打开文献库",
        "ja": "ライブラリを開く",
        "es": "Abrir la biblioteca",
        "fr": "Ouvrir la bibliothèque",
        "de": "Bibliothek öffnen",
        "ko": "라이브러리 열기",
        "pt": "Abrir a biblioteca",
        "ru": "Открыть библиотеку",
        "it": "Apri la biblioteca",
        "vi": "Mở thư viện",
        "hi": "लाइब्रेरी खोलें",
        "id": "Buka pustaka",
    },
    "library.send_button": {
        "en": "Send to Enrich and Deck",
        "zh-tw": "送往豐富化與投影片",
        "zh-cn": "发送到丰富化与幻灯片",
        "ja": "強化とスライドへ送る",
        "es": "Enviar a Enriquecer y Diapositivas",
        "fr": "Envoyer vers Enrichir et Diapos",
        "de": "An Anreichern und Folien senden",
        "ko": "보강과 슬라이드로 보내기",
        "pt": "Enviar para Enriquecer e Slides",
        "ru": "Передать в Обогащение и Слайды",
        "it": "Invia ad Arricchisci e Diapositive",
        "vi": "Gửi sang Làm giàu và Slide",
        "hi": "समृद्ध करें और स्लाइड को भेजें",
        "id": "Kirim ke Perkaya dan Slide",
    },
    "library.tab_papers": {
        "en": "Papers",
        "zh-tw": "論文",
        "zh-cn": "论文",
        "ja": "論文",
        "es": "Artículos",
        "fr": "Articles",
        "de": "Artikel",
        "ko": "논문",
        "pt": "Artigos",
        "ru": "Статьи",
        "it": "Articoli",
        "vi": "Bài báo",
        "hi": "शोध-पत्र",
        "id": "Makalah",
    },
    "library.tab_runs": {
        "en": "Searches",
        "zh-tw": "搜尋紀錄",
        "zh-cn": "搜索记录",
        "ja": "検索履歴",
        "es": "Búsquedas",
        "fr": "Recherches",
        "de": "Suchen",
        "ko": "검색 기록",
        "pt": "Pesquisas",
        "ru": "Поиски",
        "it": "Ricerche",
        "vi": "Lần tìm kiếm",
        "hi": "खोजें",
        "id": "Pencarian",
    },
    "library.col_sources": {
        "en": "Sources",
        "zh-tw": "來源",
        "zh-cn": "来源",
        "ja": "ソース",
        "es": "Fuentes",
        "fr": "Sources",
        "de": "Quellen",
        "ko": "소스",
        "pt": "Fontes",
        "ru": "Источники",
        "it": "Fonti",
        "vi": "Nguồn",
        "hi": "स्रोत",
        "id": "Sumber",
    },
    "library.col_seen": {
        "en": "Times seen",
        "zh-tw": "出現次數",
        "zh-cn": "出现次数",
        "ja": "出現回数",
        "es": "Veces vista",
        "fr": "Vu",
        "de": "Gesehen",
        "ko": "등장 횟수",
        "pt": "Vezes vista",
        "ru": "Встречалась",
        "it": "Volte vista",
        "vi": "Số lần gặp",
        "hi": "कितनी बार मिला",
        "id": "Kali terlihat",
    },
    "library.col_last_seen": {
        "en": "Last seen",
        "zh-tw": "最近出現",
        "zh-cn": "最近出现",
        "ja": "最終出現",
        "es": "Última vez",
        "fr": "Vu en dernier",
        "de": "Zuletzt gesehen",
        "ko": "마지막 등장",
        "pt": "Última vez",
        "ru": "Последний раз",
        "it": "Ultima volta",
        "vi": "Lần cuối",
        "hi": "आख़िरी बार",
        "id": "Terakhir terlihat",
    },
    "library.col_date": {
        "en": "Date",
        "zh-tw": "日期",
        "zh-cn": "日期",
        "ja": "日時",
        "es": "Fecha",
        "fr": "Date",
        "de": "Datum",
        "ko": "날짜",
        "pt": "Data",
        "ru": "Дата",
        "it": "Data",
        "vi": "Ngày",
        "hi": "तारीख़",
        "id": "Tanggal",
    },
    "library.col_kind": {
        "en": "Kind",
        "zh-tw": "類型",
        "zh-cn": "类型",
        "ja": "種類",
        "es": "Tipo",
        "fr": "Type",
        "de": "Art",
        "ko": "종류",
        "pt": "Tipo",
        "ru": "Тип",
        "it": "Tipo",
        "vi": "Loại",
        "hi": "प्रकार",
        "id": "Jenis",
    },
    "library.col_keywords": {
        "en": "Keywords",
        "zh-tw": "關鍵字",
        "zh-cn": "关键词",
        "ja": "キーワード",
        "es": "Palabras clave",
        "fr": "Mots-clés",
        "de": "Suchbegriffe",
        "ko": "키워드",
        "pt": "Palavras-chave",
        "ru": "Ключевые слова",
        "it": "Parole chiave",
        "vi": "Từ khóa",
        "hi": "कीवर्ड",
        "id": "Kata kunci",
    },
    "library.col_papers": {
        "en": "Papers",
        "zh-tw": "論文數",
        "zh-cn": "论文数",
        "ja": "論文数",
        "es": "Artículos",
        "fr": "Articles",
        "de": "Artikel",
        "ko": "논문 수",
        "pt": "Artigos",
        "ru": "Статей",
        "it": "Articoli",
        "vi": "Bài báo",
        "hi": "शोध-पत्र",
        "id": "Makalah",
    },
    "library.detail_cites": {
        "en": "Cites ({count} in the library)",
        "zh-tw": "引用了(文獻庫中 {count} 篇)",
        "zh-cn": "引用了(文献库中 {count} 篇)",
        "ja": "引用している論文(ライブラリ内 {count} 件)",
        "es": "Cita a ({count} en la biblioteca)",
        "fr": "Cite ({count} dans la bibliothèque)",
        "de": "Zitiert ({count} in der Bibliothek)",
        "ko": "인용한 논문 (라이브러리 내 {count}편)",
        "pt": "Cita ({count} na biblioteca)",
        "ru": "Цитирует ({count} в библиотеке)",
        "it": "Cita ({count} nella biblioteca)",
        "vi": "Trích dẫn ({count} trong thư viện)",
        "hi": "उद्धृत करता है (लाइब्रेरी में {count})",
        "id": "Mengutip ({count} di pustaka)",
    },
    "library.detail_cited_by": {
        "en": "Cited by ({count} in the library)",
        "zh-tw": "被引用(文獻庫中 {count} 篇)",
        "zh-cn": "被引用(文献库中 {count} 篇)",
        "ja": "引用されている論文(ライブラリ内 {count} 件)",
        "es": "Citado por ({count} en la biblioteca)",
        "fr": "Cité par ({count} dans la bibliothèque)",
        "de": "Zitiert von ({count} in der Bibliothek)",
        "ko": "이 논문을 인용한 논문 (라이브러리 내 {count}편)",
        "pt": "Citado por ({count} na biblioteca)",
        "ru": "Цитируется ({count} в библиотеке)",
        "it": "Citato da ({count} nella biblioteca)",
        "vi": "Được trích dẫn bởi ({count} trong thư viện)",
        "hi": "इनके द्वारा उद्धृत (लाइब्रेरी में {count})",
        "id": "Dikutip oleh ({count} di pustaka)",
    },
    "library.detail_checks": {
        "en": "Identifier checks ({count})",
        "zh-tw": "識別碼檢查({count})",
        "zh-cn": "标识符检查({count})",
        "ja": "識別子の確認({count})",
        "es": "Comprobaciones de identificadores ({count})",
        "fr": "Vérifications d'identifiants ({count})",
        "de": "Kennungsprüfungen ({count})",
        "ko": "식별자 검사 ({count})",
        "pt": "Verificações de identificadores ({count})",
        "ru": "Проверки идентификаторов ({count})",
        "it": "Verifiche degli identificatori ({count})",
        "vi": "Kiểm tra định danh ({count})",
        "hi": "पहचानकर्ता जाँच ({count})",
        "id": "Pemeriksaan pengenal ({count})",
    },
    "library.detail_none": {
        "en": "None.",
        "zh-tw": "無。",
        "zh-cn": "无。",
        "ja": "なし。",
        "es": "Ninguno.",
        "fr": "Aucun.",
        "de": "Keine.",
        "ko": "없음.",
        "pt": "Nenhum.",
        "ru": "Нет.",
        "it": "Nessuno.",
        "vi": "Không có.",
        "hi": "कोई नहीं।",
        "id": "Tidak ada.",
    },
    "library.detail_hint": {
        "en": "Select a paper to see its citation links and identifier checks.",
        "zh-tw": "選取一篇論文以查看其引用關係與識別碼檢查。",
        "zh-cn": "选择一篇论文以查看其引用关系与标识符检查。",
        "ja": "論文を選ぶと、引用関係と識別子の確認結果が表示されます。",
        "es": (
            "Seleccione un artículo para ver sus enlaces de citas y comprobaciones de "
            "identificadores."
        ),
        "fr": (
            "Sélectionnez un article pour voir ses liens de citation et ses vérifications "
            "d'identifiants."
        ),
        "de": "Wählen Sie einen Artikel, um seine Zitationen und Kennungsprüfungen zu sehen.",
        "ko": "논문을 선택하면 인용 관계와 식별자 검사 결과를 볼 수 있습니다.",
        "pt": (
            "Selecione um artigo para ver seus vínculos de citação e verificações de "
            "identificadores."
        ),
        "ru": "Выберите статью, чтобы увидеть её связи цитирования и проверки идентификаторов.",
        "it": (
            "Seleziona un articolo per vedere i suoi legami di citazione e le verifiche degli "
            "identificatori."
        ),
        "vi": "Chọn một bài báo để xem liên kết trích dẫn và kết quả kiểm tra định danh.",
        "hi": "उद्धरण संबंध और पहचानकर्ता जाँच देखने के लिए कोई शोध-पत्र चुनें।",
        "id": "Pilih makalah untuk melihat tautan sitasi dan pemeriksaan pengenalnya.",
    },
    "library.status_loaded": {
        "en": "Showing {shown} of {papers} papers. {runs} searches, {relations} citation links.",
        "zh-tw": "顯示 {papers} 篇中的 {shown} 篇。共 {runs} 次搜尋、{relations} 條引用關係。",
        "zh-cn": "显示 {papers} 篇中的 {shown} 篇。共 {runs} 次搜索、{relations} 条引用关系。",
        "ja": "{papers} 件中 {shown} 件を表示。検索 {runs} 回、引用リンク {relations} 件。",
        "es": (
            "Se muestran {shown} de {papers} artículos. {runs} búsquedas, {relations} enlaces de "
            "citas."
        ),
        "fr": (
            "{shown} articles affichés sur {papers}. {runs} recherches, {relations} liens de "
            "citation."
        ),
        "de": "{shown} von {papers} Artikeln angezeigt. {runs} Suchen, {relations} Zitationen.",
        "ko": "{papers}편 중 {shown}편 표시. 검색 {runs}회, 인용 관계 {relations}개.",
        "pt": (
            "Mostrando {shown} de {papers} artigos. {runs} pesquisas, {relations} vínculos de "
            "citação."
        ),
        "ru": (
            "Показано {shown} из {papers} статей. Поисков: {runs}, связей цитирования: {relations}."
        ),
        "it": (
            "Mostrati {shown} di {papers} articoli. {runs} ricerche, {relations} legami di "
            "citazione."
        ),
        "vi": (
            "Đang hiển thị {shown}/{papers} bài báo. {runs} lần tìm kiếm, {relations} liên kết "
            "trích dẫn."
        ),
        "hi": "{papers} में से {shown} शोध-पत्र दिखाए गए। {runs} खोजें, {relations} उद्धरण संबंध।",
        "id": (
            "Menampilkan {shown} dari {papers} makalah. {runs} pencarian, {relations} tautan "
            "sitasi."
        ),
    },
    "library.status_sent": {
        "en": "{count} papers sent to Enrich and Deck.",
        "zh-tw": "已將 {count} 篇論文送往豐富化與投影片。",
        "zh-cn": "已将 {count} 篇论文发送到丰富化与幻灯片。",
        "ja": "{count} 件の論文を強化とスライドへ送りました。",
        "es": "{count} artículos enviados a Enriquecer y Diapositivas.",
        "fr": "{count} articles envoyés vers Enrichir et Diapos.",
        "de": "{count} Artikel an Anreichern und Folien gesendet.",
        "ko": "논문 {count}편을 보강과 슬라이드로 보냈습니다.",
        "pt": "{count} artigos enviados para Enriquecer e Slides.",
        "ru": "Передано статей в Обогащение и Слайды: {count}.",
        "it": "{count} articoli inviati ad Arricchisci e Diapositive.",
        "vi": "Đã gửi {count} bài báo sang Làm giàu và Slide.",
        "hi": "{count} शोध-पत्र समृद्ध करें और स्लाइड को भेजे गए।",
        "id": "{count} makalah dikirim ke Perkaya dan Slide.",
    },
    "library.error": {
        "en": "Could not open the library: {error}",
        "zh-tw": "無法開啟文獻庫：{error}",
        "zh-cn": "无法打开文献库：{error}",
        "ja": "ライブラリを開けませんでした: {error}",
        "es": "No se pudo abrir la biblioteca: {error}",
        "fr": "Impossible d'ouvrir la bibliothèque : {error}",
        "de": "Bibliothek konnte nicht geöffnet werden: {error}",
        "ko": "라이브러리를 열 수 없습니다: {error}",
        "pt": "Não foi possível abrir a biblioteca: {error}",
        "ru": "Не удалось открыть библиотеку: {error}",
        "it": "Impossibile aprire la biblioteca: {error}",
        "vi": "Không mở được thư viện: {error}",
        "hi": "लाइब्रेरी नहीं खुल सकी: {error}",
        "id": "Tidak dapat membuka pustaka: {error}",
    },
    # Stage C: template check, deck review, agent hand-off ----------------
    "action.copy": {
        "en": "Copy",
        "zh-tw": "複製",
        "zh-cn": "复制",
        "ja": "コピー",
        "es": "Copiar",
        "fr": "Copier",
        "de": "Kopieren",
        "ko": "복사",
        "pt": "Copiar",
        "ru": "Копировать",
        "it": "Copia",
        "vi": "Sao chép",
        "hi": "कॉपी करें",
        "id": "Salin",
    },
    "action.close": {
        "en": "Close",
        "zh-tw": "關閉",
        "zh-cn": "关闭",
        "ja": "閉じる",
        "es": "Cerrar",
        "fr": "Fermer",
        "de": "Schließen",
        "ko": "닫기",
        "pt": "Fechar",
        "ru": "Закрыть",
        "it": "Chiudi",
        "vi": "Đóng",
        "hi": "बंद करें",
        "id": "Tutup",
    },
    "deck.check_template_button": {
        "en": "Check template",
        "zh-tw": "檢查範本",
        "zh-cn": "检查模板",
        "ja": "テンプレートを確認",
        "es": "Comprobar la plantilla",
        "fr": "Vérifier le modèle",
        "de": "Vorlage prüfen",
        "ko": "템플릿 검사",
        "pt": "Verificar o modelo",
        "ru": "Проверить шаблон",
        "it": "Verifica il modello",
        "vi": "Kiểm tra mẫu",
        "hi": "टेम्पलेट जाँचें",
        "id": "Periksa templat",
    },
    "deck.error_no_template": {
        "en": "Choose a template (.pptx) first.",
        "zh-tw": "請先選擇範本(.pptx)。",
        "zh-cn": "请先选择模板(.pptx)。",
        "ja": "先にテンプレート(.pptx)を選んでください。",
        "es": "Elija primero una plantilla (.pptx).",
        "fr": "Choisissez d'abord un modèle (.pptx).",
        "de": "Wählen Sie zuerst eine Vorlage (.pptx).",
        "ko": "먼저 템플릿(.pptx)을 선택하세요.",
        "pt": "Escolha primeiro um modelo (.pptx).",
        "ru": "Сначала выберите шаблон (.pptx).",
        "it": "Scegli prima un modello (.pptx).",
        "vi": "Hãy chọn mẫu (.pptx) trước.",
        "hi": "पहले एक टेम्पलेट (.pptx) चुनें।",
        "id": "Pilih templat (.pptx) terlebih dahulu.",
    },
    "deck.template_ok": {
        "en": "Template check: usable.",
        "zh-tw": "範本檢查：可以使用。",
        "zh-cn": "模板检查：可以使用。",
        "ja": "テンプレートの確認: 使用できます。",
        "es": "Comprobación de la plantilla: utilizable.",
        "fr": "Vérification du modèle : utilisable.",
        "de": "Vorlagenprüfung: verwendbar.",
        "ko": "템플릿 검사: 사용 가능.",
        "pt": "Verificação do modelo: utilizável.",
        "ru": "Проверка шаблона: можно использовать.",
        "it": "Verifica del modello: utilizzabile.",
        "vi": "Kiểm tra mẫu: dùng được.",
        "hi": "टेम्पलेट जाँच: उपयोग योग्य।",
        "id": "Pemeriksaan templat: dapat dipakai.",
    },
    "deck.template_not_usable": {
        "en": "Template check: not usable, {errors} problem(s). See the report.",
        "zh-tw": "範本檢查：無法使用，共 {errors} 個問題，詳見報告。",
        "zh-cn": "模板检查：无法使用，共 {errors} 个问题，详见报告。",
        "ja": "テンプレートの確認: 使用できません。問題 {errors} 件、詳しくはレポートを参照。",
        "es": "Comprobación de la plantilla: no utilizable, {errors} problema(s). Vea el informe.",
        "fr": "Vérification du modèle : inutilisable, {errors} problème(s). Voir le rapport.",
        "de": "Vorlagenprüfung: nicht verwendbar, {errors} Problem(e). Siehe Bericht.",
        "ko": "템플릿 검사: 사용 불가, 문제 {errors}건. 보고서를 확인하세요.",
        "pt": "Verificação do modelo: não utilizável, {errors} problema(s). Veja o relatório.",
        "ru": "Проверка шаблона: нельзя использовать, проблем: {errors}. См. отчёт.",
        "it": "Verifica del modello: non utilizzabile, {errors} problema/i. Vedi il rapporto.",
        "vi": "Kiểm tra mẫu: không dùng được, {errors} vấn đề. Xem báo cáo.",
        "hi": "टेम्पलेट जाँच: उपयोग योग्य नहीं, {errors} समस्या। रिपोर्ट देखें।",
        "id": "Pemeriksaan templat: tidak dapat dipakai, {errors} masalah. Lihat laporan.",
    },
    "deck.review_button": {
        "en": "Review a deck…",
        "zh-tw": "審查投影片…",
        "zh-cn": "审查幻灯片…",
        "ja": "スライドをレビュー…",
        "es": "Revisar una presentación…",
        "fr": "Contrôler un diaporama…",
        "de": "Foliensatz prüfen …",
        "ko": "슬라이드 검토…",
        "pt": "Revisar uma apresentação…",
        "ru": "Проверить презентацию…",
        "it": "Controlla una presentazione…",
        "vi": "Rà soát slide…",
        "hi": "स्लाइड की समीक्षा करें…",
        "id": "Tinjau slide…",
    },
    "deck.review_dialog_title": {
        "en": "Choose a deck to review",
        "zh-tw": "選擇要審查的投影片",
        "zh-cn": "选择要审查的幻灯片",
        "ja": "レビューするスライドを選択",
        "es": "Elija la presentación que revisar",
        "fr": "Choisissez le diaporama à contrôler",
        "de": "Zu prüfenden Foliensatz wählen",
        "ko": "검토할 슬라이드 선택",
        "pt": "Escolha a apresentação a revisar",
        "ru": "Выберите презентацию для проверки",
        "it": "Scegli la presentazione da controllare",
        "vi": "Chọn slide cần rà soát",
        "hi": "समीक्षा के लिए स्लाइड चुनें",
        "id": "Pilih slide yang ditinjau",
    },
    "deck.review_pass": {
        "en": "Deck review: PASS.",
        "zh-tw": "投影片審查：通過。",
        "zh-cn": "幻灯片审查：通过。",
        "ja": "スライドのレビュー: 合格。",
        "es": "Revisión de la presentación: APROBADA.",
        "fr": "Contrôle du diaporama : RÉUSSI.",
        "de": "Foliensatzprüfung: BESTANDEN.",
        "ko": "슬라이드 검토: 통과.",
        "pt": "Revisão da apresentação: APROVADA.",
        "ru": "Проверка презентации: ПРОЙДЕНА.",
        "it": "Controllo della presentazione: SUPERATO.",
        "vi": "Rà soát slide: ĐẠT.",
        "hi": "स्लाइड समीक्षा: पास।",
        "id": "Tinjauan slide: LULUS.",
    },
    "deck.review_fail": {
        "en": "Deck review: FAIL, {problems} problem(s). See the report.",
        "zh-tw": "投影片審查：未通過，共 {problems} 個問題，詳見報告。",
        "zh-cn": "幻灯片审查：未通过，共 {problems} 个问题，详见报告。",
        "ja": "スライドのレビュー: 不合格。問題 {problems} 件、詳しくはレポートを参照。",
        "es": "Revisión de la presentación: FALLA, {problems} problema(s). Vea el informe.",
        "fr": "Contrôle du diaporama : ÉCHEC, {problems} problème(s). Voir le rapport.",
        "de": "Foliensatzprüfung: NICHT BESTANDEN, {problems} Problem(e). Siehe Bericht.",
        "ko": "슬라이드 검토: 실패, 문제 {problems}건. 보고서를 확인하세요.",
        "pt": "Revisão da apresentação: FALHOU, {problems} problema(s). Veja o relatório.",
        "ru": "Проверка презентации: НЕ ПРОЙДЕНА, проблем: {problems}. См. отчёт.",
        "it": (
            "Controllo della presentazione: NON SUPERATO, {problems} problema/i. Vedi il rapporto."
        ),
        "vi": "Rà soát slide: KHÔNG ĐẠT, {problems} vấn đề. Xem báo cáo.",
        "hi": "स्लाइड समीक्षा: फ़ेल, {problems} समस्या। रिपोर्ट देखें।",
        "id": "Tinjauan slide: GAGAL, {problems} masalah. Lihat laporan.",
    },
    "deck.report_template_title": {
        "en": "Template check",
        "zh-tw": "範本檢查",
        "zh-cn": "模板检查",
        "ja": "テンプレートの確認",
        "es": "Comprobación de la plantilla",
        "fr": "Vérification du modèle",
        "de": "Vorlagenprüfung",
        "ko": "템플릿 검사",
        "pt": "Verificação do modelo",
        "ru": "Проверка шаблона",
        "it": "Verifica del modello",
        "vi": "Kiểm tra mẫu",
        "hi": "टेम्पलेट जाँच",
        "id": "Pemeriksaan templat",
    },
    "deck.report_review_title": {
        "en": "Deck review",
        "zh-tw": "投影片審查",
        "zh-cn": "幻灯片审查",
        "ja": "スライドのレビュー",
        "es": "Revisión de la presentación",
        "fr": "Contrôle du diaporama",
        "de": "Foliensatzprüfung",
        "ko": "슬라이드 검토",
        "pt": "Revisão da apresentação",
        "ru": "Проверка презентации",
        "it": "Controllo della presentazione",
        "vi": "Rà soát slide",
        "hi": "स्लाइड समीक्षा",
        "id": "Tinjauan slide",
    },
    "enrich.card_agent": {
        "en": "No API key? Hand off to an agent",
        "zh-tw": "沒有 API 金鑰？交給 AI 代理",
        "zh-cn": "没有 API 密钥？交给 AI 代理",
        "ja": "API キーがない場合: エージェントに任せる",
        "es": "¿Sin clave de API? Páselo a un agente",
        "fr": "Pas de clé API ? Confiez-le à un agent",
        "de": "Kein API-Schlüssel? An einen Agenten übergeben",
        "ko": "API 키가 없나요? 에이전트에게 맡기기",
        "pt": "Sem chave de API? Passe para um agente",
        "ru": "Нет ключа API? Передайте агенту",
        "it": "Nessuna chiave API? Affidalo a un agente",
        "vi": "Không có khóa API? Giao cho tác tử",
        "hi": "API कुंजी नहीं है? किसी एजेंट को सौंपें",
        "id": "Tanpa kunci API? Serahkan ke agen",
    },
    "enrich.agent_hint": {
        "en": (
            "Export the papers to a JSON file, let an MCP-aware LLM agent fill in each summary, "
            "then import the file to send the summaries to the Deck page."
        ),
        "zh-tw": (
            "把論文匯出成 JSON 檔，讓支援 MCP 的 LLM 代理填入每篇摘要，再匯入該檔案，"
            "把摘要送往投影片頁面。"
        ),
        "zh-cn": (
            "把论文导出成 JSON 文件，让支持 MCP 的 LLM 代理填写每篇摘要，再导入该文件，"
            "把摘要发送到幻灯片页面。"
        ),
        "ja": (
            "論文を JSON ファイルに書き出し、MCP 対応の LLM エージェントに各要約を書いてもらい、"
            "そのファイルを読み込むと要約がスライドページへ送られます。"
        ),
        "es": (
            "Exporte los artículos a un archivo JSON, deje que un agente LLM compatible con MCP "
            "rellene cada resumen y luego importe el archivo para enviar los resúmenes a la página "
            "Diapositivas."
        ),
        "fr": (
            "Exportez les articles dans un fichier JSON, laissez un agent LLM compatible MCP "
            "remplir chaque résumé, puis importez le fichier pour envoyer les résumés à la page "
            "Diapos."
        ),
        "de": (
            "Artikel als JSON-Datei exportieren, einen MCP-fähigen LLM-Agenten jede "
            "Zusammenfassung ausfüllen lassen und die Datei importieren, um die Zusammenfassungen "
            "an die Seite Folien zu senden."
        ),
        "ko": (
            "논문을 JSON 파일로 내보내고 MCP를 지원하는 LLM 에이전트가 각 요약을 채우게 한 뒤, "
            "파일을 가져오면 요약이 슬라이드 페이지로 전달됩니다."
        ),
        "pt": (
            "Exporte os artigos para um arquivo JSON, deixe um agente LLM compatível com MCP "
            "preencher cada resumo e depois importe o arquivo para enviar os resumos à página "
            "Slides."
        ),
        "ru": (
            "Экспортируйте статьи в JSON-файл, дайте LLM-агенту с поддержкой MCP заполнить резюме, "
            "затем импортируйте файл, чтобы передать резюме на страницу Слайды."
        ),
        "it": (
            "Esporta gli articoli in un file JSON, lascia che un agente LLM compatibile con MCP "
            "compili ogni riassunto, poi importa il file per inviare i riassunti alla pagina "
            "Diapositive."
        ),
        "vi": (
            "Xuất các bài báo ra tệp JSON, để một tác tử LLM hỗ trợ MCP điền từng bản tóm tắt, rồi "
            "nhập tệp để gửi các bản tóm tắt sang trang Slide."
        ),
        "hi": (
            "शोध-पत्रों को JSON फ़ाइल में निर्यात करें, किसी MCP-सक्षम LLM एजेंट से हर सारांश "
            "भरवाएँ, फिर फ़ाइल आयात करें ताकि सारांश स्लाइड पेज पर जाएँ।"
        ),
        "id": (
            "Ekspor makalah ke berkas JSON, biarkan agen LLM yang mendukung MCP mengisi setiap "
            "ringkasan, lalu impor berkasnya untuk mengirim ringkasan ke halaman Slide."
        ),
    },
    "enrich.agent_export_button": {
        "en": "Export for an agent…",
        "zh-tw": "匯出給代理…",
        "zh-cn": "导出给代理…",
        "ja": "エージェント用に書き出す…",
        "es": "Exportar para un agente…",
        "fr": "Exporter pour un agent…",
        "de": "Für einen Agenten exportieren …",
        "ko": "에이전트용으로 내보내기…",
        "pt": "Exportar para um agente…",
        "ru": "Экспорт для агента…",
        "it": "Esporta per un agente…",
        "vi": "Xuất cho tác tử…",
        "hi": "एजेंट के लिए निर्यात करें…",
        "id": "Ekspor untuk agen…",
    },
    "enrich.agent_import_button": {
        "en": "Import summaries…",
        "zh-tw": "匯入摘要…",
        "zh-cn": "导入摘要…",
        "ja": "要約を読み込む…",
        "es": "Importar resúmenes…",
        "fr": "Importer les résumés…",
        "de": "Zusammenfassungen importieren …",
        "ko": "요약 가져오기…",
        "pt": "Importar resumos…",
        "ru": "Импорт резюме…",
        "it": "Importa i riassunti…",
        "vi": "Nhập bản tóm tắt…",
        "hi": "सारांश आयात करें…",
        "id": "Impor ringkasan…",
    },
    "enrich.agent_exported": {
        "en": "Wrote {count} papers for an agent to {path}.",
        "zh-tw": "已將 {count} 篇論文寫入 {path}，可交給代理處理。",
        "zh-cn": "已将 {count} 篇论文写入 {path}，可交给代理处理。",
        "ja": "{count} 件の論文をエージェント用に {path} へ書き出しました。",
        "es": "Se escribieron {count} artículos para un agente en {path}.",
        "fr": "{count} articles écrits pour un agent dans {path}.",
        "de": "{count} Artikel für einen Agenten nach {path} geschrieben.",
        "ko": "에이전트용 논문 {count}편을 {path}에 저장했습니다.",
        "pt": "{count} artigos gravados para um agente em {path}.",
        "ru": "Статей для агента записано в {path}: {count}.",
        "it": "{count} articoli scritti per un agente in {path}.",
        "vi": "Đã ghi {count} bài báo cho tác tử vào {path}.",
        "hi": "एजेंट के लिए {count} शोध-पत्र {path} में लिखे गए।",
        "id": "{count} makalah untuk agen ditulis ke {path}.",
    },
    "enrich.agent_imported": {
        "en": (
            "Imported {count} summaries ({unmatched} entries matched no paper here). Sent to the "
            "Deck page."
        ),
        "zh-tw": "已匯入 {count} 篇摘要(另有 {unmatched} 筆對不上目前的論文)，已送往投影片頁面。",
        "zh-cn": "已导入 {count} 篇摘要(另有 {unmatched} 条对不上当前的论文)，已发送到幻灯片页面。",
        "ja": (
            "要約 {count} 件を読み込みました(現在の論文と一致しない項目 {unmatched} 件)。"
            "スライドページへ送りました。"
        ),
        "es": (
            "Se importaron {count} resúmenes ({unmatched} entradas no coinciden con ningún "
            "artículo). Enviados a la página Diapositivas."
        ),
        "fr": (
            "{count} résumés importés ({unmatched} entrées sans article correspondant). Envoyés à "
            "la page Diapos."
        ),
        "de": (
            "{count} Zusammenfassungen importiert ({unmatched} Einträge ohne passenden Artikel). "
            "An die Seite Folien gesendet."
        ),
        "ko": (
            "요약 {count}편을 가져왔습니다 (일치하는 논문이 없는 항목 {unmatched}개). 슬라이드 "
            "페이지로 보냈습니다."
        ),
        "pt": (
            "{count} resumos importados ({unmatched} entradas sem artigo correspondente). Enviados "
            "à página Slides."
        ),
        "ru": (
            "Импортировано резюме: {count} (записей без подходящей статьи: {unmatched}). Переданы "
            "на страницу Слайды."
        ),
        "it": (
            "Importati {count} riassunti ({unmatched} voci senza articolo corrispondente). Inviati "
            "alla pagina Diapositive."
        ),
        "vi": (
            "Đã nhập {count} bản tóm tắt ({unmatched} mục không khớp bài báo nào). Đã gửi sang "
            "trang Slide."
        ),
        "hi": (
            "{count} सारांश आयात किए गए ({unmatched} प्रविष्टियाँ किसी शोध-पत्र से मेल नहीं "
            "खातीं)। स्लाइड पेज पर भेजे गए।"
        ),
        "id": (
            "{count} ringkasan diimpor ({unmatched} entri tidak cocok dengan makalah mana pun). "
            "Dikirim ke halaman Slide."
        ),
    },
    "enrich.agent_error": {
        "en": "Hand-off failed: {error}",
        "zh-tw": "交接失敗：{error}",
        "zh-cn": "交接失败：{error}",
        "ja": "引き渡しに失敗しました: {error}",
        "es": "Error en la entrega: {error}",
        "fr": "Échec du transfert : {error}",
        "de": "Übergabe fehlgeschlagen: {error}",
        "ko": "넘겨주기 실패: {error}",
        "pt": "Falha na entrega: {error}",
        "ru": "Ошибка передачи: {error}",
        "it": "Passaggio non riuscito: {error}",
        "vi": "Bàn giao thất bại: {error}",
        "hi": "हस्तांतरण विफल: {error}",
        "id": "Serah terima gagal: {error}",
    },
    "deck.check_failed": {
        "en": "Check failed: {error}",
        "zh-tw": "檢查失敗：{error}",
        "zh-cn": "检查失败：{error}",
        "ja": "確認に失敗しました: {error}",
        "es": "La comprobación falló: {error}",
        "fr": "Échec de la vérification : {error}",
        "de": "Prüfung fehlgeschlagen: {error}",
        "ko": "검사 실패: {error}",
        "pt": "A verificação falhou: {error}",
        "ru": "Проверка не удалась: {error}",
        "it": "Verifica non riuscita: {error}",
        "vi": "Kiểm tra thất bại: {error}",
        "hi": "जाँच विफल: {error}",
        "id": "Pemeriksaan gagal: {error}",
    },
    # Stage D: PDF stage with the access switch, language switch ----------
    "settings.vpn_access": {
        "en": "I have institutional / VPN access (download IEEE PDFs)",
        "zh-tw": "我有學校或機構的 VPN 存取權(可下載 IEEE PDF)",
        "zh-cn": "我有学校或机构的 VPN 访问权限(可下载 IEEE PDF)",
        "ja": "大学・機関の VPN アクセスがある(IEEE の PDF をダウンロード)",
        "es": "Tengo acceso institucional / VPN (descargar los PDF de IEEE)",
        "fr": "J'ai un accès institutionnel / VPN (télécharger les PDF IEEE)",
        "de": "Ich habe institutionellen / VPN-Zugang (IEEE-PDFs herunterladen)",
        "ko": "기관 / VPN 접근 권한이 있음 (IEEE PDF 다운로드)",
        "pt": "Tenho acesso institucional / VPN (baixar os PDFs do IEEE)",
        "ru": "Есть институциональный / VPN-доступ (скачивать PDF из IEEE)",
        "it": "Ho accesso istituzionale / VPN (scarica i PDF IEEE)",
        "vi": "Tôi có quyền truy cập qua tổ chức / VPN (tải PDF của IEEE)",
        "hi": "मेरे पास संस्थागत / VPN पहुँच है (IEEE PDF डाउनलोड करें)",
        "id": "Saya punya akses institusi / VPN (unduh PDF IEEE)",
    },
    "deck.download_pdfs_label": {
        "en": "Download the PDFs into a pdfs folder",
        "zh-tw": "下載 PDF 到 pdfs 資料夾",
        "zh-cn": "下载 PDF 到 pdfs 文件夹",
        "ja": "PDF を pdfs フォルダーにダウンロード",
        "es": "Descargar los PDF en una carpeta pdfs",
        "fr": "Télécharger les PDF dans un dossier pdfs",
        "de": "PDFs in einen Ordner pdfs herunterladen",
        "ko": "PDF를 pdfs 폴더에 다운로드",
        "pt": "Baixar os PDFs para uma pasta pdfs",
        "ru": "Скачать PDF в папку pdfs",
        "it": "Scarica i PDF in una cartella pdfs",
        "vi": "Tải PDF vào thư mục pdfs",
        "hi": "PDF को pdfs फ़ोल्डर में डाउनलोड करें",
        "id": "Unduh PDF ke folder pdfs",
    },
    "deck.pdfs_summary": {
        "en": "PDFs: {saved} saved, {skipped} not downloaded.",
        "zh-tw": "PDF：已儲存 {saved} 篇，{skipped} 篇未下載。",
        "zh-cn": "PDF：已保存 {saved} 篇，{skipped} 篇未下载。",
        "ja": "PDF: {saved} 件保存、{skipped} 件はダウンロードできず。",
        "es": "PDF: {saved} guardados, {skipped} sin descargar.",
        "fr": "PDF : {saved} enregistrés, {skipped} non téléchargés.",
        "de": "PDFs: {saved} gespeichert, {skipped} nicht heruntergeladen.",
        "ko": "PDF: {saved}편 저장, {skipped}편 다운로드 안 됨.",
        "pt": "PDFs: {saved} salvos, {skipped} não baixados.",
        "ru": "PDF: сохранено {saved}, не скачано {skipped}.",
        "it": "PDF: {saved} salvati, {skipped} non scaricati.",
        "vi": "PDF: đã lưu {saved}, {skipped} chưa tải được.",
        "hi": "PDF: {saved} सहेजे गए, {skipped} डाउनलोड नहीं हुए।",
        "id": "PDF: {saved} tersimpan, {skipped} tidak terunduh.",
    },
    "deck.pdfs_ieee_held": {
        "en": "{count} IEEE PDFs left out: institutional / VPN access is off in Settings.",
        "zh-tw": "有 {count} 篇 IEEE PDF 未下載：「設定」中未勾選機構 / VPN 存取權。",
        "zh-cn": "有 {count} 篇 IEEE PDF 未下载：“设置”中未勾选机构 / VPN 访问权限。",
        "ja": "IEEE の PDF {count} 件を除外しました: 設定で機関 / VPN アクセスがオフです。",
        "es": (
            "{count} PDF de IEEE omitidos: el acceso institucional / VPN está desactivado en "
            "Ajustes."
        ),
        "fr": (
            "{count} PDF IEEE écartés : l'accès institutionnel / VPN est désactivé dans les "
            "Paramètres."
        ),
        "de": (
            "{count} IEEE-PDFs ausgelassen: institutioneller / VPN-Zugang ist in den Einstellungen "
            "aus."
        ),
        "ko": "IEEE PDF {count}편 제외: 설정에서 기관 / VPN 접근이 꺼져 있습니다.",
        "pt": (
            "{count} PDFs do IEEE deixados de fora: o acesso institucional / VPN está desligado em "
            "Configurações."
        ),
        "ru": (
            "Пропущено PDF из IEEE: {count}. Институциональный / VPN-доступ выключен в настройках."
        ),
        "it": (
            "{count} PDF IEEE esclusi: l'accesso istituzionale / VPN è disattivato nelle "
            "Impostazioni."
        ),
        "vi": "Bỏ qua {count} PDF của IEEE: quyền truy cập tổ chức / VPN đang tắt trong Cài đặt.",
        "hi": "{count} IEEE PDF छोड़े गए: सेटिंग्स में संस्थागत / VPN पहुँच बंद है।",
        "id": "{count} PDF IEEE dilewati: akses institusi / VPN dimatikan di Pengaturan.",
    },
    "status.language_later": {
        "en": "Work is still running, so the new interface language applies at the next start.",
        "zh-tw": "仍有工作在執行，新的介面語言將在下次啟動時套用。",
        "zh-cn": "仍有工作在执行，新的界面语言将在下次启动时应用。",
        "ja": "処理が実行中のため、新しい表示言語は次回起動時に反映されます。",
        "es": (
            "Todavía hay trabajo en curso, así que el nuevo idioma se aplicará en el próximo "
            "inicio."
        ),
        "fr": "Un traitement est en cours : la nouvelle langue s'appliquera au prochain lancement.",
        "de": "Es läuft noch eine Aufgabe, daher gilt die neue Sprache ab dem nächsten Start.",
        "ko": "작업이 아직 실행 중이라 새 인터페이스 언어는 다음 실행 때 적용됩니다.",
        "pt": (
            "Ainda há trabalho em andamento, então o novo idioma será aplicado na próxima execução."
        ),
        "ru": (
            "Работа ещё выполняется, поэтому новый язык интерфейса применится при следующем "
            "запуске."
        ),
        "it": (
            "C'è ancora un'elaborazione in corso, quindi la nuova lingua si applica al prossimo "
            "avvio."
        ),
        "vi": "Vẫn còn tác vụ đang chạy, nên ngôn ngữ mới sẽ áp dụng ở lần khởi động sau.",
        "hi": "काम अभी चल रहा है, इसलिए नई इंटरफ़ेस भाषा अगली बार शुरू करने पर लागू होगी।",
        "id": (
            "Masih ada pekerjaan berjalan, jadi bahasa antarmuka baru berlaku pada peluncuran "
            "berikutnya."
        ),
    },
    "search.ieee_locked_note": {
        "en": (
            "IEEE is off: it needs institutional / VPN access, which you can declare in Settings."
        ),
        "zh-tw": "IEEE 已停用：需要機構 / VPN 存取權，可在「設定」中勾選。",
        "zh-cn": "IEEE 已停用：需要机构 / VPN 访问权限，可在“设置”中勾选。",
        "ja": "IEEE はオフです: 機関 / VPN アクセスが必要です。設定で有効にできます。",
        "es": (
            "IEEE está desactivado: necesita acceso institucional / VPN, que puede declarar en "
            "Ajustes."
        ),
        "fr": (
            "IEEE est désactivé : il faut un accès institutionnel / VPN, à déclarer dans les "
            "Paramètres."
        ),
        "de": (
            "IEEE ist aus: Es braucht institutionellen / VPN-Zugang, den Sie in den Einstellungen "
            "angeben können."
        ),
        "ko": "IEEE 꺼짐: 기관 / VPN 접근 권한이 필요하며, 설정에서 지정할 수 있습니다.",
        "pt": (
            "O IEEE está desligado: ele exige acesso institucional / VPN, que você pode declarar "
            "em Configurações."
        ),
        "ru": (
            "IEEE отключён: нужен институциональный / VPN-доступ, его можно указать в настройках."
        ),
        "it": (
            "IEEE è disattivato: serve l'accesso istituzionale / VPN, che puoi dichiarare nelle "
            "Impostazioni."
        ),
        "vi": "IEEE đang tắt: cần quyền truy cập tổ chức / VPN, có thể khai báo trong Cài đặt.",
        "hi": (
            "IEEE बंद है: इसके लिए संस्थागत / VPN पहुँच चाहिए, जिसे सेटिंग्स में बताया जा सकता है।"
        ),
        "id": "IEEE nonaktif: perlu akses institusi / VPN, yang dapat dinyatakan di Pengaturan.",
    },
    "search.local_button": {
        "en": "Use local PDFs…",
        "zh-tw": "使用本機 PDF…",
        "zh-cn": "使用本地 PDF…",
        "ja": "ローカルの PDF を使う…",
        "es": "Usar PDF locales…",
        "fr": "Utiliser des PDF locaux…",
        "de": "Lokale PDFs verwenden …",
        "ko": "로컬 PDF 사용…",
        "pt": "Usar PDFs locais…",
        "ru": "Использовать локальные PDF…",
        "it": "Usa PDF locali…",
        "vi": "Dùng PDF trên máy…",
        "hi": "स्थानीय PDF इस्तेमाल करें…",
        "id": "Gunakan PDF lokal…",
    },
    "search.local_dialog_title": {
        "en": "Choose PDF files",
        "zh-tw": "選擇 PDF 檔案",
        "zh-cn": "选择 PDF 文件",
        "ja": "PDF ファイルを選択",
        "es": "Elija archivos PDF",
        "fr": "Choisissez des fichiers PDF",
        "de": "PDF-Dateien wählen",
        "ko": "PDF 파일 선택",
        "pt": "Escolha arquivos PDF",
        "ru": "Выберите PDF-файлы",
        "it": "Scegli i file PDF",
        "vi": "Chọn tệp PDF",
        "hi": "PDF फ़ाइलें चुनें",
        "id": "Pilih berkas PDF",
    },
    "search.local_running": {
        "en": "Reading the PDFs…",
        "zh-tw": "正在讀取 PDF…",
        "zh-cn": "正在读取 PDF…",
        "ja": "PDF を読み込んでいます…",
        "es": "Leyendo los PDF…",
        "fr": "Lecture des PDF…",
        "de": "PDFs werden gelesen …",
        "ko": "PDF를 읽는 중…",
        "pt": "Lendo os PDFs…",
        "ru": "Чтение PDF…",
        "it": "Lettura dei PDF…",
        "vi": "Đang đọc PDF…",
        "hi": "PDF पढ़े जा रहे हैं…",
        "id": "Membaca PDF…",
    },
    "search.local_done": {
        "en": "Read {count} local PDF(s). Copies are in {folder}.",
        "zh-tw": "已讀取 {count} 份本機 PDF，副本放在 {folder}。",
        "zh-cn": "已读取 {count} 份本地 PDF，副本放在 {folder}。",
        "ja": "ローカルの PDF を {count} 件読み込みました。コピーは {folder} にあります。",
        "es": "Se leyeron {count} PDF locales. Las copias están en {folder}.",
        "fr": "{count} PDF locaux lus. Les copies sont dans {folder}.",
        "de": "{count} lokale PDF(s) gelesen. Die Kopien liegen in {folder}.",
        "ko": "로컬 PDF {count}개를 읽었습니다. 사본은 {folder}에 있습니다.",
        "pt": "{count} PDFs locais lidos. As cópias estão em {folder}.",
        "ru": "Прочитано локальных PDF: {count}. Копии в {folder}.",
        "it": "Letti {count} PDF locali. Le copie sono in {folder}.",
        "vi": "Đã đọc {count} PDF trên máy. Bản sao nằm trong {folder}.",
        "hi": "{count} स्थानीय PDF पढ़े गए। प्रतियाँ {folder} में हैं।",
        "id": "{count} PDF lokal dibaca. Salinannya ada di {folder}.",
    },
    "deck.pdfs_via_browser": {
        "en": "{count} through Chrome.",
        "zh-tw": "其中 {count} 篇經由 Chrome 下載。",
        "zh-cn": "其中 {count} 篇通过 Chrome 下载。",
        "ja": "うち {count} 件は Chrome 経由。",
        "es": "{count} a través de Chrome.",
        "fr": "{count} via Chrome.",
        "de": "{count} über Chrome.",
        "ko": "그중 {count}편은 Chrome 경유.",
        "pt": "{count} pelo Chrome.",
        "ru": "Через Chrome: {count}.",
        "it": "{count} tramite Chrome.",
        "vi": "{count} qua Chrome.",
        "hi": "{count} Chrome के ज़रिए।",
        "id": "{count} melalui Chrome.",
    },
    "deck.pdfs_no_browser": {
        "en": (
            "Chrome automation was not available, so {count} publisher PDFs were tried without it, "
            "which publishers usually refuse. Install selenium, or unset "
            "THESISAGENTS_DISABLE_WEBRUNNER."
        ),
        "zh-tw": (
            "無法使用 Chrome 自動化，所以有 {count} 篇出版商 PDF 改以一般請求下載，"
            "出版商通常會拒絕。請安裝 selenium，或取消設定 THESISAGENTS_DISABLE_WEBRUNNER。"
        ),
        "zh-cn": (
            "无法使用 Chrome 自动化，所以有 {count} 篇出版商 PDF 改用普通请求下载，"
            "出版商通常会拒绝。请安装 selenium，或取消设置 THESISAGENTS_DISABLE_WEBRUNNER。"
        ),
        "ja": (
            "Chrome の自動操作が使えないため、出版社の PDF {count} "
            "件を通常のリクエストで試しました。出版社は通常これを拒否します。selenium を入れるか、"
            "THESISAGENTS_DISABLE_WEBRUNNER を解除してください。"
        ),
        "es": (
            "La automatización de Chrome no estaba disponible, así que {count} PDF de editoriales "
            "se intentaron sin ella, algo que las editoriales suelen rechazar. Instale selenium o "
            "quite THESISAGENTS_DISABLE_WEBRUNNER."
        ),
        "fr": (
            "L'automatisation de Chrome n'était pas disponible : {count} PDF d'éditeurs ont été "
            "tentés sans elle, ce que les éditeurs refusent en général. Installez selenium ou "
            "retirez THESISAGENTS_DISABLE_WEBRUNNER."
        ),
        "de": (
            "Die Chrome-Automatisierung war nicht verfügbar, daher wurden {count} Verlags-PDFs "
            "ohne sie versucht, was Verlage meist ablehnen. Installieren Sie selenium oder "
            "entfernen Sie THESISAGENTS_DISABLE_WEBRUNNER."
        ),
        "ko": (
            "Chrome 자동화를 사용할 수 없어 출판사 PDF {count}편을 일반 요청으로 시도했으며, "
            "출판사는 보통 이를 거부합니다. selenium 을 설치하거나 THESISAGENTS_DISABLE_WEBRUNNER "
            "설정을 해제하세요."
        ),
        "pt": (
            "A automação do Chrome não estava disponível, então {count} PDFs de editoras foram "
            "tentados sem ela, o que as editoras costumam recusar. Instale o selenium ou remova "
            "THESISAGENTS_DISABLE_WEBRUNNER."
        ),
        "ru": (
            "Автоматизация Chrome недоступна, поэтому PDF издательств ({count}) запрошены без неё, "
            "а издательства обычно такое отклоняют. Установите selenium или уберите "
            "THESISAGENTS_DISABLE_WEBRUNNER."
        ),
        "it": (
            "L'automazione di Chrome non era disponibile, quindi {count} PDF di editori sono stati "
            "tentati senza, cosa che gli editori di solito rifiutano. Installa selenium o rimuovi "
            "THESISAGENTS_DISABLE_WEBRUNNER."
        ),
        "vi": (
            "Không dùng được tự động hóa Chrome, nên {count} PDF của nhà xuất bản được thử bằng "
            "yêu cầu thường, điều mà nhà xuất bản thường từ chối. Hãy cài selenium hoặc bỏ đặt "
            "THESISAGENTS_DISABLE_WEBRUNNER."
        ),
        "hi": (
            "Chrome स्वचालन उपलब्ध नहीं था, इसलिए प्रकाशकों के {count} PDF उसके बिना आज़माए गए, "
            "जिन्हें प्रकाशक आमतौर पर अस्वीकार करते हैं। selenium इंस्टॉल करें या "
            "THESISAGENTS_DISABLE_WEBRUNNER हटाएँ।"
        ),
        "id": (
            "Otomasi Chrome tidak tersedia, jadi {count} PDF penerbit dicoba tanpanya, yang "
            "biasanya ditolak penerbit. Pasang selenium atau hapus THESISAGENTS_DISABLE_WEBRUNNER."
        ),
    },
    "deck.pdfs_browser_failed": {
        "en": "Chrome could not fetch {count} publisher PDFs, so they were retried without it.",
        "zh-tw": "Chrome 無法取得 {count} 篇出版商 PDF，已改以一般請求重試。",
        "zh-cn": "Chrome 无法获取 {count} 篇出版商 PDF，已改用普通请求重试。",
        "ja": (
            "Chrome で出版社の PDF {count} 件を取得できなかったため、"
            "通常のリクエストで再試行しました。"
        ),
        "es": "Chrome no pudo obtener {count} PDF de editoriales, así que se reintentaron sin él.",
        "fr": "Chrome n'a pas pu récupérer {count} PDF d'éditeurs, ils ont été retentés sans lui.",
        "de": (
            "Chrome konnte {count} Verlags-PDFs nicht abrufen, sie wurden ohne Chrome erneut "
            "versucht."
        ),
        "ko": "Chrome 이 출판사 PDF {count}편을 가져오지 못해 일반 요청으로 다시 시도했습니다.",
        "pt": (
            "O Chrome não conseguiu obter {count} PDFs de editoras, então foram tentados de novo "
            "sem ele."
        ),
        "ru": (
            "Chrome не смог получить PDF издательств ({count}), поэтому они запрошены повторно без "
            "него."
        ),
        "it": (
            "Chrome non è riuscito a scaricare {count} PDF di editori, quindi sono stati ritentati "
            "senza."
        ),
        "vi": (
            "Chrome không lấy được {count} PDF của nhà xuất bản, nên đã thử lại bằng yêu cầu "
            "thường."
        ),
        "hi": (
            "Chrome प्रकाशकों के {count} PDF नहीं ला सका, इसलिए उन्हें उसके बिना फिर आज़माया गया।"
        ),
        "id": "Chrome tidak dapat mengambil {count} PDF penerbit, jadi dicoba ulang tanpanya.",
    },
}


def normalise_language(code: str | None) -> str:
    """Map any string to a supported GUI language, defaulting to English."""
    if not code:
        return DEFAULT_LANGUAGE
    lowered = code.strip().lower().replace("_", "-")
    if lowered in SUPPORTED_LANGUAGES:
        return lowered
    # Strip locale subtags (zh-Hant-TW → zh-tw) by keeping the first
    # two segments only — covers PySide6 / QLocale strings.
    segments = lowered.split("-")
    if len(segments) >= 2:
        prefix = f"{segments[0]}-{segments[-1]}"
        if prefix in SUPPORTED_LANGUAGES:
            return prefix
    if segments and segments[0] in SUPPORTED_LANGUAGES:
        return segments[0]
    return DEFAULT_LANGUAGE


def t(key: str, language: str = DEFAULT_LANGUAGE, /, **fmt: object) -> str:
    """Translate a UI key, with optional format placeholders.

    Returns the English string when ``key`` is missing for ``language``
    (so adding a key without translating it yet is a soft failure). If
    the key is missing from English too the key itself is returned —
    a visible bug marker the test suite catches via the coverage tests.
    """
    lang = normalise_language(language)
    entry = _LABELS.get(key)
    if entry is None:
        return key
    template = entry.get(lang) or entry.get(DEFAULT_LANGUAGE) or key
    if fmt:
        try:
            return template.format(**fmt)
        except (KeyError, IndexError):
            return template
    return template
