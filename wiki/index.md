# Project knowledge base

Rules: [RULES.md](RULES.md). Status: [status.md](status.md). History: [log.md](log.md).
Answer from these pages; query the live system only when a page lacks the fact or marks it disputed, or you will change it.

## Quick facts
- Connect: SSH aliases in `machines.json` (`macbook-pro`, `macbook-air`, `devbox1`).
- Remote run: `ssh <alias> 'exec "$SHELL" -lc "cd <repo> && python3 ./t3code-customize status"'`; repo path below.
- Tools: `./t3code-customize` (`status`, `build`, `port`, `continue`, `checks`, `server`, `ios`, `fleet`); private source checkout `~/.cache/t3code-customize/t3code`, logs `~/.cache/t3code-customize/logs/`.
- Files in/out: git only; `fleet` syncs this repo to every machine.
- Deploy: merge to `main`, then `./t3code-customize fleet` ([docs/machines.md](../docs/machines.md)).
- Machine and harness facts outside this fork: `~/Devops/ttagent-memory`.

## General
- [Status](status.md): what is live, in progress, open

## Machines
- [devbox1](machines/devbox1.md): T3 server, timers, shared checkout, lock, server build
- [Macs](machines/macs.md): MacBook Pro and Air app, launcher, overlay, autoupdate agent
- [TestFlight](machines/testflight.md): iOS build on the MacBook Pro, App Store Connect access

## Porting
- [Current port](porting/current-port.md): nightly the patches cover, layers, skips, port gotchas

## Docs (human-facing, outside this folder)
- [README](../README.md): what the fork adds, install, machines and server sections
- [Fork changes](../docs/fork-changes.md): what each own patch must keep doing; update check
- [Machines](../docs/machines.md): update route per machine, idle gate, unattended ports
- [Porting](../docs/porting.md): the port loop (`port`, `continue`, `checks`), port rules
- [macOS](../docs/macos.md): macOS build and launch path (upstream-owned)

## Agent docs (owned by other skills)
- [Agent skill docs](../docs/agents/): issue tracker, triage labels, domain-doc layout
- [Agent skills block](../AGENTS.md#agent-skills): skill config in `AGENTS.md`
