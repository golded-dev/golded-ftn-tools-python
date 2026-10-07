"""Build the public manual: a front page and one page per command.

The pages stand alone. They do not link to the specification or the plan.
"""

from __future__ import annotations

import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RETIRED = ("specification.html", "json-contract.html", "plan.html")

TOOLS = (
    ("create", "Create an empty base"),
    ("write", "Append messages from JSON"),
    ("read", "Read one message"),
    ("export", "Stream a base as JSONL"),
    ("decode", "Decode a charset to UTF-8"),
    ("repair", "Repair UTF-8 mojibake"),
    ("heads", "Index a base without bodies"),
    ("catalog", "Describe this binary"),
)

SCRIPT = """
<script>
const contents=document.querySelector('.contents');
if(contents && window.matchMedia('(max-width:800px)').matches) contents.open=false;
for(const button of document.querySelectorAll('[data-copy]')){
  button.hidden=false;
  button.addEventListener('click', async () => {
    const node=document.getElementById(button.dataset.copy);
    const text=node.textContent;
    try {
      if(navigator.clipboard && window.isSecureContext){
        await navigator.clipboard.writeText(text);
      } else {
        const field=document.createElement('textarea');
        field.value=text;
        field.style.position='fixed';
        field.style.opacity='0';
        document.body.append(field);
        field.select();
        const ok=document.execCommand('copy');
        field.remove();
        button.focus();
        if(!ok) throw new Error('copy');
      }
      button.textContent='Copied';
    } catch {
      button.textContent='Select code';
      const range=document.createRange();
      range.selectNodeContents(node);
      const selection=window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
    }
    setTimeout(() => button.textContent='Copy code', 1800);
  });
}
const links=[...document.querySelectorAll('.nav a')];
const sections=[...document.querySelectorAll('main section')];
function markSection(id){
  for(const link of links){
    if(link.hash === '#' + id) link.setAttribute('aria-current','location');
    else link.removeAttribute('aria-current');
  }
}
function track(){
  if(!sections.length) return;
  let current=sections[0].id;
  for(const section of sections){
    if(section.getBoundingClientRect().top <= 120) current=section.id;
  }
  const page=document.scrollingElement;
  if(page.scrollHeight > page.clientHeight &&
     Math.ceil(page.scrollTop + page.clientHeight) >= page.scrollHeight - 2){
    current=sections[sections.length - 1].id;
  }
  markSection(current);
}
window.addEventListener('scroll', track, {passive:true});
window.addEventListener('resize', track);
window.addEventListener('hashchange', () => {
  const selected=links.find(link => link.hash === window.location.hash);
  if(selected) markSection(selected.hash.slice(1));
  else track();
});
track();
</script>
"""


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def code_pane(pane_id: str, label: str, text: str) -> str:
    return (
        f'<div class="code-pane" id="{esc(pane_id)}"><div class="code-head">'
        f"<span>{esc(label)}</span>"
        f'<button type="button" data-copy="{esc(pane_id)}-text" hidden>Copy code</button>'
        f'</div><pre><code id="{esc(pane_id)}-text">{esc(text)}</code></pre></div>'
    )


def section(slug: str, number: str, title: str, body: str) -> str:
    return (
        f'<section class="guide-section" id="{esc(slug)}">'
        f'<div class="section-title"><span>{esc(number)}</span><h2>{esc(title)}</h2></div>'
        f"{body}</section>"
    )


