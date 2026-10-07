"""Check generated reading-copy links, IDs, navigation and embedded JSON."""

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PAGES = ("index.html", "specification.html", "json-contract.html", "plan.html")


class Page(HTMLParser):
    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.links: list[str] = []
        self.copies: list[str] = []
        self.current = 0
        self.example = ""
        self._example = False
        self.feed(source)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if identity := attributes.get("id"):
            assert identity not in self.ids, f"Duplicate ID: {identity}"
            self.ids.add(identity)
        if link := attributes.get("href"):
            self.links.append(link)
        if target := attributes.get("data-copy"):
            self.copies.append(target)
        if attributes.get("aria-current") == "page":
            self.current += 1
        if tag == "code" and attributes.get("id") == "example-json":
            self._example = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "code":
            self._example = False

    def handle_data(self, data: str) -> None:
        if self._example:
            self.example += data


def main() -> None:
    pages = {name: Page((ROOT / name).read_text(encoding="utf-8")) for name in PAGES}
    for name, page in pages.items():
        assert page.current == 1, name
        assert all(copy in page.ids for copy in page.copies), name
        for link in page.links:
            target = urlsplit(link)
            if target.scheme or target.netloc:
                continue
            path = unquote(target.path) or name
            assert (ROOT / path).is_file(), (name, link)
            if target.fragment and path in pages:
                assert unquote(target.fragment) in pages[path].ids, (name, link)
    assert pages["index.html"].example == (ROOT / "examples/message.json").read_text()
    print(
        "Four HTML pages: unique IDs, local links/anchors, "
        "copy targets and page markers passed."
    )
    print("Embedded example JSON matches its source. No visual/browser check was run.")


if __name__ == "__main__":
    main()
