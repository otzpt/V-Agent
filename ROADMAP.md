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

## Other tracked items (not blocking use)

- macOS builds in the release workflow (needs a Mac runner + signing).
- Richer installer polish and code signing (removes the SmartScreen warning).
- Config directory rename `%APPDATA%\Zed` → `V-Agent` with settings migration.
- `uvx` guidance for Python-based MCP servers.
- `/model` listing configured external agents (Claude/Codex ACP) alongside
  local and BYO-key models.
