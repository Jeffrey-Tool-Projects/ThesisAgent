# Configuration reference

Every knob the user can turn — environment variables, CLI flags
that map to env vars, GUI Settings page fields, and the on-disk
QSettings store. This page is the single source of truth; other
docs link here.

## Environment variables

All env vars are read **at the moment a fetcher or extra is
constructed**, not lazily — so a `set ANTHROPIC_API_KEY=...`
after the CLI is running has no effect. Set them in the shell
before launching, or use the GUI's Settings page, which mirrors
each value into `os.environ` before any fetcher initialises.

### LLM enrichment

| Variable | Default | Effect |
|---|---|---|
| `ANTHROPIC_API_KEY` | unset | Required for the Python `--enrich` pipeline. Triggers auto-enrichment when set (override with `--lightweight`). Never needed for the LLM-as-agent flow over MCP. |
| `THESISAGENTS_LLM_MODEL` | `claude-opus-5-5` | Override the model used when `--enrich` is on. `--llm-model` on the CLI takes precedence. |

### Source plugin keys

| Variable | Default | Effect |
|---|---|---|
| `THESISAGENTS_S2_API_KEY` | unset | Sent with every Semantic Scholar request, which is then served from your own quota instead of the one all anonymous users share. The plugin stays at 1 request per second either way. **Also used by the OA resolver's S2 `openAccessPdf` lookup step** — without the key the resolver's S2 calls hit the anonymous tier and rate-limit fast. Free key at <https://www.semanticscholar.org/product/api>. |
| `THESISAGENTS_NCBI_API_KEY` | unset | Sent with every PubMed request. NCBI allows 10 req/s with a key, the plugin stays at 3. |
| `THESISAGENTS_IEEE_API_KEY` | unset | Switches the IEEE plugin from the scrape fallback to the official Xplore API (`ieeexploreapi.ieee.org`). Surfaces `pdf_url` for papers in your subscription scope. Apply at <https://developer.ieee.org/>. |
| `THESISAGENTS_DISABLE_IEEE_SCRAPING` | unset | **IEEE plugin is now default-ON.** Set `=1` to opt out of the scrape fallback. IEEE Xplore ToS are grey on automated traffic — set this if you don't want the scrape path running. |
| `THESISAGENTS_SPRINGER_API_KEY` | unset | Free key from <https://dev.springernature.com/>. **Required** for the Springer plugin — it raises `ConfigError` at construction without a key, which the pipeline silently skips. |
| `THESISAGENTS_CROSSREF_PLUS_TOKEN` | unset | Crossref Plus subscriber token. Attached to requests as `Crossref-Plus-API-Token: Bearer <token>`. Raises rate limits and improves cache freshness on the `acm` and `crossref` plugins. |
| `THESISAGENTS_DISABLE_SCHOLAR_SCRAPING` | unset | **Scholar plugin is now default-ON.** Set `=1` to opt out. Google's ToS forbids automated access; default-on for coverage, opt-out if you'd rather not take the captcha / IP-block risk. |
| `THESISAGENTS_DISABLE_WEBRUNNER` | unset | **Scholar + IEEE plugins + the PDF downloader for paywalled publisher CDNs all default to driving a real visible Chrome through Selenium** (`selenium` is a default dependency) — publisher bot-detection is far less aggressive on real browsers. PDF download host list includes `ieeexplore.ieee.org`, `dl.acm.org`, `link.springer.com`, `sciencedirect.com`, `onlinelibrary.wiley.com`, `tandfonline.com`, `academic.oup.com`, `nature.com`, `science.org`, plus a few engineering-society CDNs. Set `=1` to force the httpx paths instead (useful for CI / Docker without a Chrome binary). |
| `THESISAGENTS_CHROME_PROFILE_DIR` | unset | When set, passes `--user-data-dir=<path>` to Chrome so cookies / login state survive across CLI invocations. Used by **both** Scholar (one-time Google sign-in suppresses Scholar captchas) and IEEE (institutional auth cookies surface paywalled metadata). |
| `THESISAGENTS_CORE_API_KEY` | unset | Free key from <https://core.ac.uk/services/api>. Enables both the OA resolver's CORE.ac.uk lookup step (200M+ institutional / regional OA repository items) **and** the `core` search source. Skipped silently when unset — the `core` source drops out and the other OA strategies (Unpaywall, Semantic Scholar, arXiv) still run. |
| `THESISAGENTS_CONTACT_EMAIL` | unset | Sent to Crossref / OpenAlex as the `mailto=` parameter (entry into their polite pool), to NCBI as the `tool` / `email` query parameters, **and to Unpaywall as `email=`** for the post-dedup OA PDF resolver. Highly recommended — without it the resolver skips Unpaywall lookups entirely, which is the single biggest PDF coverage win for IEEE / ACM / Springer / Elsevier paywalled papers (typical lift 40-70%). |

