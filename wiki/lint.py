#!/usr/bin/env python3
"""Lint a project-memory folder. Python 3.9+ stdlib only, read-only.

Usage: python3 lint.py [knowledge-folder]      default: the folder this file is in
Prints `path:line: rule: detail` per finding and a summary. Exit 0 clean, 1 findings, 2 usage error.
A `dream due: ...` line after the summary is a notice, not a finding.
The rules it enforces are in RULES.md, installed beside it.
"""
import datetime
import os
import re
import sys
from collections import Counter

INDEX_BYTES = 6000          # index.md is loaded every session
ROUTE_CHARS = 80            # text after the link in a routing line
PAGE_BYTES = 16000
STATUS_BYTES = 5000
LINE_CHARS = 220
MARKER_DAYS = 21
LOG_LINES = 200
DREAM_DAYS = 7              # a dream pass is due after this many days with logged changes
LOG_ACTIONS = ("setup", "add", "change", "fix", "remove", "verify", "dream")
MARKERS_ALLOWED = ("Disputed", "Unverified", "Betwist", "Onbevestigd")
MARKERS_FORBIDDEN = ("Outdated", "Superseded", "Deprecated", "Verouderd")
NEIGHBOUR_FILE = re.compile(r"^(GLOSSARY|CONTEXT)(-MAP)?\.md$")  # other skills' docs; never linted as pages
INSTALLED = ("RULES.md", "DREAM.md")  # installed by the skill, not project knowledge
SPECIAL = ("index.md", "status.md", "log.md") + INSTALLED
HISTORY = re.compile(
    r"(?i)\((was|previously|formerly)\b[^)]*\)|\b(previously|formerly)\b|\bwas (set|raised|lowered|changed|moved|replaced)\b"
    r"|\b(raised|lowered|changed|moved|increased|decreased) from\b|\breplaced \S+ (in|on) |\bsince (rev|release|step|version)\b"
)

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
ROUTE = re.compile(r"^- \[[^\]]+\]\(([^)\s]+)\)(?::\s*(.*))?$")
DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b(0?[1-9]|[12]\d|3[01])-(0?[1-9]|1[0-2])(-\d{2,4})?\b")
HEADER = re.compile(r"^>\s*[\w ]+:\s*\S")
HEADER_DATE = re.compile(r"^>\s*[\w ]+:\s*\d{4}-\d{2}-\d{2}\s*$")
LOG_ENTRY = re.compile(r"^- (\d{4}-\d{2}-\d{2}) ([a-z-]+) \| (.+?) \| (\S+) \| (.+)$")
SECRET = re.compile(
    r"(?i)(password|passwd|pwd|client_secret|secret|token|api[_-]?key)\s*[:=]\s*['\"]?(?!<)[^\s'\"<>;]{8,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(ghp_|github_pat_|sk-ant-|xox[bp]-)[A-Za-z0-9_-]{16,}"
)


def slugs(text):
    """GitHub-style heading anchors of a page."""
    seen, out = Counter(), set()
    for _, line in outside_fences(text.splitlines()):
        m = re.match(r"^#{1,6}\s+(.*?)\s*#*\s*$", line)
        if m:
            base = re.sub(r"[^\w\- ]", "", re.sub(r"`", "", m.group(1)).lower()).replace(" ", "-")
            out.add(base if not seen[base] else "%s-%d" % (base, seen[base]))
            seen[base] += 1
    return out


def outside_fences(lines):
    fence = False
    for n, line in enumerate(lines, 1):
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if not fence:
            yield n, line


