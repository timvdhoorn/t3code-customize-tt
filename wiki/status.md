# Status

> Source: `./t3code-customize status` on each machine; GitHub PRs of `timvdhoorn/t3code-customize-tt`
> Updated: 2026-11-27

What is live, what is in progress and what is open. Finished work leaves this page; its facts live on the owning page.

## Live
- Patches ported to nightly 0.1.14-nightly.20261127.5332 on `main` (PR #150); see [Current port](porting/current-port.md).
- devbox1: server runs 5332 with the patches. See [devbox1](machines/devbox1.md).

- MacBook Pro: T3 Code 5258 customized; TestFlight has iOS build 202611271237 (5258).

## In progress
- Macs stay on 5258: nightly 5332 turns the inspector fuse off, so the macOS launcher cannot inject
  and the prebuild fails; the downloaded update waits (issue #152).
- MacBook Air: offline (with Tim); same block once it downloads 5332.

## Open
- Issue #152: choose a new macOS hook (own signed build, re-signed app, or wait for upstream).