### PDF download

| Variable | Default | Effect |
|---|---|---|
| `THESISAGENTS_PDF_COOKIES_FILE` | unset | Path to a Netscape-format `cookies.txt`. When set, cookies whose `domain` field matches the host of an outbound PDF download are attached to that request only. **You** are responsible for compliance with the relevant publisher's terms of service. A startup warning fires when the env var is loaded. |

### Logging / debug

| Variable | Default | Effect |
|---|---|---|
| `THESISAGENTS_LOG_LEVEL` | `INFO` | Set to `DEBUG` for verbose HTTP and rate-limit tracing. `WARNING` quiets the normal per-paper progress line. |

### Qt / GUI

These are read by Qt itself (not by ThesisAgents), but the GUI
sets sensible defaults when they're absent. See the [GUI doc](gui.md)
for the full HiDPI story.

| Variable | Default | Effect |
|---|---|---|
| `QT_ENABLE_HIGHDPI_SCALING` | `1` (set by app.py if unset) | Enables Qt's HiDPI scaling. |
| `QT_SCALE_FACTOR_ROUNDING_POLICY` | `PassThrough` (set by app.py if unset) | Lets fractional scale factors (125%, 150%) flow through unchanged. |
| `QT_QPA_PLATFORM` | OS default | Set to `offscreen` for headless / CI runs of the GUI. |

## Language models

Summaries are written by the model you choose. `THESISAGENTS_LLM_PROVIDER`
names who runs it:

| Provider | API key | Address |
|---|---|---|
| `anthropic` (default) | `ANTHROPIC_API_KEY` | Anthropic's SDK |
| `openai` | `OPENAI_API_KEY` | `https://api.openai.com/v1` |
| `gemini` | `GEMINI_API_KEY` | `https://generativelanguage.googleapis.com/v1beta/openai` |
| `mistral` | `MISTRAL_API_KEY` | `https://api.mistral.ai/v1` |
| `deepseek` | `DEEPSEEK_API_KEY` | `https://api.deepseek.com/v1` |
| `xai` | `XAI_API_KEY` | `https://api.x.ai/v1` |
| `groq` | `GROQ_API_KEY` | `https://api.groq.com/openai/v1` |
| `openrouter` | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` |
| `together` | `TOGETHER_API_KEY` | `https://api.together.xyz/v1` |
| `fireworks` | `FIREWORKS_API_KEY` | `https://api.fireworks.ai/inference/v1` |
| `dashscope` | `DASHSCOPE_API_KEY` | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| `moonshot` | `MOONSHOT_API_KEY` | `https://api.moonshot.ai/v1` |
| `ollama` | none | `http://localhost:11434/v1` |
| `lmstudio` | none | `http://localhost:1234/v1` |
| `llamacpp` | none | `http://localhost:8080/v1` |
| `vllm` | none | `http://localhost:8000/v1` |
| `custom` | `THESISAGENTS_LLM_API_KEY` (optional) | `THESISAGENTS_LLM_BASE_URL` |
| `claude-cli` | none, signed in to Claude Code | `claude -p --output-format text --tools "" --no-session-persistence --permission-prompts none` |
| `gemini-cli` | none, signed in to the Gemini CLI | `gemini` |
| `codex-cli` | none, signed in to Codex | `codex exec --skip-git-repo-check --sandbox read-only --ephemeral --color never -` |
| `ollama-cli` | none, Ollama on this computer | `ollama run` (the model is required) |
| `cli` | whatever the program needs | `THESISAGENTS_LLM_COMMAND` |

