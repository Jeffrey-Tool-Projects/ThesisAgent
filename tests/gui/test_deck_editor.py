"""The slide editor: preview, texts, order, undo, saving."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox

from thesisagents.core.models import ExportOptions, Paper, PaperCollection, PaperSummary, Query
from thesisagents.exporters import export_collection, pptx_edit
from thesisagents.gui.pages.deck import DeckPage
from thesisagents.gui.widgets.deck_editor import DeckEditor
from thesisagents.gui.widgets.slide_preview import render_slide


@pytest.fixture
def deck(tmp_path) -> Path:
    paper = Paper(
        source="a", source_id="1", title="A paper", authors=("A",), year=2020, venue="V",
        abstract="Words. " * 40, url="https://example.org",
        summary=PaperSummary(
            language="en", motivation=("m1", "m2"), limitations=("l",),
            technique_table=(("a", "b"),), core_observation="c",
        ),
    )
    return export_collection(
        PaperCollection(query=Query("x", ("arxiv",)), papers=(paper,)),
        ExportOptions(
            formats=("pptx",), out_dir=str(tmp_path), filename_stem="deck",
            verify_identifiers=False,
        ),
    )["pptx"]


@pytest.fixture
def editor(qtbot, deck):
    editor = DeckEditor(str(deck), "en")
    qtbot.addWidget(editor)
    return editor


def _titles(path) -> list[str]:
    return [view.title for view in pptx_edit.inspect(path)]


def test_slides_and_texts_are_shown(editor, deck):
    assert editor.slide_list().count() == len(pptx_edit.inspect(deck))
    editor.slide_list().setCurrentRow(1)
    assert "title" in editor.text_boxes()
    assert "page_number" not in editor.text_boxes()
    assert editor.preview().width() == 640
    assert not editor.button("save").isEnabled()


def test_text_is_changed_only_when_saved(editor, deck):
    before = deck.read_bytes()
    editor.slide_list().setCurrentRow(1)
    editor.text_boxes()["title"].setPlainText("Changed title")
    assert editor.button("save").isEnabled()
    assert editor.apply_texts()
    assert deck.read_bytes() == before
    saved = []
    editor.saved.connect(saved.append)
    assert editor.save()
    assert _titles(deck)[1] == "Changed title"
    assert saved == [str(deck)]
    assert not editor.button("save").isEnabled()
    assert list(deck.parent.glob("*.saving")) == []


def test_typed_text_survives_selecting_another_slide(editor, deck):
    editor.slide_list().setCurrentRow(1)
    editor.text_boxes()["title"].setPlainText("Typed, not applied")
    editor.slide_list().setCurrentRow(2)
    assert editor.slide_list().currentRow() == 2
    editor.save()
    assert _titles(deck)[1] == "Typed, not applied"
    assert _titles(deck)[2] != "Typed, not applied"


def test_slides_are_added_moved_deleted_and_undone(editor, deck):
    original = _titles(deck)
    editor.slide_list().setCurrentRow(1)
    editor.add_slide()
    assert editor.slide_list().currentRow() == 2
    assert editor.slide_list().count() == len(original) + 1
    editor.move_slide(1)
    assert editor.slide_list().currentRow() == 3
    editor.move_slide(99)
    editor.slide_list().setCurrentRow(0)
    editor.delete_slide()
    editor.save_to(str(deck.parent / "other.pptx"))
    other = _titles(deck.parent / "other.pptx")
    assert other == [original[1], original[2], "New slide", *original[3:]]
    assert _titles(deck) == original


def test_undo_goes_back_step_by_step(editor, deck):
    count = editor.slide_list().count()
    editor.delete_slide()
    editor.delete_slide()
    assert editor.slide_list().count() == count - 2
    editor.undo()
    assert editor.slide_list().count() == count - 1
    editor.undo()
    assert editor.slide_list().count() == count
    assert not editor.button("undo").isEnabled()
    assert not editor.button("save").isEnabled()
    editor.undo()


def test_the_last_slide_stays(qtbot, deck):
    for _ in range(len(pptx_edit.inspect(deck)) - 1):
        pptx_edit.delete_slide(deck, 0)
    editor = DeckEditor(str(deck), "en")
    qtbot.addWidget(editor)
    assert not editor.button("delete").isEnabled()
    editor.delete_slide()
    assert editor.slide_list().count() == 1


def test_dragging_reorders(editor, deck):
    original = _titles(deck)
    slides = editor.slide_list()
    item = slides.takeItem(2)
    slides.insertItem(1, item)
    editor._on_reordered()  # noqa: SLF001 - what a drop calls
    editor.save()
    assert _titles(deck) == [original[0], original[2], original[1], *original[3:]]


def test_a_locked_file_is_explained(editor, deck, monkeypatch):
    def locked(_source, _target):
        raise PermissionError("in use")

    monkeypatch.setattr("thesisagents.gui.widgets.deck_editor.os.replace", locked)
    editor.delete_slide()
    assert not editor.save()
    assert "open in PowerPoint" in editor.status_text()
    assert list(deck.parent.glob("*.saving")) == []
    assert editor.button("undo").isEnabled()


@pytest.mark.parametrize(("answer", "closed"), [
    (QMessageBox.StandardButton.No, False), (QMessageBox.StandardButton.Yes, True),
])
def test_closing_with_changes_asks(qtbot, editor, monkeypatch, answer, closed):
    monkeypatch.setattr(QMessageBox, "question", lambda *_: answer)
    editor.show()
    editor.slide_list().setCurrentRow(1)
    editor.text_boxes()["title"].setPlainText("x")
    editor.reject()
    assert editor.isHidden() is closed


def test_the_working_copy_goes_with_the_dialog(qtbot, deck):
    editor = DeckEditor(str(deck), "en")
    folder = editor.working_folder()
    assert folder.exists()
    editor.deleteLater()
    qtbot.waitUntil(lambda: not folder.exists(), timeout=3000)


def test_the_deck_page_opens_the_editor_and_explains_a_bad_file(qtbot, deck, tmp_path):
    page = DeckPage(ui_language="en")
    qtbot.addWidget(page)
    page.edit_deck_file(str(deck))
    assert page.deck_editor().slide_list().count() > 1
    page.deck_editor().close()
    bad = tmp_path / "bad.pptx"
    bad.write_bytes(b"x")
    page.edit_deck_file(str(bad))
    assert "not a PowerPoint file" in page.status_text()
    page.edit_deck_file(str(tmp_path / "none.pptx"))
    assert page.status_text()


# --- preview -----------------------------------------------------------------------------


def test_the_preview_draws_background_text_picture_and_table(qtbot, tmp_path):
    from PIL import Image
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Inches, Pt

    picture = tmp_path / "p.png"
    Image.new("RGB", (4, 4), (255, 0, 0)).save(picture)
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = RGBColor(0, 0, 80)
    slide.shapes.add_picture(str(picture), 0, 0, Inches(2), Inches(2))
    table = slide.shapes.add_table(1, 1, Inches(5), 0, Inches(2), Inches(1)).table
    table.cell(0, 0).fill.solid()
    table.cell(0, 0).fill.fore_color.rgb = RGBColor(0, 200, 0)
    box = slide.shapes.add_textbox(Inches(1), Inches(4), Inches(6), Inches(2))
    run = box.text_frame.paragraphs[0].add_run()
    run.text = "█" * 10
    run.font.size = Pt(60)
    run.font.color.rgb = RGBColor(255, 255, 0)
    size = (presentation.slide_width, presentation.slide_height)
    image = render_slide(slide, size, 400)
    assert (image.width(), image.height()) == (400, 300)
    assert image.pixelColor(40, 40).name() == "#ff0000"
    assert image.pixelColor(390, 290).name() == "#000050"
    assert image.pixelColor(240, 15).name() == "#00c800"
    colours = {image.pixelColor(x, y).name() for x in range(50, 340, 3) for y in range(160, 260, 3)}
    assert "#ffff00" in colours
