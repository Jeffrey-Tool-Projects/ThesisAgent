"""What can be done with one paper of a result list: open its pages, copy its citation."""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QMenu, QWidget

from thesisagents.core.models import Paper
from thesisagents.exporters.bibtex import bibtex_entry
from thesisagents.gui.i18n import t

_OPENABLE_SCHEMES: frozenset[str] = frozenset({"http", "https"})


def paper_menu(paper: Paper, language: str, parent: QWidget) -> QMenu:
    """Open page / Open PDF / Copy DOI / Copy BibTeX for one paper."""
    menu = QMenu(parent)
    open_page = menu.addAction(t("search.menu_open_page", language))
    open_page.triggered.connect(lambda: open_web_link(paper.url))
    open_pdf = menu.addAction(t("search.menu_open_pdf", language))
    open_pdf.setEnabled(bool(paper.pdf_url))
    open_pdf.triggered.connect(lambda: open_web_link(paper.pdf_url or ""))
    menu.addSeparator()
    copy_doi = menu.addAction(t("search.menu_copy_doi", language))
    copy_doi.setEnabled(bool(paper.doi))
    copy_doi.triggered.connect(lambda: copy_text(paper.doi or ""))
    copy_bib = menu.addAction(t("search.menu_copy_bibtex", language))
    copy_bib.triggered.connect(lambda: copy_text(bibtex_entry(paper)))
    return menu


def open_web_link(url: str) -> None:
    """Open ``url`` in the browser when it is an ``http`` / ``https`` link.

    The URL comes from a remote API: handing a ``file:`` or custom-scheme
    link to the desktop would let a source record launch a local program.
    """
    link = QUrl(url)
    if link.scheme() in _OPENABLE_SCHEMES:
        QDesktopServices.openUrl(link)


def copy_text(text: str) -> None:
    QGuiApplication.clipboard().setText(text)
