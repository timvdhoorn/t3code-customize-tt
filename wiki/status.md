# Status

> Source: `./t3code-customize status` on each machine; GitHub PRs of `timvdhoorn/t3code-customize-tt`
> Updated: 2026-11-22

What is live, what is in progress and what is open. Finished work leaves this page; its facts live on the owning page.

## Live
- Patches ported to nightly 0.1.12-nightly.20261122.5085 on `main`, plus `patches-tt/0017` (quiet thread list: iOS cold-start thread open 33 s → 1.7 s); see [Current port](porting/current-port.md).
- devbox1: server runs 5085 with the patches. See [devbox1](machines/devbox1.md).
- MacBook Pro: 5085 with the patches (incl. `patches-tt/0017`); iOS build 202611221444 for 5085 on TestFlight.

## In progress
- MacBook Air: 5009 with the patches; picks up 5085 through its update.

## Open
- Port to nightly 5098 with the APNs reconnect fix (`patches-tt/0003`: idle connection replaced after 4 min, one resend on a network error) and the `vite.config.ts` typecheck detection: PR open, not yet on any machine.
