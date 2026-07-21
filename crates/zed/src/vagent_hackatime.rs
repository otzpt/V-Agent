//! V-Agent: Hackatime / WakaTime coding-time tracking.
//!
//! Sends heartbeats through `wakatime-cli` — the standard WakaTime agent, which
//! handles queuing, offline buffering, and reads credentials (`api_key`,
//! `api_url`) from `~/.wakatime.cfg`. Hackatime provides that config from
//! <https://hackatime.hackclub.com/my/wakatime_setup>.
//!
//! Tracking is entirely opt-in: if `wakatime-cli` isn't installed or
//! `~/.wakatime.cfg` is missing, this does nothing at all — no network calls,
//! no errors, no prompts.

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Mutex;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use gpui::{App, Context, Entity};
use workspace::{Event, MultiWorkspace, Workspace};

/// Identifies V-Agent to the WakaTime API.
const PLUGIN: &str = "V-Agent/1.0.0";

/// WakaTime's convention: at most one heartbeat per file per two minutes,
/// unless the file was just saved (a "write", which always sends).
const THROTTLE: Duration = Duration::from_secs(120);

/// Last heartbeat sent per file, so we respect the throttle.
static LAST_SENT: Mutex<Option<HashMap<String, SystemTime>>> = Mutex::new(None);

/// `~/.wakatime.cfg` — presence of this file is what opts the user in.
fn wakatime_config_present() -> bool {
    dirs_home()
        .map(|home| home.join(".wakatime.cfg").is_file())
        .unwrap_or(false)
}

fn dirs_home() -> Option<PathBuf> {
    std::env::var_os("USERPROFILE")
        .or_else(|| std::env::var_os("HOME"))
        .map(PathBuf::from)
}

/// Locate `wakatime-cli` on PATH, or where the official installers put it
/// (`~/.wakatime/wakatime-cli`).
fn wakatime_cli() -> Option<PathBuf> {
    let exe = if cfg!(windows) {
        "wakatime-cli.exe"
    } else {
        "wakatime-cli"
    };

    if let Some(paths) = std::env::var_os("PATH") {
        for dir in std::env::split_paths(&paths) {
            let candidate = dir.join(exe);
            if candidate.is_file() {
                return Some(candidate);
            }
        }
    }

    // Fall back to the standard install location used by WakaTime plugins.
    let home = dirs_home()?;
    for name in [exe, "wakatime-cli-windows-amd64.exe"] {
        let candidate = home.join(".wakatime").join(name);
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    None
}

/// True if enough time has passed for this file (writes always pass).
fn should_send(entity: &str, is_write: bool) -> bool {
    let now = SystemTime::now();
    let mut guard = match LAST_SENT.lock() {
        Ok(guard) => guard,
        Err(_) => return false,
    };
    let seen = guard.get_or_insert_with(HashMap::new);

    if !is_write
        && let Some(last) = seen.get(entity)
        && now.duration_since(*last).unwrap_or(THROTTLE) < THROTTLE
    {
        return false;
    }

    seen.insert(entity.to_string(), now);
    true
}

/// Fire a heartbeat. Detached and best-effort: failures are never surfaced to
/// the user, matching how other editors' WakaTime plugins behave.
fn send_heartbeat(entity: String, is_write: bool) {
    if !wakatime_config_present() {
        return;
    }
    let Some(cli) = wakatime_cli() else {
        return;
    };
    if !should_send(&entity, is_write) {
        return;
    }

    let time = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64();

    let mut cmd = std::process::Command::new(cli);
    cmd.args([
        "--entity",
        &entity,
        "--entity-type",
        "file",
        "--plugin",
        PLUGIN,
        "--time",
        &format!("{time:.3}"),
    ]);
    if is_write {
        cmd.arg("--write");
    }
    // `wakatime-cli` infers language and project (from git) itself, and reads
    // api_key / api_url from ~/.wakatime.cfg.
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd.stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null());
    let _ = cmd.spawn();
}

/// Absolute path of the item's file, if it has one on disk.
fn entity_for(item: &dyn workspace::ItemHandle, workspace: &Entity<Workspace>, cx: &App) -> Option<String> {
    let project_path = item.project_path(cx)?;
    let worktree = workspace
        .read(cx)
        .project()
        .read(cx)
        .worktree_for_id(project_path.worktree_id, cx)?;
    let abs = worktree.read(cx).absolutize(&project_path.path);
    Some(abs.to_string_lossy().to_string())
}

/// Watch a workspace and report coding activity to Hackatime/WakaTime.
/// Call once per window from `initialize_workspace`.
pub fn watch(workspace: &Entity<Workspace>, cx: &mut Context<MultiWorkspace>) {
    cx.subscribe(workspace, |_multi, workspace, event: &Event, cx| {
        match event {
            // Saving is a "write" — always reported.
            Event::UserSavedItem { item, .. } => {
                if let Some(item) = item.upgrade()
                    && let Some(entity) = entity_for(item.as_ref(), &workspace, cx)
                {
                    send_heartbeat(entity, true);
                }
            }
            // Opening or switching files is activity too (throttled).
            Event::ItemAdded { item } => {
                if let Some(entity) = entity_for(item.as_ref(), &workspace, cx) {
                    send_heartbeat(entity, false);
                }
            }
            Event::ActiveItemChanged => {
                if let Some(item) = workspace.read(cx).active_item(cx)
                    && let Some(entity) = entity_for(item.as_ref(), &workspace, cx)
                {
                    send_heartbeat(entity, false);
                }
            }
            _ => {}
        }
    })
    .detach();
}
