#!/usr/bin/env python3
"""Static checks over the shipping source (app/src). Second line of defence;
the first is architectural (no code path can produce a colour without the
Stage 0 table — see fork block).

  static_checks.py all [srcdir]

Checks:
  identifiers   no identifier contains a word-boundary segment 'test', 'debug',
                'mock', or a '_dev' segment (harness purity; ordinary words
                like 'attested' or 'latest' do not false-positive)
  colour        no numeric colour literal in the star's render path
                (hex colours, rgb()/hsl(), 0xRRGGBB constructor args)
  sinhash       no sin-based hash in any shader chunk ('fract(sin', or sin
                inside a function whose name contains hash/rand/noise)
  timeliterals  pacing path contains exactly one named duration parameter and
                no other numeric time literal (active once autoplay exists)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SRC = ROOT / "app" / "src"

FORBIDDEN_SEGMENTS = {"test", "debug", "mock", "dev"}
IDENT_RE = re.compile(r"\b[A-Za-z_$][A-Za-z0-9_$]*\b")
STRING_OR_COMMENT_RE = re.compile(
    r"//[^\n]*|/\*.*?\*/|'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`",
    re.S,
)
HEX_COLOUR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b|0x[0-9a-fA-F]{6}\b|\brgba?\s*\(|\bhsla?\s*\(")


def split_segments(ident):
    # snake_case and camelCase segmentation
    parts = []
    for chunk in ident.split("_"):
        parts.extend(re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z0-9]+|\$", chunk))
    return [p.lower() for p in parts if p]


def strip_strings_comments(text):
    return STRING_OR_COMMENT_RE.sub(" ", text)


def check_identifiers(srcdir):
    bad = []
    for p in sorted(Path(srcdir).rglob("*")):
        if p.suffix not in (".js", ".mjs", ".html", ".css", ".glsl"):
            continue
        code = strip_strings_comments(p.read_text())
        for m in IDENT_RE.finditer(code):
            segs = split_segments(m.group(0))
            if FORBIDDEN_SEGMENTS & set(segs):
                line = code[: m.start()].count("\n") + 1
                bad.append(f"{p.relative_to(srcdir)}:{line}: {m.group(0)}")
    return bad


def check_colour_literals(srcdir):
    """Render-path files are declared by marker comment '@render-path' at head
    of file; the check runs on those. CSS for the instrument panel is UI, not
    the star's render path, and is exempt by construction."""
    bad = []
    for p in sorted(Path(srcdir).rglob("*")):
        if p.suffix not in (".js", ".mjs", ".glsl"):
            continue
        text = p.read_text()
        if "@render-path" not in text.split("\n", 3)[0:3].__str__():
            continue
        for m in HEX_COLOUR_RE.finditer(text):
            line = text[: m.start()].count("\n") + 1
            bad.append(f"{p.relative_to(srcdir)}:{line}: {m.group(0)}")
    return bad


def check_sin_hash(srcdir):
    bad = []
    fn_re = re.compile(r"\b(?:float|vec[234]|uint|int)\s+(\w*(?:hash|rand|noise)\w*)\s*\(([^)]*)\)\s*\{", re.I)
    for p in sorted(Path(srcdir).rglob("*")):
        if p.suffix not in (".glsl", ".js", ".mjs", ".html"):
            continue
        text = p.read_text()
        for m in re.finditer(r"fract\s*\(\s*sin", text):
            bad.append(f"{p.relative_to(srcdir)}:{text[:m.start()].count(chr(10)) + 1}: fract(sin")
        for m in fn_re.finditer(text):
            # body = text from { to matching }
            depth, i = 1, m.end()
            while i < len(text) and depth:
                depth += text[i] == "{"
                depth -= text[i] == "}"
                i += 1
            if re.search(r"\bsin\s*\(", text[m.end():i]):
                bad.append(f"{p.relative_to(srcdir)}: sin inside hash fn {m.group(1)}")
    return bad


def check_timeliterals(srcdir):
    """Pacing path: exactly one named duration parameter (PLAY_SPAN_S) and
    no other numeric literal on any line that references it — the check
    declared dormant in this module's docstring, active now that autoplay
    exists. A second pacing constant, or a raw number spliced into the
    advance expression, fails by construction."""
    bad = []
    defs = 0
    for p in sorted(srcdir.rglob("*.js")):
        for i, line in enumerate(p.read_text().splitlines(), 1):
            if "PLAY_SPAN_S" not in line:
                continue
            stripped = strip_strings_comments(line)
            if re.search(r"\bconst\s+PLAY_SPAN_S\s*=", stripped):
                defs += 1
                if not re.fullmatch(r"\s*const\s+PLAY_SPAN_S\s*=\s*\d+(\.\d+)?\s*;\s*",
                                    stripped):
                    bad.append(f"{p.name}:{i}: duration definition is not a bare named number")
            elif re.search(r"\d", stripped):
                bad.append(f"{p.name}:{i}: numeric literal beside the named duration")
    if defs != 1:
        bad.append(f"expected exactly one PLAY_SPAN_S definition, found {defs}")
    return bad


def main(argv):
    # argv: [script, ("all",) (srcdir,)] — "all" is the subcommand, not a dir
    rest = [a for a in argv[1:] if a != "all"]
    srcdir = Path(rest[0]) if rest else DEFAULT_SRC
    if not srcdir.exists():
        # measuring nothing must never read as success once the app exists
        print(f"FAIL  static: source dir {srcdir} does not exist")
        return 1
    failures = 0
    for name, fn in [("identifiers", check_identifiers),
                     ("colour-literals", check_colour_literals),
                     ("sin-hash", check_sin_hash),
                     ("time-literals", check_timeliterals)]:
        bad = fn(srcdir)
        print(f"{'PASS ' if not bad else 'FAIL '} static/{name}" + ("" if not bad else f"  ({len(bad)})"))
        for b in bad:
            print(f"    {b}")
        failures += bool(bad)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