- `THESISAGENTS_LLM_MODEL` is the model. Anthropic has a default, the others
  need one: model names change too often to build in. The GUI's **Settings →
  AI model → List models** asks the service.
- `THESISAGENTS_LLM_BASE_URL` replaces the address, for a gateway or a
  server elsewhere. Plain HTTP is accepted only for this computer and
  private addresses.
- The `*-cli` providers and `cli` run an AI program on the command line, the
  last column being their command. The instructions and the paper go in on
  standard input and the answer is read from standard output. The command
  is run without a shell, in a new empty folder that is removed afterwards,
  and on Windows without a console window. Claude Code runs without tools
  and Codex may only read, but a program allowed to read can still open a
  file by its full path. The API keys the app holds are left out of the
  program's environment, so it uses the account it is signed in to (Claude
  Code would bill a set `ANTHROPIC_API_KEY` instead), except for `cli`,
  whose command may need one. `THESISAGENTS_LLM_COMMAND` (or
  `--llm-command`) replaces the command of the provider the environment
  selects, and of `cli`. The model (`THESISAGENTS_LLM_MODEL`, under the same
  rule, or `--llm-model`) is added with the program's model flag unless the
  command names one. `THESISAGENTS_LLM_CLI_TIMEOUT` is how many seconds one
  paper may take (600), after which the program and everything it started
  are ended. Install the program and sign in to it first: the paper goes to
  whatever service it uses.
- An API key in the environment never selects its service by itself. A
  paper's text goes only to the provider you named, and nowhere with a
  local one.
- `THESISAGENTS_LLM_MAX_CHARS` is how much of a paper is sent: 80,000
  characters to a hosted service, 24,000 to a local one. Local programs
  often run with a small context window and silently drop what does not
  fit. Raise both together (in Ollama, `num_ctx` of the model).
- The providers other than Anthropic were checked against a local test
  server that speaks the same protocol, not against the real services.

## QSettings on-disk store

When the GUI's **Settings → Save** is clicked, the API keys land in the
system credential store (see below), the other values land in a per-OS
persistent store **and** all of them are mirrored into
`os.environ` for the current process. Each subsequent launch
of the GUI calls `apply_saved_env()` at startup, so the env
vars are re-applied automatically.

### Storage locations

| OS | Path |
|---|---|
| Windows | `HKEY_CURRENT_USER\Software\ThesisAgents\ThesisAgents` |
| macOS | `~/Library/Preferences/com.ThesisAgents.ThesisAgents.plist` |
| Linux | `~/.config/ThesisAgents/ThesisAgents.conf` |

The QSettings organisation name is `ThesisAgents` and the
application name is `ThesisAgents`. Tests inject a temporary
storage path via `QSettings.setPath(...)` so they never touch
the user's real store.

### API keys

The `api/…` values are secrets and go to the system credential store,
under the service name `ThesisAgents` and the key in the table below:
Windows Credential Manager, macOS Keychain, or the Secret Service (GNOME
Keyring, KWallet) on Linux. Keys that an earlier version saved in
QSettings are moved at the next start, and the plain copy is removed only
after the stored one was read back. Where no store is usable (a headless
Linux box, a locked keychain), keys stay in QSettings as plain text and
the Settings page says so under the fields. Keys set as environment
variables are never written anywhere.

