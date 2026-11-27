"""Full-text summaries for the Enrich and Deck pages."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

from thesisagents.core.exceptions import ConfigError, ThesisAgentsError
from thesisagents.core.models import Paper, PaperCollection, PaperSummary
from thesisagents.fetchers.http import shutdown_clients
from thesisagents.gui.i18n import t
from thesisagents.gui.pdf_stage import needs_institutional_access
from thesisagents.intelligence import providers

type SummaryChanges = tuple[tuple[Paper, Paper], ...]


def apply_summary_changes(collection: PaperCollection, changes: SummaryChanges) -> PaperCollection:
    """Carry summaries across selection changes only for the original paper objects."""
    updated = {id(original): enriched for original, enriched in changes}
    if any(id(paper) in updated for paper in collection.papers):
        return replace(collection, papers=tuple(updated.get(id(p), p) for p in collection.papers))
    return collection


def cli_provider_choices(language: str) -> Iterator[tuple[str, str]]:
    """The label and provider name for each terminal program offered by the GUI."""
    for provider in providers.PROVIDERS.values():
        if provider.is_cli:
            label = (
                t("model.cli_custom", language) if provider.name == providers.CLI
                else t("model.cli", language, name=provider.label)
            )
            yield label, provider.name


def local_text(paper: Paper) -> str:
    """Read text already extracted when the user opened a local PDF."""
    text = (paper.raw or {}).get("extracted_text")
    return text if isinstance(text, str) and text.strip() else ""


async def summarise_for_page(
    settings: providers.LlmSettings, paper: Paper, language: str,
) -> PaperSummary:
    """Read the paper and ask the selected provider on the page's worker."""
    from thesisagents.intelligence.pdf import fetch_and_extract
    from thesisagents.intelligence.summarise import summarise_with

    text = local_text(paper)
    if text:
        return summarise_with(settings, paper, text, language, len(text))
    try:
        pdf = await fetch_and_extract(paper.pdf_url or "", source=paper.source)
    finally:
        await shutdown_clients()
    return summarise_with(settings, paper, pdf.text, language, pdf.chars)


async def prepare_cli_deck(
    collection: PaperCollection, settings: providers.LlmSettings, language: str,
    *, ui_language: str, vpn_access: bool,
) -> PaperCollection:
    """Prepare every selected paper before writing any of the requested formats."""
    reason = providers.cli_readiness_problem(settings)
    if reason:
        raise ConfigError(t("deck.cli_setup", ui_language, reason=reason))

    papers = []
    for paper in collection.papers:
        summary = paper.summary
        if summary is not None and summary.language == language and not summary.is_empty():
            papers.append(paper)
            continue
        try:
            if not local_text(paper):
                if not paper.pdf_url:
                    raise ThesisAgentsError(t("deck.cli_no_pdf", ui_language))
                if not vpn_access and needs_institutional_access(paper):
                    raise ThesisAgentsError(t("deck.pdfs_ieee_held", ui_language, count=1))
            summary = await summarise_for_page(settings, paper, language)
            if summary.is_empty():
                raise ThesisAgentsError(t("deck.cli_empty_summary", ui_language))
        except ConfigError as err:
            raise ConfigError(t("deck.cli_setup", ui_language, reason=str(err))) from err
        except ThesisAgentsError as err:
            raise ThesisAgentsError(f"{paper.title}\n{err}") from err
        papers.append(replace(paper, summary=summary))
    return replace(collection, papers=tuple(papers))
