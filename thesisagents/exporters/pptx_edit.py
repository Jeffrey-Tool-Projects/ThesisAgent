"""Editing operations for an existing .pptx file.

These wrap python-pptx with semantic helpers (`title` / `meta` / `body` lookup
by shape name when the file was written by `PptxExporter`, falling back to
positional access otherwise) and the slide-list XML manipulation required to
delete and reorder slides — python-pptx does not expose those operations
directly.

An edit keeps how the text looked. Writing ``text_frame.text`` alone drops
the runs' colour and size, and text without an explicit colour is invisible
on a dark deck (the dark-mode contract in ``deck-design``). A slide that is
added takes the look of the deck's other content slides, and the page
numbers are counted again whenever slides come, go or move.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.exc import PackageNotFoundError
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

from thesisagents.core.exceptions import ExportError
from thesisagents.exporters.template import ROLE_CONTENT, LayoutSet, content_layout

_DEFAULT_TITLE_PT = 28
_DEFAULT_BODY_PT = 14
_SLIDE_LEFT = Inches(0.5)
_SLIDE_TOP = Inches(0.6)
_SLIDE_WIDTH = Inches(9.0)
_TITLE_HEIGHT = Inches(1.2)
_BODY_HEIGHT = Inches(5.4)
#: Text colours for a shape that has none to keep, on a light and a dark slide.
_INK = RGBColor(0x1F, 0x29, 0x37)
_INK_ON_DARK = RGBColor(0xE5, 0xE7, 0xEB)
_DARK_LUMINANCE = 90
#: Shapes that make the look of a content slide and hold no content.
_CHROME_NAMES = ("accent_top", "accent_rule")
_PAGE_NUMBER = re.compile(r"^\s*\d+(\s*/\s*)\d+\s*$")


@dataclass(frozen=True, slots=True)
class ShapeView:
    """A read-only view of one text-bearing shape on a slide."""

    index: int
    name: str
    text: str


@dataclass(frozen=True, slots=True)
class SlideView:
    """A read-only view of one slide and its text-bearing shapes."""

    index: int
    title: str
    shapes: tuple[ShapeView, ...]


def inspect(path: str | Path) -> list[SlideView]:
    """Return a list of SlideView for `path` so callers can decide what to edit."""
    presentation = _open(path)
    views: list[SlideView] = []
    for slide_index, slide in enumerate(presentation.slides):
        shapes: list[ShapeView] = []
        title = ""
        for shape_index, shape in enumerate(slide.shapes):
            if not shape.has_text_frame:
                continue
            text = shape.text_frame.text
            shape_name = (shape.name or "").lower()
            shapes.append(ShapeView(index=shape_index, name=shape.name, text=text))
            if not title and (shape_name == "title" or shape_index == 0):
                title = text
        views.append(SlideView(index=slide_index, title=title, shapes=tuple(shapes)))
    return views


def update_slide(
    path: str | Path,
    slide_index: int,
    *,
    title: str | None = None,
    body: str | None = None,
    meta: str | None = None,
    shape_updates: dict[int, str] | None = None,
    out_path: str | Path | None = None,
) -> Path:
    """Update text on `slide_index` and save.

    `title` / `body` / `meta` look the shape up by name when present; if the
    file was produced by PptxExporter that always works. `shape_updates` is the
    fallback — `{shape_index: new_text}` for arbitrary shape edits, with the
    indices `inspect` reports.
    """
    presentation = _open(path)
    slide = _slide_at(presentation, slide_index)
    by_name = {(s.name or "").lower(): s for s in slide.shapes if s.has_text_frame}
    if title is not None:
        _set_text_by_name(by_name, "title", title, _DEFAULT_TITLE_PT, bold=True)
    if meta is not None:
        _set_text_by_name(by_name, "meta", meta, _DEFAULT_BODY_PT)
    if body is not None:
        _set_text_by_name(by_name, "body", body, _DEFAULT_BODY_PT)
    if shape_updates:
        # Every shape counts, as in ``inspect``. Counting only those with text
        # hit a neighbour as soon as a picture came before the shape.
        shapes = list(slide.shapes)
        for shape_idx, new_text in shape_updates.items():
            if shape_idx < 0 or shape_idx >= len(shapes):
                raise ExportError(
                    "pptx_edit",
                    f"shape index {shape_idx} out of range for slide {slide_index}",
                )
            if not shapes[shape_idx].has_text_frame:
                raise ExportError(
                    "pptx_edit",
                    f"shape {shape_idx} on slide {slide_index} holds no text",
                )
            _write_text_frame(shapes[shape_idx], new_text)
    return _save(presentation, path, out_path)


def delete_slide(
    path: str | Path,
    slide_index: int,
    out_path: str | Path | None = None,
) -> Path:
    """Delete the slide at `slide_index` and save."""
    presentation = _open(path)
    _ = _slide_at(presentation, slide_index)
    _remove_slide_at(presentation, slide_index)
    _renumber(presentation)
    return _save(presentation, path, out_path)


def reorder_slides(
    path: str | Path,
    new_order: list[int],
    out_path: str | Path | None = None,
) -> Path:
    """Reorder slides so `new_order[i]` becomes the new index `i`."""
    presentation = _open(path)
    slide_count = len(presentation.slides)
    _validate_permutation(new_order, slide_count)
    sld_id_lst = presentation.slides._sldIdLst  # noqa: SLF001  # python-pptx exposes no public reorder API
    children = list(sld_id_lst)
    reordered = [children[i] for i in new_order]
    for child in children:
        sld_id_lst.remove(child)
    for child in reordered:
        sld_id_lst.append(child)
    _renumber(presentation)
    return _save(presentation, path, out_path)


def add_slide(
    path: str | Path,
    *,
    title: str,
    body: str = "",
    meta: str = "",
    position: int | None = None,
    out_path: str | Path | None = None,
) -> Path:
    """Append (or insert at `position`) a new slide with title/meta/body textboxes."""
    presentation = _open(path)
    # Not ``slide_layouts[6]``: that is the blank layout only in python-pptx's
    # own template, and a deck built on a custom template may not have it.
    slide = LayoutSet({ROLE_CONTENT: content_layout(presentation)}).add_slide(
        presentation, ROLE_CONTENT
    )
    look = _content_slide(presentation, exclude=slide)
    if look is not None:
        _take_look(slide, look)
    for name, text, top, height, size, bold in (
        ("title", title, _SLIDE_TOP, _TITLE_HEIGHT, _DEFAULT_TITLE_PT, True),
        ("meta", meta, Inches(1.8), Inches(0.8), _DEFAULT_BODY_PT, False),
        ("body", body, Inches(2.8), _BODY_HEIGHT, _DEFAULT_BODY_PT, False),
    ):
        if text or name == "title":
            model = _text_shape(look, name) if look is not None else None
            if model is not None:
                _add_like(slide, model, text)
            else:
                _add_named_textbox(slide, name, text, top, height, size, bold=bold)
    if position is not None:
        target = max(0, min(position, len(presentation.slides) - 1))
        current_index = len(presentation.slides) - 1
        _move_slide(presentation, current_index, target)
    _renumber(presentation)
    return _save(presentation, path, out_path)


def _open(path: str | Path) -> Presentation:
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise ExportError("pptx_edit", f"pptx file not found: {resolved}")
    try:
        return Presentation(str(resolved))
    except (PackageNotFoundError, KeyError, ValueError) as err:
        raise ExportError("pptx_edit", f"{resolved} is not a PowerPoint file") from err


def _save(
    presentation: Presentation,
    original: str | Path,
    out_path: str | Path | None,
) -> Path:
    target = Path(out_path).expanduser().resolve() if out_path else Path(original).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    presentation.save(str(target))
    return target


def _slide_at(presentation: Presentation, slide_index: int):
    slides = presentation.slides
    if slide_index < 0 or slide_index >= len(slides):
        raise ExportError(
            "pptx_edit",
            f"slide index {slide_index} out of range (have {len(slides)})",
        )
    return slides[slide_index]


def _set_text_by_name(by_name, key, text, font_pt, bold=False):
    shape = by_name.get(key)
    if shape is None:
        raise ExportError(
            "pptx_edit",
            f"no shape named {key!r} on this slide — use shape_updates instead",
        )
    _write_text_frame(shape, text, font_pt=font_pt, bold=bold)


def _write_text_frame(shape, text: str, *, font_pt: int | None = None, bold: bool = False) -> None:
    """Replace the text and keep its formatting, paragraph by paragraph.

    More lines than before look like the last one. ``font_pt`` and ``bold``
    are for a shape that had no text to take the look from.
    """
    text_frame = shape.text_frame
    looks = [
        (copy.deepcopy(paragraph._p.pPr), copy.deepcopy(paragraph.runs[0]._r.rPr))  # noqa: SLF001
        for paragraph in text_frame.paragraphs
        if paragraph.runs
    ]
    text_frame.word_wrap = True
    text_frame.text = text
    for index, paragraph in enumerate(text_frame.paragraphs):
        paragraph_look, run_look = looks[min(index, len(looks) - 1)] if looks else (None, None)
        if paragraph_look is not None:
            _replace_child(paragraph._p, "a:pPr", paragraph_look)  # noqa: SLF001
        for run in paragraph.runs:
            if run_look is not None:
                _replace_child(run._r, "a:rPr", run_look)  # noqa: SLF001
            else:
                if font_pt is not None:
                    run.font.size = Pt(font_pt)
                run.font.bold = bold
            _ensure_colour(shape, run)


def _replace_child(element, tag: str, replacement) -> None:
    """Put a copy of ``replacement`` where ``tag`` belongs: first in the element."""
    for old in element.findall(qn(tag)):
        element.remove(old)
    element.insert(0, copy.deepcopy(replacement))


def _ensure_colour(shape, run) -> None:
    """Give a run without any colour one that shows on its slide."""
    colour = run.font.color
    if colour is not None and colour.type is not None:
        return
    run.font.color.rgb = _INK_ON_DARK if _on_dark(shape) else _INK


def _on_dark(shape) -> bool:
    """Whether the shape's slide has a dark background of its own."""
    try:
        fill = shape.part.slide.background.fill
        red, green, blue = fill.fore_color.rgb
    except (AttributeError, TypeError):
        return False
    return 0.299 * red + 0.587 * green + 0.114 * blue < _DARK_LUMINANCE


