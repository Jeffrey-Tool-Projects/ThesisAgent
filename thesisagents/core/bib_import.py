"""Read BibTeX and RIS files into papers, to take over an existing library.

Zotero, Mendeley, EndNote and JabRef export both. The parser here is small
on purpose: ``bibtexparser`` 1 and 2 have different APIs and a user may have
either, and what is needed is only the fields a ``Paper`` has. A record it
cannot use is skipped and reported, it never stops the others.

Example::

    result = read_bibliography(Path("zotero.bib"))
    library.add_papers(result.papers, kind="import")
    result.skipped      # ("line 40: no title", ...)
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from thesisagents.core.exceptions import ThesisAgentsError
from thesisagents.core.models import Paper

SOURCE_BIBTEX: Final[str] = "bibtex"
SOURCE_RIS: Final[str] = "ris"
#: Larger files are refused. 20,000 records with abstracts fit.
MAX_FILE_BYTES: Final[int] = 50_000_000

_YEAR = re.compile(r"\b(1[5-9]\d{2}|20\d{2}|21\d{2})\b")
_ARXIV = re.compile(
    r"(?:arxiv[:./ ]|abs/|pdf/)\s*(\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+(?:\.[A-Z]{2})?/\d{7})", re.I
)
_DOI = re.compile(r"10\.\d{4,9}/\S+")


@dataclass(frozen=True, slots=True)
class ImportedBibliography:
    """The papers of a file, and why each other record was left out."""

    papers: tuple[Paper, ...]
    skipped: tuple[str, ...]


def read_bibliography(path: str | Path) -> ImportedBibliography:
    """Read a ``.bib`` or ``.ris`` file, told apart by its content.

    Raises ``ThesisAgentsError`` when it cannot be read or holds neither.
    """
    file = Path(path)
    try:
        if file.stat().st_size > MAX_FILE_BYTES:
            raise ThesisAgentsError(f"{file} is larger than {MAX_FILE_BYTES:,} bytes")
        data = file.read_bytes()
    except OSError as err:
        raise ThesisAgentsError(f"cannot read {file}: {err}") from err
    text = _decode(data)
    if re.search(r"(?m)^\s*TY {1,2}-", text):
        return parse_ris(text)
    if re.search(r"(?m)^\s*@\s*\w+\s*[{(]", text):
        return parse_bibtex(text)
    raise ThesisAgentsError(f"{file} holds no BibTeX or RIS record")


def _decode(data: bytes) -> str:
    """UTF-8 (with or without BOM), UTF-16 with BOM, else Latin-1, which older tools write."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")


# --- BibTeX -------------------------------------------------------------------


@dataclass(slots=True)
class _Record:
    kind: str
    key: str
    fields: dict[str, str]
    line: int


def parse_bibtex(text: str) -> ImportedBibliography:
    """Papers of a BibTeX text. ``@string`` abbreviations are resolved."""
    papers: list[Paper] = []
    skipped: list[str] = []
    for record in _bibtex_records(text, skipped):
        if record.kind in {"comment", "preamble", "string"}:
            continue
        fields = {name: _plain(value) for name, value in record.fields.items()}
        paper = _bibtex_paper(record.key, fields, record.fields)
        if paper is None:
            skipped.append(f"line {record.line}: {record.key or record.kind} has no title")
        else:
            papers.append(paper)
    return ImportedBibliography(tuple(papers), tuple(skipped))


def _bibtex_paper(key: str, fields: dict[str, str], raw: dict[str, str]) -> Paper | None:
    title = fields.get("title", "")
    if not title:
        return None
    # Names are split before LaTeX is resolved: braces group a name that
    # contains "and".
    authors = tuple(
        _turn_name(_plain(name)) for name in _split_names(raw.get("author", raw.get("editor", "")))
    )
    doi = _doi_of(fields.get("doi", "") or fields.get("url", ""))
    venue = next(
        (fields[f] for f in ("journal", "journaltitle", "booktitle", "school", "institution",
                             "publisher") if fields.get(f)),
        None,
    )
    arxiv = _arxiv_of(
        *(
            [f"arxiv:{fields['eprint']}"]
            if fields.get("eprint")
            and fields.get("archiveprefix", fields.get("eprinttype", "arxiv")).lower() == "arxiv"
            else []
        ),
        fields.get("url", ""), fields.get("journal", ""), fields.get("note", ""),
    )
    return _paper(
        SOURCE_BIBTEX, key, title, authors, fields.get("year") or fields.get("date", ""),
        venue, fields.get("abstract", ""), fields.get("url", ""), doi, arxiv,
    )