def lint(kb, today=None):
    today = today or datetime.date.today()
    found = []

    def add(page, n, rule, text):
        found.append((page, n, rule, text))

    pages = []
    for d, dirs, names in os.walk(kb):
        top = os.path.normpath(d) == os.path.normpath(kb) and os.path.basename(os.path.abspath(kb)) == "docs"
        for x in [x for x in dirs if x == "adr" or (top and x in ("solutions", "agents"))] + [x for x in names if NEIGHBOUR_FILE.match(x)]:
            add(os.path.relpath(os.path.join(d, x), kb).replace(os.sep, "/"), 0, "neighbour-docs",
                "owned by another skill: keep the knowledge folder beside it, not around it")
            (dirs if x in dirs else names).remove(x)
        dirs[:] = sorted(x for x in dirs if not x.startswith("."))
        pages += [os.path.relpath(os.path.join(d, x), kb).replace(os.sep, "/") for x in sorted(names) if x.endswith(".md")]
    texts = {}
    for p in pages:
        with open(os.path.join(kb, p), encoding="utf-8") as fh:
            texts[p] = fh.read()
    for p in ("index.md", "status.md", "log.md"):
        if p not in texts:
            add(p, 0, "missing-file", "required file is missing")

    for p, text in texts.items():
        if p in INSTALLED:
            continue
        lines = text.splitlines()
        for n, line in outside_fences(lines):
            if len(line) > LINE_CHARS:
                add(p, n, "line-too-long", "%d chars (max %d)" % (len(line), LINE_CHARS))
            if SECRET.search(line):
                add(p, n, "secret-like", "looks like a credential; write <redacted>")
            for target in LINK.findall(re.sub(r"`[^`]*`", "", line)):
                path, _, anchor = target.partition("#")
                if re.match(r"^[a-z][a-z0-9+.-]*:", target):
                    continue
                full = os.path.normpath(os.path.join(kb, os.path.dirname(p), path)) if path else os.path.join(kb, p)
                if not os.path.exists(full):
                    add(p, n, "dead-link", target)
                elif anchor and full.endswith(".md") and os.path.isfile(full):
                    with open(full, encoding="utf-8") as fh:
                        if anchor.lower() not in slugs(fh.read()):
                            add(p, n, "dead-anchor", target)
            prose = re.sub(r'`[^`]*`|"[^"]*"|\u201c[^\u201d]*\u201d', "", line)  # quoted text is the system's, not ours
            if p != "log.md" and HISTORY.search(prose):
                add(p, n, "history", "%r: state the current value only; git and the log hold history" % HISTORY.search(prose).group(0))
            for word in MARKERS_FORBIDDEN:
                if re.search(r"\*\*(Status:\s*)?%s\b" % word, line):
                    add(p, n, "marker-forbidden", "%s: rewrite the claim to the current state" % word)
            for word in MARKERS_ALLOWED:
                m = re.search(r"\*\*(?:Status:\s*)?%s\*\*\s*(?:\((\d{4}-\d{2}-\d{2})\))?" % word, line)
                if m and not m.group(1):
                    add(p, n, "marker-undated", "%s marker needs (YYYY-MM-DD)" % word)
                elif m and (today - datetime.date.fromisoformat(m.group(1))).days > MARKER_DAYS:
                    add(p, n, "marker-stale", "%s since %s: settle it" % (word, m.group(1)))
        if p in SPECIAL and p != "status.md":
            continue
        limit = STATUS_BYTES if p == "status.md" else PAGE_BYTES
        if len(text.encode("utf-8")) > limit:
            add(p, 0, "page-size", "%d bytes (max %d)" % (len(text.encode("utf-8")), limit))
        head = lines[:8]
        if not any(HEADER.match(l) and not HEADER_DATE.match(l) for l in head):
            add(p, 1, "missing-source", "a `> Source: ...` line in the first 8 lines")
        if not any(HEADER_DATE.match(l) for l in head):
            add(p, 1, "missing-updated", "a `> Updated: YYYY-MM-DD` line in the first 8 lines")

    if "index.md" in texts:
        text = texts["index.md"]
        if len(text.encode("utf-8")) > INDEX_BYTES:
            add("index.md", 0, "index-size", "%d bytes (max %d)" % (len(text.encode("utf-8")), INDEX_BYTES))
        routed, section_no = set(), 0
        for n, line in outside_fences(text.splitlines()):
            if line.startswith("## "):
                section_no += 1
                continue
            m = ROUTE.match(line)
            if not m or section_no < 2:  # section 1 is the quick facts
                continue
            routed.add(os.path.normpath(m.group(1).split("#")[0]).replace(os.sep, "/"))
            desc = (m.group(2) or "").strip()
            if not desc:
                add("index.md", n, "route-empty", "routing line needs `: <questions it answers>`")
            if len(desc) > ROUTE_CHARS:
                add("index.md", n, "route-too-long", "%d chars (max %d)" % (len(desc), ROUTE_CHARS))
            if DATE.search(re.sub(r"`[^`]*`", "", desc)):
                add("index.md", n, "route-has-date", "routing lines carry no dates")
        if section_no < 2:
            add("index.md", 0, "missing-quick-facts", "need a first `## ` quick-facts section, then routing sections")
        for p in pages:
            if p not in ("index.md", "log.md") + INSTALLED and p not in routed:
                add(p, 0, "not-indexed", "no routing line in index.md")

    if "log.md" in texts:
        prev, count, seen = None, 0, set()
        for n, line in outside_fences(texts["log.md"].splitlines()):
            if not line.startswith("- "):
                continue
            count += 1
            m = LOG_ENTRY.match(line)
            if not m:
                add("log.md", n, "log-format", "expected `- YYYY-MM-DD <action> | <what> | <page> | <source>`")
                continue
            date, action, _, page, _ = m.groups()
            if line in seen:
                add("log.md", n, "log-duplicate", "same entry twice")
            seen.add(line)
            if action not in LOG_ACTIONS:
                add("log.md", n, "log-action", "%r not in %s" % (action, ", ".join(LOG_ACTIONS)))
            if page != "-" and page.split("#")[0] not in texts:
                add("log.md", n, "log-page", "%s is not a page here" % page)
            if prev and date > prev:
                add("log.md", n, "log-order", "newest first: %s after %s" % (date, prev))
            prev = date
        if count > LOG_LINES:
            add("log.md", 0, "log-size", "%d entries (max %d): delete the oldest" % (count, LOG_LINES))
    return found


