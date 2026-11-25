# Releases

The auto-release pipeline, what triggers it, and how to opt out.

## The pipeline

```
Push to main
   │
   ▼ ci.yml runs (matrix: Ubuntu + Windows × Python 3.12 / 3.13 / 3.14)
   │
   ▼ CI passes → workflow_run fires release.yml
   │
   ▼
┌──────────────┐
│ bump-version │  patch +1 in pyproject.toml, push back to main via GITHUB_TOKEN
└──────────────┘
   │
   ▼
┌──────────────┐
│ publish-pypi │  python -m build + twine upload (PYPI_API_TOKEN)
└──────────────┘
   │
   ▼
┌──────────────────────┐
│ create-draft-release │  GitHub Release at tag v<X.Y.Z>, draft: true
└──────────────────────┘
   │
   ▼
┌──────────────┐
│ build-nuitka │  Windows .zip with the standalone bundle
└──────────────┘
   │
   ▼
┌────────────────┐
│ publish-release│  unmarks the draft, release appears in sidebar
└────────────────┘
```

## What gets published per release

| Artefact | Where | Size |
|---|---|---|
| **`thesisagents-<version>.tar.gz`** (sdist, without the test suite) | PyPI | ~250 KB |
| **`thesisagents-<version>-py3-none-any.whl`** | PyPI | ~280 KB |
| **`thesisagents-windows-x86_64.zip`** | GitHub Release | ~140 MB expected (Nuitka bundle + PySide6, v0.1.26 was 100 MB with one executable) |
| **`thesisagents-windows-x86_64.zip.sha256`** | GitHub Release | 80 bytes |

The PyPI artefacts work on Linux / macOS / Windows; the zip is
the standalone Windows bundle for users who don't want a Python
install.

## Version bump strategy

Patch +1 on every CI-success push to `main`:

```
0.1.0 → 0.1.1 → 0.1.2 → 0.1.3 → …
```

The `bump-version` job:

1. Reads the current `version = "X.Y.Z"` from `pyproject.toml`.
2. Increments `Z` by 1.
3. Commits the bump back to `main` as
   `chore: bump version to X.Y.<Z+1>` via the workflow's
   `GITHUB_TOKEN`.
4. Outputs the new SHA, which downstream jobs check out.

The bump commit's push **does not re-trigger CI** — GitHub's
rule that `GITHUB_TOKEN`-driven pushes can't start new workflow
runs naturally terminates the loop.

For a minor or major bump, edit `pyproject.toml` manually in a
PR (`0.1.5 → 0.2.0`); the bump-version job sees that the version
changed but its patch logic still adds `+1` to the patch, so a
manual `0.2.0` becomes `0.2.1` on the next CI success. Plan
accordingly.

## Opting out of a release: `[skip release]`

Include `[skip release]` anywhere in a commit message and the
auto-bump + every downstream job are gated off:

```bash
git commit -m "Tweak docs typo [skip release]"
git push
```

Use this for:

- Docs / typo / comment-only changes.
- Refactors that don't change behaviour.
- Test-only changes that don't gate functionality.
- Anything where the version number would just be noise.

CI still runs (it always runs on push to any branch). Only the
release pipeline is skipped.

## Loop prevention

Two layers of belt + suspenders:

1. **GitHub's native rule**: pushes via `GITHUB_TOKEN` don't
   trigger workflows. So the bump commit's push doesn't fire CI,
   doesn't fire `workflow_run`, and the release pipeline can't
   re-enter.
2. **Defensive check**: `bump-version` calls `git log -1 --pretty=%B`
   and skips if the previous commit message starts with
   `chore: bump version to`. Survives even if GitHub's rule
   changes.

## Why `--standalone` not `--onefile`

The Nuitka build uses `--standalone` (produces a
`thesisagents.dist/` folder, which we zip) rather than
`--onefile` (single self-extracting `.exe`).

Reasons:

| Concern | `--onefile` | `--standalone` |
|---|---|---|
| Startup latency | Self-extracts to `%TEMP%` on every launch (~1-3 s) | Runs in place, no extraction (sub-second) |
| Antivirus | Self-extracting binary often flagged | Folder + .exe, treated normally |
| Locked-down corporate machines | `%TEMP%` write or exec sometimes blocked | No `%TEMP%` write needed |
| Distribution | Just the .exe | A .zip the user unzips once |
| Update mechanism | Replace the whole .exe | Replace the folder (rsync-friendly) |

The zip pattern is the standard for Qt apps on Windows (Krita,
OBS, KeePass all ship this way).

## Two executables: windowed app and console CLI

The zip holds the same build twice. `thesisagents.exe` is a windowed
program, so opening the desktop app shows no console window.
`thesisagents-cli.exe` is the console program for a terminal. Up to
v0.1.26 there was one console executable, and Windows opened a black
console window, filled with Qt and log lines, behind the app.

Windows decides from one field of the executable's header (the PE
subsystem) whether a program gets a console, and a program that has to
serve a terminal cannot also be windowed. `scripts/split_windows_exe.py`
runs after the Nuitka build: it copies the executable and changes that
field in the copy a user opens. Nuitka's own `--windows-console-mode`
was tried and not used:

