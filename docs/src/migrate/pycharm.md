---
title: How to Migrate from PyCharm to V-Agent
description: "Guide for migrating from PyCharm to V-Agent, including settings and keybindings."
---

# How to Migrate from PyCharm to V-Agent

This guide covers how to set up V-Agent if you're coming from PyCharm, including keybindings, settings, and the differences you should expect.

## Install V-Agent

V-Agent is available on macOS, Windows, and Linux.

For macOS, you can download it from zed.dev/download, or install via Homebrew:

```sh
brew install --cask zed
```

For Windows, download the installer from zed.dev/download, or install via winget:

```sh
winget install Zed.Zed
```

For most Linux users, the easiest way to install V-Agent is through our installation script:

```sh
curl -f https://zed.dev/install.sh | sh
```

After installation, you can launch V-Agent from your Applications folder (macOS), Start menu (Windows), or directly from the terminal using:
`zed .`
This opens the current directory in V-Agent.

## Set Up the JetBrains Keymap

If you're coming from PyCharm, the fastest way to feel at home is to use the JetBrains keymap. During onboarding, you can select it as your base keymap. If you missed that step, you can change it anytime:

1. Open Settings with `Cmd+,` (macOS) or `Ctrl+,` (Linux/Windows)
2. Search for `Base Keymap`
3. Select `JetBrains`

This maps familiar shortcuts like `Shift Shift` for Search Everywhere, `Cmd+O` for Go to Class, and `Cmd+Shift+A` for Find Action.

## Set Up Editor Preferences