def dream_due(kb, today=None):
    """One notice line when the last `dream` (else `setup`) log entry is over DREAM_DAYS old and changes followed it."""
    today = today or datetime.date.today()
    try:
        with open(os.path.join(kb, "log.md"), encoding="utf-8") as fh:
            entries = [m.groups() for m in map(LOG_ENTRY.match, fh.read().splitlines()) if m]
    except OSError:
        return None
    for action in ("dream", "setup"):
        hit = [i for i, e in enumerate(entries) if e[1] == action]
        if hit:
            last, since = entries[hit[0]][0], hit[0]  # newest first: entries above it came later
            break
    else:
        return None
    days = (today - datetime.date.fromisoformat(last)).days
    if days <= DREAM_DAYS or not since:
        return None
    return "dream due: last %s %s (%d days, %d changes since); offer the user a dream pass (DREAM.md)" % (action, last, days, since)


def main(argv):
    if len(argv) > 2 or (len(argv) == 2 and not os.path.isdir(argv[1])):
        print(__doc__.strip().splitlines()[2])
        return 2
    kb = argv[1].rstrip("/") if len(argv) == 2 else os.path.relpath(os.path.dirname(os.path.abspath(__file__)))
    found = lint(kb)
    for p, n, rule, text in found:
        print("%s/%s:%d: %s: %s" % (kb, p, n, rule, text))
    counts = Counter(r for _, _, r, _ in found)
    print("lint: %d findings%s" % (len(found), (" (" + ", ".join("%s %d" % kv for kv in sorted(counts.items())) + ")") if counts else ""))
    if dream_due(kb):
        print(dream_due(kb))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