def _text_shape(slide, name: str):
    return next(
        (s for s in slide.shapes if s.has_text_frame and (s.name or "").lower() == name), None
    )


def _content_slide(presentation: Presentation, *, exclude):
    """A slide to copy the look from: one with a title and a body, not the cover."""
    best = None
    for index, slide in enumerate(presentation.slides):
        if slide.slide_id == exclude.slide_id or _text_shape(slide, "title") is None:
            continue
        if _text_shape(slide, "body") is not None and index > 0:
            return slide
        if index > 0:
            best = best or slide
    return best


def _take_look(slide, look) -> None:
    """Copy the background and the decoration of ``look`` behind the new slide."""
    background = look._element.cSld.find(qn("p:bg"))  # noqa: SLF001
    if background is not None:
        slide._element.cSld.insert(0, copy.deepcopy(background))  # noqa: SLF001
    # The new slide's empty placeholders would cover the copied title.
    for placeholder in list(slide.placeholders):
        placeholder._element.getparent().remove(placeholder._element)  # noqa: SLF001
    for shape in look.shapes:
        if (shape.name or "").lower() in (*_CHROME_NAMES, "page_number"):
            slide.shapes._spTree.append(copy.deepcopy(shape._element))  # noqa: SLF001


def _add_like(slide, model, text: str) -> None:
    """A copy of the text shape ``model`` with other text."""
    element = copy.deepcopy(model._element)  # noqa: SLF001
    slide.shapes._spTree.append(element)  # noqa: SLF001
    added = list(slide.shapes)[-1]
    _write_text_frame(added, text)


