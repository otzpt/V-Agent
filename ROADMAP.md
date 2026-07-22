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

## Other tracked items (not blocking use)

- macOS builds in the release workflow (needs a Mac runner + signing).
- Richer installer polish and code signing (removes the SmartScreen warning).
- Config directory rename `%APPDATA%\Zed` → `V-Agent` with settings migration.
- `uvx` guidance for Python-based MCP servers.
- `/model` listing configured external agents (Claude/Codex ACP) alongside
  local and BYO-key models.
