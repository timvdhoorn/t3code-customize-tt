# Dream

The consolidation pass over this folder, by [RULES.md](RULES.md). Started by the user, or by their yes after lint printed `dream due`.
Done when lint exits 0 (or only markers you listed remain) and one log line records the pass.

0. **Delegate.** You are the main agent and your harness can start a subagent: start one with the brief "Follow `<this folder>/DREAM.md` from step 1 and report what changed", wait, relay its report and stop here. Steps 1-7 are for that subagent, or for you when no subagent exists.
1. Run lint; fix every finding.
2. Merge duplicates: list the identifiers (backticked terms, config keys, values) that occur on more than one page, e.g. ``rg -o '`[^`]+`' <this folder> | sort | uniq -c``; each stays on its owner, the others link.
   A page that defines a term `GLOSSARY.md` defines, or retells an ADR's reasoning, gives way: the page keeps the current state and links there. Where the two disagree, change neither and list it for the user.
3. Move misplaced facts to their owning page; split an oversized page by topic.
4. Shorten `status.md`: finished items leave, their facts go to the owning page.
5. Verify against sources: for every page, replay its `Source` read-only (repo, `raw/`, human docs, a read-only query of the live system; never a command that changes anything) and compare each value it states, marked or not.
   Replace a differing value in place by RULES.md Write. Mark `Disputed` with `Settle:` only what you cannot settle; list those and every stale marker you could not settle for the user.
6. Mine recent sessions for facts verified there but never written down.
   - Window: since the date of the newest `dream` line in `log.md`; none: the last 7 days. Cap the step at about 30 minutes and list the sessions you skipped.
   - Sessions: those whose working directory is this repository, from the harness transcripts present, found by modification time. Claude Code: `~/.claude/projects/<repo path, every non-alphanumeric character as ->/*.jsonl`. Codex: `~/.codex/sessions/**/rollout-*.jsonl`, keeping files whose `cwd` field is this repository. Other harnesses only when their session folder exists.
   - Read only the user messages and the final assistant message of each session; open more only where they point to a durable fact (a decision, a changed value, a confirmed behavior, a corrected claim).
   - Per candidate: find the owner page with `rg` on its identifier, verify it read-only against the source (RULES.md Write), then write it there by RULES.md Write. A candidate you cannot verify gets the `Unverified` marker from RULES.md. Never copy a secret, token or credential; point to where it lives.
   - Skip what git, the code or a page already holds, one-off task detail and anything cheap to rediscover.
7. Append `- <date> dream | <what changed> | index.md | lint` at the top of `log.md`; run lint again.