### Keys

| Key | Env var mirrored to | Type |
|---|---|---|
| `api/anthropic` | `ANTHROPIC_API_KEY` | string |
| `api/semantic_scholar` | `THESISAGENTS_S2_API_KEY` | string |
| `api/ncbi` | `THESISAGENTS_NCBI_API_KEY` | string |
| `api/ieee` | `THESISAGENTS_IEEE_API_KEY` | string |
| `api/springer` | `THESISAGENTS_SPRINGER_API_KEY` | string |
| `api/crossref_plus` | `THESISAGENTS_CROSSREF_PLUS_TOKEN` | string |
| `contact/email` | `THESISAGENTS_CONTACT_EMAIL` | string |
| `pdf/cookies_file` | `THESISAGENTS_PDF_COOKIES_FILE` | string (absolute path) |
| `ui/language` | (not mirrored) | string — a BCP-47 code from the 14 supported languages |

## CLI flags ↔ env var equivalents

Many CLI flags have an environment-variable counterpart so
unattended deployments don't need to pass long argument lists.

| CLI flag | Env var | Notes |
|---|---|---|
| `--llm-model MODEL` | `THESISAGENTS_LLM_MODEL` | CLI wins if both are set. |
| `--llm-provider NAME` | `THESISAGENTS_LLM_PROVIDER` | CLI wins if both are set. |
| `--llm-base-url URL` | `THESISAGENTS_LLM_BASE_URL` | CLI wins if both are set. |
| `--llm-command COMMAND` | `THESISAGENTS_LLM_COMMAND` | CLI wins if both are set. |

Those are the only ones today; everything else is per-source plugin
config above. The CLI explicitly does NOT read API keys via
flags (no `--anthropic-key`) — passing a key on the command
line writes it to shell history, which is a security footgun.

## CLI defaults

Behaviour you don't see in `--help` because it's hard-coded:

| Setting | Value | Where |
|---|---|---|
| Default page size (`--max`) | `25` | `thesisagents.core.constants.DEFAULT_PAGE_SIZE` |
| Max results per source (`--max` ceiling) | `200` | `thesisagents.core.constants.MAX_RESULTS_PER_SOURCE` |
| Default output dir | `./exports` | `thesisagents.cli._DEFAULT_OUT_DIR` |
| Default export formats (`--query`) | `pptx, xlsx, bibtex` | `thesisagents.cli._DEFAULT_EXPORTS_SEARCH` |
| Default export formats (`--paper`) | `pptx, bibtex` | `thesisagents.cli._DEFAULT_EXPORTS_SINGLE` |
| Default slide language (`--lang`) | `en` | `thesisagents.exporters.i18n.DEFAULT_LANGUAGE` |
| Default max slides per paper | `25` | `thesisagents.cli` (`--max-slides`) |
| Paywall warning threshold | `0.30` (30%) | `thesisagents.cli.DEFAULT_PAYWALL_THRESHOLD` |
| Top-tier-only filter | off (on via `--top-tier-only`) | `thesisagents.cli` |

## Per-source rate limits

Defined in each plugin's `config.py`; enforced by a per-source
token bucket in `thesisagents.fetchers.rate_limit`. The
defaults match each upstream's published or observed soft limit:

