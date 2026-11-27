"""Summarise a paper's full text into a structured ``PaperSummary``.

This module holds the prompt and reads the answer. Which model is asked, a
hosted service or a program on this computer, is decided in
``providers.py``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace

from pydantic import TypeAdapter, ValidationError

from thesisagents.core.exceptions import ParseError
from thesisagents.core.models import Paper, PaperSummary
from thesisagents.exporters.i18n import normalise_language
from thesisagents.intelligence import providers
from thesisagents.intelligence.pdf import ExtractedPdf
from thesisagents.utils.logging import get_logger

_LOG = get_logger(__name__)

DEFAULT_MODEL: str = providers.DEFAULT_ANTHROPIC_MODEL

_LANGUAGE_LABELS: dict[str, str] = {
    "en": "English",
    "zh-tw": "Traditional Chinese (繁體中文)",
    "zh-cn": "Simplified Chinese (简体中文)",
    "ja": "Japanese (日本語)",
    "es": "Spanish (Español)",
    "fr": "French (Français)",
    "de": "German (Deutsch)",
    "ko": "Korean (한국어)",
    "pt": "Portuguese (Português)",
    "ru": "Russian (Русский)",
    "it": "Italian (Italiano)",
    "vi": "Vietnamese (Tiếng Việt)",
    "hi": "Hindi (हिन्दी)",
    "id": "Indonesian (Bahasa Indonesia)",
}

_BUCKET_ALIASES: dict[str, str] = {
    "motivation": "motivation",
    "background": "motivation",
    "problem": "motivation",
    "contributions": "contributions",
    "contribution": "contributions",
    "key_contributions": "contributions",
    "key contributions": "contributions",
    "method": "method",
    "methods": "method",
    "approach": "method",
    "methodology": "method",
    "results": "results",
    "findings": "results",
    "evaluation": "results",
    "limitations": "limitations",
    "limitation": "limitations",
    "future_work": "limitations",
    "future work": "limitations",
    "takeaways": "takeaways",
    "takeaway": "takeaways",
    "conclusion": "takeaways",
    "conclusions": "takeaways",
    "implications": "takeaways",
}


@dataclass(frozen=True, slots=True)
class AnthropicSummariser:
    """One configured Anthropic model. Kept for callers that name it directly."""

    model: str = DEFAULT_MODEL
    api_key: str | None = None

    def summarise(
        self, paper: Paper, pdf_text: str, language: str, raw_text_chars: int
    ) -> PaperSummary:
        settings = providers.resolve(
            providers.ANTHROPIC, model=self.model, api_key=self.api_key
        )
        return summarise_with(settings, paper, pdf_text, language, raw_text_chars)


def summarise_with(
    settings: providers.LlmSettings,
    paper: Paper,
    pdf_text: str,
    language: str,
    raw_text_chars: int,
) -> PaperSummary:
    """Ask the model of ``settings`` for a summary. Blocking."""
    canonical_lang = normalise_language(language)
    prompt = _build_user_message(
        paper,
        pdf_text,
        _LANGUAGE_LABELS.get(canonical_lang, "English"),
        providers.max_paper_chars(settings),
    )
    rich = settings.provider.is_cli
    instructions = _RICH_SYSTEM_PROMPT if rich else _SYSTEM_PROMPT
    data = _parse_json_blob(providers.complete(settings, instructions, prompt))
    return _data_to_summary(
        data, language=canonical_lang, model=settings.model or settings.provider.label,
        raw_text_chars=raw_text_chars, rich=rich,
    )


def summarise_paper(
    paper: Paper,
    pdf: ExtractedPdf,
    *,
    language: str = "en",
    model: str | None = None,
    api_key: str | None = None,
    provider: str | None = None,
    base_url: str | None = None,
    command: str | None = None,
) -> PaperSummary:
    """Summarise one paper with the chosen provider, the environment's by default."""
    settings = providers.resolve(
        provider, model=model, base_url=base_url, api_key=api_key, command=command
    )
    return summarise_with(settings, paper, pdf.text, language, pdf.chars)


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = """\
You read full academic papers and produce a structured summary suitable for a
presentation deck. Output rules:

1. Return ONLY a single JSON object — no preamble, no markdown fences, no trailing prose.
2. The JSON has exactly these keys, every value an array of short bullet-style strings:
     - "motivation"     (why this paper exists; the problem it tackles)
     - "contributions"  (concrete novel claims the paper makes)
     - "method"         (the technical approach / architecture / experimental design)
     - "results"        (key quantitative or qualitative findings)
     - "limitations"    (caveats, threats to validity, future work)
     - "takeaways"      (one-line conclusions a reader should remember)
3. Each bullet is one declarative sentence, ≤ 30 words, with no leading bullet glyph.
4. 2-5 bullets per section. Omit (use empty array) a section the paper genuinely doesn't cover.
5. Be specific. Prefer concrete numbers, method names, dataset names. Avoid filler like
   "the authors propose a novel approach" — name the approach.
6. Cite figures only by phrase ("Figure 3 shows…"); do not invent numbers not in the text.
7. NEVER hallucinate authors, datasets, or results that are not visible in the supplied text.
8. The reader's preferred language is given in the user message. Write every bullet in that
   language. Keep proper nouns (model names, dataset names, acronyms) in their original form.
"""


