"""What sources really send: markup, entities, abbreviated names, odd identifiers.

Each case here reached a bibliography or broke de-duplication before it was
handled. The records are reduced to the fields that matter.
"""
from __future__ import annotations

import pytest

from thesisagents.core.dedup import dedupe
from thesisagents.core.models import Paper, Query
from thesisagents.sources.acm.parser import parse_record as parse_acm
from thesisagents.sources.arxiv.fetcher import ArxivFetcher
from thesisagents.sources.arxiv.parser import parse_atom_feed
from thesisagents.sources.crossref.parser import parse_record as parse_crossref
from thesisagents.sources.dblp.parser import parse_hit
from thesisagents.sources.doaj.parser import parse_result as parse_doaj
from thesisagents.sources.europepmc.parser import parse_result as parse_europepmc
from thesisagents.sources.ieee.parser import parse_search_record
from thesisagents.sources.openaire.parser import parse_product
from thesisagents.sources.openalex.fetcher import OpenAlexFetcher
from thesisagents.sources.openalex.parser import parse_work
from thesisagents.sources.pubmed.parser import parse_efetch
from thesisagents.sources.scholar.parser import parse_serp
from thesisagents.sources.springer.parser import parse_record as parse_springer
from thesisagents.utils.markup import plain_text

# --- markup -----------------------------------------------------------------------------


@pytest.mark.parametrize(("raw", "text"), [
    ("On <i>E. coli</i> &amp; friends", "On E. coli & friends"),
    ("H<sub>2</sub>O", "H2O"),
    ("<jats:p>One.</jats:p><jats:p>Two.</jats:p>", "One. Two."),
    ("<h4>Background</h4>We ask.", "Background We ask."),
    ("&lt;i&gt;x&lt;/i&gt;", "x"),
    ('<a href="https://e.org/?a=1&amp;b=2">link</a>', "link"),
    ("<mml:math><mml:mi>k</mml:mi></mml:math>-means", "k-means"),
    # Comparisons are text.
    ("If n<5 and m>3 it holds", "If n<5 and m>3 it holds"),
    ("p &lt; 0.05 and q &gt; 3", "p < 0.05 and q > 3"),
    ("x <y and z> w", "x <y and z> w"),
    (None, ""),
    ("  a \n b ", "a b"),
])
def test_markup_becomes_plain_text(raw, text):
    assert plain_text(raw) == text


_TITLE = "On <i>E. coli</i> &amp; friends"
_ABSTRACT = "<p>If n<5 and m>3.</p>"


@pytest.mark.parametrize("paper", [
    parse_crossref({"title": [_TITLE], "abstract": _ABSTRACT}),
    parse_acm({"title": [_TITLE], "abstract": _ABSTRACT}),
    parse_springer({"title": _TITLE, "abstract": _ABSTRACT}),
    parse_europepmc({"title": _TITLE, "abstractText": _ABSTRACT}),
    parse_product({"mainTitle": _TITLE, "descriptions": [_ABSTRACT]}),
    parse_doaj({"bibjson": {"title": _TITLE, "abstract": _ABSTRACT}}),
    parse_search_record({"articleTitle": _TITLE, "abstract": _ABSTRACT}),
], ids=lambda paper: paper.source)
def test_titles_and_abstracts_arrive_as_plain_text(paper):
    assert paper.title == "On E. coli & friends"
    assert paper.abstract == "If n<5 and m>3."


def test_openalex_titles_arrive_as_plain_text():
    assert parse_work({"title": _TITLE}).title == "On E. coli & friends"


def test_a_springer_abstract_that_is_no_text_is_left_out():
    assert parse_springer({"title": "T", "abstract": {"p": "x"}}).abstract == ""


# --- names ------------------------------------------------------------------------------


def test_dblp_homonym_numbers_are_not_surnames():
    paper = parse_hit({"info": {
        "title": "A &amp; B.", "year": "2020",
        "authors": {"author": [{"text": "Wei Wang 0001"}, {"text": "Ann Bee"}]},
    }})
    assert paper.authors == ("Wei Wang", "Ann Bee")
    assert paper.title == "A & B"
    assert paper.bibtex_key().startswith("wang2020")


@pytest.mark.parametrize(("venue", "expected"), [
    (["ICSE", "FSE"], "ICSE, FSE"), ("ICSE", "ICSE"), ({"text": "ICSE"}, "ICSE"), (None, None),
])
def test_a_dblp_record_with_several_venues_does_not_fail_the_source(venue, expected):
    assert parse_hit({"info": {"title": "T", "venue": venue}}).venue == expected


@pytest.mark.parametrize(("author", "name"), [
    ({"fullName": "Kim JY", "firstName": "Ju Young", "lastName": "Kim"}, "Ju Young Kim"),
    ({"fullName": "Kim JY", "initials": "JY", "lastName": "Kim"}, "JY Kim"),
    ({"fullName": "van der Berg A"}, "A van der Berg"),
    ({"fullName": "Jane Smith"}, "Jane Smith"),
    ({"collectiveName": "The Study Group"}, "The Study Group"),
])
def test_europepmc_authors_end_with_the_surname(author, name):
    assert parse_europepmc({"title": "T", "authorList": {"author": [author]}}).authors == (name,)