| Mode | Why not |
|---|---|
| `disable` | One executable, and the CLI prints nothing. |
| `attach` | PowerShell gets no exit code and no captured output. Without a console the standard input handle is invalid, so `subprocess.run(capture_output=True)` raises `OSError`. Selenium Manager is run that way, so Chrome could not start. |
| `hide` | Still a console program: Windows creates the window and the program then hides it. |
| Two builds | The mode is a compiler define, so the second build finds nothing in the compiler cache and adds about an hour. |

The second executable adds about 41 MB to the zip and 123 MB unzipped
(measured on the v0.1.26 executable). When CLI flags are typed after
`thesisagents.exe`, `thesisagents/utils/windows_console.py` prints into
that terminal, but the shell does not wait for a windowed program.

## Why Windows only

Linux + macOS users install from PyPI. Shipping Nuitka binaries
for those platforms just inflates the release page without
serving a real use case — `pip install thesisagents` is already
the one-command install path. Windows is the only platform where
"download and double-click" is the common install pattern.

## Build timings

| Stage | Cold (no cache) | Warm (cache hit) |
|---|---|---|
| `bump-version` | ~5 s | ~5 s |
| `publish-pypi` | ~3-5 min | ~3-5 min |
| `create-draft-release` | ~10 s | ~10 s |
| `build-nuitka` | **~80-100 min** with 2 jobs, 4 jobs not yet measured | ~5-10 min (expected) |
| `publish-release` | ~5 s | ~5 s |
| Total | ~85-105 min | ~10-15 min (expected) |

The Nuitka cold build dominates because it compiles one C file per
Python module in the bundle, the standard library included: 4,191 C
files in the 2026-11-19 release (`Compiled 4191 C files using clcache`
in the job log). About 2,200 of them, roughly half, come from the
`anthropic` SDK, which keeps every API type in a module of its own
(counted 2026-11-20: 2,228 modules, against 141 for `thesisagents` and
38 for PySide6, whose Qt libraries arrive prebuilt). The releases of 2026-09-23 to 2026-09-25 spent 82-88 min
on the compile and those of 2026-10-08 and 2026-10-11 97-100 min.

The compile runs with `--jobs=4`, one job per core of the Windows
runner, and runs again with `--jobs=2` if that fails. Two jobs was
the setting from 2026-05-17, when `module.uvicorn._types.c` ran out
of MSVC heap under parallel compilation. uvicorn has been left out of
the build since then, so four jobs are expected to fit, and the
retry keeps a heap failure from losing the release.

