# V-Agent roadmap

Post-1.0 work, in rough priority order.

## Shells: batch, bash, PowerShell (post-release)

Goal: first-class support for running batch (`.bat`/`.cmd`), bash (`.sh`) and
PowerShell (`.ps1`) scripts.

What already works today:

- The integrated terminal runs any shell via the `terminal.shell` setting —
  point it at `cmd.exe`, `bash`, or `pwsh.exe`.
- **bash (`.sh`) is already fully native** — bundled tree-sitter grammar
  (highlighting) *and* bash-language-server (completions, diagnostics).

What this task adds — batch and PowerShell have NO native support today, not
even highlighting:

- Bundle tree-sitter grammars for `.bat`/`.cmd` and `.ps1` (community grammars
  `tree-sitter-powershell` and a batch grammar exist), or ship them as
  extensions.
- Optional: PowerShell LSP (PowerShellEditorServices) for `.ps1` IDE features.
- Quick shell switching from the terminal UI (a dropdown), not just settings.
- **Build & Run** detecting script type by extension and invoking the right
  interpreter automatically (`.bat`/`.cmd` → cmd, `.ps1` → PowerShell,
  `.sh` → bash — bash already covered).

## Niche languages as a differentiator (positioning)

Programmers of "forgotten" languages — Pascal, Ada, Fortran, Zig, Nim, Crystal,
Haskell, OCaml, Forth, assembly — skew toward purists who distrust telemetry
and want a fast, honest tool. VS Code treats these as second-class; Vim/Emacs
serve them but intimidate newcomers. V-Agent already fits this crowd: **zero
telemetry** (verified) and **local-first AI**.

The play is not to bundle every language (that bloats the binary). It is:

- Keep the community extension registry (already kept) so Zig/Nim/Haskell/OCaml
  and friends are one click away.
- **Curate** a recommended set of niche-language extensions with frictionless
  install.
- Bundle a small number the Zed ecosystem underserves but this audience wants.
  **First concrete target: Pascal / FreePascal** (a maintainer here already
  uses FPC). Needs a tree-sitter grammar + optional LSP (e.g. pasls).

This pairs naturally with the batch/PowerShell grammar work above.

## The harness, not the model (core thesis)

Small local models are not the bottleneck — the tooling around them is. The
whole tool-use problem in 1.0 was fixed with ~59 tokens of prompt, not a new
model. The differentiator is a **better harness around the same small model**,
with no telemetry. Concrete work, by impact:

1. **Robust `edit_file`.** When `old_text` matches multiple locations (e.g. a
   file with many identical lines), fall back to line/fuzzy matching, ask the
   model for more context, or suggest `write_file`. This is the exact failure
   small models hit today.
2. **Automatic tool-call retry.** On a failed call, feed the short error back
   and let the model correct — small models usually fix it on the second try.
3. **Curated, smaller toolset** for small models — 23 tools confuses them.
4. **Grammar-constrained decoding** for tool calls (Ollama supports it) so calls
   are always well-formed.
5. **Prefer `write_file`** (whole-file rewrite) over surgical `edit_file` for
   small models on small files — more reliable.

Fine-tuning model *weights* is explicitly out of scope: the leverage is in the
harness code, not new weights.

## Distro package managers — the honest state

**`pacman -S v-agent` / `apt install v-agent` from official repos: not without
distro adoption.**

- **Arch official (core/extra):** requires an Arch Package Maintainer to adopt
  it. The AUR is the community path *around* that; refusing AUR leaves only
  official adoption, which does not happen for a young fork. The AUR PKGBUILD
  is written and lives in `packaging/arch/PKGBUILD-bin`; only publishing is
  left.
- **Debian/Ubuntu:** needs a Debian Maintainer + review + the NEW queue
  (months to years).

What IS achievable without adoption:

- **A self-hosted package repository** you sign and host: users add it once,
  then `pacman -S` / `apt install` work. This is real infrastructure (hosting +
  GPG signing + a `repo-add` / `dpkg-scanpackages` pipeline).
- **Direct install packages** (already the plan): `.pkg.tar.zst` (`pacman -U`),
  `.deb` (`dpkg -i` / `apt install ./file.deb`), `.AppImage`, attached to the
  GitHub release. No repo, no AUR.

Recommended order: ship the direct packages now (done in the release workflow);
consider a self-hosted repo later if demand warrants the hosting cost.

## FreeBSD & Arch Linux packaging

### Arch — done in 1.0.1

`packaging/arch/` holds two maintained PKGBUILDs:

- `PKGBUILD-bin` — the AUR package (`v-agent-bin`), installing the prebuilt
  binary from the GitHub release. This is the one to publish to the AUR.
- `PKGBUILD` — from-source build for people who prefer compiling.

Both declare a real `depends=()` mirroring the official Arch `zed` package.
The release workflow's `.pkg.tar.zst` previously shipped with **no** `depends`
at all, so it installed but the binary could not start on a clean system; it
now carries the same set and derives `pkgver` from `script/get-crate-version`
instead of a hardcoded literal.

Remaining: publish `v-agent-bin` to the AUR (needs an AUR account and an SSH
key; `updpkgsums` + `makepkg --printsrcinfo > .SRCINFO` before the first push).
`sha256sums` are `SKIP` until then — the AUR expects real checksums for a
versioned release.

### FreeBSD — build job added in 1.0.1, unverified

`build-freebsd` in the release workflow builds inside a FreeBSD 14.2 VM via
`vmactions/freebsd-vm` (GitHub has no native FreeBSD runner) and reuses
upstream's own `script/freebsd` for `pkg` dependencies rather than duplicating
a package list that would drift.

The job is `continue-on-error` and the release gates on `needs.build` only, so
a FreeBSD failure cannot hold back a release. **It has not run against a real
tag yet** — expect the first run to need iteration (rustup bootstrap inside the
VM, build timeouts on a VM-hosted runner).

Remaining:

- Verify the first real run and drop `continue-on-error` once it is reliable.
- Package as a native `.pkg` rather than only a portable `.tar.gz`.
- `script/bundle-freebsd` still only builds `remote_server`; most of it is
  commented out. Either finish it or delete it in favour of the CI job.

## Other tracked items (not blocking use)

- macOS builds in the release workflow (needs a Mac runner + signing).
- Richer installer polish and code signing (removes the SmartScreen warning).
- Config directory rename `%APPDATA%\Zed` → `V-Agent` with settings migration.
- `uvx` guidance for Python-based MCP servers.
- `/model` listing configured external agents (Claude/Codex ACP) alongside
  local and BYO-key models.
