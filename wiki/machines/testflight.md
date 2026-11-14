# TestFlight

> Source: `~/.cache/t3code-customize/logs/ios-*.log` on the MacBook Pro; `asccli apps list` with the env from `ios.json`
> Updated: 2026-11-14

The iOS app is built on the MacBook Pro by `./t3code-customize ios` (also run by `autoupdate --ios` and `fleet`) and uploaded to TestFlight with asc-cli.

## Access
- API key: `ascKeyId` and `ascIssuerId` in `ios.json`; the `.p8` lives at `~/.asc/keys/AuthKey_<key id>.p8` on the MacBook Pro and in 1Password ("App Store Connect API key t3code-customize").
- A 403 `FORBIDDEN.REQUIRED_AGREEMENTS_MISSING_OR_EXPIRED` from `asccli apps list` means the Account Holder has to accept an agreement in App Store Connect (Business / Agreements); no tool can do it.
- The build waits for the Mac's desktop app to be on the nightly it builds for.