def test_scholar_marks_and_cut_lists_are_not_text():
    page = (
        '<div id="gs_res_ccl"><div class="gs_r gs_or gs_scl"><h3 class="gs_rt">'
        '<span class="gs_ctu"><span class="gs_ct1">[CITATION]</span>'
        '<span class="gs_ct2">[C]</span></span> <span id="x">Real title</span></h3>'
        '<div class="gs_a">A Vaswani, N Parmar… - Advances in neural …, 2017 - x.y</div>'
        "</div></div>"
    )
    paper = parse_serp(page)[0]
    assert (paper.title, paper.authors) == ("Real title", ("A Vaswani", "N Parmar"))


# --- identifiers ------------------------------------------------------------------------


def _feed(*entries: str) -> str:
    body = "".join(f"<entry>{entry}</entry>" for entry in entries)
    return f'<feed xmlns="http://www.w3.org/2005/Atom">{body}</feed>'


def test_old_arxiv_identifiers_are_kept_whole():
    papers = parse_atom_feed(_feed(
        "<id>http://arxiv.org/abs/cs/0112017v1</id><title>One</title>",
        "<id>http://arxiv.org/abs/cs/0203001v2</id><title>Two</title>",
        "<id>http://arxiv.org/abs/2401.00001v3</id><title>Three</title>",
    ))
    assert [p.arxiv_id for p in papers] == ["cs/0112017", "cs/0203001", "2401.00001"]
    # Both were "cs", and one of two different papers was dropped.
    assert len(dedupe(papers)) == 3


def test_an_arxiv_error_entry_is_no_paper():
    assert parse_atom_feed(_feed(
        "<id>http://arxiv.org/api/errors#incorrect_id_format</id><title>Error</title>"
    )) == []


@pytest.mark.parametrize(("keywords", "sent"), [
    ('ti:"Attention Is All You Need"', 'ti:"Attention Is All You Need"'),
    ("graph networks", "all:graph networks"),
    ("ti: graphs", "all:ti: graphs"),
])
def test_an_arxiv_field_query_is_sent_as_it_is(keywords, sent):
    params = ArxivFetcher._build_params(Query(keywords, ("arxiv",)))  # noqa: SLF001
    assert params["search_query"] == sent


@pytest.mark.parametrize("url", [
    "https://arxiv.org/pdf/1706.03762v5.pdf", "https://arxiv.org/pdf/1706.03762.pdf",
    "https://arxiv.org/abs/1706.03762v5", "https://arxiv.org/abs/1706.03762",
])
def test_an_openaire_link_to_the_file_gives_the_identifier(url):
    paper = parse_product({"mainTitle": "t", "instances": [{"urls": [url]}]})
    assert paper.arxiv_id == "1706.03762"


def test_pubmed_finds_the_doi_beside_the_article_and_not_in_the_references():
    xml = (
        "<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID>"
        "<Article><ArticleTitle>T</ArticleTitle></Article></MedlineCitation><PubmedData>"
        "<ReferenceList><Reference><ArticleIdList>"
        '<ArticleId IdType="doi">10.1000/cited</ArticleId></ArticleIdList></Reference>'
        '</ReferenceList><ArticleIdList><ArticleId IdType="doi">10.1000/own</ArticleId>'
        "</ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>"
    )
    assert parse_efetch(xml)[0].doi == "10.1000/own"


def test_openalex_is_asked_for_as_many_papers_as_wanted():
    params = OpenAlexFetcher()._build_search_params(  # noqa: SLF001
        Query("x", ("openalex",), max_results=200)
    )
    assert params["per-page"] == "200"


# --- identity ---------------------------------------------------------------------------


def _paper(title: str, **fields) -> Paper:
    defaults = {
        "source": "bibtex", "source_id": title, "authors": ("王小明",), "year": 2020,
        "venue": None, "abstract": "", "url": "",
    }
    return Paper(title=title, **{**defaults, **fields})


def test_titles_in_other_scripts_tell_papers_apart():
    papers = [_paper("深度學習於影像辨識之研究"), _paper("自然語言處理綜述")]
    assert len({p.dedup_key() for p in papers}) == 2
    # Both were "bert" once everything but ASCII was dropped.
    assert len(dedupe([_paper("基於BERT之情感分析"), _paper("BERT模型之問答系統")])) == 2


def test_the_same_title_in_another_script_is_one_paper():
    other = _paper("深度學習 影像辨識！", source="x")
    assert len(dedupe([_paper("深度學習，影像辨識"), other])) == 1


def test_latin_titles_keep_the_key_libraries_have_stored():
    """The stored keys of existing libraries must still match."""
    accented = _paper("Étude of α-synuclein — Part II", authors=("Ada Lovelace",))
    plain = _paper("tude of synuclein part ii", authors=("Ada Lovelace",))
    assert accented.title_key() == plain.title_key()


@pytest.mark.parametrize("doi", [
    "10.1145/ABC", "doi:10.1145/abc", "https://doi.org/10.1145/abc", " 10.1145/abc ",
])
def test_every_spelling_of_a_doi_is_one_identity(doi):
    assert _paper("T", doi=doi).doi_key() == "doi:10.1145/abc"


@pytest.mark.parametrize(("author", "surname"), [
    ("Lovelace, Ada", "lovelace"), ("Ada Lovelace", "lovelace"), (", Ada", "anon"),
])
def test_the_cite_key_takes_the_surname(author, surname):
    assert _paper("Some title", authors=(author,)).bibtex_key() == f"{surname}2020some"
