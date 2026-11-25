# docs/updates: update log index

`progress.md` holds only work that is **not done yet**. Everything that *was* done (what changed, measured numbers, decisions, snapshots) is recorded here: **one batch file per month**, one entry per piece of work, each entry with a fixed-format ID and tags, and one row per entry in the index below.

> No TODOs here. If an entry mentions something still open, it only points to it (e.g. "open item: `progress.md` #3"); the item itself lives in `progress.md`.

## How to query

Run from the repository root:

| To find | Command |
|---|---|
| every entry, one line each | `rg -n "^## U-2" docs/updates` |
| entries of one type | `rg -n "^## U-2.*#done" docs/updates` |
| entries with a topic tag | `rg -n "^## U-2.*#<tag>" docs/updates` |
| one day or one month | `rg -n "^## U-202609" docs/updates` |
| the full text of one entry | `rg -n -A 60 "^## U-20260922-01" docs/updates` |
| any keyword | `rg -n "keyword" docs/updates` |

Without `rg`: `git grep -n "^## U-2" -- docs/updates`, or in PowerShell `Select-String -Path docs/updates/*.md -Pattern '^## U-2'`.

## Entry format

```markdown
## U-YYYYMMDD-NN · YYYY-MM-DD · one-line title · #type #topic

- **What**: ...
- **Result / numbers**: ...
- **Files**: `path` ...
- **Evidence**: commit, file:line, link ...
- **Open items**: none / see `progress.md` ...
```

- **ID**: `U-` + date + two-digit sequence for that day. IDs are never renumbered or reused, so code comments and other documents can cite them.
- **Type tag** (exactly one): `#done` finished `progress.md` item, `#snapshot` measurement or inventory, `#decision`, `#incident`, `#migration`, `#docs`, `#release`.
- Topic tags are free-form (`#mcp`, `#wayland`, ...).
- Keep conclusions, numbers, files and evidence; drop the reasoning trail and dead ends.

## Batch rules

1. One file per month: `docs/updates/YYYY-MM.md`. Append new entries at the end.
2. Over about 800 lines, continue in `YYYY-MM-b.md` (then `-c`) and list it in the batch table below.
3. **Claim the ID under a lock.** Several sessions may write this log at the same time (for example parallel autonomous runs), and without a lock two of them pick the same number:
   1. `mkdir docs/updates/.id-lock`. Creating a directory is atomic, so only one writer succeeds. If it already exists, someone else is claiming: wait a few seconds and retry. A lock older than 10 minutes is stale and may be removed.
   2. Find the day's last number with `rg -n "^## U-YYYYMMDD" docs/updates` and write the heading line and the index row.
   3. `rmdir docs/updates/.id-lock`, then fill in the body. Git never tracks the empty lock directory.
   4. Before committing, `rg -c "^## U-<your ID>" docs/updates` must report one match in total. If not, renumber your entry under the lock and fix its index row. Whoever merges a branch renumbers entries that reuse an ID.
4. **One line per index row**: title only (about 60 characters), no summary.
5. Never rewrite a recorded entry. Correct it with a new `#decision` or `#incident` entry and add "→ corrected in U-..." to the old one.

## When a `progress.md` item is done

In the same commit: delete the item from `progress.md`, add a `#done` entry here that names it, and add its index row.

---

## Index (newest first)

