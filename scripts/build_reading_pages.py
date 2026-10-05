"""Rebuild reading copies: uv run --with markdown --with pygments scripts/build_reading_pages.py."""

import html
import re
from pathlib import Path

import markdown
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import JsonLexer, get_lexer_by_name

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    home_path = ROOT / "index.html"
    home = home_path.read_text(encoding="utf-8")
    source = (ROOT / "examples/message.json").read_text(encoding="utf-8")
    highlighted = highlight(source, JsonLexer(), HtmlFormatter(nowrap=True))
    pane = (
        '<div class="code-pane" id="example-message"><div class="code-head">'
        "<span>message.json · example input / MSG, JAM, Hudson</span>"
        '<button type="button" data-copy="example-json" hidden>Copy code</button>'
        '</div><pre><code id="example-json">' + highlighted + "</code></pre></div>"
    )
    old = '<p><a href="examples/message.json">See the example message →</a></p>'
    if old in home:
        home = home.replace(old, pane)
    else:
        home, count = re.subn(
            r'<div class="code-pane" id="example-message">.*?</code></pre></div>',
            lambda _: pane,
            home,
            flags=re.DOTALL,
        )
        assert count == 1, "Expected one example message panel"
    home = home.replace('href="docs/PLAN.md"', 'href="plan.html"')
    home = home.replace("Implementation plan ↗", "Implementation plan →")
    styles = ".nt{color:#8fb2ff}.p{color:#ff6868}@media print{.nt,.p{color:black}}"
    if styles not in home:
        home = home.replace("</style>", styles + "</style>", 1)
    home = home.replace('href="docs/SPEC.md"', 'href="specification.html"')
    home = home.replace('href="docs/JSON.md"', 'href="json-contract.html"')
    home = home.replace("Specification ↗", "Specification →")
    home = home.replace("JSON contract ↗", "JSON contract →")
    home_path.write_text(home, encoding="utf-8")

    pages = [
        (
            "SPEC",
            "specification.html",
            "Specification",
            "Small commands. Clear boundaries.",
        ),
        (
            "JSON",
            "json-contract.html",
            "JSON contract",
            "Old messages. Structured input.",
        ),
        (
            "PLAN",
            "plan.html",
            "Implementation plan",
            "Small commands. A concrete plan.",
        ),
    ]
    destinations = {source + ".md": target for source, target, _, _ in pages}
    for source, target, title, eyebrow in pages:
        text = (ROOT / "docs" / (source + ".md")).read_text(encoding="utf-8")
        parts = re.split(r"^## (.+)$", text, flags=re.MULTILINE)
        sections = [("overview", "Overview", re.sub(r"^# [^\n]+\n", "", parts[0]))]
        for offset in range(1, len(parts), 2):
            heading = parts[offset]
            slug = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")
            sections.append((slug, heading, parts[offset + 1]))
        article = (
            '<main><div class="eyebrow">'
            + html.escape(eyebrow)
            + "</div>"
            + "<h1>"
            + html.escape(title)
            + '</h1><p class="intro">'
            + 'A reading copy of <a href="docs/'
            + source
            + '.md">the Markdown source</a>.'
            + " Proposed scope — no CLI has been implemented.</p>"
        )
        navigation = []
        for number, (slug, heading, content) in enumerate(sections):
            display = re.sub(r"^\d+\. ", "", heading)
            rendered = markdown.markdown(content, extensions=["tables", "fenced_code"])

            def code_panel(match: re.Match[str], section_number: int = number) -> str:
                language = match[1] or "text"
                code = html.unescape(match[2])
                highlighted_code = highlight(
                    code, get_lexer_by_name(language), HtmlFormatter(nowrap=True)
                )
                code_id = f"code-{section_number}-{match.start()}"
                return (
                    '<div class="code-pane"><div class="code-head"><span>'
                    + html.escape(language)
                    + '</span><button type="button" data-copy="'
                    + code_id
                    + '" hidden>Copy code</button></div><pre><code id="'
                    + code_id
                    + '">'
                    + highlighted_code
                    + "</code></pre></div>"
                )

            rendered = re.sub(
                r'<pre><code(?: class="language-([^"]+)")?>(.*?)</code></pre>',
                code_panel,
                rendered,
                flags=re.DOTALL,
            )
            for origin, destination in destinations.items():
                rendered = rendered.replace(
                    'href="' + origin + '"', 'href="' + destination + '"'
                )
            rendered = rendered.replace("<table>", '<div class="table-wrap"><table>')
            rendered = rendered.replace("</table>", "</table></div>")
            navigation.append(
                f'<a href="#{slug}"><span class="num">{number:02d}</span>'
                f"{html.escape(display)}</a>"
            )
            article += (
                f'<section class="guide-section" id="{slug}"><div class="section-title">'
                f"<span>{number:02d}</span><h2>{html.escape(display)}</h2></div>"
                + rendered
                + "</section>"
            )
        article += (
            '<div class="next"><a href="index.html">← Back to the tool</a>'
            + '<a href="docs/'
            + source
            + '.md">Markdown source →</a></div></main>'
        )
        page_links = '<a href="index.html">Home</a>'
        for _, destination, label, _ in pages:
            current = ' aria-current="page"' if destination == target else ""
            page_links += f'<a href="{destination}"{current}>{label}</a>'
        aside = (
            '<aside><div class="sidebar"><nav class="page-nav" aria-label="Project">'
            + page_links
            + '</nav><details class="contents" open><summary>On this page</summary>'
            + '<nav class="nav" aria-label="Sections">'
            + "".join(navigation)
            + '</nav></details><nav class="page-nav" aria-label="Libraries">'
            + '<a href="https://golded-dev.github.io/golded-ftn-python-docs/">'
            + 'Python library docs ↗</a></nav><div class="aside-note">Proposed contract.<br>'
            + "No implementation.<br>No release.</div></div></aside>"
        )
        page = re.sub(
            r"<aside>.*?</main>",
            lambda _, replacement=aside + article: replacement,
            home,
            flags=re.DOTALL,
        )
        page = re.sub(
            r"<title>.*?</title>",
            "<title>golded-ftn-tools · " + title + "</title>",
            page,
        )
        page = re.sub(
            r'<meta name="description" content="[^"]*"',
            '<meta name="description" content="GoldED FTN tools: '
            + title
            + '. Proposed CLI documentation."',
            page,
        )
        page = page.replace(
            'class="logo-mark" href="#overview"', 'class="logo-mark" href="index.html"'
        )
        (ROOT / target).write_text(page, encoding="utf-8")


if __name__ == "__main__":
    main()