def shell(
    filename: str,
    title: str,
    description: str,
    eyebrow: str,
    command: str,
    heading: str,
    lead: str,
    sections: list[tuple[str, str, str, str]],
) -> str:
    current = "index.html" if filename == "index.html" else filename
    nav = ['<nav class="page-nav" aria-label="Manual">']
    home_current = ' aria-current="page"' if current == "index.html" else ""
    nav.append(f'<a href="index.html"{home_current}>Home</a>')
    for name, _label in TOOLS:
        marker = ' aria-current="page"' if current == f"{name}.html" else ""
        nav.append(f'<a href="{name}.html"{marker}>{name}</a>')
    nav.append("</nav>")
    contents = ['<details class="contents" open><summary>On this page</summary>']
    contents.append('<nav class="nav" aria-label="Sections">')
    for slug, number, heading_text, _body in sections:
        contents.append(
            f'<a href="#{esc(slug)}"><span class="num">{esc(number)}</span>{esc(heading_text)}</a>'
        )
    contents.append("</nav></details>")
    main = [
        "<main>",
        f'<p class="eyebrow">{esc(eyebrow)}</p>',
        f'<p class="command">{esc(command)}</p>',
        f"<h1>{esc(heading)}</h1>",
        f'<p class="hero-lead">{lead}</p>',
    ]
    main.extend(
        section(slug, number, heading_text, body)
        for slug, number, heading_text, body in sections
    )
    main.append("</main>")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{esc(description)}">
