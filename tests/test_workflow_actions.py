"""Every GitHub Actions step pins its action to a commit SHA.

A tag such as ``@v4`` can be moved to new code at any time (the 2025
tj-actions/changed-files compromise rewrote tags), so each ``uses:`` names a
full 40-hex commit and carries the release it corresponds to as a comment,
which is what Dependabot reads and updates. Pinning also keeps Node 20 actions
from lingering unnoticed: GitHub removed Node 20 from its runners on 2026-09-23.

The rest of the workflow supply chain is guarded here too: Dependabot's
settings, checkout credentials, job timeouts, the Nuitka cache, and the
hash-locked tooling and build backend of the job that holds the PyPI token,
and the hash-locked dependencies the CI test job installs.
"""
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

import pytest
from packaging.requirements import Requirement  # pytest itself depends on packaging

_ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".github" / "workflows").is_dir())
_WORKFLOWS = sorted((_ROOT / ".github" / "workflows").glob("*.yml"))
_USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)(.*)$")
_PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
_LOCAL = re.compile(r"^\./")
#: The version comment, optionally followed by a SonarCloud suppression with
#: its reason (``# v7.0.1  NOSONAR sha is this repo's own commit``): Sonar
#: only honours NOSONAR on the flagged line, which is the ``uses:`` line.
_VERSION_COMMENT = re.compile(r"^\s+#\s*v\d+(\.\d+)*(\s+NOSONAR\s+\S.*)?\s*$")


def _uses(path: Path) -> list[tuple[int, str, str]]:
    """Return ``(line number, action reference, rest of line)`` for each remote ``uses:``."""
    found = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = _USES.match(line)
        if match and not _LOCAL.match(match.group(1)):
            found.append((number, match.group(1), match.group(2)))
    return found


def test_workflows_exist():
    assert _WORKFLOWS


@pytest.mark.parametrize("workflow", _WORKFLOWS, ids=lambda p: p.name)
def test_every_action_is_pinned_to_a_commit_with_its_version(workflow):
    bad = [f"{workflow.name}:{number} {ref}{rest}"
           for number, ref, rest in _uses(workflow)
           if not (_PINNED.match(ref) and _VERSION_COMMENT.match(rest))]
    assert bad == []


def test_one_version_per_action():
    # The same action at two different commits means a partial upgrade.
    seen: dict[str, set[str]] = {}
    for workflow in _WORKFLOWS:
        for _number, ref, _rest in _uses(workflow):
            action, _, sha = ref.partition("@")
            seen.setdefault(action, set()).add(sha)
    assert {action: shas for action, shas in seen.items() if len(shas) > 1} == {}


