# Status

> Source: `./t3code-customize status` on each machine; GitHub PRs of `timvdhoorn/t3code-customize-tt`
> Updated: 2026-11-27

What is live, what is in progress and what is open. Finished work leaves this page; its facts live on the owning page.

## Live
- Patches ported to nightly 0.1.14-nightly.20261127.5332 on `main` (PR #150); see [Current port](porting/current-port.md).
- devbox1: server runs 5345 with the patches (covered by `covered-nightly.txt`). See [devbox1](machines/devbox1.md).
- MacBook Pro: own signed T3 Code 5345 (PR #158), installed 2026-11-27; T3's 5258 app in
  `~/.local/share/t3code-customize/rollback/`. TestFlight: T3 Code TT 2.4.0 (202611272015) for 5345. Keychain prompt answered 2026-11-28.
- MacBook Air: own signed T3 Code 5345 (its own Developer ID certificate), installed by `fleet`
  2026-11-28; no keychain prompt appeared.

## In progress
- A port to a newer nightly (onto upstream 9ceb8bfbec) runs in the shared source checkout on devbox1 (another thread, 2026-11-28).

## Open
- Macs: the own signed app has no passkeys (Tim accepts this, 2026-11-27); watch upstream
  t3code-customize for a new macOS hook.
