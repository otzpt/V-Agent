//! V-Agent: when you open a file whose compiler/runtime isn't installed, show a
//! toast offering to install it. Companion to the F9 "Build & Run" task — this
//! catches the missing toolchain the moment the file opens, not just at run.

use std::collections::HashSet;
use std::sync::Mutex;

use gpui::{App, Context, Entity};
use notifications::status_toast::StatusToast;
use ui::{Color, Icon, IconName, IconSize};
use workspace::{Event, MultiWorkspace, Workspace};

/// Toolchains we already prompted about this session, keyed by [`Toolchain::key`],
/// so we never nag twice for the same language.
static PROMPTED: Mutex<Option<HashSet<&'static str>>> = Mutex::new(None);

struct Toolchain {
    /// Stable id used for de-duplicating prompts.
    key: &'static str,
    /// Executables to look for on PATH; missing only if *none* are present.
    binaries: &'static [&'static str],
    /// Human-friendly name shown in the toast.
    name: &'static str,
    /// Shell command(s) that install the toolchain (Windows-focused, with
    /// `||` fallbacks across package managers). Written to a .bat and run in a
    /// fresh console window.
    install: &'static str,
}

fn toolchain_for_ext(ext: &str) -> Option<Toolchain> {
    let ext = ext.to_ascii_lowercase();
    let tc = |key, binaries, name, install| Some(Toolchain { key, binaries, name, install });
    match ext.as_str() {
        "c" | "h" | "cpp" | "cc" | "cxx" | "c++" | "hpp" | "hh" | "hxx" | "ino" => tc(
            "gcc",
            &["gcc", "g++", "clang", "clang++", "cl"],
            "A C/C++ compiler (gcc)",
            "scoop install gcc || choco install -y mingw || winget install -e --id MSYS2.MSYS2",
        ),
        "py" | "pyw" => tc(
            "python",
            &["python", "python3", "py"],
            "Python",
            "winget install -e --id Python.Python.3.12",
        ),
        "js" | "mjs" | "cjs" | "ts" | "tsx" | "jsx" => tc(
            "node",
            &["node"],
            "Node.js",
            "winget install -e --id OpenJS.NodeJS",
        ),
        "go" => tc("go", &["go"], "Go", "winget install -e --id GoLang.Go"),
        "rs" => tc(
            "rust",
            &["cargo", "rustc"],
            "Rust",
            "winget install -e --id Rustlang.Rustup",
        ),
        "java" => tc(
            "java",
            &["java", "javac"],
            "The Java JDK",
            "winget install -e --id EclipseAdoptium.Temurin.21.JDK",
        ),
        "rb" => tc(
            "ruby",
            &["ruby"],
            "Ruby",
            "winget install -e --id RubyInstallerTeam.Ruby.3.3",
        ),
        "php" => tc(
            "php",
            &["php"],
            "PHP",
            "winget install -e --id PHP.PHP || scoop install php",
        ),
        "lua" => tc(
            "lua",
            &["lua"],
            "Lua",
            "scoop install lua || winget install -e --id DEVCOM.Lua",
        ),
        _ => None,
    }
}

/// True if any of `binaries` is found on PATH.
fn any_on_path(binaries: &[&str]) -> bool {
    let Some(paths) = std::env::var_os("PATH") else {
        return false;
    };
    let dirs: Vec<_> = std::env::split_paths(&paths).collect();
    binaries.iter().any(|bin| {
        let candidates: Vec<String> = if cfg!(windows) {
            vec![
                format!("{bin}.exe"),
                format!("{bin}.cmd"),
                format!("{bin}.bat"),
                bin.to_string(),
            ]
        } else {
            vec![bin.to_string()]
        };
        dirs.iter()
            .any(|dir| candidates.iter().any(|name| dir.join(name).is_file()))
    })
}

/// Launch the install command in a fresh, visible console window.
fn launch_install(script: &str) {
    #[cfg(windows)]
    {
        let mut path = std::env::temp_dir();
        path.push("vagent_install.bat");
        let body = format!(
            "@echo off\r\necho Installing via V-Agent...\r\n{script}\r\necho.\r\npause\r\n"
        );
        if std::fs::write(&path, body).is_ok()
            && let Some(p) = path.to_str()
        {
            let _ = std::process::Command::new("cmd")
                .args(["/c", "start", "V-Agent Install", "cmd", "/k", p])
                .spawn();
        }
    }
    #[cfg(not(windows))]
    {
        // Best-effort on Unix: try a few common terminal emulators, else run
        // the command detached in a login shell.
        let launched = ["x-terminal-emulator", "gnome-terminal", "konsole"]
            .iter()
            .any(|term| {
                std::process::Command::new(term)
                    .args(["-e", "sh", "-c", &format!("{script}; read -p 'Done. Press enter…'")])
                    .spawn()
                    .is_ok()
            });
        if !launched {
            let _ = std::process::Command::new("sh").args(["-c", script]).spawn();
        }
    }
}

fn maybe_prompt(workspace: Entity<Workspace>, ext: &str, cx: &mut App) {
    let Some(tc) = toolchain_for_ext(ext) else {
        return;
    };

    // Only prompt once per toolchain per session.
    {
        let mut guard = PROMPTED.lock().unwrap();
        let seen = guard.get_or_insert_with(HashSet::new);
        if !seen.insert(tc.key) {
            return;
        }
    }

    if any_on_path(tc.binaries) {
        return;
    }

    let name = tc.name;
    let install = tc.install;
    workspace.update(cx, |workspace, cx| {
        let toast = StatusToast::new(
            format!("{name} isn't installed — install it to build & run this file?"),
            cx,
            move |this, _cx| {
                this.icon(
                    Icon::new(IconName::Warning)
                        .size(IconSize::Small)
                        .color(Color::Warning),
                )
                // Persist until the user acts — an install prompt shouldn't
                // vanish on its own before they can click it.
                .auto_dismiss(false)
                .action("Install", move |_window, _cx| launch_install(install))
                .dismiss_button(true)
            },
        );
        workspace.toggle_status_toast(toast, cx);
    });
}

/// Watch a workspace for newly opened files and prompt to install any missing
/// toolchain. Call once per window from `initialize_workspace`.
pub fn watch(workspace: &Entity<Workspace>, cx: &mut Context<MultiWorkspace>) {
    cx.subscribe(workspace, |_multi, workspace, event: &Event, cx| {
        // Catch both newly opened items and the active item — the latter covers
        // files opened at startup via the CLI, before this subscription existed.
        let ext = match event {
            Event::ItemAdded { item } => item
                .project_path(cx)
                .and_then(|p| p.path.extension().map(str::to_string)),
            Event::ActiveItemChanged => workspace
                .read(cx)
                .active_item(cx)
                .and_then(|item| item.project_path(cx))
                .and_then(|p| p.path.extension().map(str::to_string)),
            _ => None,
        };
        if let Some(ext) = ext {
            maybe_prompt(workspace, &ext, cx);
        }
    })
    .detach();
}