def test_dependabot_keeps_pins_current_on_dev():
    # Pinned SHAs only stay current if something bumps them; every update
    # goes to dev because main is the release branch. Parsed as text: PyYAML
    # is not a test dependency.
    text = (_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    blocks = re.split(r"^\s*-\s*package-ecosystem:", text, flags=re.MULTILINE)[1:]
    ecosystems = {block.split()[0].strip("\"'") for block in blocks}
    assert {"pip", "github-actions"} <= ecosystems
    assert all(re.search(r"^\s*target-branch:\s*\"dev\"", block, re.MULTILINE)
               for block in blocks)


def test_dependabot_waits_a_week_before_proposing_a_release():
    # A compromised release is usually found and yanked within days. Dependabot's
    # own default wait is 3 days, and zizmor's dependabot-cooldown audit asks
    # for 7. The wait never delays security updates.
    text = (_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    blocks = re.split(r"^\s*-\s*package-ecosystem:", text, flags=re.MULTILINE)[1:]
    days = [re.search(r"^\s*default-days:\s*(\d+)", block, re.MULTILINE) for block in blocks]
    assert blocks
    assert all(match and int(match.group(1)) >= 7 for match in days)


def test_dependabot_watches_the_hash_locked_requirements():
    # From "/" Dependabot does not reach .github/requirements, so the directory
    # has to be named or publish.txt is never updated. Comment lines are dropped
    # first: a path quoted in a comment configures nothing.
    text = (_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    blocks = re.split(r"^\s*-\s*package-ecosystem:", text, flags=re.MULTILINE)[1:]
    pip = next(block for block in blocks if block.split()[0].strip("\"'") == "pip")
    settings = "\n".join(line for line in pip.splitlines() if not line.lstrip().startswith("#"))
    assert re.search(r"^\s*directories:", settings, re.MULTILINE)
    assert set(re.findall(r"\"(/[^\"]*)\"", settings)) == {"/", "/.github/requirements"}


def test_release_runs_only_for_pushes_to_this_repository():
    # workflow_run's `branches:` filter compares the head branch *name*, so
    # a pull request from a fork's `main` also completes CI "on main". The
    # release job must additionally require a push to this repository.
    text = (_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "github.event.workflow_run.event == 'push'" in text
    assert "github.event.workflow_run.head_repository.full_name == github.repository" in text


def _steps_using(text: str, action: str) -> list[tuple[int, str]]:
    """Return ``(line number, step text)`` for each step that uses ``action``.

    A step runs from its ``uses:`` line to the next line indented less than
    ``uses:`` or starting another list item, e.g.
    ``_steps_using(text, "actions/checkout")``.
    """
    lines = text.splitlines()
    steps = []
    for index, line in enumerate(lines):
        if not re.search(rf"uses:\s*{re.escape(action)}@", line):
            continue
        column = line.index("uses:")
        body = [line]
        for following in lines[index + 1:]:
            indent = len(following) - len(following.lstrip())
            if following.strip() and (indent < column or following.lstrip().startswith("- ")):
                break
            body.append(following)
        steps.append((index + 1, "\n".join(body)))
    return steps


def _checkout_steps(path: Path) -> list[tuple[int, str]]:
    """Return ``(line number, step text)`` for each ``actions/checkout`` step."""
    return _steps_using(path.read_text(encoding="utf-8"), "actions/checkout")


@pytest.mark.parametrize("workflow", _WORKFLOWS, ids=lambda p: p.name)
def test_every_checkout_decides_on_persisted_credentials(workflow):
    # actions/checkout leaves the job token in .git/config unless told not
    # to, where every later step (and any uploaded workspace) can read it.
    # Only jobs that push keep it, and they say so.
    bad = [f"{workflow.name}:{number}" for number, step in _checkout_steps(workflow)
           if not re.search(r"^\s*persist-credentials:\s*(true|false)\b", step, re.MULTILINE)]
    assert bad == []


def test_nuitka_cache_step_saves_the_directory_nuitka_uses():
    # Nuitka's compiler cache lives under NUITKA_CACHE_DIR. The release
    # cached ~/.nuitka and ~/.cache/Nuitka instead, which Nuitka does not
    # use on Windows, so every release compiled every C file cold
    # ("0 cache hits") and ran within minutes of its 90 min cap.
    text = (_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    env = re.search(r"^\s*NUITKA_CACHE_DIR:\s*(\S+)\s*$", text, re.MULTILINE)
    assert env, "release.yml must set NUITKA_CACHE_DIR for the Nuitka build"
    cache_step = next(step for _number, step in _steps_using(text, "actions/cache")
                      if "nuitka-" in step)
    assert re.search(rf"^\s*path:\s*{re.escape(env.group(1))}\s*$", cache_step, re.MULTILINE)


def test_release_splits_the_executable_before_testing_and_zipping_it():
    # Built as one console program, thesisagents.exe opened a console window
    # behind the desktop app. The split must precede the smoke test, which
    # runs both programs, and the zip, which ships them.
    text = (_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    split = text.index("python scripts/split_windows_exe.py thesisagents.dist/thesisagents.exe")
    console_test = text.index("./thesisagents.dist/thesisagents-cli.exe --help")
    windowed_test = text.index("./thesisagents.dist/thesisagents.exe --help")
    assert text.index("nuitka_build --jobs=2") < split < console_test < windowed_test
    assert windowed_test < text.index("Compress-Archive -Path")
    assert "--windows-console-mode=" not in text
    assert "--disable-console" not in text


_JOB_HEAD = re.compile(r"^  [A-Za-z0-9_-]+:\s*(#.*)?$")


def _jobs(path: Path) -> list[tuple[str, str]]:
    """Return ``(job id, job text)`` for each job under ``jobs:`` in a workflow."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if re.match(r"^jobs:\s*(#.*)?$", line))
    heads = [i for i in range(start + 1, len(lines)) if _JOB_HEAD.match(lines[i])]
    ends = [*heads[1:], len(lines)]
    pairs = zip(heads, ends, strict=True)
    return [(lines[i].strip().rstrip(":"), "\n".join(lines[i:end])) for i, end in pairs]


@pytest.mark.parametrize("workflow", _WORKFLOWS, ids=lambda p: p.name)
def test_every_job_has_a_timeout(workflow):
    # Without timeout-minutes a hung job runs for GitHub's default six hours.
    # Each job sets about three times its slowest recent run, at least 15 minutes.
    bad = [name for name, body in _jobs(workflow)
           if "runs-on:" in body and not re.search(r"^\s*timeout-minutes:", body, re.MULTILINE)]
    assert bad == []


_REQUIREMENTS = _ROOT / ".github" / "requirements"
_LOCKED_INSTALL = ("python -m pip install --require-hashes --only-binary :all: "
                   "-r .github/requirements/publish.txt")
_PIP_INSTALL = re.compile(r"(?:python3? -m )?\bpip3? install\b.*")
_RUN_OR_IMPORT = re.compile(r"python3? -m ([A-Za-z_]\w*)|^\s*import ([A-Za-z_]\w*)", re.MULTILINE)


def _publish_jobs() -> list[tuple[str, str]]:
    """Return ``(workflow:job, job text less comments)`` for each job that reads the PyPI token.

    These are the jobs whose installs run next to ``secrets.PYPI_API_TOKEN``, e.g.
    ``[("release.yml:publish-pypi", "publish-pypi:\\n    name: ...")]``. Comment lines are
    dropped so a command quoted in a comment is neither counted as an install nor as a tool.
    """
    found = []
    for workflow in _WORKFLOWS:
        for name, body in _jobs(workflow):
            if "secrets.PYPI_API_TOKEN" in body:
                code = [line for line in body.splitlines() if not line.lstrip().startswith("#")]
                found.append((f"{workflow.name}:{name}", "\n".join(code)))
    return found


_PUBLISH_JOBS = _publish_jobs()
_PUBLISH_IDS = [name for name, _body in _PUBLISH_JOBS]
_PUBLISH_BODIES = [body for _name, body in _PUBLISH_JOBS]


def _distribution(name: str) -> str:
    """Return a module or requirement name the way PyPI spells a distribution.

    Lets a module a job runs be compared with a requirement line, e.g.
    ``_distribution("Pyproject_Hooks") == "pyproject-hooks"``.
    """
    return name.lower().replace("_", "-")


def _tools(body: str) -> set[str]:
    """Return what a job runs with ``python -m`` or imports inline, less pip and the stdlib.

    This is the set that has to be locked before the job can use it, e.g. a job that runs
    ``python -m build`` and ``python -m twine upload`` gives ``{"build", "twine"}``.
    """
    named = {module or imported for module, imported in _RUN_OR_IMPORT.findall(body)}
    return {_distribution(name) for name in named - {"pip"} - set(sys.stdlib_module_names)}


def _requirements(name: str) -> set[str]:
    """Return the distributions a file in ``.github/requirements`` names at the start of a line.

    Reads ``publish.in`` (the tools and build backend asked for) or ``publish.txt`` (every
    pin), e.g. ``_requirements("publish.in") == {"build", "twine", "setuptools", "wheel"}``.
    Comments, hashes and ``# via`` lines start with ``#`` or a space and are not matched.
    """
    text = (_REQUIREMENTS / name).read_text(encoding="utf-8")
    found = re.findall(r"^([A-Za-z0-9][\w.-]*)", text, re.MULTILINE)
    return {_distribution(requirement) for requirement in found}


def _build_requires() -> list[Requirement]:
    """Return ``[build-system] requires`` of ``pyproject.toml``, the metadata the job builds from.

    ``python -m build --no-isolation`` does not install these: it checks that the job's
    environment already satisfies each one and stops when it does not. For
    ``requires = ["setuptools>=77", "wheel"]`` the names are ``["setuptools", "wheel"]`` and
    the first specifier accepts ``84.0.0``.
    """
    metadata = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return [Requirement(entry) for entry in metadata["build-system"]["requires"]]


def _locked_versions() -> dict[str, str]:
    """Return ``{distribution: version}`` for every pin in ``publish.txt``.

    This is what the publish job has installed when it builds, e.g.
    ``_locked_versions()["setuptools"] == "84.0.0"``.
    """
    text = (_REQUIREMENTS / "publish.txt").read_text(encoding="utf-8")
    pins = re.findall(r"^([A-Za-z0-9][\w.-]*)==(\S+)", text, re.MULTILINE)
    return {_distribution(name): version for name, version in pins}


def test_the_job_that_holds_the_pypi_token_is_publish_pypi():
    # A second job that reads the token must be listed here on purpose, which
    # puts its installs under the tests below.
    assert _PUBLISH_IDS == ["release.yml:publish-pypi"]


@pytest.mark.parametrize("body", _PUBLISH_BODIES, ids=_PUBLISH_IDS)
def test_publish_job_installs_only_the_hash_locked_tooling(body):
    # Whatever this job installs runs next to the PyPI token. An unpinned
    # "pip install build twine", or upgrading pip first, takes the newest upload
    # of that day. The lock allows only wheels whose hashes were recorded.
    assert [command.strip() for command in _PIP_INSTALL.findall(body)] == [_LOCKED_INSTALL]


def test_publish_in_lists_exactly_the_tools_the_job_runs_and_the_build_backend():
    # A tool the job starts using has to be locked first, or the release fails at that step.
    # The build backend is never run by name: `python -m build --no-isolation` imports it
    # from the job's environment, so it is locked beside the tools.
    used = set().union(*(_tools(body) for body in _PUBLISH_BODIES))
    backend = {_distribution(requirement.name) for requirement in _build_requires()}
    assert backend
    assert used | backend == _requirements("publish.in")


@pytest.mark.parametrize("body", _PUBLISH_BODIES, ids=_PUBLISH_IDS)
def test_publish_job_builds_without_an_isolated_environment(body):
    # A plain `python -m build` creates an isolated environment and downloads the newest
    # build backend into it, outside the lock, in the job that uploads with the token.
    builds = re.findall(r"\bpython3? -m build\b[^\n]*", body)
    assert builds
    assert [command for command in builds if "--no-isolation" not in command.split()] == []


def test_the_locked_build_backend_satisfies_build_system_requires():
    # --no-isolation checks [build-system] requires instead of installing it. A floor raised
    # in pyproject.toml without regenerating the lock (Dependabot edits both files) has to
    # fail here and not in the publish job.
    locked = _locked_versions()
    unmet = [str(requirement) for requirement in _build_requires()
             if _distribution(requirement.name) not in locked
             or not requirement.specifier.contains(locked[_distribution(requirement.name)])]
    assert unmet == []


def test_publish_lock_pins_every_tool_of_publish_in():
    # publish.txt is generated. Editing publish.in alone changes nothing the job installs.
    assert _requirements("publish.in") <= _requirements("publish.txt")


def test_publish_lock_is_resolved_for_the_python_and_runner_of_the_job():
    # The lock holds the wheels of one Python version on one platform. A job on
    # another version or operating system may find no wheel whose hash is listed.
    header = (_REQUIREMENTS / "publish.txt").read_text(encoding="utf-8").splitlines()[1]
    locked_python = re.search(r"--python-version (\S+)", header).group(1)
    locked_platform = re.search(r"--python-platform (\S+)", header).group(1)
    set_up = {version for body in _PUBLISH_BODIES
              for version in re.findall(r"python-version:\s*\"([^\"]+)\"", body)}
    runners = {runner for body in _PUBLISH_BODIES
               for runner in re.findall(r"^\s*runs-on:\s*(\S+)", body, re.MULTILINE)}
    assert set_up == {locked_python}
    assert locked_platform.startswith("x86_64-manylinux")
    assert runners == {"ubuntu-latest"}


_CI_LOCK = "ci.txt"
_CI_INSTALLS = [
    "python -m pip install --require-hashes --only-binary :all: -r .github/requirements/ci.txt",
    "python -m pip install --no-deps --no-build-isolation -e .",
]


def _ci_test_job() -> str:
    """Return the ``test`` job of ``ci.yml`` with comment lines dropped.

    A command quoted in a comment is not an install, e.g. the result holds
    ``pip install --require-hashes ...`` once, from the run block.
    """
    body = dict(_jobs(_ROOT / ".github" / "workflows" / "ci.yml"))["test"]
    return "\n".join(line for line in body.splitlines() if not line.lstrip().startswith("#"))


def _ci_locked_versions() -> dict[str, str]:
    """Return ``{distribution: version}`` for every pin in ``ci.txt``.

    A pin that differs by platform carries an environment marker after the
    version, which is not part of it, e.g. ``_ci_locked_versions()["pywin32"]``
    is ``"312"`` from ``pywin32==312 ; sys_platform == 'win32'``.
    """
    text = (_REQUIREMENTS / _CI_LOCK).read_text(encoding="utf-8")
    pins = re.findall(r"^([A-Za-z0-9][\w.-]*)==([^\s;]+)", text, re.MULTILINE)
    return {_distribution(name): version for name, version in pins}


def _project_requirements() -> list[Requirement]:
    """Return what CI tests the project with: ``[project] dependencies`` and the ``dev`` extra.

    Each has to be pinned in ``ci.txt`` at a version its specifier accepts,
    e.g. ``httpx>=0.27`` is met by a locked ``httpx==0.28.1``.
    """
    project = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    entries = [*project["dependencies"], *project["optional-dependencies"]["dev"]]
    return [Requirement(entry) for entry in entries]


def test_ci_installs_only_the_hash_locked_dependencies():
    # An unpinned `pip install -e ".[dev]"` takes the newest upload of that day
    # into CI, the supply-chain risk SonarCloud text:S8565 names. The project
    # itself comes in with --no-deps, so nothing unlocked rides along, and
    # --no-build-isolation, so the locked setuptools builds it.
    installs = [command.strip() for command in _PIP_INSTALL.findall(_ci_test_job())]
    installs = [command.split("  #")[0].strip() for command in installs]
    assert installs == _CI_INSTALLS


def test_ci_lock_pins_every_project_and_dev_requirement_within_its_range():
    # ci.txt is generated from pyproject.toml. A requirement added or a floor
    # raised there without regenerating the lock has to fail here, on dev,
    # not as a missing import in the middle of the test run.
    locked = _ci_locked_versions()
    unmet = [str(requirement) for requirement in _project_requirements()
             if _distribution(requirement.name) not in locked
             or not requirement.specifier.contains(locked[_distribution(requirement.name)])]
    assert unmet == []


def test_ci_lock_holds_a_build_backend_that_satisfies_build_system_requires():
    # --no-build-isolation checks [build-system] requires instead of installing it.
    locked = _ci_locked_versions()
    backend = _build_requires()
    assert {_distribution(requirement.name) for requirement in backend} <= _requirements("ci.in")
    unmet = [str(requirement) for requirement in backend
             if _distribution(requirement.name) not in locked
             or not requirement.specifier.contains(locked[_distribution(requirement.name)])]
    assert unmet == []


def test_ci_lock_is_one_universal_file_for_the_whole_matrix():
    # The test job runs on Linux and Windows and on every supported Python. A
    # lock resolved for one of them can miss a platform-only package (pywin32,
    # colorama) or a wheel another cell needs. --universal resolves for all of
    # them, with environment markers where they differ.
    header = (_REQUIREMENTS / _CI_LOCK).read_text(encoding="utf-8").splitlines()[1]
    assert "--universal" in header.split()
    assert "--generate-hashes" in header.split()
    floor = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    minimum = floor["project"]["requires-python"].removeprefix(">=")
    assert re.search(r"--python-version (\S+)", header).group(1) == minimum


def _ci_step(action: str) -> str:
    """Return the one step of the CI ``test`` job that uses ``action``, from its ``uses:`` line.

    E.g. ``_ci_step("actions/cache/save")`` starts with
    ``uses: actions/cache/save@<sha>`` and holds that step's ``if:`` and ``with:``.
    """
    steps = _steps_using(_ci_test_job(), action)
    assert len(steps) == 1, f"the CI test job should use {action} exactly once"
    return steps[0][1]


def test_ci_pip_cache_is_saved_only_from_main():
    # A run reads caches of its own ref and of main, never a sibling
    # branch's. setup-python's `cache: pip` saved a full ~450 MB set of six
    # on dev, every PR merge ref and every Dependabot branch: 17.3 GB on
    # 2026-11-21 against the 10 GB store, with the 54 MB Nuitka cache next
    # in line for eviction. main's set alone serves every ref.
    setup = _ci_step("actions/setup-python")
    assert not re.search(r"^\s*cache:", setup, re.MULTILINE)
    restore = _ci_step("actions/cache/restore")
    assert "hashFiles('.github/requirements/ci.txt')" in restore
    assert "pyproject.toml" not in restore
    save = _ci_step("actions/cache/save")
    condition = re.search(r"^\s*if:\s*(.+)$", save, re.MULTILINE)
    assert condition, "the save step needs an if: that limits it to main"
    assert "github.ref == 'refs/heads/main'" in condition.group(1)
    assert "||" not in condition.group(1)
    assert re.search(r"^\s*key:\s*\$\{\{\s*steps\.pip-cache\.outputs\.cache-primary-key\s*\}\}\s*$",
                     save, re.MULTILINE)
    path = re.compile(r"^\s*path:\s*(.+?)\s*$", re.MULTILINE)
    assert path.search(save).group(1) == path.search(restore).group(1)


def test_no_ci_job_caches_pip_on_every_ref():
    # The same eviction applies to any job ci.yml gains later, since ci.yml
    # runs on every branch. release.yml is not checked: its jobs run on main
    # alone, so setup-python's own cache saves only main's copy there.
    text = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert not re.search(r"^\s*cache:\s*pip\b", text, re.MULTILINE)


def test_every_ci_pin_carries_a_hash():
    # --require-hashes refuses the whole install when one pin has no hash, so a
    # hand edit that drops one would break every CI run, caught here first.
    text = (_REQUIREMENTS / _CI_LOCK).read_text(encoding="utf-8")
    blocks = re.split(r"\n(?=[A-Za-z0-9])", text)
    pins = [block for block in blocks if re.match(r"[A-Za-z0-9][\w.-]*==", block)]
    assert pins
    assert [block.split()[0] for block in pins if "--hash=sha256:" not in block] == []
