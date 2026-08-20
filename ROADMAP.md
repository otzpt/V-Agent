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

## Local AI: llama.cpp — already a first-party provider, corrected entry

**This section previously claimed V-Agent had no first-party llama.cpp
integration and proposed building one from scratch. That was wrong** — found
while debugging a user's config on this machine: `crates/language_models/src/
provider/llama_cpp.rs` (2100+ lines) is a dedicated provider, documented at
`docs/src/ai/use-a-local-model.md`, that was missed before writing the
original version of this section. Correcting rather than leaving it, per this
file's own standard of tracking real state.

What already exists, confirmed by reading the provider source and the docs,
not assumed:

- A native `"llama.cpp"` settings key (`language_models.llama.cpp` —
  literal dot, not the generic `openai_compatible` map), with `api_url` and
  an `auto_discover` flag that **defaults to true**.
- Router-mode **auto-discovery via the server's `/models/sse` stream**:
  models loading/unloading in `llama-server`'s router mode are picked up
  live, with context length and tool/vision capabilities refined once each
  model actually loads. No hand-written `available_models` list needed
  unless `auto_discover` is turned off.
- `available_models` still exists as a manual override path for
  non-router setups or pinned capabilities, matching the shape the previous
  version of this section proposed building.

So the real gap is smaller than previously written:

1. **Server-side setup is still all manual** — GPU backend detection, VRAM-
   aware `-ngl`, KV cache quantization, and enabling MTP
   (`--spec-type draft-mtp`) for GGUFs that carry `nextn_predict_layers`
   tensors are all `llama-server`-side configuration with no V-Agent
   involvement, and rightly so — this is inference-server tuning, not editor
   scope. A `script/setup-local-llama`-style helper (detect backend, generate
   a router config) is still a real, unclaimed idea, just not a V-Agent
   *feature* — more a companion script or a doc walkthrough.
2. **MTP is invisible in the UI.** The provider's auto-discovery reads
   context/tool/vision capabilities from the server but has no concept of
   speculative decoding — a model picker showing "speculative decoding
   active" would need the server to expose that (llama-server's `/props` or
   model listing does not currently carry it either, so this starts
   upstream, not in V-Agent).
3. Managing the `llama-server` process lifecycle from inside V-Agent
   (start/stop, a "Local Models" panel) remains out of scope — no proof the
   existing auto-discovery isn't sufficient.

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
  `.deb` (`dpkg -i` / `apt install ./file.deb`), `.rpm` (`dnf install ./file.rpm`,
  added in 1.1.0), `.AppImage`, attached to the GitHub release. No repo, no AUR.

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

### FreeBSD — build job added in 1.0.1, one compile error fixed in 1.1.0

`build-freebsd` in the release workflow builds inside a FreeBSD 14.2 VM via
`vmactions/freebsd-vm` (GitHub has no native FreeBSD runner) and reuses
upstream's own `script/freebsd` for `pkg` dependencies rather than duplicating
a package list that would drift.

The job is `continue-on-error` and the release gates on `needs.build` only, so
a FreeBSD failure cannot hold back a release.

It has now run against a real tag (v1.0.2) and failed, in gpui:
`error[E0425]: cannot find type PlatformScreenCaptureFrame in this scope`. The
`scap_screen_capture` module was gated on windows/linux/freebsd while the type
alias it depends on listed only windows and linux, so the module compiled on
FreeBSD against a type that did not exist there. Fixed in 1.1.0.

Whether the build now completes is still unverified — the fix addresses the one
error the log showed, and a target upstream does not test may have more behind
it.

Remaining:

- Confirm the 1.1.0 run gets further, and drop `continue-on-error` once it is
  reliably green.
- Package as a native `.pkg` rather than only a portable `.tar.gz`.
- `script/bundle-freebsd` still only builds `remote_server`; most of it is
  commented out. Either finish it or delete it in favour of the CI job.

### Void Linux — not started, generic-distro tier only

No native package, no CI job, no distro-specific docs exist today. What
currently applies to Void is only the same "any distro" fallback that applies
to every untested Linux: the AppImage or the portable tarball, gated on
V-Agent's two real requirements — glibc ≥ 2.31 and a Vulkan-capable GPU.

One glibc-variant Void install was checked by hand this session:
`ldd --version` reported glibc 2.41, comfortably above the floor. Vulkan
support on that machine was not confirmed in the same session — do not treat
glibc alone as "V-Agent works on Void," the GPU driver side is the other half
of the requirement and remains unverified.

Void ships **two libc variants**, glibc and musl, selected at install time by
which ISO is downloaded (the musl one is explicitly named `-musl-` in the
filename; the default is glibc). This matters more here than for other
distros: musl systems have no system-wide glibc to fall back on at all, so the
prebuilt binary cannot run there under any circumstance, only a from-source
build against the musl target — and V-Agent already has one relevant asset for
that: `remote_server` already builds against
`x86_64-unknown-linux-musl` for remote-development's static server (see
`docs/src/remote-development.md`). Whether the full GUI app builds against
musl is untested; the existing musl build only covers the headless remote
server, not gpui/Vulkan.

Remaining, in order:

1. Confirm Vulkan actually works on a real glibc-Void install end to end
   (not just glibc version) — the missing half of the check done this
   session.
2. Void's package system is `xbps`, built from `void-packages` templates
   (a `template` file, analogous to Arch's `PKGBUILD`) — not compatible with
   the `.pkg.tar.zst`/`.deb`/`.rpm` already produced by the release workflow.
   A native package needs its own template, following the same
   prebuilt-binary pattern as `PKGBUILD-bin`.
3. Upstream inclusion in `void-packages` needs Void maintainer review, the
   same adoption problem already true for Arch official and Debian above — a
   self-hosted `xbps` repo is the realistic path if that stalls, mirroring the
   self-hosted-repo option already noted for pacman/apt.
4. No native Void GitHub Actions runner exists, same problem FreeBSD solves
   with a VM — but Void has an official Docker image
   (`voidlinux/voidlinux`), so a container job is enough to compile in CI
   (a real headless-GUI *run* is a separate, harder problem CI does not
   currently attempt for any Linux target).
5. A `docs/src/development/voidlinux.md` covering Void-specific quirks
   (xbps commands, the musl/glibc distinction, driver package names) once any
   of the above is real enough to document — not before, per this file's own
   pattern of writing docs after the thing works, not ahead of it.

### Fedora/RHEL — `.rpm` added in 1.1.0

Built in a `fedora:latest` container (the runner is Ubuntu and has no
`rpmbuild`), matching how the Arch package is produced. `Requires:` are left to
rpmbuild's own ELF scan rather than hand-listed, so they cannot drift from the
binary's actual linkage. The `dist` tag is blanked because a single prebuilt
binary ships for every Fedora version.

Remaining: verify against a real Fedora install — the binary is built on
Ubuntu 22.04, so the generated glibc/soname requires must resolve on Fedora,
which has not been tested on a real system yet.

## Upstream sync — 2 releases behind (checked 2026-08-19)

Currently synced to `v1.15.0` (`e17dc4f9d50d`, see `CREDITS.md`). Upstream's
latest **stable** is `v1.16.1` (`eb8e1c8b55`) — `v1.15.1` and `v1.16.1` both
shipped since our last sync, 75 commits ahead per
`gh api repos/zed-industries/zed/compare/e17dc4f9d50d...eb8e1c8b55`.

A `v1.17.0-pre` is already cut past that (`605674a6cfb6`, 171 commits ahead of
our sync point) — pre-release, not the sync target per this file's own
convention of syncing to stable tags, but it already carries **Gemini 3.7
Flash** superseding the 3.6 Flash added in `v1.16.1` (upstream PR
[#62670](https://github.com/zed-industries/zed/pull/62670)), and a new
`ask_user` agent tool (PR
[#61497](https://github.com/zed-industries/zed/pull/61497)) letting the agent
ask the user questions through forms — directly adjacent to this fork's own
harness work above, worth reading before the next sync even though it isn't
one yet.

Nothing in the gap looks blocking — no CVE/security notice in either
release's notes — but two items are worth pulling in deliberately rather than
waiting for the next routine sync:

- **`v1.16.1`: "Linux: Improved memory usage."** ([zed-industries/zed#62192](https://github.com/zed-industries/zed/pull/62192))
  Directly relevant to this fork specifically, given the local-first/low-spec
  audience `ROADMAP.md`'s "harness, not the model" section already targets.
- **`v1.15.1`: GPG passphrase modal fix.** Was appearing on every commit for
  users whose pinentry can already supply it without prompting — an actual
  annoyance-class regression fix, not a feature.

`v1.16.1`'s other headline items (Gemini 3.6 Flash, Git Panel grouping,
Mermaid diagram zoom) are upstream cloud/model-list changes this fork's own
system prompt and provider setup (see the Local AI section above) are
independent of, and don't need to block a sync. Same reasoning applies to
Gemini 3.7 Flash once `v1.17.0` actually ships stable.

Remaining: do the actual squashed sync to `v1.16.1` (same process as the
`v1.15.0` sync already recorded in `CREDITS.md`), re-verify the native system
prompt customizations in `crates/agent/src/templates/system_prompt.hbs`
survive it, per the pattern already used for the v1.15.0 sync earlier.

## Other tracked items (not blocking use)

- macOS builds in the release workflow (needs a Mac runner + signing).
- Richer installer polish and code signing (removes the SmartScreen warning).
- Settings migration for users coming from Zed. The directory rename itself is
  already done — `config_dir()` in `crates/paths` resolves to `%APPDATA%\V-Agent`
  and `~/.config/v-agent`, so a Zed user's existing settings are simply not
  picked up rather than being converted.
- `uvx` guidance for Python-based MCP servers.
- `/model` listing configured external agents (Claude/Codex ACP) alongside
  local and BYO-key models.