Nuitka keeps a compiler cache (clcache with MSVC) under
`NUITKA_CACHE_DIR`, and the workflow saves that directory with
`actions/cache`, so a later build should only recompile the files
that changed. The warm figures are what the cache is expected to
give. Before 2026-09-25 the workflow cached directories Nuitka does
not use on Windows. The 2026-10-11 release restored the cache saved
three days earlier and still compiled for 100 min, so the cache gave
few hits, and no warm build has been measured yet (see `progress.md`
#5).

The timeout cap is 180 min, which leaves room for a failed 4-job
try followed by a full 2-job compile. A cold build still happens
whenever the cache is missing, for example after a quiet week: GitHub
evicts a cache that has not been used for 7 days.

## Dependencies of the CI test job

The `test` job of `ci.yml` installs every package from one hash-locked
file, then the project itself without its dependencies:

```
python -m pip install --require-hashes --only-binary :all: -r .github/requirements/ci.txt
python -m pip install --no-deps --no-build-isolation -e .
```

- `.github/requirements/ci.txt` pins the runtime dependencies, the
  `dev` extra of `pyproject.toml` and the build backend (`setuptools`,
  `wheel`, named in `ci.in`) to exact versions with the SHA-256 hash of
  every wheel. A new or compromised release on PyPI reaches CI only
  through a Dependabot PR on `dev` that updates the file, after its
  7-day wait.
- It is generated with `uv pip compile ... --universal`, so one file
  serves every cell of the matrix (Linux and Windows, Python 3.12 to
  3.14), with environment markers for the platform-only packages. The
  command is in the header of `ci.in` and `ci.txt`.
- A requirement added to `pyproject.toml`, or a floor raised there,
  needs `ci.txt` regenerated in the same change.
  `tests/test_workflow_actions.py` fails when a requirement is missing
  from the lock or locked outside its range, when the job runs any
  other `pip install`, or when the lock is not universal.
- The pip cache of the job is keyed on `ci.txt` alone. Keyed on
  `pyproject.toml`, every release's version bump saved six new
  entries of about 400 MB per branch, and by 2026-11-20 they filled
  the repository's 10 GB cache store and evicted the Nuitka compiler
  cache within hours. The Nuitka job keeps no pip cache for the same
  reason, and `publish-pypi` keys its cache on `publish.txt`.
- Every ref restores the pip cache, but only a run on `main` saves it
  (`actions/cache/restore` and `actions/cache/save` in place of
  setup-python's `cache: pip`). A run can read the caches of its own
  ref and of `main`, never a sibling branch's, so with `cache: pip`
  `dev`, each PR merge ref and each Dependabot branch saved a full set
  of six entries of about 450 MB. On 2026-11-21 the store held
  17.3 GB, and the Nuitka cache had only 2 GB of less recently used
  caches ahead of it. Check the store with
  `gh api repos/Jeffrey-Automations/ThesisAgent/actions/cache/usage`
  and `gh cache list -L 100`.

## Build tooling of `publish-pypi`

`publish-pypi` is the only job that receives `PYPI_API_TOKEN`, so
whatever it installs runs next to that token. It installs one file and
nothing else (no pip upgrade, no second install):

```
python -m pip install --require-hashes --only-binary :all: -r .github/requirements/publish.txt
```

- `.github/requirements/publish.in` names the tools the job runs,
  `build` and `twine`, and the build backend, `setuptools` and
  `wheel`: every package in `[build-system] requires` of
  `pyproject.toml`.
- `.github/requirements/publish.txt` is generated from it with
  `uv pip compile` and pins those four and their dependencies to exact
  versions with the SHA-256 hash of every wheel, resolved for the
  job's Python (3.12) and runner (Linux x86_64). pip refuses a file
  whose hash is not listed, and `--only-binary :all:` refuses a
  source distribution, which would run its own build script.
- The command that regenerates the lock is in the header of both
  files. Dependabot proposes updates to it on `dev`, after its 7-day
  wait.
- A tool the job starts using has to be added to `publish.in` and
  locked first. `tests/test_workflow_actions.py` fails when the job
  runs any other `pip install`, or runs a tool `publish.in` does not
  name.

The job builds with `python -m build --no-isolation`. A plain
`python -m build` creates an isolated environment and downloads the
newest build backend into it without hashes, outside the lock. With
`--no-isolation` the build imports the locked `setuptools` and `wheel`
from the job's own environment, and nothing is downloaded at build
time.

`--no-isolation` does not install `[build-system] requires`, it checks
that the environment already satisfies each entry and stops with
"Unmet dependencies" when one does not. So the lock has to keep up
with `pyproject.toml`:

- Raising a floor there (for example `setuptools>=77` to a version
  above the locked one) or adding a build requirement needs
  `publish.in` updated and `publish.txt` regenerated in the same
  change.
- `tests/test_workflow_actions.py` fails when a `python -m build` in
  the job lacks `--no-isolation`, when `publish.in` does not name
  exactly the job's tools plus the `[build-system] requires` packages,
  or when a locked version does not satisfy the specifier written in
  `pyproject.toml`. The mismatch shows up in CI on `dev`, not in the
  release.

`build-nuitka` does not receive the PyPI token and installs its
dependencies unpinned.

## Repo settings the pipeline needs

Configure once after forking / first deploy:

1. **`Settings → Actions → General → Workflow permissions`** →
   "Read and write permissions". The `bump-version` job pushes
   the version commit via `GITHUB_TOKEN`; default `read-only`
   permissions would block it.

2. **`Settings → Secrets and variables → Actions → New repository
   secret`** → `PYPI_API_TOKEN`. Generate a project-scoped token
   at <https://pypi.org/manage/account/token/>.

3. No GitHub Environment is needed. The `publish-pypi` job
   intentionally does NOT attach `environment: pypi` — that would
   make GitHub treat the run as a Deployment and surface a
   "Deployments" sidebar widget, which is noise alongside the
   real Release entry.

## Recovering from a failed release

The pipeline is stage-fail-fast. If `build-nuitka` times out
after `publish-pypi` succeeded:

- **PyPI** has the new version. It cannot be re-published with
  the same version number (PyPI is immutable).
- **GitHub** has a draft release at `v<version>`. It can be
  deleted: `gh release delete v0.1.X --yes`.
- **`pyproject.toml`** on `main` has the new version. The next
  push to `main` will bump to the next patch.

So a failed release just "skips" a version number — the gap
(`v0.1.1` skipped between `v0.1.0` and `v0.1.2`) is cosmetic.
Don't try to recycle the PyPI version; bump to the next number
and try again.

## Branch protection (recommended)

Optional but recommended for shared forks:

- Require PR review before merging to `main`.
- Require CI to pass before merging.
- Require linear history (rebases) for cleaner version-bump
  commits.

The `bump-version` push uses the GitHub Actions bot identity, so
branch protections that require a CODEOWNER review will block
the bump. Add an exception for the GitHub Actions bot or use a
"Restrict who can push" rule that allows the bot.

## Watching a release in progress

```bash
gh run watch                              # latest run, any workflow
gh run list --workflow=release.yml -L 5   # last 5 release runs
gh run view <run-id> --log                # all logs
gh run view <run-id> --log-failed         # only failed-step logs
```

The pipeline's stages are linear — if `bump-version` runs but
`publish-pypi` is skipped, look at the `bump-version` outputs;
that's usually a `[skip release]` tag triggering the skip path.
