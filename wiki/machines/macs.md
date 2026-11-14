# Macs

> Source: `ssh macbook-air|macbook-pro … ./t3code-customize status`; `~/.cache/t3code-customize/logs/autoupdate.log` on the Mac
> Updated: 2026-11-14

The MacBook Pro (`mbp`, `"ios": true`) and MacBook Air (`mba`) run T3 Code Nightly with the patches through a launcher overlay.

## Layout
- App: `/Applications/T3 Code (Nightly).app`, signed and untouched.
- Launcher: `/Applications/T3 Code (Customized).app`; it starts the app with the overlay from `~/.local/share/t3code-customize/builds/<build>/overlay`.
- Repo: `~/Devops/agent-tooling/t3code-customize-tt`. `~/.local/bin` is not on the Air's `PATH`; run the tool by its repo path.
- LaunchAgent: `com.github.t3code-customize.update` runs `autoupdate`; its log is `~/.cache/t3code-customize/logs/autoupdate.log`.

## Update route
- The customized build downloads a new nightly that `covered-nightly.txt` on `main` covers and installs it on quit (`patches-tt/0005`).
- The LaunchAgent sees the new `Info.plist` and rebuilds the overlay for that version (about 3 minutes). A launch before the rebuild finishes opens stock; `status` then says `Next launch opens: stock T3 Code`.
- `status` on the Mac shows the installed version, the customized build's version and what the next launch opens.