| Source | Rate | Jitter | Notes |
|---|---|---|---|
| `arxiv` | 1 req / 3 s | 0.5 s | Matches arXiv's API ToS. |
| `semantic_scholar` | 1 req / s | 0.1 s | With and without an API key. |
| `openalex` | 10 req / s | 0.1 s | Polite pool (with `THESISAGENTS_CONTACT_EMAIL`). |
| `pubmed` | 3 req / s | 0.1 s | With and without `THESISAGENTS_NCBI_API_KEY`. |
| `acm` (via crossref) | 50 req / s | 0.05 s | Crossref public; Plus token raises further. |
| `dblp` | 1 req / 2 s | 0.5 s | Conservative — DBLP is single-server. |
| `crossref` | 50 req / s | 0.05 s | Polite pool with `mailto`. |
| `openaire` | 2 req / s | 0.2 s | Conservative — OpenAIRE rate limits are not published. |
| `europepmc` | 5 req / s | 0.2 s | Half of Europe PMC's stated 10 req/s ceiling. |
| `doaj` | 2 req / s | 0.3 s | DOAJ asks for ≤ 2 req/s from a single client. |
| `hal` | 2 req / s | 0.3 s | Polite — HAL publishes no per-second cap. |
| `ieee` (API) | 10 req / s | 0.1 s | Per the IEEE Xplore API ToS. |
| `ieee` (scrape) | 1 req / 5 s | 1.0 s | ToS-grey — extra-conservative. |
| `springer` | 5 req / s | 0.2 s | Per the Springer Meta API ToS. |
| `core` | 1 req / s | 0.3 s | Free-tier headroom; needs `THESISAGENTS_CORE_API_KEY`. |
| `scholar` | 1 req / 10 s | 2.0 s | ToS forbids scraping — extra-conservative. |

These are enforced by a decorator on the HTTP client; retries on
429 / 5xx also go through the bucket so a burst can't slip past
the limit.

## Response caching

ThesisAgents currently pools HTTP connections but does not persist API
responses between runs. Repeating a search contacts its sources again and
remains subject to their current rate limits.

## Suppressing Scholar captchas with a persistent Chrome profile

Google flags an IP after a few automated Scholar requests even with
WebRunner's real-browser path. The reliable workaround is to seed a
persistent Chrome profile with a real Google sign-in once; subsequent
headless runs reuse the same session cookies, which Google trusts.

**One-time setup:**

```powershell
# 1. Pick a directory anywhere on disk
$env:THESISAGENTS_CHROME_PROFILE_DIR = "D:\thesisagents-scholar-profile"

# 2. Open Chrome visibly and trigger one Scholar request
$env:THESISAGENTS_CHROME_HEADLESS = "0"
thesisagents --query "any keywords" --source scholar --max 1 --out .\tmp\

# Chrome opens. Sign into your Google account, accept any consent
# banners, complete any captcha. The window holds open for 60s.
```

**Every run after that:**

```powershell
$env:THESISAGENTS_CHROME_PROFILE_DIR = "D:\thesisagents-scholar-profile"
Remove-Item Env:\THESISAGENTS_CHROME_HEADLESS   # back to headless
thesisagents --query "..." --out .\exports\
```

Chrome boots headless but loads the same profile dir, sends your
authenticated Google session cookie, and Scholar serves real results
instead of a captcha page.

**Caveats:**

- Only one Chrome process can hold the profile dir at a time. If you
  have a regular Chrome open on the same profile path, the
  WebRunner instance will fail to start. Use a dedicated path.
- The session cookie is a real authentication credential. Treat the
  profile directory like a secret — back it up if you re-image the
  machine, restrict file permissions.
- Cookie eventually expires (~1-2 months for Google). Re-do the
  interactive sign-in then.

## Settings the project explicitly does NOT have

By design — listing them so a contributor doesn't accidentally
add them.

- **No `--anthropic-key` / `--ieee-key` / etc. CLI flag.** Keys on
  the command line land in shell history, a screen-sharing reveal,
  and process listings. Use env vars or the GUI.
- **No global rate-limit override.** Per-source buckets are the
  enforcement boundary; a global override would let users break a
  single source's ToS by upping the wrong limit.
- **No "skip robots.txt" flag.** The scrape-based plugins are
  off-by-default precisely because of robots / ToS concerns.
- **No `--insecure` / `--allow-http` flag.** All egress is HTTPS,
  enforced by the project's transport wrapper. Plain-HTTP URLs are
  refused even after a redirect.