<title>{esc(title)}</title>
<link rel="stylesheet" href="assets/manual.css">
</head>
<body>
<a class="skip" href="#{esc(sections[0][0])}">Skip to content</a>
<div class="page">
<header class="masthead">
<a class="logo-mark" href="index.html" aria-label="FTNT home">
<img class="logo" src="assets/golded-logo.png" width="600" height="205" alt="GoldED">
<span class="logo-subtitle" aria-hidden="true">for the shell</span>
</a>
<div><span>FTNT💥</span><a href="https://golded-dev.github.io/golded-ftn-python-docs/">Library docs ↗</a></div>
</header>
<div class="shell">
<div class="bar"><span>GOLDED / FTN TOOLS</span><span>LOCAL IMPLEMENTATION · NOT RELEASED · PYTHON 3.12+</span></div>
<div class="layout">
<aside><div class="sidebar">
{"".join(nav)}
{"".join(contents)}
</div></aside>
{"".join(main)}
</div></div>
<footer><span>GoldED FTN tools / GoldED.dev</span><span>LOCAL IMPLEMENTATION · MIT LICENSE</span></footer>
</div>
{SCRIPT}
</body>
</html>
"""


def index_page() -> str:
    tools = "".join(
        f'<li><a href="{name}.html"><code>{name}</code></a> — {esc(label)}</li>'
        for name, label in TOOLS
    )
    sections = [
        (
            "install",
            "00",
            "Install",
            "<p>FTNT is implemented locally and is not on PyPI yet. From a checkout:</p>"
            + code_pane(
                "install-local",
                "local checkout",
                "uv sync --locked\nuv run ftnt --help\n",
            )
            + "<p>The executable is <code>ftnt</code>. The package name is "
            "<code>golded-ftn-tools</code>. Development resolves the format "
            "packages from sibling checkouts. A public install waits until this "
            "package itself is published.</p>",
        ),
        (
            "shared",
            "01",
            "Shared rules",
            '<ul class="contract-list">'
            "<li><strong>Close the base first.</strong> Stop GoldED and any other "
            "program using the base. Concurrent use is not supported.</li>"
            "<li><strong>Name the format.</strong> <code>create</code>, <code>write</code>, "
            "<code>read</code> and <code>export</code> require "
            "<code>--format msg</code>, <code>opus</code>, <code>jam</code>, "
            "<code>squish</code> or <code>hudson</code>.</li>"
            "<li><strong>Hudson boards.</strong> <code>write</code> and <code>read</code> "
            "require <code>--board</code> from 1 to 200. <code>export</code> accepts "
            "the same option to keep one board.</li>"
            "<li><strong>JSON on stdout, diagnostics on stderr.</strong> "
            "<code>--debug</code> adds a traceback. <code>--version</code> prints "
            "the program version.</li>"
            "<li><strong>Paths in JSON are resolved absolute paths.</strong> "
            "Do not publish output if the path itself is private.</li>"
            "</ul>"
            '<div class="table-wrap"><table><thead><tr><th>Exit</th><th>Meaning</th></tr></thead><tbody>'
            "<tr><td>0</td><td>The command finished. For <code>export --archive</code>, no reader issues were reported.</td></tr>"
            "<tr><td>2</td><td>The input was rejected before or during a write. Nothing new was committed when the message says <code>committed 0</code>.</td></tr>"
            "<tr><td>3</td><td>The base or message was missing, or <code>create</code> found an existing base.</td></tr>"
            "<tr><td>4</td><td>A format parser or writer rejected the message.</td></tr>"
            "<tr><td>5</td><td>The lock timed out or the revision conflicted.</td></tr>"
            "<tr><td>6</td><td>The filesystem failed, or a writer rolled back.</td></tr>"
            "<tr><td>7</td><td><code>export --archive</code> wrote every message it could and reported at least one reader issue.</td></tr>"
            "<tr><td>130</td><td>Interrupted.</td></tr>"
            "<tr><td>141</td><td>The next program closed the pipe. On Windows this is exit 6. A write receipt can already have been committed.</td></tr>"
            "</tbody></table></div>",
        ),
        (
            "commands",
            "02",
            "Commands",
            f'<ul class="contract-list">{tools}</ul>'
            "<p><code>msg</code> selects an FTSC-style <code>.MSG</code> base. "
            "<code>opus</code> selects the Opus header variant in the same file layout. "
            "JAM, Squish and Hudson use their own base files. The format packages "
            "own locks, encoding and rollback.</p>",
        ),
    ]
    return shell(
        "index.html",
        "FTNT · GoldED message-base tools",
        "FTNT is a command-line toolkit for FTN message bases, JSON fixtures and text filters.",
        "Old messages. New blast radius.",
        "ftnt",
        "Six commands for message bases.",
        "Six commands for FidoNet message bases. Create a base, append JSON, "
        "read one message, export a stream, or filter text through a charset.",
        sections,
    )


def create_page() -> str:
    sections = [
        (
            "usage",
            "00",
            "Usage",
            "<p><code>ftnt create BASE --format FORMAT</code></p>"
            "<p>Creates an empty base at <code>BASE</code>. The path is the base "
            "the format package expects: a <code>.MSG</code> directory for "
            "<code>msg</code> and <code>opus</code>, and the JAM, Squish or Hudson "
            "base path for the other formats. Hudson <code>create</code> does not "
            "take <code>--board</code>; boards are chosen when you write.</p>"
            + code_pane(
                "create-jam",
                "create a JAM base",
                "ftnt create ./fixtures/general --format jam\n",
            )
            + "<p>Stdout is one JSON object. <code>base</code> is the resolved path.</p>"
            + code_pane(
                "create-result",
                "create_result",
                '{"schema_version":1,"type":"create_result","format":"jam","base":"/resolved/fixtures/general"}\n',
            ),
        ),
        (
            "failures",
            "01",
            "Failures",
            "<p>An existing base fails with exit 3. An unknown path problem from "
            "the filesystem fails with exit 6. <code>--format</code> is required "
            "and must be one of <code>msg</code>, <code>opus</code>, <code>jam</code>, "
            "<code>squish</code> or <code>hudson</code>.</p>",
        ),
    ]
    return shell(
        "create.html",
        "ftnt create",
        "Create an empty FTN message base with ftnt create.",
        "Empty files. Nothing imported.",
        "ftnt create",
        "Create an empty base.",
        "Make a new message base in one format. The command does not import messages.",
        sections,
    )


def write_page() -> str:
    message = (ROOT / "examples/message.json").read_text(encoding="utf-8")
    if not message.endswith("\n"):
        message += "\n"
    squish = (ROOT / "examples/message-squish.json").read_text(encoding="utf-8")
    if not squish.endswith("\n"):
        squish += "\n"
    sections = [
        (
            "usage",
            "00",
            "Usage",
            "<p><code>ftnt write BASE --format FORMAT [options]</code></p>"
            "<p>Reads one JSON object from stdin and appends it. "
            "<code>--jsonl</code> reads one JSON value per line and appends each "
            "value as its own message. Structural checks finish before the writer "
            "opens. Each successful append commits on its own and prints a receipt.</p>"
            + code_pane(
                "write-one",
                "append one message",
                "ftnt write ./fixtures/general --format jam < examples/message.json\n",
            )
            + code_pane(
                "write-jsonl",
                "append a batch",
                "ftnt write ./fixtures/general --format jam --jsonl < examples/messages.jsonl\n",
            )
            + '<p>Options:</p><div class="table-wrap"><table><thead><tr>'
            "<th>Option</th><th>Default</th><th>Meaning</th></tr></thead><tbody>"
            "<tr><td><code>--jsonl</code></td><td>off</td><td>Read a JSONL batch. Without it, the whole stdin value is one object.</td></tr>"
            "<tr><td><code>--encoding</code></td><td><code>CP850</code></td><td>Charset the writer stores.</td></tr>"
            "<tr><td><code>--lock-timeout</code></td><td><code>5</code></td><td>Seconds to wait for the lock. A finite number, zero or greater.</td></tr>"
            "<tr><td><code>--board</code></td><td>required for Hudson</td><td>Hudson board, 1..200. Rejected for every other format.</td></tr>"
            "</tbody></table></div>",
        ),
        (
            "input",
            "01",
            "Input object",
            "<p>Required strings: <code>from_name</code>, <code>to_name</code>, "
            "<code>subject</code>, <code>body_text</code>. Empty strings pass the "
            "structural check; the format writer may still reject them.</p>"
            '<div class="table-wrap"><table><thead><tr><th>Field</th><th>JSON</th><th>When omitted</th></tr></thead><tbody>'
            "<tr><td><code>external_id</code></td><td>string or null</td><td>null. This is an external MSGID, not a message number in the base.</td></tr>"
            "<tr><td><code>from_address</code>, <code>to_address</code></td><td>FTN address string or null</td><td>null. Example: <code>2:236/77.1@fidonet</code>. Abbreviated forms are not expanded.</td></tr>"
            "<tr><td><code>posted_at</code></td><td>datetime string or null</td><td>null. Omitted dates are not filled with the current time.</td></tr>"
            "<tr><td><code>attributes_raw</code></td><td>integer ≥ 0 or null</td><td>null</td></tr>"
            "<tr><td><code>control_lines</code></td><td>array of objects</td><td>empty. Each object needs string <code>name</code> and <code>value</code>. Optional <code>raw</code> defaults to an empty string.</td></tr>"
            "<tr><td><code>reply_to_msgno</code>, <code>reply1st_msgno</code>, <code>reply_next_msgno</code></td><td>integer ≥ 0 or null</td><td>null</td></tr>"
            "<tr><td><code>reply_list</code></td><td>array of integers ≥ 0</td><td>empty</td></tr>"
            "<tr><td><code>routing_seen_by</code>, <code>routing_path</code></td><td>array of strings</td><td>empty. Order and duplicates are kept.</td></tr>"
            "</tbody></table></div>"
            "<p>Unknown keys, duplicate keys, NaN, Infinity, a BOM and invalid UTF-8 "
            "are rejected. Booleans are not integers. <code>msgno</code>, "
            "<code>identity</code>, <code>revision</code> and export envelopes are "
            "not write input. Append assigns the message number. There is no "
            "automatic reply-link resolver.</p>"
            + code_pane("write-message", "examples/message.json", message)
            + "<p><code>posted_at</code> is <code>YYYY-MM-DDTHH:MM:SS</code> with an "
            "optional <code>Z</code> or numeric UTC offset, and no microseconds. "
            "Invalid calendar dates are rejected. The timezone rule depends on the format:</p>"
            '<div class="table-wrap"><table><thead><tr><th>Format</th><th>Date</th></tr></thead><tbody>'
            "<tr><td><code>msg</code></td><td>Naive. No timezone.</td></tr>"
            "<tr><td><code>opus</code></td><td>Naive, years 1980–2069, even seconds. Odd seconds are rejected. GoldED interoperability for Opus writes is still unverified.</td></tr>"
            "<tr><td><code>jam</code></td><td>Naive, read as UTC, or timezone-aware.</td></tr>"
            "<tr><td><code>squish</code></td><td>Timezone-aware. The writer converts it to UTC.</td></tr>"
            "<tr><td><code>hudson</code></td><td>Naive. No timezone.</td></tr>"
            "</tbody></table></div>"
            + code_pane("write-squish", "examples/message-squish.json", squish),
        ),
        (
            "receipts",
            "02",
            "Receipts and reruns",
            "<p>A receipt is one JSON object per committed append:</p>"
            + code_pane(
                "write-result",
                "write_result",
                '{"schema_version":1,"type":"write_result","input_record":1,'
                '"identity":{"format":"jam","base":"/resolved/fixtures/general","msgno":1,"board":null},'
                '"revision":{"identity":{"format":"jam","base":"/resolved/fixtures/general","msgno":1,"board":null},'
                '"location":[0,0],"digest":"opaque"}}\n',
            )
            + "<p><code>input_record</code> counts from 1 in the batch. "
            "<code>identity</code> and <code>revision</code> describe what the "
            "writer stored. Treat <code>location</code> and <code>digest</code> "
            "as opaque. They belong to that base, not to a portable id.</p>"
            "<p>If record 3 fails after record 1 and 2 committed, those two "
            "messages stay. Stderr names the failing record and the committed "
            "count. A broken pipe can hide a receipt for a message that is "
            "already stored. Running the same batch again can append duplicates.</p>",
        ),
    ]
    return shell(
        "write.html",
        "ftnt write",
        "Append JSON messages to an FTN base with ftnt write.",
        "JSON in. One commit each.",
        "ftnt write",
        "Append messages from JSON.",
        "One object, or a JSONL batch. Validation finishes before the first append.",
        sections,
    )


def read_page() -> str:
    sections = [
        (
            "usage",
            "00",
            "Usage",
            "<p><code>ftnt read BASE MSGNO --format FORMAT [options]</code></p>"
            "<p><code>MSGNO</code> is the message number in that base, starting at 1. "
            "The default output is one JSON envelope on stdout.</p>"
            + code_pane(
                "read-one",
                "read message 1",
                "ftnt read ./fixtures/general 1 --format jam\n",
            )
            + '<div class="table-wrap"><table><thead><tr><th>Option</th><th>Meaning</th></tr></thead><tbody>'
            "<tr><td><code>--body</code></td><td>Write <code>body_text</code> only. No added newline. Controls that the reader left in the body stay there.</td></tr>"
            "<tr><td><code>--revision</code></td><td>Add writer <code>identity</code> and <code>revision</code> to the envelope. Mutually exclusive with <code>--body</code>.</td></tr>"
            "<tr><td><code>--fallback-charset</code></td><td>Charset when the message does not declare one. Default <code>CP850</code>.</td></tr>"
            "<tr><td><code>--lock-timeout</code></td><td>Used with <code>--revision</code>. Default 5 seconds.</td></tr>"
            "<tr><td><code>--board</code></td><td>Required for Hudson, 1..200. The number must match the message board.</td></tr>"
            "</tbody></table></div>",
        ),
        (
            "envelope",
            "01",
            "Envelope",
            "<p><code>message</code> contains the reader fields, including nulls. "
            "Dates use ISO 8601. Addresses stay reader strings. "
            "<code>source.base</code> is the resolved base path. "
            "<code>source.board</code> is null except for Hudson, where it is the board byte.</p>"
            + code_pane(
                "read-envelope",
                "message envelope",
                '{\n  "schema_version": 1,\n  "type": "message",\n'
                '  "source": {"format": "jam", "base": "/resolved/fixtures/general", "board": null},\n'
                '  "message": {"msgno": 1, "from_name": "Alice", "to_name": "Bob",'
                ' "subject": "Encoding fixture: æøå", "body_text": "First line.\\nSecond line.",'
                ' "attributes_raw": 0}\n}\n',
            )
            + "<p>A missing number exits 3. Text is not repaired on the way out. "
            'Use <a href="repair.html"><code>repair</code></a> on purpose when you want that heuristic.</p>',
        ),
    ]
    return shell(
        "read.html",
        "ftnt read",
        "Read one message from an FTN base with ftnt read.",
        "One number. The whole message.",
        "ftnt read",
        "Read one message.",
        "JSON for the whole message, or the body text alone.",
        sections,
    )


def export_page() -> str:
    sections = [
        (
            "usage",
            "00",
            "Usage",
            "<p><code>ftnt export BASE --format FORMAT [options]</code></p>"
            "<p>Writes one JSON envelope per message on stdout. The shape matches "
            '<a href="read.html"><code>read</code></a> without '
            "<code>--revision</code>. This is a data export, not a byte-for-byte backup. "
            "Raw metadata outside the reader model is absent.</p>"
            + code_pane(
                "export-pipe",
                "filter subjects",
                "ftnt export ./fixtures/general --format jam \\\n"
                "  | jq -c 'select(.message.subject | contains(\"fixture\"))'\n",
            )
            + '<div class="table-wrap"><table><thead><tr><th>Option</th><th>Meaning</th></tr></thead><tbody>'
            "<tr><td><code>--archive</code></td><td>Keep going after reader issues. Each issue is a JSON object on stderr. Exit 7 when any issue was reported, otherwise 0.</td></tr>"
            "<tr><td><code>--board</code></td><td>Optional Hudson filter, 1..200. Other formats reject it.</td></tr>"
            "<tr><td><code>--fallback-charset</code></td><td>Default <code>CP850</code>.</td></tr>"
            "</tbody></table></div>",
        ),
        (
            "partial",
            "01",
            "Partial output",
            "<p>Readers may buffer the base. If the command fails, stdout can "
            "already contain earlier messages. Check the exit status before "
            "treating the stream as complete. Without <code>--archive</code>, "
            "a reader problem stops the command instead of being collected as an issue.</p>"
            + code_pane(
                "export-issue",
                "reader_issue on stderr",
                '{"schema_version":1,"type":"reader_issue","issue":{}}\n',
            )
            + "<p>The <code>issue</code> object is the reader’s own report.</p>",
        ),
    ]
    return shell(
        "export.html",
        "ftnt export",
        "Export an FTN message base as JSONL with ftnt export.",
        "Every message. Not a byte copy.",
        "ftnt export",
        "Stream a base as JSONL.",
        "One envelope per message. Check the exit status before trusting a partial stream.",
        sections,
    )


def decode_page() -> str:
    sections = [
        (
            "usage",
            "00",
            "Usage",
            "<p><code>ftnt decode --charset CHARSET</code></p>"
            "<p>Reads all of stdin into memory and writes UTF-8 text to stdout. "
            "Decoding is strict. Line endings and trailing nulls are preserved. "
            "<code>CHARSET</code> is a core charset alias, for example "
            "<code>IBMPC</code>, <code>CP850</code> or <code>LATIN-1</code>.</p>"
            + code_pane(
                "decode-example",
                "decode a legacy file",
                "ftnt decode --charset IBMPC < old-text.txt\n",
            ),
        ),
        (
            "failures",
            "01",
            "Failures",
            "<p>An unknown alias or a byte that is illegal in that charset fails "
            "the command. The filter does not guess a replacement character and "
            "does not run the mojibake repair.</p>",
        ),
    ]
    return shell(
        "decode.html",
        "ftnt decode",
        "Decode a legacy charset to UTF-8 with ftnt decode.",
        "Old bytes. No substitutions.",
        "ftnt decode",
        "Decode a charset to UTF-8.",
        "A strict text filter. The whole input is read before any output.",
        sections,
    )


def repair_page() -> str:
    sections = [
        (
            "usage",
            "00",
            "Usage",
            "<p><code>ftnt repair [options]</code></p>"
            "<p>Reads all of stdin as UTF-8 and writes repaired text. The repair "
            "is the core mojibake heuristic, run only because you asked for it. "
            "<code>read</code>, <code>write</code> and <code>export</code> do not "
            "apply it.</p>"
            + code_pane(
                "repair-text",
                "repair text",
                "ftnt repair < utf8-text.txt\n",
            )
            + code_pane(
                "repair-json",
                "repair as JSON",
                "ftnt repair --json < utf8-text.txt\n",
            )
            + '<div class="table-wrap"><table><thead><tr><th>Option</th><th>Meaning</th></tr></thead><tbody>'
            "<tr><td><code>--charset</code></td><td>Optional charset hint. When set, it must be a known core alias.</td></tr>"
            "<tr><td><code>--json</code></td><td>Write a JSON result instead of the text.</td></tr>"
            "<tr><td><code>--no-prefer-quoted</code></td><td>Do not prefer the quoted-printable interpretation.</td></tr>"
            "</tbody></table></div>"
            + code_pane(
                "repair-result",
                "repair_result",
                '{"schema_version":1,"type":"repair_result","text":"repaired","changed":true,"confidence":0.95}\n',
            ),
        ),
        (
            "failures",
            "01",
            "Failures",
            "<p>Input that is not UTF-8 exits 2. The command never claims the "
            "heuristic recovered the original bytes. <code>confidence</code> is a "
            "score from 0 to 1, not a verdict. Read it together with "
            "<code>changed</code> when you use <code>--json</code>.</p>",
        ),
    ]
    return shell(
        "repair.html",
        "ftnt repair",
        "Repair UTF-8 mojibake with ftnt repair.",
        "Mojibake. Only when asked.",
        "ftnt repair",
        "Repair UTF-8 mojibake.",
        "An explicit text filter. Message import and export leave text alone.",
        sections,
    )


def heads_page() -> str:
    sections = [
        (
            "usage",
            "00",
            "Usage",
            "<p><code>ftnt heads BASE --format FORMAT [options]</code></p>"
            "<p>Prints one JSON object per message and leaves out "
            '<code>body_text</code>. Use <a href="read.html"><code>read</code></a> '
            "for the message you actually need. The default <code>--limit</code> is "
            "100. <code>--limit 0</code> reads the whole base. <code>--after MSGNO</code> "
            "skips that number and everything before it.</p>"
            + code_pane(
                "heads-example",
                "first hundred subjects",
                "ftnt heads ./fixtures/general --format jam --limit 100\n",
            )
            + "<p><code>body_bytes</code> is the UTF-8 length of the body the reader "
            "returned. <code>msgid</code> is present only when the reader parsed one. "
            "Exit 0, or 7 with <code>--archive</code> when a reader issue was reported.</p>",
        ),
    ]
    return shell(
        "heads.html",
        "ftnt heads",
        "Index an FTN message base without message bodies.",
        "Subjects first. Bodies later.",
        "ftnt heads",
        "Index a base without bodies.",
        "A short list for choosing one message. Not an archive.",
        sections,
    )


def catalog_page() -> str:
    sections = [
        (
            "usage",
            "00",
            "Usage",
            "<p><code>ftnt catalog</code></p>"
            "<p>Prints one JSON document that describes this binary: commands, flags, "
            "write fields, date rules, exit codes and error codes. It is built from "
            "the parser and the tables the commands use. Proposals are not included.</p>"
            + code_pane("catalog-example", "describe the binary", "ftnt catalog\n")
            + "<p><code>--json-errors</code> prints a failure as one JSON object on "
            "stderr. A stderr that is not a terminal does the same. On a terminal, "
            "the sentence stays unless you pass the flag. The object carries "
            "<code>code</code>, <code>exit_status</code> and <code>message</code>. "
            "A write also carries <code>input_record</code> and <code>committed</code>.</p>",
        ),
    ]
    return shell(
        "catalog.html",
        "ftnt catalog",
        "Machine-readable description of the ftnt binary.",
        "Read the tool. Not the base.",
        "ftnt catalog",
        "Describe this binary.",
        "Commands, fields, date rules and error codes for the version you are running.",
        sections,
    )


def main() -> None:
    pages = {
        "index.html": index_page(),
        "create.html": create_page(),
        "write.html": write_page(),
        "read.html": read_page(),
        "export.html": export_page(),
        "decode.html": decode_page(),
        "repair.html": repair_page(),
        "heads.html": heads_page(),
        "catalog.html": catalog_page(),
    }
    for name, text in pages.items():
        (ROOT / name).write_text(text, encoding="utf-8")
    for name in RETIRED:
        path = ROOT / name
        if path.exists():
            path.unlink()
    print(f"Wrote {len(pages)} manual pages. Removed retired reading copies.")


if __name__ == "__main__":
    main()