def _bibtex_records(text: str, skipped: list[str]) -> Iterator[_Record]:
    """Every ``@type{…}`` of ``text``, abbreviations already replaced."""
    strings = {m: m for m in ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep",
                              "oct", "nov", "dec")}
    for match in re.finditer(r"@\s*(\w+)\s*([{(])", text):
        line = text.count("\n", 0, match.start()) + 1
        kind = match.group(1).lower()
        if kind in {"comment", "preamble"}:
            continue
        closer = "}" if match.group(2) == "{" else ")"
        end = _closing(text, match.end(), closer)
        if end < 0:
            skipped.append(f"line {line}: the record is not closed")
            continue
        body = text[match.end():end]
        if kind == "string":
            strings.update(_fields(body, strings))
            continue
        key, _comma, rest = body.partition(",")
        yield _Record(kind, key.strip(), _fields(rest, strings), line)


def _closing(text: str, start: int, closer: str) -> int:
    """Index of the bracket that closes a record opened just before ``start``, or -1.

    A new ``@type{`` at the beginning of a line means the record was never
    closed, so a broken one does not swallow the rest of the file.
    """
    depth = 0
    index = start
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "{":
            depth += 1
        elif char == closer and depth == 0:
            return index
        elif char == "}":
            depth -= 1
        elif char == "@" and text[:index].rstrip(" \t").endswith("\n") and re.match(
            r"@\s*\w+\s*\{[^{}=]*,", text[index:index + 200]
        ):
            return -1
        index += 1
    return -1


def _fields(body: str, strings: dict[str, str]) -> dict[str, str]:
    """``name = value`` pairs. A value is braced, quoted, a number, or an
    abbreviation, and ``#`` joins several."""
    fields: dict[str, str] = {}
    index = 0
    name_pattern = re.compile(r"[\s,]*([A-Za-z][\w:.+-]*)\s*=\s*")
    while match := name_pattern.match(body, index):
        index = match.end()
        parts: list[str] = []
        while True:
            part, index = _value(body, index, strings)
            parts.append(part)
            joined = re.compile(r"\s*#\s*").match(body, index)
            if not joined:
                break
            index = joined.end()
        fields.setdefault(match.group(1).lower(), "".join(parts))
        comma = body.find(",", index)
        if comma < 0:
            break
        index = comma
    return fields


def _value(body: str, index: int, strings: dict[str, str]) -> tuple[str, int]:
    if index < len(body) and body[index] in '{"':
        opener = body[index]
        depth, start = 0, index + 1
        index = start
        while index < len(body):
            char = body[index]
            if char == "\\":
                index += 2
                continue
            if char == '"' and opener == '"' and depth == 0:
                break
            if char == "{":
                depth += 1
            elif char == "}":
                if depth == 0:
                    break
                depth -= 1
            index += 1
        return body[start:index], index + 1
    match = re.compile(r"[^\s,#{}]*").match(body, index)
    word = match.group(0) if match else ""
    return strings.get(word.lower(), word), index + len(word)


def _split_names(text: str) -> list[str]:
    """Split at `` and `` outside braces."""
    names, depth, start = [], 0, 0
    for match in re.finditer(r"[{}]|\s+and\s+", text):
        mark = match.group(0)
        if mark == "{":
            depth += 1
        elif mark == "}":
            depth -= 1
        elif depth == 0:
            names.append(text[start:match.start()])
            start = match.end()
    names.append(text[start:])
    return [name.strip() for name in names if name.strip() and name.strip() != "others"]


def _turn_name(name: str) -> str:
    """``"Lovelace, Ada"`` as ``"Ada Lovelace"``, like the search sources write it."""
    family, comma, given = name.partition(",")
    if not comma:
        return name
    # "Family, Jr, Given" has the suffix in the middle.
    suffix, comma, rest = given.partition(",")
    if comma:
        return " ".join(f"{rest.strip()} {family.strip()} {suffix.strip()}".split())
    return " ".join(f"{given.strip()} {family.strip()}".split())


#: LaTeX accent commands and the combining character each stands for.
_ACCENTS: Final[dict[str, str]] = {
    "`": "\u0300", "'": "\u0301", "^": "\u0302", "~": "\u0303", "=": "\u0304", "u": "\u0306",
    ".": "\u0307", '"': "\u0308", "r": "\u030a", "H": "\u030b", "v": "\u030c", "c": "\u0327",
    "k": "\u0328", "d": "\u0323", "b": "\u0331",
}
_LETTERS: Final[dict[str, str]] = {
    "ss": "ß", "o": "ø", "O": "Ø", "l": "ł", "L": "Ł", "ae": "æ", "AE": "Æ", "oe": "œ",
    "OE": "Œ", "aa": "å", "AA": "Å", "i": "ı", "j": "ȷ", "dh": "ð", "DH": "Ð", "th": "þ",
    "TH": "Þ", "textendash": "–", "textemdash": "—", "textquoteright": "’", "ldots": "…",
    "textasciitilde": "~", "textbackslash": "\\",
}
_ACCENT = re.compile(
    r"""\\([`'^~=."])\s*(?:\{\s*(\\?[A-Za-z])\s*\}|(\\?[A-Za-z]))"""
    r"""|\\([uvHcdbkr])(?:\s*\{\s*(\\?[A-Za-z])\s*\}|\s+(\\?[A-Za-z]))"""
)
_COMMAND = re.compile(r"\\([A-Za-z]+)\s*(?:\{\})?")