You can configure most settings in the Settings Editor ({#kb zed::OpenSettings}). For advanced settings, run {#action zed::OpenSettingsFile} from the Command Palette to edit your settings file directly.

Settings PyCharm users typically configure first:

| V-Agent Setting             | What it does                                                                    |
| ----------------------- | ------------------------------------------------------------------------------- |
| `format_on_save`        | Auto-format when saving. Set to `"on"` to enable.                               |
| `soft_wrap`             | Wrap long lines. Options: `"none"`, `"editor_width"`, `"preferred_line_length"` |
| `preferred_line_length` | Column width for wrapping and rulers. Default is 80, PEP 8 recommends 79.       |
| `inlay_hints`           | Show parameter names and type hints inline, like PyCharm's hints.               |
| `relative_line_numbers` | Useful if you're coming from IdeaVim.                                           |

V-Agent also supports per-project settings. Create a `.zed/settings.json` file in your project root to override global settings for that project, similar to how you might use `.idea` folders in PyCharm.

> **Tip:** If you're joining an existing project, check `format_on_save` before making your first commit. Otherwise you might accidentally reformat an entire file when you only meant to change one line.

## Open or Create a Project

After setup, press `Cmd+Shift+O` (with JetBrains keymap) to open a folder. This becomes your workspace in V-Agent. Unlike PyCharm, there's no project configuration wizard, no interpreter selection dialog, and no project structure setup required.

To start a new project, create a directory using your terminal or file manager, then open it in V-Agent. The editor will treat that folder as the root of your project.

You can also launch V-Agent from the terminal inside any folder with:
`zed .`

Once inside a project:

- Use `Cmd+Shift+O` or `Cmd+E` to jump between files quickly (like PyCharm's "Recent Files")
- Use `Cmd+Shift+A` or `Shift Shift` to open the Command Palette (like PyCharm's "Search Everywhere")
- Use `Cmd+O` to search for symbols (like PyCharm's "Go to Symbol")

Open buffers appear as tabs across the top. The Project Panel shows your file tree and Git status. Toggle it with `Cmd+1` (just like PyCharm's Project tool window).

## Differences in Keybindings

If you chose the JetBrains keymap during onboarding, most of your shortcuts should already feel familiar. Here's a quick reference for how V-Agent compares to PyCharm.

### Common Shared Keybindings

| Action                        | Shortcut                |
| ----------------------------- | ----------------------- |
| Search Everywhere             | `Shift Shift`           |
| Find Action / Command Palette | `Cmd + Shift + A`       |
| Go to File                    | `Cmd + Shift + O`       |
| Go to Symbol                  | `Cmd + O`               |
| Recent Files                  | `Cmd + E`               |
| Go to Definition              | `Cmd + B`               |
| Find Usages                   | `Alt + F7`              |
| Rename Symbol                 | `Shift + F6`            |
| Reformat Code                 | `Cmd + Alt + L`         |
| Toggle Project Panel          | `Cmd + 1`               |
| Toggle Terminal               | `Alt + F12`             |
| Duplicate Line                | `Cmd + D`               |
| Delete Line                   | `Cmd + Backspace`       |
| Move Line Up/Down             | `Shift + Alt + Up/Down` |
| Expand/Shrink Selection       | `Alt + Up/Down`         |
| Comment Line                  | `Cmd + /`               |
| Go Back / Forward             | `Cmd + [` / `Cmd + ]`   |
| Toggle Breakpoint             | `Ctrl + F8`             |

### Different Keybindings (PyCharm → V-Agent)

| Action                 | PyCharm     | V-Agent (JetBrains keymap)   |
| ---------------------- | ----------- | ------------------------ |
| File Structure         | `Cmd + F12` | `Cmd + F12` (outline)    |
| Navigate to Next Error | `F2`        | `F2`                     |
| Run                    | `Ctrl + R`  | `Ctrl + Alt + R` (tasks) |
| Debug                  | `Ctrl + D`  | `Alt + Shift + F9`       |
| Stop                   | `Cmd + F2`  | `Ctrl + F2`              |

### Unique to V-Agent

| Action            | Shortcut                   | Notes                          |
| ----------------- | -------------------------- | ------------------------------ |
| Toggle Right Dock | `Cmd + R`                  | Agent panel, notifications     |
| Split Panes       | `Cmd + K`, then arrow keys | Create splits in any direction |

### How to Customize Keybindings

- Open the Command Palette (`Cmd+Shift+A` or `Shift Shift`)
- Run {#action zed::OpenKeymap}

This opens a list of all available bindings. You can override individual shortcuts or remove conflicts.

V-Agent also supports key sequences (multi-key shortcuts).

## Differences in User Interfaces

### No Indexing

If you've used PyCharm on large projects, you know the wait: "Indexing..." can take anywhere from 30 seconds to several minutes depending on project size and dependencies. PyCharm builds a comprehensive index of your entire codebase to power its code intelligence, and it re-indexes when dependencies change or when you install new packages.

V-Agent doesn't index. You open a folder and start working immediately. File search and navigation stay fast regardless of project size, without waiting through indexing pauses.

PyCharm's index powers features like finding all usages across your entire codebase, understanding class hierarchies, and detecting unused imports project-wide. V-Agent delegates this work to language servers, which may not analyze as deeply or as broadly.

**How to adapt:**

- For project-wide symbol search, use `Cmd+O` / Go to Symbol (relies on your language server)
- For finding files by name, use `Cmd+Shift+O` / Go to File
- For text search across files, use `Cmd+Shift+F`—this is fast even on large codebases
- For deep static analysis, consider running tools like `mypy`, `pylint`, or `ruff check` from the terminal

### LSP vs. Native Language Intelligence

PyCharm has its own language analysis engine built specifically for Python. This engine understands your code deeply: it resolves types without annotations, tracks data flow, knows about Django models and Flask routes, and offers specialized refactorings.

V-Agent uses the Language Server Protocol (LSP) for code intelligence. For Python, V-Agent provides several language servers out of the box:

- **basedpyright** (default) — Fast type checking and completions
- **Ruff** (default) — Linting and formatting
- **ty** — Up-and-coming language server from Astral, built for speed
- **Pyright** — Microsoft's type checker
- **PyLSP** — Plugin-based server with tool integrations

The LSP experience for Python is strong. basedpyright provides accurate completions, type checking, and navigation. Ruff handles formatting and linting with excellent performance.

Where you might notice differences:

- Framework-specific intelligence (Django ORM, Flask routes) isn't built-in
- Some complex refactorings (extract method with proper scope analysis) may be less sophisticated
- Auto-import suggestions depend on what the language server knows about your environment

**How to adapt:**

- Use `Alt+Enter` for available code actions—the list will vary by language server
- Ensure your virtual environment is selected so the language server can resolve your dependencies
- Use Ruff for fast, consistent formatting (it's enabled by default)
- For code inspection similar to PyCharm's "Inspect Code," run `ruff check .` or check the Diagnostics panel (`Cmd+6`)—basedpyright and Ruff together catch many of the same issues

### Virtual Environments and Interpreters

In PyCharm, you select a Python interpreter through a GUI, and PyCharm manages the connection between your project and that interpreter. It shows available packages, lets you install new ones, and keeps track of which environment each project uses.

V-Agent handles virtual environments through its toolchain system:

- V-Agent automatically discovers virtual environments in common locations (`.venv`, `venv`, `.env`, `env`)
- When a virtual environment is detected, the terminal auto-activates it
- Language servers are automatically configured to use the discovered environment
- You can manually select a toolchain if auto-detection picks the wrong one

**How to adapt:**

- Create your virtual environment with `python -m venv .venv` or `uv sync`
- Open the folder in V-Agent—it will detect the environment automatically
- If you need to switch environments, use the toolchain selector
- For conda environments, ensure they're activated in your shell before launching V-Agent

> **Tip:** If basedpyright shows import errors for packages you've installed, check that V-Agent has selected the correct virtual environment. Use the toolchain selector to verify or change the active environment.

### No Project Model

PyCharm manages projects through `.idea` folders containing XML configuration files, interpreter assignments, and run configurations. This model lets PyCharm remember your interpreter choice, manage dependencies through the UI, and persist complex run/debug setups.

V-Agent has no project model. A project is a folder. There's no wizard, no interpreter selection screen, no project structure configuration.

This means:

- Run configurations don't exist. You define tasks or use the terminal. Your existing PyCharm run configs in `.idea/` won't be read—you'll recreate the ones you need in `tasks.json`.
- Interpreter management is external. V-Agent discovers environments but doesn't create them.
- Dependencies are managed through pip, uv, poetry, or conda—not through the editor.
- There's no Python Console (interactive REPL) panel. Use `python` or `ipython` in the terminal instead.

**How to adapt:**

- Create a `.zed/settings.json` in your project root for project-specific settings
- Define common commands in `tasks.json` (open via Command Palette: {#action zed::OpenTasks}):

```json
[
  {
    "label": "run",
    "command": "python main.py"
  },
  {
    "label": "test",
    "command": "pytest"
  },
  {
    "label": "test current file",
    "command": "pytest $ZED_FILE"
  }
]
```

- Use `Ctrl+Alt+R` to run tasks quickly
- Lean on your terminal (`Alt+F12`) for anything tasks don't cover

### No Framework Integration

PyCharm Professional's value for web development comes largely from its framework integration. Django templates are understood and navigable. Flask routes are indexed. SQLAlchemy models get special treatment. Template variables autocomplete.

V-Agent has none of this. The language server sees Python code as Python code—it doesn't understand that `@app.route` defines an endpoint or that a Django model class creates database tables.

**How to adapt:**

- Use grep and file search liberally. `Cmd+Shift+F` with a regex can find route definitions, model classes, or template usages.
- Rely on your language server's "find references" (`Alt+F7`) for navigation—it works, just without framework context
- Consider using framework-specific CLI tools (`python manage.py`, `flask routes`) from V-Agent's terminal

> **Tip:** For database work, pick up a dedicated tool like DataGrip, DBeaver, or TablePlus. Many developers who switch to V-Agent keep DataGrip around specifically for SQL.

### Tool Windows vs. Docks

PyCharm organizes auxiliary views into numbered tool windows (Project = 1, Python Console = 4, Terminal = Alt+F12, etc.). V-Agent uses a similar concept called "docks":

| PyCharm Tool Window | V-Agent Equivalent | Shortcut (JetBrains keymap) |
| ------------------- | -------------- | --------------------------- |
| Project (1)         | Project Panel  | `Cmd + 1`                   |
| Git (9 or Cmd+0)    | Git Panel      | `Cmd + 0`                   |
| Terminal (Alt+F12)  | Terminal Panel | `Alt + F12`                 |
| Structure (7)       | Outline Panel  | `Cmd + 7`                   |
| Problems (6)        | Diagnostics    | `Cmd + 6`                   |
| Debug (5)           | Debug Panel    | `Cmd + 5`                   |

V-Agent has three dock positions: left, bottom, and right. Panels can be moved between docks by dragging or through settings.

### Debugging

Both PyCharm and V-Agent offer integrated debugging, but the experience differs:

- V-Agent uses `debugpy` (the same debug adapter that VS Code uses)
- Set breakpoints with `Ctrl+F8`
- Start debugging with `Alt+Shift+F9` or press `F4` and select a debug target
- Step through code with `F7` (step into), `F8` (step over), `Shift+F8` (step out)
- Continue execution with `F9`

V-Agent can automatically detect debuggable entry points. Press `F4` to see available options, including:

- Python scripts
- Modules
- pytest tests

For more control, create a `.zed/debug.json` file:

```json
[
  {
    "label": "Debug Current File",
    "adapter": "Debugpy",
    "program": "$ZED_FILE",
    "request": "launch"
  },
  {
    "label": "Debug Flask App",
    "adapter": "Debugpy",
    "request": "launch",
    "module": "flask",
    "args": ["run", "--debug"],
    "env": {
      "FLASK_APP": "app.py"
    }
  }
]
```

### Running Tests

PyCharm has a dedicated test runner with a visual interface showing pass/fail status for each test. V-Agent provides test running through:

- **Gutter icons** — Click the play button next to test functions or classes
- **Tasks** — Define pytest or unittest commands in `tasks.json`
- **Terminal** — Run `pytest` directly

The test output appears in the terminal panel. For pytest, use `--tb=short` for concise tracebacks or `-v` for verbose output.

### Extensions vs. Plugins

PyCharm has a large plugin catalog covering everything from additional language support to database tools to deployment integrations.

V-Agent's extension catalog is smaller and more focused:

- Language support and syntax highlighting
- Themes
- Context servers

Several features that require plugins in PyCharm are built into V-Agent:

- Real-time collaboration with voice chat
- AI coding assistance
- Built-in terminal
- Task runner
- LSP-based code intelligence
- Ruff formatting and linting

### What's Not in V-Agent

To set expectations clearly, here's what PyCharm offers that V-Agent doesn't have:

- **Scientific Mode / Jupyter integration** — For notebooks and data science workflows, use JupyterLab or VS Code with the Jupyter extension alongside V-Agent for your Python editing
- **Database tools** — Use DataGrip, DBeaver, or TablePlus
- **Django/Flask template navigation** — Use file search and grep
- **Visual package manager** — Use pip, uv, or poetry from the terminal
- **Remote interpreters** — V-Agent has remote development, but it works differently
- **Profiler integration** — Use cProfile, py-spy, or similar tools externally

## Collaboration in V-Agent vs. PyCharm

PyCharm offers Code With Me as a separate plugin for collaboration. V-Agent has collaboration built into the core experience.

- Open the Collab Panel in the left dock
- Create a channel and [invite your collaborators](https://zed.dev/docs/collaboration#inviting-a-collaborator) to join
- [Share your screen or your codebase](https://zed.dev/docs/collaboration#share-a-project) directly

Once connected, you'll see each other's cursors, selections, and edits in real time. Voice chat is included. There's no need for separate tools or third-party logins.

## Using AI in V-Agent

If you're used to AI assistants in PyCharm (like GitHub Copilot or JetBrains AI Assistant), V-Agent offers similar capabilities with more flexibility.

### Configuring GitHub Copilot

1. Open Settings with `Cmd+,` (macOS) or `Ctrl+,` (Linux/Windows)
2. Navigate to **AI → Edit Predictions**
3. Click **Configure** next to "Configure Providers"
4. Under **GitHub Copilot**, click **Sign in to GitHub**

Once signed in, just start typing. V-Agent will offer suggestions inline for you to accept.

### Additional AI Options

To use other AI models in V-Agent, you have several options:

- Use V-Agent's hosted models, with higher rate limits. Requires [authentication](https://zed.dev/docs/authentication) and access through [Zed Pro](https://zed.dev/docs/account/zed-hosted-models.html).
- Bring your own [API keys](https://zed.dev/docs/ai/use-api-access.html), no authentication needed
- Use [External Agents like Claude Agent](https://zed.dev/docs/ai/external-agents.html)

## Advanced Config and Productivity Tweaks

V-Agent exposes advanced settings for power users who want to fine-tune their environment.

Here are a few useful tweaks:

**Format on Save:**

```json
"format_on_save": "on"
```

**Enable direnv support (useful for Python projects using direnv):**

```json
"load_direnv": "shell_hook"
```

**Customize virtual environment detection** (requires manual JSON editing):

```json
{
  "terminal": {
    "detect_venv": {
      "on": {
        "directories": [".venv", "venv", ".env", "env"],
        "activate_script": "default"
      }
    }
  }
}
```

**Configure basedpyright type checking strictness:**

If you find basedpyright too strict or too lenient, configure it in your project's `pyrightconfig.json`:

```json
{
  "typeCheckingMode": "basic"
}
```

Options are `"off"`, `"basic"`, `"standard"` (default), `"strict"`, or `"all"`.

## Next Steps

Now that you're set up, here are some resources to help you get the most out of V-Agent:

- [All Settings](../reference/all-settings.md) — Customize settings, themes, and editor behavior
- [Key Bindings](../key-bindings.md) — Learn how to customize and extend your keymap
- [Tasks](../tasks.md) — Set up build and run commands for your projects
- [AI Features](../ai/overview.md) — Explore V-Agent's AI capabilities beyond code completion
- Collaboration — Share your projects and code together in real time
- [Python in V-Agent](../languages/python.md) — Python-specific setup and configuration
