# Desktop GUI (PySide6)

ThesisAgents ships an optional desktop interface built on
[PySide6](https://doc.qt.io/qtforpython-6/). It wraps the existing
CLI flow (search → results table → export) in a window so users who
don't want a terminal can still drive the project.

## Install

The GUI is gated behind a separate extra to avoid forcing PySide6
(~80 MB) on CLI / MCP users who don't need it:

```powershell
pip install thesisagents[gui]
```

If you also want the rich-tier enrichment path:

```powershell
pip install thesisagents[gui,intelligence,mcp]
```

## Launch

Three equivalent entry points:

```powershell
thesisagents-gui                    # PyPI window program, no console on Windows
thesisagents gui                    # CLI subcommand
py -m thesisagents gui              # module entry, useful while developing
```

In the Windows release zip, opening `thesisagents.exe` (or running
`thesisagents.exe gui`) starts the app without a console window. The
bundle includes PySide6 and the source plugins, so no extra install is
needed. `thesisagents-cli.exe gui` starts the same app from a terminal
and shows its log there, which is the way to see why a start failed.

## Window layout

The window has a sidebar on the left and one page at a time on the right.
The sidebar lists where papers come from, **Search** and **Library**, then
the two steps that work on them, **Enrich** and **Deck**, with **Settings**
pinned at the bottom. Each page opens with its title and a one-line
subtitle saying what it does.

- After a search (or **Send to Enrich and Deck** on the Library page),
  the Enrich and Deck entries show the number of papers waiting for them
  (`Enrich · 25`), so you can see that the next step has data without
  opening it.
- `Ctrl+1` … `Ctrl+5` switch to Search, Library, Enrich, Deck and
  Settings.
- `Ctrl++` (or `Ctrl+=`) makes the text larger, `Ctrl+-` smaller, and
  `Ctrl+0` puts it back to the default, see **Font size** under Settings.
- **Log** in the status bar (`Ctrl+L`) opens the activity log, live, with
  **Copy** and **Open log folder**. The same lines go to
  `%LOCALAPPDATA%\ThesisAgents\logs\thesisagents.log` on Windows
  (`~/.local/share` on Linux, `~/Library/Application Support` on macOS),
  three files of 1 MB. API keys are replaced with `***` in both.
- When a page in the visible Chrome window asks whether you are human, a
  banner above the page says which site, counts down how long the search
  waits, and flashes the taskbar entry. If time runs out, it says that this
  source returned nothing.
- An error nobody caught is shown in the status bar and logged. One during
  start-up is shown in a dialog that names the log file.
- While a search, an enrichment run or an export is working, the status
  bar at the bottom shows `Working…` and a moving progress bar. The page
  that started the work keeps its own detailed status line.
- The pages with results (Search, Enrich, Deck) split into a controls
  side and a results side. The controls scroll on their own, and the
  page's main buttons stay pinned below them, so **Search** or
  **Export** never scrolls out of reach. How the two sides are arranged
  depends on the window width, see "Responsive layout & HiDPI" below.

All four pages are functional in this release.

### Search

The core search → export flow.

- **Query** — keyword string (UTF-8; CJK works).
- **Sources** — one check box per source, pre-selected to the CLI's
  default set (`DEFAULT_SOURCES`, currently all fifteen). The boxes
  re-flow into as many columns as the controls side has room for.
  Sources that need a key or a browser (`ieee`, `springer`, `core`,
  `scholar`) only return results once the matching value is set in
  **Settings**, otherwise the status line marks them disabled.
  `ieee` is also locked (unticked, greyed out, with a note below the
  boxes) until **Settings** declares institutional / VPN access: the
  project's IEEE rule asks for the access status before any search with
  `ieee` in it, and without access IEEE answers with abstract pages and
  403s after opening a browser window. A restored form cannot bring it
  back. Saving the switch on in **Settings** unlocks it at once and ticks
  it again.
- **Slide language** — picks the language for any `.pptx` exported
  from this run. Defaults to English.
- **Max results per source** — 1 … 200 (same as the CLI `--max`).
- **Year from / Year to** — leave at `—` to disable.
- **Top-tier venues only** — mirrors the CLI's default; un-tick to
  keep every result.

The controls are grouped in three cards: **What to search** (query and
sources), **Filters** (slide language, max results, years, top-tier
venues) and **Snowball and library**.

Press **Search**, or Enter in the query field. The query runs on a worker
thread so the UI stays responsive. The status bar shows the progress
indicator and the results table populates when the run finishes.
While it runs, **Cancel** stops it at its next network wait. A
cancelled search changes nothing: the table keeps the previous results
and the status line says so.

**Use local PDFs…** (in the *What to search* card) reads PDF files from
your disk instead of searching, the GUI form of the CLI's `--pdf` mode
(`thesisagents/core/local_pdf.py`, needs the `[intelligence]` extra for
`pypdf`). Each file's own front matter gives its title, authors, year,
DOI and abstract, and a copy goes to the `pdfs` folder of the Deck
page's output folder, next to the deck you will build from it. The
papers then fill the table like search results (`Read 3 local PDF(s).
Copies are in …`), so they can be ticked, enriched and exported. An
empty, encrypted, oversized or non-PDF file stops the read with its name
on the status line.

**Working with the results:**

- **Sort** by clicking a column header. Until you do, the table keeps
  the ranked order of the search. Years and citation counts sort as
  numbers, and a missing value sorts after every real one when
  descending.
- **Filter** with the box above the table (it matches every word you
  type against the title, authors, venue and DOI) and the source
  picker beside it. Filtering only hides rows. A hidden paper keeps its
  tick and is still sent on.
- **Tick** the papers to send on. Every paper of a new result starts
  ticked. **Enrich**, **Deck** and **Export…** receive only the ticked
  papers, and the line above the table counts them
  (`12 of 25 ticked`). **Tick shown** and **Untick shown** act on the
  rows the filter currently shows, so "filter, then untick shown" drops
  a whole group at once.
- **Right-click** a row for *Open paper page*, *Open PDF* (greyed out
  when the paper has no PDF link), *Copy DOI* and *Copy BibTeX* (one
  entry under the paper's own BibTeX key). Double-clicking a row also
  opens the paper's page. Only `http` / `https` links are opened, a
  link of any other kind from a source record is ignored.

When the run finishes the status line reports the number of papers and
what each source returned, for example
`Found 25 paper(s). Sources: arxiv 23, openalex 25, dblp 0, ieee (failed), springer (disabled)`.
A source marked failed, rate limited or disabled contributed nothing
for a reason other than the topic, so check it before concluding the
topic has few papers.

The last column, **Suggestion**, shows the advisory recommendation the
search recorded for each paper: keep, review or prune. Hover any cell
of a row to see why: the score split into relevance, recency and
citations, a sentence per contribution, and the rule that triggered the
recommendation. The column is advice. Every result stays in the table
and in the export, and a low citation count alone never produces a
recommendation. The rules are listed in [`cli.md`](cli.md) "Ranking
diagnostics".

**Citation snowball** expands the top results along their citation
links before they are shown: *References* adds the papers they cite,
*Cited by* the papers that cite them, *Both* does both. It is off by
default. The papers it finds are appended to the table and the status
line adds `Snowball: 3 new.` Same as the CLI `--snowball` flag, see
[`cli.md`](cli.md) "Citation snowballing".

Tick **Advanced snowball settings** to change its bounds. The fields
start at the CLI's defaults, so leaving the section closed gives the
same expansion as the CLI:

| Field | CLI flag | Default | Range |
|---|---|---|---|
| Top results to expand | `--snowball-seeds` | 5 | 1 – 200 |
| Steps from each result | `--snowball-depth` | 1 | 1 – 3 |
| Papers per result and direction | `--snowball-max-per-seed` | 20 | 1 – 100 |
| New papers in all (at most) | `--snowball-max-total` | 20 | 1 – 1000 |
| Minimum relevance | `--snowball-min-relevance` | — (off) | 0 – 1 |

The minimum relevance drops found papers whose relevance to the query
is below that fraction of the best the keywords allow. A dash (0) keeps
every paper found.

**Library** names a literature library, an SQLite file that keeps
papers between sessions (see [`cli.md`](cli.md) "Literature
library"). Type a path or press **Browse…**. A file that does not
exist yet is created the first time papers are added to it.

- **Add results to the library**, when ticked, merges each search
  into the file, snowball finds and their citation links included.
  The status line adds `Library: 4 added, 21 already there.` A paper
  the library already holds is merged, not duplicated. Ticked with
  no library file, the search does not start and the status line
  asks for the file.
- **Search library** fills the table from the library instead of
  the network. The query field is the library query (empty lists
  the most recently seen papers), and max results and the year
  range apply. The status line reads `12 of 132 library papers.`
  The papers then behave like search results: they can be
  exported, enriched and built into a deck.
- With a library file set, **Export…** here and the Deck page's
  export keep their DOI / URL checks in it, so an identifier that
  verified is not checked again for 30 days.

Press **Export…**, pick an output directory, and the standard
`.pptx` + `.xlsx` + `.bib` triple of the ticked papers lands there.

### Library

The papers of a literature library file, with what you record about them.
It is the SQLite file the Search page's **Library** field and the CLI `--library` flag fill. The
path follows the Search page's library field, and **Browse…** picks
another file. Press **Open library** (or Enter in either field) to read
it. Opening never creates a file: a path with no library behind it
reports `Could not open the library: …` instead of
making an empty one.

- The **find** box narrows the list the way **Search library** does
  (the search ranker, stemming and phrases included). Empty lists every
  paper, most recently seen first.
- **Overview** counts the papers, the searches that filled the library,
  the citation links between its papers, the year span, the papers each
  source returned and the stored identifier checks per status (`ok 20,
  invalid 1`).
- The **Papers** tab lists the papers with their sources, how often they
  were seen and when last. Select one to see, below the list, the
  library papers it cites and that cite it, and its stored DOI / URL
  checks with their date. Every value there is shown as plain text, a
  title with markup in it is not rendered.
- **Filter** narrows the list by tag, reading status and screening
  decision. What is listed is also what **Send to Enrich and Deck** sends.
- **My notes**, below the list, records tags (separated by commas), a
  reading status, a note, and a screening decision with its reason at one
  of two stages: title and abstract, or full text. With several papers
  selected, tags are added to all of them and notes are left alone.
  Searching again never changes any of it.
- **Delete** and **Merge** act on the selected papers after asking. A merge
  keeps the first paper's fields and fills its gaps from the others.
- **Import…** reads a BibTeX or RIS file (Zotero, Mendeley, EndNote,
  JabRef) and creates the library when there is none yet. **Find
  duplicates** lists papers an import could not decide on, such as a
  preprint and its journal version.
- The **Saved searches** tab saves the search described on the Search page
  under a name. **Run** repeats it, adds what it finds and selects the
  papers the library did not hold before.
- The **Citations** tab draws the citation links: papers in columns by
  year, an arrow from each to what it cites, circles sized by citation
  count. Click one to select it in the list. Dragging pans, `Ctrl` with
  the wheel zooms.
- The **Review** tab shows the PRISMA 2020 flow of the recorded decisions
  and saves it as an SVG drawing in the interface language.
- The **Searches** tab lists every import, newest first: date, kind,
  keywords and how many papers it brought.
- **Send to Enrich and Deck** hands the listed papers (with the citation
  links between them) on, as a search result would be.

Every change is made on a worker thread and in one transaction, so one
that fails leaves the library as it was. The same actions are available as
`thesisagents library` on the command line (`docs/cli.md`) and as MCP
tools (`docs/mcp.md`).

### Settings

API keys are kept in the system credential store (Windows Credential
Manager, macOS Keychain, Secret Service), see
[`configuration.md`](configuration.md) "API keys". Interface language,
theme, style, contact email, cookies file and Chrome profile directory are
stored locally via Qt's
[`QSettings`](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QSettings.html)
(Windows registry, macOS plist, Linux ini). Saving a value also
exports the matching environment variable into the current process,
so the source plugins pick it up without a shell restart.

Fields:

| UI label | Env var written |
|---|---|
| Anthropic API key | `ANTHROPIC_API_KEY` |
| Semantic Scholar API key | `THESISAGENTS_S2_API_KEY` |
| NCBI / PubMed API key | `THESISAGENTS_NCBI_API_KEY` |
| IEEE Xplore API key | `THESISAGENTS_IEEE_API_KEY` |
| Springer Nature API key | `THESISAGENTS_SPRINGER_API_KEY` |
| Crossref Plus token | `THESISAGENTS_CROSSREF_PLUS_TOKEN` |
| CORE.ac.uk API key | `THESISAGENTS_CORE_API_KEY` |
| Contact email | `THESISAGENTS_CONTACT_EMAIL` |
| PDF cookies file | `THESISAGENTS_PDF_COOKIES_FILE` |
| Chrome profile directory | `THESISAGENTS_CHROME_PROFILE_DIR` |

Empty values clear the corresponding env var. **Restart the app**
to refresh fetcher singletons that cached the env value at
construction time.

**I have institutional / VPN access (download IEEE PDFs)**, off by
default (QSettings key `access/vpn`), tells the PDF download stage
whether IEEE PDFs can be fetched. The project's rule is to know about
VPN / institutional access before any paywalled-publisher download:
without it IEEE answers with an abstract page or a 403, after a browser
window has opened for nothing. While the box is off, IEEE papers are
left out of the PDF batch and counted on the status line. Tick it only
when this computer reaches IEEE through a university or company
network or VPN.

**Theme** picks how the app looks: *Follow the system* (the default),
*Light* or *Dark*. It is applied the moment you press **Save**, with no
restart, and *Follow the system* keeps tracking the operating system
when you switch it between light and dark while the app is open. The app
theme is separate from the Deck page's **Dark mode** check box, which
decides how the exported `.pptx` looks.

**Style** picks the visual language, also applied on **Save** (QSettings
key `ui/style`), and works with either theme:

| Style | Look |
|---|---|
| *Classic* (the default) | A navy sidebar and white cards with a thin border. The sidebar uses the deck's navy and the accent is the deck's highlight blue, so the app and its decks look like one product. |
| *Material 3* | Google's Material 3 design system: tonal surfaces generated from one blue seed colour, borderless filled cards, a pill-shaped highlight on the active sidebar entry, fully rounded buttons with tonal secondary buttons, and regular-weight page titles. |

Both styles are drawn by the app's own stylesheet
(`thesisagents/gui/theme.py`), so neither needs an extra package. Every
palette is tested for WCAG AA contrast (4.5:1) on body, secondary,
sidebar and button text.

**Check for a new version once a day** (on by default, QSettings key
`updates/check`) asks PyPI for the latest version number and nothing else.
A newer release shows as a button in the status bar that opens the download
page. The app downloads and installs nothing itself.

**AI model** chooses who writes the summaries on the Enrich page: Anthropic,
another service, a program on this computer, or an AI program on the
command line (Claude Code, Gemini CLI, Codex, Ollama, or any command),
which shows a **Command** field in place of the address. Every provider
keeps its own model, address or command, and key, so switching back and
forth loses nothing. **List models** asks the provider what it offers.
Of the command-line programs only Ollama can say: for the others, type
the model name the program knows or leave it empty for its own default. The note under the fields
says whether a paper's text leaves the computer. See
[`configuration.md`](configuration.md) "Language models".

**Font size** sets the text of the whole app, from 8 to 24 pt (QSettings
key `ui/font_size`). It is applied as you change it and needs no
**Save**, since the right size is found by looking at it. **Reset**
forgets the choice, so the default applies again: the system's size, at
least 10 pt. The mouse wheel changes the box only after you click into
it, so scrolling the page past it does not resize the window. What
follows the size, beyond the text itself (`thesisagents/gui/font_size.py`):

- Page titles, table rows, buttons, fields and the sidebar grow with it.
- The window widths at which the layout changes grow with it. A 1280 px
  window at 16 pt is laid out like an 800 px one at 10 pt.
- A page that no longer fits scrolls instead of squeezing its widgets.

The exported decks are not affected.

On a wide window the cards sit in two columns (interface and browser
access on the left, API keys on the right). On a compact window they
stack.

### Enrich

Drives the per-paper PDF + LLM enrichment step through the Python
pipeline. The Search page emits a `collection_ready` signal as soon as
the results table populates. The Enrich page catches it and lists one
row per paper with three columns:

- **Title**, shortened to 80 characters.
- **PDF**, a tick when the paper has a `pdf_url` on file (lifted by
  Unpaywall / S2 / arXiv / CORE.ac.uk), a dash otherwise. A paper
  with no PDF link is skipped.
- **Status**, pending, then done, skipped or failed with the first 60
  characters of the error.

Pick the summary language and, optionally, the model, then press
**Enrich**. The button needs an Anthropic API key in **Settings**,
and without one the status line points there. Papers are enriched one
at a time on a worker thread (each call already takes several seconds,
running them in parallel would only hit the rate limit). A failed paper
keeps its search record, so the Deck page still renders it in the
lightweight tier.

**Cancel** stops the run. A paper whose PDF is still downloading is
stopped at once, one already in the summary call finishes first and its
summary is dropped. Papers not reached are marked *not run (stopped)*
and keep their search record, so the Deck page still gets every paper.
If the Search page sends new results (a new search, or changed ticks)
while a run is going, they are held and shown once the run ends,
because swapping them in mid-run would point the run at the wrong rows.

When the run finishes the enriched collection is sent to the Deck
page, so its **Export** picks up the rich-tier layout automatically.
**No API key? Hand off to an agent.** Without an Anthropic key the
project's other enrichment path is LLM-as-agent: an MCP-aware LLM reads
each PDF and writes the summary itself. The card of that name connects
the GUI to it:

1. **Export for an agent…** writes a JSON hand-off file: the papers with
   their PDF links, the summary language, an empty summary listing every
   field (`summary_template`), and plain instructions saying which thesis
   section each field feeds. Papers already enriched keep their summary
   in the file.
2. Give the file to the agent. It fills `papers[i].paper.summary` for
   each paper it could read and leaves the rest `null`.
3. **Import summaries…** reads the file back and attaches each summary
   to the paper with the same `key` (`Paper.dedup_key()`), so a reordered
   or shortened file still lands on the right papers. The table marks
   them *ok*, the status line counts them, and the result goes to the
   Deck page. An entry whose key matches no paper here is counted and
   skipped, and a paper with no summary in the file keeps the one it had.

A file that is not a hand-off, from a newer version, larger than 20 MB
or with a summary that cannot be read is refused with the reason on the
status line, and nothing changes. Format: `thesisagents/gui/handoff.py`
(`format: "thesisagents-agent-handoff"`, `version: 1`).

**Edit summary** below the list (or a double click on a row) opens the
summary as text, one tab per thesis section, whether or not a model wrote
it. The line above the tabs names the sections that have nothing yet. Lists
take one statement per line, `#` starts a heading, `|` separates columns.
Figures and tables taken from the paper are kept as they are. The Library
page has the same button and stores what you save in the library.

### Deck

The pre-export deck-shaping controls, in three cards: **Output**
(directory, filename stem, deck language), **Formats** (one check box
per export format, re-flowed to the available width) and **Options**.
They wire `ExportOptions` fields behind Qt widgets:

- **Dark mode** checkbox — unchecked (default) ships the light
  navy-band deck (white slides, navy header band with a white title,
  navy cover panel). Tick it for the dark OLED / low-light variant
  (slide bg `#12151B`, body text `#E5E7EB`, brighter blue accent
  `#60A5FA`, lightened navy band / cover / table fills). Mirrors the
  CLI `--dark-mode` flag.
- **Max slides per paper** — integer spinner. Defaults to 25;
  `0` means unlimited.
- **Include abstract** checkbox — when off, the deck skips the
  abstract slide entirely (useful for an "executive overview only"
  variant).
- **Verify DOIs and URLs before export** checkbox, ticked by default.
  The export first looks up every paper's DOI at doi.org and requests
  every URL once, and a wrong or unreachable identifier stops the
  export with the failed papers listed in the status line. Untick it
  only when working offline. Mirrors the CLI `--no-verify-identifiers`
  flag. The Search page's one-button Export always runs the check.
- **Download the PDFs into a pdfs folder**, unticked by default, is the
  CLI's `--export pdf` stage: after the files are written it downloads
  every paper's PDF into `{output folder}/pdfs/` with the same
  `download_pdfs` the CLI and the MCP tool use (publisher pages go
  through a visible Chrome window, PDFs already on disk are kept). It
  can run on its own, with no file format ticked. IEEE PDFs are left out
  unless **Settings** declares institutional / VPN access. The table
  lists the `pdfs` folder and the status line counts them, for example
  `PDFs: 12 saved, 3 not downloaded. 2 IEEE PDFs left out: institutional
  / VPN access is off in Settings.` It also says how many came through
  Chrome, and warns when a publisher PDF was tried without it: *Chrome
  automation was not available …* (selenium missing or
  `THESISAGENTS_DISABLE_WEBRUNNER` set, the fix is in the message) or
  *Chrome could not fetch N publisher PDFs …*. The project's browser rule
  says a publisher download that skipped the visible Chrome window must be
  surfaced, not trusted.
- **Template (.pptx)** and **Template config** build the deck on your
  own PowerPoint template instead of the built-in design, and apply
  a TOML / JSON file of overrides to it (layout per kind of slide,
  fonts, colours, chrome). Both are empty by default. They mirror the
  CLI `--pptx-template` and `--pptx-template-config` flags. The
  template is checked before anything is rendered, and one that does
  not meet the template contract stops the export with every problem
  in the status line. **Check template** runs the same check without
  exporting (it takes a second, where a failed export may come after a
  whole search), and opens the full report, the same text as
  `thesisagents validate-template FILE`: the slide size, the layout each
  kind of slide resolves to, every error and warning. The status line
  says *usable* or *not usable, N problem(s)*. With **Dark mode** ticked
  it adds the warnings that apply to a dark export. Contract:
  [`pptx_templates.md`](pptx_templates.md).

**Review a deck…**, above the written-files table, audits any `.pptx`
the way `thesisagents review` does: text overflowing its box, the colour
contracts (invisible, red or light-on-light text) and, for a
thesis-style deck, the `paper_rule` sections it is missing. The file
picker starts at the deck the last export wrote. The full report opens
in a window you can copy from, and the status line reads `Deck review:
PASS` or `FAIL, N problem(s)`. Reports are in English, like the CLI's,
because they quote shape names and measurements.

The PPTX inspector / editor surface (drives `pptx_inspect` /
`pptx_update_slide` / `pptx_reorder_slides` / `pptx_delete_slide` /
`pptx_add_slide`) is wired to the same shape names the exporter
produces — `title`, `meta`, `body`, `kpi`, `rq_question`, `figure`,
`accent_top`, `accent_left` — so the editor list view labels each
slide by its semantic role rather than by raw shape index.

**Edit slides…** opens the deck selected in the list of written files, or
one you pick. Thumbnails on the left can be dragged into another order. On
the right is the selected slide and its texts, which keep their colour and
size when you change them. Slides can be added in the deck's own look and
deleted, every step can be undone, and the page numbers are counted again.
The file on disk changes only with **Save** (`Ctrl+S`) or **Save as…**. The
preview is drawn from the file without PowerPoint, so fonts and line breaks
differ a little, and charts are not drawn.

## i18n

The UI ships in **all 14 languages** that the slide-deck exporter
supports: English, 繁體中文, 简体中文, 日本語, Español, Français,
Deutsch, 한국어, Português, Русский, Italiano, Tiếng Việt, हिन्दी,
Bahasa Indonesia.

Pick the language under **Settings → Interface language** (the
dropdown shows each language in its own script) and press **Save**.
The window is rebuilt in the new language at once and keeps your work:
its size and place, every form field, the search result with its
ticks, the open library, the Enrich and Deck collections and the page
you were on. While a search, enrichment or export is running the switch
waits for the next start instead (the status bar says so), because
running work cannot be moved to a new window.

First-run behaviour: if no language is saved yet, the app reads
the OS locale via `QLocale().name()` and maps it to the closest
supported code (e.g. `zh_TW` → `zh-tw`, `es_ES` → `es`,
`zh-Hant-TW` → `zh-tw`). Unsupported locales fall back to English.

Two separate i18n tables live in the repo:

- `thesisagents/gui/i18n.py` — UI labels (this page).
- `thesisagents/exporters/i18n.py` — slide-deck output strings.

They're kept in lockstep by `tests/gui/test_i18n.py::test_supported
_languages_match_deck_table`. Adding a key is a single-file change;
the per-key, per-language coverage test catches any missing entry
at PR time.

## Responsive layout & HiDPI

The window sorts its width into three size classes and re-arranges every
page when the class changes (`thesisagents/gui/widgets/responsive.py`):

| Window width | Sidebar | Controls and results | Form labels |
|---|---|---|---|
| below 760 px (compact) | icons only, labels in tooltips | controls above results | above their fields |
| 760 – 1179 px (medium) | icons and labels | controls above results, split by a draggable handle | beside their fields when the card has room |
| 1180 px and up (expanded) | icons and labels | controls in a 420 px column beside the results | above their fields while the column is narrow |

- The ☰ button at the top of the sidebar collapses or expands it by hand
  at any width. Crossing a size class applies that class's default again.
- Form labels follow the width of their own card, not of the window: a
  card narrower than 460 px puts each label above its field, so long
  labels in German or Russian do not squeeze the fields.
- Groups of check boxes (sources, export formats) re-flow into as many
  aligned columns as fit.
- On a compact window the Search results hide the Authors and DOI
  columns so the title stays readable. Both are still in every export.
- The window has a minimum size of 640×480 and a default of 1280×800.
- Closing the window saves its size, position and maximised state
  (QSettings key `window/geometry`); the next launch restores them,
  moving the window back on-screen if its monitor is gone.
- HiDPI scaling is enabled at boot via
  `QT_ENABLE_HIGHDPI_SCALING=1` and
  `QT_SCALE_FACTOR_ROUNDING_POLICY=PassThrough`. Both are set
  *before* `QApplication` is constructed, which is the only safe
  time to pin them.
- The default font is bumped to point size 10 (Qt's platform
  default is 8 on some Windows machines) so CJK glyphs stay
  readable on dense screens. The font family list includes
  Windows-shipped CJK / Devanagari fallbacks (Microsoft JhengHei
  UI, Yu Gothic UI, Malgun Gothic, Nirmala UI) so a missing glyph
  in the primary font cascades cleanly rather than rendering a
  tofu box.
- Sidebar icons, check marks and arrows are drawn at run time in the
  theme's colours (`thesisagents/gui/icons.py`), at twice their size for
  sharp rendering at 200 % scaling. No SVG plug-in is needed, so a
  packaged build cannot lose them.

## Threading model

Every backend call runs off the main thread:

- `AsyncWorker` wraps a coroutine factory and calls `asyncio.run`
  inside `QRunnable.run` — used for `run_search`, single-paper
  fetches, anything that touches `httpx.AsyncClient`.
- `BlockingWorker` wraps a plain function — used for
  `export_collection`, which renders the `.pptx` via python-pptx.

Both emit `finished(object)` / `failed(object)` signals on
completion; the receiving slot lives on the main thread so it can
update widgets safely.

## Testing the GUI

The test suite under `tests/gui/` uses `pytest-qt` (installed by
the `[dev]` extra). It mocks the backend so no live HTTP is made:

```powershell
pip install -e ".[dev]"
py -m pytest tests/gui/
```

Tests fall into four families: i18n coverage, Qt model behaviour,
page-level wiring (a search button click populates the table, the
export button stays disabled until results arrive, settings round-trip
through QSettings), and the adaptive shell (`test_responsive.py`,
`test_theme_and_shell.py`: size classes, sidebar collapse, split
orientation, re-flowing grids, theme contrast, busy indicator).

## Remembered form values

Closing the window saves the Search, Enrich and Deck fields to QSettings
(groups `form/search`, `form/enrich`, `form/deck`), and the next start
fills them back in: the query, ticked sources, filters, snowball
direction and bounds, library file, summary language and model, output
folder, deck language, formats and deck options. The Deck page's
filename stem is not saved on purpose: it names one export, and a
remembered stem would make the next export overwrite the last one. A
value that is missing or no longer valid (a source that was removed)
leaves that field at its default.

## Known limitations

- The Settings page does not validate keys against the live API —
  validation would leak the key into HTTP logs and slow down save.
  An invalid key surfaces later as a `ConfigError` / 401 from the
  relevant source plugin.
- An export cannot be cancelled: stopping it half-way would leave
  partial files behind. A search and an enrichment run can.

Planned GUI work is tracked in `progress.md` (items #19 – #28).
