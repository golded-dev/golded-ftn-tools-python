# GoldED FTN tools design

Read this file before editing the HTML page. The design follows
[GoldED for Python DESIGN.md](https://github.com/golded-dev/golded-ftn-python-docs/blob/main/DESIGN.md).
This is a standalone tool landing page, not a copy of the documentation navigation.

## Identity and tokens

Dark, rectangular, quiet and precise. Yellow GoldED logo, red masthead rules,
blue shell and status bar. No gradients, rounded cards or decorative animation.

| Role | Color |
| --- | --- |
| Canvas | #05070B |
| Reading surface | #0B0F18 |
| Raised surface | #101624 |
| Primary text | #F5F7FF |
| Secondary text | #BCC5D9 |
| Shell | #4F6DFF |
| Status bar | #2D47C7 |
| Identity/sections/strings | #FFE45A |
| Links/keywords | #8FB2FF |
| Dividers | #273149 |
| Masthead/operators/terminal flags | #FF6868 |
| Syntax numbers/constants | #55FF55 |

IBM Plex Sans for text; IBM Plex Mono for labels, numbers and code. Include the
font license. The standalone HTML embeds fonts and logo; rendering needs no
network requests. External destination links remain ordinary links.

## Shell and typography

1260px maximum page width, 40px vertical margin, 24px horizontal padding.
Masthead: red 1px top/bottom rules, 7px vertical padding, 24px gap before shell.
Logo: 210px desktop width, existing optical offset and right-aligned subtitle.
Square shell with a 1px blue frame. Columns: 230px sidebar + minmax(0,1fr).
Main padding: 42px 48px 36px. Footer sits outside the shell with 18px vertical
padding. Use the 4/8/12/16/24/32/48/64 scale for new spacing.

Body/intro: 17px/1.65; section text: 15px/1.65. H1: 44px/1.1, weight 600;
h2: 24px/1.2, weight 500. Yellow section numbers: 20px/1.2, weight 500,
non-shrinking, baseline-aligned, 12px gap. Eyebrow: “Old messages. New blast radius.”
Balance headings; use pretty paragraph wrapping and macOS font smoothing.

## Code and navigation

All blocks use code-pane, code-head, clear labels and a Copy code button with a
unique target ID. Syntax highlighting follows the palette, including terminal
examples. Copy plain text with original whitespace. Hide buttons without JS
and in print. Inline code uses a raised surface, 2px/4px padding, 2px corners
and natural wrapping.

Sidebar: Home, Specification, JSON contract and Implementation plan as HTML
reading copies, then native On this page details and a library-docs link. The
landing page sections are Overview 00, Pipes 01, Fixtures 02 and Contract 03.
The plan has its own numbered section index, starting at Overview 00. Exactly one aria-current=page. Section tracking may
add aria-current=location; it is distinct from page state.
Links/disclosure have >=40px height. Focus-visible uses a yellow 2px outline.
Hover only for fine pointers with hover support. Navigation must work without JS.

## Mobile and print

At <=800px: one column, sidebar above main, 20px page margin/padding, main
28px/20px, H1 34px, logo 160px, subtitle 10px, code 12px. Two-column navigation,
no sticky/scrolling sidebar, no sidebar note. On this page starts collapsed
with JS, expanded without it. Footer wraps. Section numbers stay 20px. Only
code/table containers may scroll horizontally; the document must fit the viewport.

Print: white surface, black text/syntax; no sidebar/masthead/footer/copy/skip.
Remove shell frame and main padding, wrap code and keep panels together where possible.

## Copy and verification

Public-facing copy is English. The page may sell the idea but must clearly show
“Implemented locally / not released” while public installation is unavailable.
Command blocks show working local workflows. Public installation claims require
released dependencies and CLI distribution verification.
A local Git repository does not authorize a remote, release or Pages deployment.

Check desktop/mobile in Safari, keyboard focus, disclosure, anchors, copy, no-JS,
print and local links/HTML structure. Report only what was actually checked.

The landing page embeds the example JSON in a highlighted, copyable code panel.
Document links open `specification.html`, `json-contract.html` and `plan.html`;
the files in `docs/` remain the editable Markdown sources. Rebuild
all reading copies with `scripts/build_reading_pages.py`. They share the shell,
fonts, palette, navigation behavior and print styles.

The tool identity is **FTNT💥**; the executable is `ftnt`. The package remains
`golded-ftn-tools`, with import name `golded_ftn_tools`. Use the explosion in
branding, never in executable names or command output.

Desktop sidebar scrolling must hand off to document scrolling at either end.
Use normal scroll chaining; do not trap wheel/trackpad input with
`overscroll-behavior-y: contain`. Verify scrolling upward over the TOC can
return the document to the masthead.
