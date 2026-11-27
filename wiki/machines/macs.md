# Macs

> Source: `ssh macbook-air|macbook-pro … ./t3code-customize status`; `~/.cache/t3code-customize/logs/autoupdate.log` on the Mac
> Updated: 2026-11-27

The MacBook Pro (`mbp`, `"ios": true`) and MacBook Air (`mba`) run T3 Code Nightly with the patches: from nightly 5332 (inspector fuse off)
as an own signed app, before that through a launcher overlay. Route details: "Own signed macOS app" and "macOS launcher" in [fork-changes](../../docs/fork-changes.md).

## Layout
- App: `/Applications/T3 Code (Nightly).app`. On the signed route: our build, signed with the login keychain's
  "Developer ID Application" identity (MacBook Pro has it, the Air not), marker `T3CodeCustomize` in its `Info.plist`; on the launcher route: T3's own, untouched.
- Signing from SSH fails (`errSecInternalComponent`); builds that sign run in the LaunchAgent (GUI session).
- Rollback to T3's app: `~/.local/share/t3code-customize/rollback/<version>.zip` (`ditto -x -k <zip> /Applications` after removing the app).
- Launcher (launcher route only; the signed install removes it): `/Applications/T3 Code (Customized).app`; it starts the app with the overlay from `~/.local/share/t3code-customize/builds/<build>/overlay`.
- Repo: `~/Devops/agent-tooling/t3code-customize-tt`. `~/.local/bin` is not on the Air's `PATH`; run the tool by its repo path.
- LaunchAgent: `com.github.t3code-customize.update` runs `autoupdate`; its log is `~/.cache/t3code-customize/logs/autoupdate.log`.

## Update route
- The customized build downloads a new nightly that `covered-nightly.txt` on `main` covers and installs it on quit (`patches-tt/0005`).
- The LaunchAgent sees the new `Info.plist` and rebuilds the overlay for that version (about 3 minutes). A launch before the rebuild finishes opens stock; `status` then says `Next launch opens: stock T3 Code`.
- `status` on the Mac shows the installed version, the customized build's version and what the next launch opens.
