# Status

> Source: `./t3code-customize status` on each machine; GitHub PRs of `timvdhoorn/t3code-customize-tt`
> Updated: 2026-11-27

What is live, what is in progress and what is open. Finished work leaves this page; its facts live on the owning page.

## Live
- Patches ported to nightly 0.1.14-nightly.20261127.5332 on `main` (PR #150); see [Current port](porting/current-port.md).
- devbox1: server runs 5332 with the patches. See [devbox1](machines/devbox1.md).

## In progress
- MacBook Pro: unreachable over SSH since 2026-11-27 morning; still on 5258 or older, so the app update to 5332 and the iOS build wait until it is reachable and T3 Code restarts.
- MacBook Air: offline (with Tim); picks up 5332 through its updater when T3 Code quits.

## Open
- Upstream closed pingdotgg/t3code#16699 unmerged; keeping the child-threads patch waits for Tim's confirmation.