| ID | Date | Title | Tags | Batch |
|---|---|---|---|---|
| U-20261126-09 | 2026-11-26 | Summary editor, comparison table, Word and LaTeX literature review drafts | #done #gui #export #i18n | [2026-11](2026-11.md) |
| U-20261126-08 | 2026-11-26 | Summaries from many model providers, local ones included | #done #intelligence #gui #cli #i18n | [2026-11](2026-11.md) |
| U-20261126-07 | 2026-11-26 | The Library page edits: notes, screening, imports, saved searches, citation graph, PRISMA | #done #gui #library #i18n | [2026-11](2026-11.md) |
| U-20261126-06 | 2026-11-26 | The library can be edited: tags, notes, screening, merging, imports, saved searches, PRISMA | #done #library #cli #mcp | [2026-11](2026-11.md) |
| U-20261126-05 | 2026-11-26 | Update notice, Windows installer, a real version number | #done #gui #release #i18n | [2026-11](2026-11.md) |
| U-20261126-04 | 2026-11-26 | API keys move to the system credential store | #done #gui #security #i18n | [2026-11](2026-11.md) |
| U-20261126-03 | 2026-11-26 | Log window, captcha banner and start-up errors in the GUI | #done #gui #i18n | [2026-11](2026-11.md) |
| U-20261126-02 | 2026-11-26 | Code review findings closed, icon and technique header fixed | #done #security #gui #pptx | [2026-11](2026-11.md) |
| U-20261126-01 | 2026-11-26 | The interface font size is adjustable | #done #gui #i18n | [2026-11](2026-11.md) |
| U-20261125-01 | 2026-11-25 | The Windows app opens without a console, Qt font lines gone | #done #gui #release | [2026-11](2026-11.md) |
| U-20261121-01 | 2026-11-21 | CI saves its pip cache from main only | #done #ci | [2026-11](2026-11.md) |
| U-20261120-05 | 2026-11-20 | CI installs from a hash-locked lock, caches stop evicting the Nuitka cache | #done #ci #security | [2026-11](2026-11.md) |
| U-20261120-04 | 2026-11-20 | SonarCloud new-code issues on main cleared | #done #quality #sonar | [2026-11](2026-11.md) |
| U-20261120-03 | 2026-11-20 | The Nuitka release build compiles with 4 jobs | #done #ci #release | [2026-11](2026-11.md) |
| U-20261120-02 | 2026-11-20 | Project agents run on the newest Opus | #done #agents | [2026-11](2026-11.md) |
| U-20261120-01 | 2026-11-20 | CI retries the Linux Qt library install | #done #ci | [2026-11](2026-11.md) |
| U-20261119-13 | 2026-11-19 | PDF metadata reads flattened front matter: abstract, all authors, ORCID | #done #pdf #intelligence | [2026-11](2026-11.md) |
| U-20261119-12 | 2026-11-19 | A library takes a richer summary for a paper it holds | #done #library | [2026-11](2026-11.md) |
| U-20261119-11 | 2026-11-19 | DBLP pages instead of results are retried and say what came | #done #sources #dblp | [2026-11](2026-11.md) |
| U-20261119-10 | 2026-11-19 | Deck meta line and research-question callout fit long text | #done #pptx #fix | [2026-11](2026-11.md) |
| U-20261119-09 | 2026-11-19 | PDF downloads record their route; a skipped browser is surfaced | #done #pdf #compliance #mcp #gui | [2026-11](2026-11.md) |
| U-20261119-08 | 2026-11-19 | Local PDFs in the GUI; the --pdf builder moved to core | #done #gui #cli #pdf #i18n | [2026-11](2026-11.md) |
| U-20261119-07 | 2026-11-19 | GUI searches leave out IEEE until VPN access is declared | #done #gui #compliance #i18n | [2026-11](2026-11.md) |
| U-20261119-06 | 2026-11-19 | GUI: PDF download with the VPN switch, language switch without restart | #done #gui #pdf #i18n | [2026-11](2026-11.md) |
| U-20261119-05 | 2026-11-19 | GUI: template check, deck review, enrichment hand-off to an agent | #done #gui #pptx #i18n | [2026-11](2026-11.md) |
| U-20261119-04 | 2026-11-19 | GUI Library page: overview, papers with links and checks, searches | #done #gui #library #i18n | [2026-11](2026-11.md) |
| U-20261119-03 | 2026-11-19 | GUI: cancel, snowball bounds, results subset, remembered forms | #done #gui #i18n | [2026-11](2026-11.md) |
| U-20261119-02 | 2026-11-19 | Selectable GUI style: classic navy or Material 3 | #done #gui #i18n | [2026-11](2026-11.md) |
| U-20261119-01 | 2026-11-19 | GUI rebuilt: sidebar, themes, layouts that adapt to the width | #done #gui #i18n #docs | [2026-11](2026-11.md) |
| U-20261008-08 | 2026-10-08 | The GUI gets snowballing, the library and deck templates | #done #gui #snowball #library #templates | [2026-10](2026-10.md) |
| U-20261008-07 | 2026-10-08 | A template contract for decks, with validation before the export | #done #pptx #templates #cli #mcp | [2026-10](2026-10.md) |
| U-20261008-06 | 2026-10-08 | A persistent SQLite literature library | #done #library #cli #mcp | [2026-10](2026-10.md) |
| U-20261008-05 | 2026-10-08 | Citation providers and a bounded snowball search | #done #snowball #sources #cli #mcp | [2026-10](2026-10.md) |
| U-20261008-04 | 2026-10-08 | Every search reports what each source returned | #done #search #cli #mcp #gui | [2026-10](2026-10.md) |
| U-20261008-03 | 2026-10-08 | Rankings are explained, results get advisory pruning recommendations | #done #ranking #cli #mcp #gui | [2026-10](2026-10.md) |
| U-20261008-02 | 2026-10-08 | Export verifies every DOI and URL before writing | #done #export #cli #mcp #gui | [2026-10](2026-10.md) |
| U-20261008-01 | 2026-10-08 | Test suite restores the environment and refuses live HTTP | #incident #tests | [2026-10](2026-10.md) |
| U-20261001-05 | 2026-10-01 | Publish job builds with the locked build backend | #done #ci #security #X-13 | [2026-10](2026-10.md) |
| U-20261001-04 | 2026-10-01 | Publish job installs hash-locked build tooling | #done #ci #security #X-13 | [2026-10](2026-10.md) |
| U-20261001-03 | 2026-10-01 | The sdist carries no tests | #done #packaging #X-13 | [2026-10](2026-10.md) |
| U-20261001-02 | 2026-10-01 | Workflow-timeout test failed CI lint (ruff B905) | #incident #ci | [2026-10](2026-10.md) |
| U-20261001-01 | 2026-10-01 | Every workflow job has a timeout | #ci #tests | [2026-10](2026-10.md) |
| U-20260925-04 | 2026-09-25 | Translated READMEs link back to the repository root | #docs #tests | [2026-09](2026-09.md) |
| U-20260925-03 | 2026-09-25 | License metadata uses the SPDX expression | #packaging | [2026-09](2026-09.md) |
| U-20260925-02 | 2026-09-25 | Dependabot waits 7 days before proposing a new release | #ci #security #deps | [2026-09](2026-09.md) |
| U-20260925-01 | 2026-09-25 | Nuitka release build actually uses its compiler cache; cap raised to 120 min | #ci #release #fix | [2026-09](2026-09.md) |
| U-20260924-03 | 2026-09-24 | Test that every checkout decides on persisted credentials | #ci #tests | [2026-09](2026-09.md) |
| U-20260924-02 | 2026-09-24 | Release runs only for pushes here; least-privilege workflow permissions | #ci #security | [2026-09](2026-09.md) |
| U-20260924-01 | 2026-09-24 | Move CI to Node 24 actions pinned by commit | #ci #security #deps | [2026-09](2026-09.md) |
| U-20260923-10 | 2026-09-23 | MCP server runs on mcp 1.x and 2.x; extras allow <3 | #done #mcp #compat | [2026-09](2026-09.md) |
| U-20260923-09 | 2026-09-23 | Release 0.1.19 | #done #release | [2026-09](2026-09.md) |
| U-20260923-08 | 2026-09-23 | MCP tools report expected failures as ToolError | #mcp #compat | [2026-09](2026-09.md) |
| U-20260923-07 | 2026-09-23 | selenium replaces the je_web_runner dependency | #done #deps | [2026-09](2026-09.md) |
| U-20260923-06 | 2026-09-23 | The GUI window remembers its size and position | #done #gui | [2026-09](2026-09.md) |
| U-20260923-05 | 2026-09-23 | GUI tests wrote to the real settings registry | #bugfix #tests #gui | [2026-09](2026-09.md) |
| U-20260923-04 | 2026-09-23 | bandit no longer points at the removed sources/ | #done #docs #ci | [2026-09](2026-09.md) |
| U-20260923-03 | 2026-09-23 | dev merged into main (PR #19); SonarCloud gate green | #done #release | [2026-09](2026-09.md) |
| U-20260923-02 | 2026-09-23 | Evaluator CLI path goes through resolve_safe | #done #security | [2026-09](2026-09.md) |
| U-20260923-01 | 2026-09-23 | CI green again: keep mcp on the 1.x SDK | #done #mcp #ci | [2026-09](2026-09.md) |
| U-20260922-08 | 2026-09-22 | Thesis-defence and TCSE deck scripts with figures | #done #decks | [2026-09](2026-09.md) |
| U-20260922-07 | 2026-09-22 | New authoring rules; agent docs drop retired tooling | #docs #rules | [2026-09](2026-09.md) |
| U-20260922-06 | 2026-09-22 | Docs synced to 15 sources and 13 MCP tools in 14 languages | #docs #i18n | [2026-09](2026-09.md) |
| U-20260922-05 | 2026-09-22 | Offline search-quality evaluator | #done #evaluation | [2026-09](2026-09.md) |
| U-20260922-04 | 2026-09-22 | Treat --export pdf as the PDF download stage | #done #cli #mcp | [2026-09](2026-09.md) |
| U-20260922-03 | 2026-09-22 | Contain per-source, per-paper and write failures | #done #robustness | [2026-09](2026-09.md) |
| U-20260922-02 | 2026-09-22 | Dedup on every identity key, with field provenance | #done #dedup | [2026-09](2026-09.md) |
| U-20260922-01 | 2026-09-22 | Adopt progress/architecture/docs-updates rules | #docs #migration | [2026-09](2026-09.md) |

## Batches

| File | Period | Entries |
|---|---|---:|
| [2026-11.md](2026-11.md) | 2026-11 | 19 |
| [2026-10.md](2026-10.md) | 2026-10 | 13 |
| [2026-09.md](2026-09.md) | 2026-09 | 25 |
