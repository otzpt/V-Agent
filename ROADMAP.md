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

### Void Linux: packaged, Vulkan confirmed

Steps 1, 2, 4 and 5 of the previous plan are done; step 3 (upstream inclusion
in `void-packages`) is the only one left, and it is an adoption problem rather
than a technical one.

**Vulkan is confirmed working** on a real glibc-Void install (the missing half
of the earlier check, which had only verified glibc 2.41). OBSERVED on Void
6.18.50_1, NVIDIA RTX 3050 Mobile, driver 595.91.07: the release binary
enumerated the GPU through the Vulkan backend and reached
`[workspace] Rendered first frame`, reporting
`GpuSpecs { is_software_emulated: false, device_name: "NVIDIA GeForce RTX 3050
Laptop GPU", driver_name: "NVIDIA" }`. `ldd` on the release binary resolves
every `NEEDED` entry on a stock Void install with no extra packages.

**The glibc floor in this repository is wrong.** README.md, docs/src/linux.md
and docs/src/installation.md all state glibc >= 2.31, inherited from upstream
Zed. MEASURED on the v1.1.1 release binary (sha256 verified against the release
asset): `objdump -T` reports non-weak `__libc_start_main@GLIBC_2.34` and
`hypot@GLIBC_2.35`, so it cannot start below 2.35. The release workflow builds
on `ubuntu-22.04`, which ships glibc 2.35, so the floor tracks the runner.
Upstream's 2.31 may well be correct for upstream's own binaries; it is not
correct for ours. Only the Void package and its docs were corrected here,
because the repository-wide fix is a decision rather than an edit: either
restate the requirement as 2.35 everywhere, or move the Linux build to an older
runner or a sysroot so 2.31 becomes true again. Ubuntu 20.04 runners are
retired, so the second option means a container or `cargo-zigbuild`.

Two things worth recording from that check:

- **CUDA being broken is not evidence Vulkan is.** On the same machine
  `cuInit(0)` returns 999 through `libcuda.so.1`, and Vulkan works anyway.
  They are separate driver entry points, and V-Agent uses only Vulkan.
- **`mesa` installs no Vulkan ICD on Void.** The drivers are separate
  packages (`mesa-vulkan-radeon`, `mesa-vulkan-intel`, `mesa-vulkan-nouveau`,
  `mesa-vulkan-lavapipe`) and there is no `vulkan-driver` virtual package to
  depend on, unlike Arch. On the machine tested only `nvidia_icd.json` was
  present, so the integrated Radeon was visible to wgpu through the GL backend
  only. A Void package therefore cannot guarantee a working GPU by its
  dependencies alone; the driver has to be named in the docs and release
  notes instead, and it is.

Two packaging paths now exist, deliberately:

- `packaging/void/template`, an `xbps-src` template (`v-agent-bin`), mirroring
  `packaging/arch/PKGBUILD-bin`. This is the one to submit to `void-packages`.
  xbps-src derives the library dependencies from the binary's `NEEDED` entries
  against `common/shlibs`, so they cannot drift; only the dlopened ones
  (`vulkan-loader`, `wayland`, `libglvnd`, `fontconfig`) and `git` are declared
  by hand. VERIFIED by building it: `./xbps-src pkg v-agent-bin` produced
  `v-agent-bin-1.1.1_1.x86_64.xbps` (405 MB, 2284 MB installed) with the
  expected three files and fourteen runtime dependencies, no lint warnings.
  `xbps-src binary-bootstrap` needs no root.
- A `Package Linux (Void .xbps)` step in the release workflow, building the
  same package with `xbps-create` in `ghcr.io/void-linux/void-glibc-full`.
  It hand-lists dependencies because `xbps-create` does no ELF scanning (that
  is an xbps-src hook), the same trade the Arch and `.deb` steps already make.
  Bootstrapping xbps-src in CI just to re-wrap an already-built binary is not
  worth the minutes.

Notes for whoever touches this next:

- **Do not rename the `.xbps` release asset.** xbps resolves a package file as
  `<pkgver>.<arch>.xbps` from the repository index; renaming it to
  `V-Agent-x86_64.xbps` for consistency with the other assets makes
  `xbps-install` fail with `failed to checksum: No such file or directory`.
  OBSERVED locally, which is why the asset keeps xbps-create's own filename.
- Installing needs the directory indexed first (`xbps-rindex -a`); xbps has no
  `pacman -U` equivalent.
- The ROADMAP previously named `voidlinux/voidlinux` on Docker Hub as the CI
  image. The official images are now under `ghcr.io/void-linux/`
  (`void-glibc-full`, `void-glibc`); the workflow uses the former.
- `script/linux` already had a Void branch, inherited from upstream. All
  twenty-one package names in it still resolve against current Void repos
  (checked with `xbps-query -R`). It installs `vulkan-loader` but no ICD, so
  a from-source build still needs the driver package installed separately.
- musl is still unsupported and untested, for the reason recorded before: the
  prebuilt binary is glibc-linked, and only `remote_server` has ever been
  built against `x86_64-unknown-linux-musl`.
- Installed size is 2.3 GB against a 405 MB download, because the release
  binary ships unstripped (`debug = "limited"` in `[profile.release]`, and the
  workflow deliberately does not strip, matching Arch's `!strip`). That is a
  release-profile question, not a packaging one, but it is a lot to ask of a
  distro package and is worth revisiting.

Docs live in `docs/src/development/voidlinux.md`, linked from `SUMMARY.md`.

Remaining: submit `v-agent-bin` to `void-packages`, which needs Void maintainer
review. The same adoption problem applies to Arch official and Debian, and the
same fallback applies: a self-hosted xbps repository users add once.

### Fedora/RHEL — `.rpm` added in 1.1.0

Built in a `fedora:latest` container (the runner is Ubuntu and has no
`rpmbuild`), matching how the Arch package is produced. `Requires:` are left to
rpmbuild's own ELF scan rather than hand-listed, so they cannot drift from the
binary's actual linkage. The `dist` tag is blanked because a single prebuilt
binary ships for every Fedora version.

Remaining: verify against a real Fedora install — the binary is built on
Ubuntu 22.04, so the generated glibc/soname requires must resolve on Fedora,
which has not been tested on a real system yet.

## Upstream sync — synced to v1.16.1 (2026-08-29)

Synced to `v1.16.1` (`eb8e1c8b5502`, see `CREDITS.md`), up from `v1.15.0`
(`e17dc4f9d50d`), as a single squashed commit on top of the recorded base per
`CREDITS.md`'s documented process. Both flagged items from the previous check
landed: the Linux memory usage improvement
([zed-industries/zed#62192](https://github.com/zed-industries/zed/pull/62192))
and the `v1.15.1` GPG passphrase-modal fix. The native system prompt
customizations in `crates/agent/src/templates/system_prompt.hbs` were
untouched by upstream in this range and came through byte-identical.

Upstream's `v1.15.0`..`v1.16.1` range also included several commits that were
cherry-picked onto the `v1.15.x` stable branch (not present in `v1.16.1`'s own
ancestry by commit hash, only by equivalent content already merged via `main`)
— the sync used `e17dc4f9d50d` as an explicit merge base
(`git merge-tree --merge-base=`) rather than git's auto-detected common
ancestor, so these showed up as no-op hunks instead of spurious conflicts.

Upstream has since moved on further: `v1.16.2`, `v1.16.3`, and a
`v1.17.0-pre` are already cut past `v1.16.1`. Not pulled in this pass, per
this file's convention of syncing to stable tags one release at a time.

Remaining: none for this sync. Next sync should target whatever `v1.17.x` (or
later) stable tag exists when picked up, re-checking
`system_prompt.hbs` again since upstream's extension-docs restructure in this
range (`docs/src/extensions/publishing/*.md` replacing part of
`developing-extensions.md`) is a reminder that doc/template reorganizations
can silently drop a rebrand if the merge isn't checked file-by-file.

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
