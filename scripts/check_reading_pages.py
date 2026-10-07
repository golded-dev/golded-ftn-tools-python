"""Check the public manual: IDs, navigation, local links and embedded examples."""

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PAGES = (
    "index.html",
    "create.html",
    "write.html",
    "read.html",
    "export.html",
    "decode.html",
    "repair.html",
    "heads.html",
    "catalog.html",
)


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
        if tag == "code" and attributes.get("id") == "write-message-text":
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
        text = (ROOT / name).read_text(encoding="utf-8").lower()
        for banned in (
            "specification.html",
            "plan.html",
            "docs/spec.md",
            "docs/plan.md",
        ):
            assert banned not in text, (name, banned)
    source = (ROOT / "examples/message.json").read_text(encoding="utf-8")
    if not source.endswith("\n"):
        source += "\n"
    assert pages["write.html"].example == source
    print(
        "Nine manual pages: unique IDs, local links, copy targets, "
        "page markers and no spec/plan links passed."
    )
    print("Embedded message.json matches its source. No visual/browser check was run.")


if __name__ == "__main__":
    main()