def _renumber(presentation: Presentation) -> None:
    """Count the page numbers again ("3  /  12"), in the deck's own spacing."""
    numbered = [
        shape
        for slide in presentation.slides
        for shape in slide.shapes
        if (shape.name or "").lower() == "page_number"
        and shape.has_text_frame
        and _PAGE_NUMBER.match(shape.text_frame.text)
    ]
    for number, shape in enumerate(numbered, 1):
        separator = _PAGE_NUMBER.match(shape.text_frame.text).group(1)
        _write_text_frame(shape, f"{number}{separator}{len(numbered)}")


def _add_named_textbox(slide, name: str, text: str, top, height, font_pt: int, bold: bool = False):
    box = slide.shapes.add_textbox(_SLIDE_LEFT, top, _SLIDE_WIDTH, height)
    box.name = name
    _write_text_frame(box, text, font_pt=font_pt, bold=bold)
    return box


def _remove_slide_at(presentation: Presentation, slide_index: int) -> None:
    slides = presentation.slides
    sld_id_lst = slides._sldIdLst  # noqa: SLF001
    children = list(sld_id_lst)
    target = children[slide_index]
    rid = target.attrib.get(
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    )
    sld_id_lst.remove(target)
    if rid:
        presentation.part.drop_rel(rid)


def _move_slide(presentation: Presentation, src_index: int, dst_index: int) -> None:
    sld_id_lst = presentation.slides._sldIdLst  # noqa: SLF001
    children = list(sld_id_lst)
    moving = children.pop(src_index)
    children.insert(dst_index, moving)
    # ``children`` holds the same elements as ``sld_id_lst``, only reordered,
    # so it doubles as the snapshot to remove from (removing while iterating
    # ``sld_id_lst`` itself would skip every other element).
    for child in children:
        sld_id_lst.remove(child)
    for child in children:
        sld_id_lst.append(child)


def _validate_permutation(order: list[int], slide_count: int) -> None:
    if len(order) != slide_count:
        raise ExportError(
            "pptx_edit",
            f"new_order length {len(order)} does not match slide count {slide_count}",
        )
    if sorted(order) != list(range(slide_count)):
        raise ExportError(
            "pptx_edit",
            f"new_order must be a permutation of [0..{slide_count - 1}]",
        )


