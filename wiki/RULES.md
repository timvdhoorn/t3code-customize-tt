# Project memory: rules

This folder records how this project's systems work and their **current state**, for agents. Git holds the history.

## Read

1. `index.md` loads every session; its **quick facts** answer what every session needs.
2. Pick a page from its routing line, then `rg -n '<term>' <this folder>` and read only the matching section.

## Where things live

| Place | Holds |
| --- | --- |
| `index.md` | Quick facts, then one routing line per page. |
| `status.md` | What is live, in progress, open. Finished work leaves it. |
| `<area>/<page>.md` | Current state of one topic: how it works, settings, gotchas. |
| `log.md` | One line per change, newest first. |
| `raw/<area>/` (repo root) | Verbatim copies from the live system, dated, never edited. |
| `scripts/<area>/` (repo root) | Our own scripts and SQL. |
| Human docs (outside this folder) | Customer-facing notes, procedures, minutes, change records. Pages link to them; they never copy them. |
| `GLOSSARY.md`, `docs/adr/`, `docs/solutions/` (repo root, when present) | What a term means, why a decision was made, how a bug was solved. Their own skills write them. Pages use the glossary's terms, state the resulting current state and link there; these rules change nothing in them. |

## Write

Write in the same turn you **verify** a fact, **change** the live system, **disprove** a claim, or are **told** one.

1. **Owner.** Each fact lives on exactly one page; other pages name it and link there, leaving the value to the owner (`pool_size`: see [Database](database.md)). Find the owner with `rg` on the identifier. A new topic gets a new page (kebab-case, in its area folder) and one routing line in `index.md`.
2. **Current state.** Replace a wrong or superseded value in place. No history on pages: not "(was 120)", "previously", "replaced X in May", "since rev 12"; git and the log hold it.
3. **Unknown state.** Only when the real state cannot be settled now:
   `> **Status: Disputed** (YYYY-MM-DD): <conflicting sources>. Settle: <query or screen>.`
   Markers: `Disputed`/`Unverified` (Dutch pages: `Betwist`/`Onbevestigd`).
4. **Header.** Bump the page's `Updated` date when content changes.
5. **Status.** Update `status.md` when something goes live, starts or finishes.
6. **Log.** One line at the top of `log.md`.
7. **Lint.** Run `lint.py` in this folder; exit 0 before you finish. When it prints `dream due`, end your reply by offering the user a dream pass ([DREAM.md](DREAM.md)).

## Formats

Page (labels in the page language, e.g. `Bron`/`Bijgewerkt`):

```markdown
# Title

> Source: <system + read-only command or query that returns the values, raw/ file, human doc>
> Updated: YYYY-MM-DD

One paragraph: what this is and where it lives.

## <sections by content>
```

Index routing line, at most 80 characters of text, no dates: `- [Page title](area/page.md): <questions it answers; key identifiers>`

Log line (actions: `setup`, `add`, `change`, `fix`, `remove`, `verify`, `dream`):

```markdown
- 2026-03-02 change | App pool identity set to svc-app | web/iis.md | raw/web/2026-03-02-apppool.xml
```

## Secrets

Passwords, client secrets, tokens and credentialed connection strings never enter this folder, `raw/` or `scripts/`: write `<redacted>` and name where the secret lives (vault item, `.env` key).
