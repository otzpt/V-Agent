# Contributing to V-Agent

Thanks for your interest in V-Agent.

V-Agent is a fork of [Zed](https://github.com/zed-industries/zed) and is
released under **GPL-3.0-or-later**. By contributing here, you agree your
contributions are licensed under those same terms.

## Upstream vs. here

If your change improves the **underlying editor** (the parts inherited from
Zed), please consider sending it to
[Zed](https://github.com/zed-industries/zed) instead — it helps far more people,
and V-Agent picks up upstream improvements. Note that Zed has its own
contribution process and CLA, which do **not** apply to this repository.

Contributions here are best suited to **V-Agent-specific** work: the activity
bar, Build & Run, the local-first AI setup, branding, and defaults.

## Before opening a PR

- Make sure it builds: `cargo build -p zed`
- Keep third-party attribution intact. If you add third-party code or assets,
  record them in [CREDITS.md](./CREDITS.md) along with their license.
- Do **not** add Zed Industries' branding or trademarks, telemetry endpoints
  pointing at their servers, or funding/sponsorship links. V-Agent is not
  affiliated with, endorsed by, or sponsored by Zed Industries, Inc.
- Keep changes focused — one thing per PR — and include a clear description.

## Reporting issues

Open an issue with: what you expected, what actually happened, your OS, and
steps to reproduce.