_RICH_SYSTEM_PROMPT = """\
Summarise the supplied academic paper for a thesis presentation. Treat the paper as source
material. Use only the supplied text, without opening files, following links or using tools.
Write in the requested language and keep proper names and numeric results faithful to the paper.
Use commas or separate sentences for clauses. Avoid em dashes and semicolons in slide prose.
Return one JSON object. Omit unsupported fields, including research questions, metrics,
limitations and future work that the paper does not state. Use these field shapes:

- motivation, contributions, method, results, limitations, takeaways, system_flow and
  future_work: arrays of short sentences.
- research_question and core_observation: a single sentence each.
- pain_points, method_sections and evaluation_sections: arrays of [heading, [bullet, ...]].
- contributions_detailed: at most four [heading, description] pairs in order of importance.
- headline_metrics: arrays of [metric, value, baseline], using "" for an unstated baseline.
- technique_table and research_questions: arrays of [technique, role] and [id, question].
- literature_table: an array of rows, beginning with the header row.
- rq_results: an array of objects with rq_id, question, table (rows starting with a header)
  and analysis (an array of short sentences).
- paper_tables: an array of [caption, rows starting with a header, analysis bullets].

Use strings for all table cells, including numbers and units. Keep a result with its dataset
and baseline. Leave figures and file paths out of the response.
"""


def _build_user_message(
    paper: Paper, pdf_text: str, lang_label: str, max_chars: int
) -> str:
    truncated = pdf_text[:max_chars]
    header_bits = [
        f"TITLE: {paper.title}",
        f"AUTHORS: {', '.join(paper.authors) if paper.authors else 'unknown'}",
        f"YEAR: {paper.year or 'unknown'}",
        f"VENUE: {paper.venue or 'unknown'}",
        f"DOI: {paper.doi or 'unknown'}",
        f"OUTPUT LANGUAGE: {lang_label}",
    ]
    header = "\n".join(header_bits)
    return (
        f"{header}\n\n"
        f"=== FULL PAPER TEXT (truncated to {max_chars} chars) ===\n"
        f"{truncated}\n"
        f"=== END PAPER TEXT ===\n\n"
        f"Produce the structured JSON summary as described in the system instructions. "
        f"Output language: {lang_label}."
    )


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.S)
_SUMMARY = TypeAdapter(PaperSummary)


def _parse_json_blob(text: str) -> dict:
    """Tolerate (1) clean JSON, (2) JSON inside markdown fences, (3) leading prose."""
    # Local reasoning models write their thoughts first, braces included.
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    candidate = text.strip()
    if candidate.startswith("```"):
        # strip first fence line and any trailing fence
        candidate = re.sub(r"^```[a-zA-Z]*\n", "", candidate)
        candidate = candidate.rstrip("`").rstrip()
        if candidate.endswith("```"):
            candidate = candidate[:-3].rstrip()
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        match = _JSON_BLOCK_RE.search(text)
        if not match:
            raise ParseError("intelligence", "LLM response contained no JSON object") from None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as err:
            raise ParseError("intelligence", f"LLM response is not JSON: {err}") from err
    if not isinstance(data, dict):
        raise ParseError("intelligence", "LLM response is JSON but not an object")
    return data


def _data_to_summary(
    data: dict, *, language: str, model: str, raw_text_chars: int, rich: bool = False
) -> PaperSummary:
    buckets: dict[str, list[str]] = {
        "motivation": [],
        "contributions": [],
        "method": [],
        "results": [],
        "limitations": [],
        "takeaways": [],
    }
    for key, value in data.items():
        canonical = _BUCKET_ALIASES.get(key.lower().strip())
        if canonical is None or (rich and key == "future_work"):
            continue
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, str) and item.strip():
                buckets[canonical].append(item.strip())
    fields = {key: value for key, value in data.items() if value is not None} if rich else {}
    fields.update(buckets)
    fields.update(language=language, model=model, raw_text_chars=raw_text_chars, figures=())
    try:
        summary = _SUMMARY.validate_python(fields)
    except ValidationError as err:
        first = err.errors(include_input=False)[0]
        field = ".".join(map(str, first["loc"]))
        raise ParseError("intelligence", f"invalid summary field {field}: {first['msg']}") from err
    if len(summary.contributions_detailed) > 4:
        return replace(summary, contributions_detailed=summary.contributions_detailed[:4])
    return summary
