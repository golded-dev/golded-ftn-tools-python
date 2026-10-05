# Planning-material checks

2026-10-05. No CLI is implemented or tested.

- Compared specification and JSON fields with core models and writer-session signatures.
- Parsed JSON examples and mapped them to public OutgoingMessage/ControlLine
  models. In temporary bases, three inputs were accepted and read back with
  MSG/JAM/Hudson; the timezone-aware Squish example was accepted and read back.
  This checks examples, not independent binary interoperability.
- Date checks exposed different timezone requirements; corrected JSON specification
  and examples. No changes to existing Python packages.
- Local link checks covered Markdown links, HTML IDs, anchors and copy targets.
  HTML has exactly one current-page marker. JSON and JSONL examples parse correctly.
- Safari desktop: visually checked shell, masthead, fonts, section jumps, code
  panels and syntax colors. Copy code changed to Copied on activation.
  Clipboard contents were not inspected separately.
- Embedded example JSON matches `examples/message.json` exactly. Both HTML pages
  have unique IDs and valid local links, section anchors and copy targets; all
  implementation-plan sections are present in `plan.html`.
- Safari desktop: clicking 03 Contract moves the yellow section marker to Contract
  at the bottom of the home page. The Implementation plan link opens `plan.html`
  with the shared design and its own section navigation.
- Ruff check and format checks passed for `scripts/build_reading_pages.py`.
- Specification and JSON contract now have HTML reading copies generated from
  their Markdown sources. Local-link, unique-ID, anchor, copy-target and current-page
  checks passed for all four HTML pages. Safari navigation opened both new HTML
  pages; the JSON contract layout and selected-page marker were visually checked.
- Mobile/no-JS/print have CSS and fallback code but have not been visually checked.
  No claim of full browser acceptance or Pages publication.
- English translation: checked visible HTML text and local document links.
  The previous Git history was removed and a fresh local repository initialized.
  No remote is configured; the GitHub repository was deleted by Odinn.

Implementation must test SPEC acceptance criteria separately.

Opus scope update: specification, JSON contract and plan include the planned MSG
writer prerequisite. Regenerated all HTML reading copies and checked local links,
unique IDs, anchors and copy targets. No Opus writer was implemented or tested.

TOC scroll fix: reproduced in Safari on the long plan page. Upward scrolling
over a sidebar already at its top left the document scroll value at 0.6481752.
Changed sidebar overscroll behavior from contain to auto and regenerated all
four pages. Repeating upward scrolling over the sidebar reached document scroll
value 0 and showed the masthead. Recorded the rule in DESIGN.md.