def _plain(text: str) -> str:
    """LaTeX markup as plain text.

    >>> _plain(r"{\\'E}tude of {BERT} \\& G{\\"o}del")
    'Étude of BERT & Gödel'
    """
    def accent(match: re.Match[str]) -> str:
        mark = match.group(1) or match.group(4)
        letter = next(g for g in match.group(2, 3, 5, 6) if g)
        # A dotless i or j under an accent is the plain letter.
        return unicodedata.normalize("NFC", letter.lstrip("\\") + _ACCENTS[mark])

    text = _ACCENT.sub(accent, text)
    text = re.sub(r"\\([&%$#_{}])", r"\1", text)
    # Formatting commands vanish, their argument stays.
    text = _COMMAND.sub(lambda m: _LETTERS.get(m.group(1), ""), text)
    text = text.replace("---", "—").replace("--", "–").replace("~", " ")
    text = re.sub(r"(?<!\\)[{}]", "", text)
    return " ".join(text.split())


# --- RIS ------------------------------------------------------------------------

_RIS_LINE = re.compile(r"^\s*([A-Z][A-Z0-9]) {1,2}-(?: (.*))?$")


def parse_ris(text: str) -> ImportedBibliography:
    """Papers of a RIS text. A line without a tag continues the one before it."""
    papers: list[Paper] = []
    skipped: list[str] = []
    fields: dict[str, list[str]] = {}
    last, start = "", 0
    for number, line in enumerate([*text.splitlines(), "ER  - "], 1):
        match = _RIS_LINE.match(line)
        if match is None:
            if last and line.strip():
                fields[last][-1] = f"{fields[last][-1]} {line.strip()}".strip()
            continue
        tag, value = match.group(1), (match.group(2) or "").strip()
        if tag in {"TY", "ER"}:
            if fields:
                paper = _ris_paper(fields, start)
                if paper is None:
                    skipped.append(f"line {start}: the record has no title")
                else:
                    papers.append(paper)
            fields, last, start = {}, "", number
            continue
        fields.setdefault(tag, []).append(value)
        last = tag
    return ImportedBibliography(tuple(papers), tuple(skipped))


def _ris_paper(fields: dict[str, list[str]], line: int) -> Paper | None:
    def first(*tags: str) -> str:
        return next((v for tag in tags for v in fields.get(tag, ()) if v), "")

    title = first("TI", "T1", "CT")
    if not title:
        return None
    return _paper(
        SOURCE_RIS,
        first("ID", "AN") or f"line-{line}",
        " ".join(title.split()),
        tuple(
            _turn_name(name)
            for tag in ("AU", "A1")
            for name in fields.get(tag, ())
            if name
        ),
        first("PY", "Y1", "DA"),
        first("JO", "JF", "T2", "BT", "JA", "PB") or None,
        first("AB", "N2"),
        first("UR", "L2"),
        _doi_of(first("DO", "M3")) or _doi_of(first("UR")),
        _arxiv_of(first("UR"), first("JO"), first("AN"), first("M1")),
    )


# --- shared -----------------------------------------------------------------------


def _doi_of(text: str) -> str | None:
    match = _DOI.search(text)
    return match.group(0).rstrip(".,;)}") if match else None


def _arxiv_of(*texts: str) -> str | None:
    for text in texts:
        match = _ARXIV.search(text)
        if match:
            return match.group(1)
    return None


def _paper(
    source: str,
    source_id: str,
    title: str,
    authors: tuple[str, ...],
    date: str,
    venue: str | None,
    abstract: str,
    url: str,
    doi: str | None,
    arxiv: str | None,
) -> Paper:
    year = _YEAR.search(date)
    if not url.startswith(("https://", "http://")):
        url = ""
    if not url and doi:
        url = f"https://doi.org/{doi}"
    elif not url and arxiv:
        url = f"https://arxiv.org/abs/{arxiv}"
    return Paper(
        source=source,
        source_id=source_id or doi or title[:60],
        title=title,
        authors=authors,
        year=int(year.group(1)) if year else None,
        venue=venue,
        abstract=abstract,
        url=url,
        doi=doi,
        arxiv_id=arxiv,
    )
