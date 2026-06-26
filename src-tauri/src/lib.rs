// V-Agent Rust backend
// Exposes file-system commands to the frontend and bridges the Python sidecar.

use std::collections::HashMap;
use std::fs;
use std::io::{Read, Write};
use std::path::Path;
use std::process::Command;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use portable_pty::{native_pty_system, CommandBuilder, PtySize};
use serde::Serialize;
use tauri::Emitter;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::{CommandEvent, CommandChild};

#[derive(Serialize)]
struct DirEntry {
    name: String,
    path: String,
    is_dir: bool,
}

// On Windows, spawning a console subprocess (git, wmic, nvidia-smi, powershell)
// flashes a console window in release builds where the app has no console of its
// own. CREATE_NO_WINDOW suppresses that. `new_command` wraps Command so every
// external process we launch is window-less on Windows and unchanged elsewhere.
#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

fn new_command(program: &str) -> Command {
    let mut cmd = Command::new(program);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd
}

// ── File system commands ───────────────────────────────────────────────

#[tauri::command]
fn read_file(path: String) -> Result<String, String> {
    fs::read_to_string(&path).map_err(|e| format!("read_file: {e}"))
}

#[tauri::command]
fn write_file(path: String, content: String) -> Result<(), String> {
    // atomic-ish write: write to temp then rename
    let tmp = format!("{path}.vatmp");
    fs::write(&tmp, content).map_err(|e| format!("write_file (tmp): {e}"))?;
    fs::rename(&tmp, &path).map_err(|e| format!("write_file (rename): {e}"))?;
    Ok(())
}

#[tauri::command]
fn list_dir(path: String) -> Result<Vec<DirEntry>, String> {
    let mut out = Vec::new();
    let entries = fs::read_dir(&path).map_err(|e| format!("list_dir: {e}"))?;
    for entry in entries.flatten() {
        let p = entry.path();
        let name = entry.file_name().to_string_lossy().to_string();
        // skip hidden + heavy dirs
        if name.starts_with('.') || name == "node_modules" || name == "__pycache__" {
            continue;
        }
        out.push(DirEntry {
            name,
            path: p.to_string_lossy().to_string(),
            is_dir: p.is_dir(),
        });
    }
    // folders first, then alphabetical
    out.sort_by(|a, b| match (a.is_dir, b.is_dir) {
        (true, false) => std::cmp::Ordering::Less,
        (false, true) => std::cmp::Ordering::Greater,
        _ => a.name.to_lowercase().cmp(&b.name.to_lowercase()),
    });
    Ok(out)
}

#[tauri::command]
fn path_exists(path: String) -> bool {
    Path::new(&path).exists()
}

#[tauri::command]
fn create_file(path: String, content: String) -> Result<(), String> {
    let p = Path::new(&path);
    if p.exists() {
        return Err(format!("create_file: already exists: {path}"));
    }
    if let Some(parent) = p.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("create_file (mkdir): {e}"))?;
    }
    fs::write(&path, content).map_err(|e| format!("create_file: {e}"))
}

#[tauri::command]
fn delete_file(path: String) -> Result<(), String> {
    let p = Path::new(&path);
    if p.is_dir() {
        fs::remove_dir(&path).map_err(|e| format!("delete_file (dir): {e}"))
    } else {
        fs::remove_file(&path).map_err(|e| format!("delete_file: {e}"))
    }
}

#[tauri::command]
fn rename_file(old_path: String, new_path: String) -> Result<(), String> {
    fs::rename(&old_path, &new_path).map_err(|e| format!("rename_file: {e}"))
}

#[tauri::command]
fn create_dir(path: String) -> Result<(), String> {
    fs::create_dir_all(&path).map_err(|e| format!("create_dir: {e}"))
}

// ── Settings helpers ───────────────────────────────────────────────────

fn config_dir() -> std::path::PathBuf {
    #[cfg(target_os = "windows")]
    {
        let base = std::env::var("APPDATA").unwrap_or_else(|_| ".".into());
        Path::new(&base).join("VAgent")
    }
    #[cfg(not(target_os = "windows"))]
    {
        let home = std::env::var("HOME").unwrap_or_else(|_| ".".into());
        Path::new(&home).join(".config").join("VAgent")
    }
}

#[tauri::command]
fn write_env_key(key: String, value: String) -> Result<(), String> {
    let dir = config_dir();
    fs::create_dir_all(&dir).map_err(|e| format!("write_env_key (mkdir): {e}"))?;
    let env_path = dir.join(".env");

    // Read existing lines, replace or append the key
    let existing = fs::read_to_string(&env_path).unwrap_or_default();
    let prefix = format!("{key}=");
    let new_line = format!("{key}={value}");
    let mut lines: Vec<String> = existing
        .lines()
        .map(|l| {
            if l.starts_with(&prefix) {
                new_line.clone()
            } else {
                l.to_string()
            }
        })
        .collect();
    if !lines.iter().any(|l| l.starts_with(&prefix)) {
        lines.push(new_line);
    }
    let content = lines.join("\n") + "\n";
    fs::write(&env_path, content).map_err(|e| format!("write_env_key (write): {e}"))
}

// ── Config (onboarding / first-run) ───────────────────────────────────

#[tauri::command]
fn get_config() -> Option<String> {
    let path = config_dir().join("config.json");
    fs::read_to_string(&path).ok()
}

#[tauri::command]
fn save_config(json: String) -> Result<(), String> {
    let dir = config_dir();
    fs::create_dir_all(&dir).map_err(|e| format!("save_config (mkdir): {e}"))?;
    fs::write(dir.join("config.json"), json).map_err(|e| format!("save_config: {e}"))
}

#[derive(Serialize)]
struct SystemInfo {
    total_ram_mb: u64,
    vram_mb: u64,
}

#[tauri::command]
fn get_system_info() -> SystemInfo {
    let total_ram_mb = get_total_ram_mb();
    let vram_mb = get_vram_mb();
    SystemInfo { total_ram_mb, vram_mb }
}

// Run a PowerShell command and return trimmed stdout (Windows only). Used as a
// fallback because `wmic` has been removed on recent Windows 11 builds.
#[cfg(target_os = "windows")]
fn powershell_query(command: &str) -> Option<String> {
    let out = new_command("powershell")
        .args(["-NoProfile", "-NonInteractive", "-Command", command])
        .output()
        .ok()?;
    if !out.status.success() {
        return None;
    }
    let s = String::from_utf8_lossy(&out.stdout).trim().to_string();
    if s.is_empty() { None } else { Some(s) }
}

fn get_total_ram_mb() -> u64 {
    #[cfg(target_os = "windows")]
    {
        // wmic ComputerSystem get TotalPhysicalMemory
        if let Ok(out) = new_command("wmic")
            .args(["ComputerSystem", "get", "TotalPhysicalMemory", "/value"])
            .output()
        {
            let s = String::from_utf8_lossy(&out.stdout);
            for line in s.lines() {
                if line.starts_with("TotalPhysicalMemory=") {
                    if let Ok(n) = line.trim_start_matches("TotalPhysicalMemory=").trim().parse::<u64>() {
                        return n / 1024 / 1024;
                    }
                }
            }
        }
        // Fallback for Win11 (no wmic): CIM via PowerShell
        if let Some(s) = powershell_query("(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory") {
            if let Ok(n) = s.parse::<u64>() {
                return n / 1024 / 1024;
            }
        }
    }
    #[cfg(target_os = "linux")]
    {
        if let Ok(content) = fs::read_to_string("/proc/meminfo") {
            for line in content.lines() {
                if line.starts_with("MemTotal:") {
                    let parts: Vec<&str> = line.split_whitespace().collect();
                    if let Some(kb) = parts.get(1) {
                        if let Ok(n) = kb.parse::<u64>() {
                            return n / 1024;
                        }
                    }
                }
            }
        }
    }
    0
}

fn get_vram_mb() -> u64 {
    // Try nvidia-smi first (cross-platform)
    if let Ok(out) = new_command("nvidia-smi")
        .args(["--query-gpu=memory.total", "--format=csv,noheader,nounits"])
        .output()
    {
        let s = String::from_utf8_lossy(&out.stdout);
        if let Ok(n) = s.trim().parse::<u64>() {
            return n;
        }
    }
    #[cfg(target_os = "windows")]
    {
        // wmic path win32_VideoController get AdapterRAM
        if let Ok(out) = new_command("wmic")
            .args(["path", "win32_VideoController", "get", "AdapterRAM", "/value"])
            .output()
        {
            let s = String::from_utf8_lossy(&out.stdout);
            for line in s.lines() {
                if line.starts_with("AdapterRAM=") {
                    if let Ok(n) = line.trim_start_matches("AdapterRAM=").trim().parse::<u64>() {
                        return n / 1024 / 1024;
                    }
                }
            }
        }
        // Fallback for Win11 (no wmic): largest AdapterRAM across video controllers
        if let Some(s) = powershell_query(
            "(Get-CimInstance Win32_VideoController | Measure-Object -Property AdapterRAM -Maximum).Maximum",
        ) {
            if let Ok(n) = s.parse::<u64>() {
                return n / 1024 / 1024;
            }
        }
    }
    0
}

// ── Hackatime / WakaTime heartbeats ───────────────────────────────────

fn os_name() -> &'static str {
    #[cfg(target_os = "windows")] { "Windows" }
    #[cfg(target_os = "linux")]   { "Linux"   }
    #[cfg(target_os = "macos")]   { "macOS"   }
    #[cfg(not(any(target_os = "windows", target_os = "linux", target_os = "macos")))]
    { "Unknown" }
}

#[tauri::command]
fn get_os_name() -> &'static str { os_name() }

// ── wakatime-cli helpers ───────────────────────────────────────────────

fn wakatime_cli_path() -> std::path::PathBuf {
    let home = std::env::var("USERPROFILE")
        .or_else(|_| std::env::var("HOME"))
        .unwrap_or_else(|_| ".".to_string());
    #[cfg(windows)]
    { Path::new(&home).join(".wakatime").join("wakatime-cli.exe") }
    #[cfg(not(windows))]
    { Path::new(&home).join(".wakatime").join("wakatime-cli") }
}

fn detect_waka_platform() -> (&'static str, &'static str) {
    let os   = if cfg!(windows) { "windows" } else if cfg!(target_os = "macos") { "darwin" } else { "linux" };
    let arch = if cfg!(target_arch = "aarch64") { "arm64" } else { "amd64" };
    (os, arch)
}

async fn download_wakatime_cli() -> Result<(), String> {
    let (os, arch) = detect_waka_platform();
    let zip_name = format!("wakatime-cli-{os}-{arch}.zip");
    let url = format!("https://github.com/wakatime/wakatime-cli/releases/latest/download/{zip_name}");

    let bytes = reqwest::Client::new()
        .get(&url)
        .send()
        .await
        .map_err(|e| format!("download wakatime-cli: {e}"))?
        .bytes()
        .await
        .map_err(|e| format!("read download: {e}"))?;

    let dest = wakatime_cli_path();
    fs::create_dir_all(dest.parent().unwrap())
        .map_err(|e| format!("mkdir ~/.wakatime: {e}"))?;

    let cursor = std::io::Cursor::new(&bytes[..]);
    let mut archive = zip::ZipArchive::new(cursor)
        .map_err(|e| format!("open zip: {e}"))?;

    for i in 0..archive.len() {
        let mut entry = archive.by_index(i)
            .map_err(|e| format!("zip entry: {e}"))?;
        let name = entry.name().to_lowercase();
        let is_cli = if cfg!(windows) { name.ends_with(".exe") } else { !name.contains('.') };
        if is_cli {
            let mut out = fs::File::create(&dest)
                .map_err(|e| format!("create wakatime-cli: {e}"))?;
            std::io::copy(&mut entry, &mut out)
                .map_err(|e| format!("extract wakatime-cli: {e}"))?;
            break;
        }
    }

    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(&dest, fs::Permissions::from_mode(0o755))
            .map_err(|e| format!("chmod wakatime-cli: {e}"))?;
    }

    Ok(())
}

async fn find_wakatime_cli() -> Result<String, String> {
    // 1. Check ~/.wakatime/wakatime-cli[.exe]
    let local = wakatime_cli_path();
    if local.exists() {
        return Ok(local.to_string_lossy().to_string());
    }
    // 2. Check PATH
    let bin = if cfg!(windows) { "wakatime-cli.exe" } else { "wakatime-cli" };
    if let Ok(out) = new_command(bin).arg("--version").output() {
        if out.status.success() {
            return Ok(bin.to_string());
        }
    }
    // 3. Download from GitHub releases
    download_wakatime_cli().await?;
    Ok(local.to_string_lossy().to_string())
}

#[tauri::command]
async fn send_heartbeat(
    entity:    String,
    project:   String,
    language:  String,
    is_write:  bool,
    api_key:   String,    // kept for frontend compat; wakatime-cli reads ~/.wakatime.cfg
    api_url:   String,    // kept for frontend compat
    lines:     Option<u32>,
    lineno:    Option<u32>,
    cursorpos: Option<u32>,
    branch:    Option<String>,
) -> Result<(), String> {
    let _ = (api_key, api_url, lines, branch); // auth/config handled by wakatime-cli

    let cli = find_wakatime_cli().await?;

    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs_f64();
    let time_str      = format!("{now:.3}");
    let lineno_str    = lineno.map(|v| v.to_string());
    let cursorpos_str = cursorpos.map(|v| v.to_string());

    let mut cmd = new_command(&cli);
    cmd.args([
        "--entity",      &entity,
        "--entity-type", "file",
        "--plugin",      "V-Agent/0.9.0",
        "--time",        &time_str,
        "--project",     &project,
        "--language",    &language,
    ]);
    if is_write                        { cmd.arg("--write"); }
    if let Some(ref l) = lineno_str    { cmd.args(["--lineno",    l]); }
    if let Some(ref c) = cursorpos_str { cmd.args(["--cursorpos", c]); }

    let out = cmd.output().map_err(|e| format!("wakatime-cli run: {e}"))?;

    if out.status.success() {
        Ok(())
    } else {
        let stderr = String::from_utf8_lossy(&out.stderr).trim().to_string();
        Err(if stderr.is_empty() {
            format!("wakatime-cli exited with code {}", out.status.code().unwrap_or(-1))
        } else {
            stderr
        })
    }
}

#[tauri::command]
fn get_file_line_count(path: String) -> Result<u32, String> {
    let content = fs::read_to_string(&path)
        .map_err(|e| format!("get_file_line_count: {e}"))?;
    Ok(content.lines().count() as u32)
}

// ── Arduino CLI ────────────────────────────────────────────────────────

/// Returns a list of serial port addresses detected by arduino-cli.
/// Returns an empty list (not an error) when no boards are connected.
/// Returns Err when arduino-cli is not installed.
#[tauri::command]
fn arduino_list_ports() -> Result<Vec<String>, String> {
    let out = new_command("arduino-cli")
        .args(["board", "list", "--format", "json"])
        .output()
        .map_err(|e| {
            if e.kind() == std::io::ErrorKind::NotFound {
                "arduino-cli not found. Install from https://arduino.github.io/arduino-cli/latest/installation/".to_string()
            } else {
                format!("arduino-cli board list: {e}")
            }
        })?;

    let Ok(json) = serde_json::from_slice::<serde_json::Value>(&out.stdout) else {
        return Ok(vec![]);
    };

    // arduino-cli ≥0.35 wraps ports in { "detected_ports": [...] };
    // older versions return a top-level array directly.
    let extract_ports = |arr: &Vec<serde_json::Value>| -> Vec<String> {
        arr.iter()
            .filter_map(|e| {
                e.get("port")?.get("address")?.as_str().map(String::from)
            })
            .collect()
    };

    if let Some(arr) = json.as_array() {
        return Ok(extract_ports(arr));
    }
    if let Some(arr) = json.get("detected_ports").and_then(|d| d.as_array()) {
        return Ok(extract_ports(arr));
    }
    Ok(vec![])
}

/// Compile an Arduino sketch (directory of the .ino file).
#[tauri::command]
fn arduino_compile(fqbn: String, file_path: String) -> Result<String, String> {
    let sketch_dir = Path::new(&file_path)
        .parent()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|| file_path.clone());
    let out = new_command("arduino-cli")
        .args(["compile", "--fqbn", &fqbn, &sketch_dir])
        .output()
        .map_err(|e| format!("arduino-cli compile: {e}"))?;
    let stdout = String::from_utf8_lossy(&out.stdout).to_string();
    let stderr = String::from_utf8_lossy(&out.stderr).to_string();
    let combined = if stderr.is_empty() { stdout } else { format!("{stdout}{stderr}") };
    if out.status.success() { Ok(combined) } else { Err(combined) }
}

/// Upload an Arduino sketch to a board via the given port.
#[tauri::command]
fn arduino_upload(port: String, fqbn: String, file_path: String) -> Result<String, String> {
    let sketch_dir = Path::new(&file_path)
        .parent()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|| file_path.clone());
    let out = new_command("arduino-cli")
        .args(["upload", "-p", &port, "--fqbn", &fqbn, &sketch_dir])
        .output()
        .map_err(|e| format!("arduino-cli upload: {e}"))?;
    let stdout = String::from_utf8_lossy(&out.stdout).to_string();
    let stderr = String::from_utf8_lossy(&out.stderr).to_string();
    let combined = if stderr.is_empty() { stdout } else { format!("{stdout}{stderr}") };
    if out.status.success() { Ok(combined) } else { Err(combined) }
}

// ── Extension store ───────────────────────────────────────────────────

fn extensions_dir() -> std::path::PathBuf {
    config_dir().join("extensions")
}

#[tauri::command]
async fn install_extension(id: String, url: String) -> Result<(), String> {
    let dir = extensions_dir().join(&id);
    fs::create_dir_all(&dir).map_err(|e| format!("install_extension mkdir: {e}"))?;
    let resp = reqwest::Client::new()
        .get(&url)
        .send()
        .await
        .map_err(|e| format!("install_extension download: {e}"))?;
    if !resp.status().is_success() {
        return Err(format!("download failed: HTTP {}", resp.status().as_u16()));
    }
    let bytes = resp.bytes().await
        .map_err(|e| format!("install_extension read: {e}"))?;
    fs::write(dir.join("main.py"), &bytes)
        .map_err(|e| format!("install_extension write: {e}"))?;
    Ok(())
}

#[tauri::command]
fn uninstall_extension(id: String) -> Result<(), String> {
    let dir = extensions_dir().join(&id);
    if dir.exists() {
        fs::remove_dir_all(&dir)
            .map_err(|e| format!("uninstall_extension: {e}"))?;
    }
    Ok(())
}

#[tauri::command]
fn list_extensions() -> Result<Vec<String>, String> {
    let dir = extensions_dir();
    if !dir.exists() { return Ok(vec![]); }
    let mut ids: Vec<String> = fs::read_dir(&dir)
        .map_err(|e| format!("list_extensions: {e}"))?
        .flatten()
        .filter(|e| e.path().is_dir())
        .map(|e| e.file_name().to_string_lossy().to_string())
        .collect();
    ids.sort();
    Ok(ids)
}

// ── Git integration ────────────────────────────────────────────────────

#[derive(Serialize, Clone)]
struct GitFileStatus {
    path:   String,
    status: String, // raw 2-char XY from `git status --porcelain`
}

#[derive(Serialize, Clone)]
struct GitLogEntry {
    hash:    String,
    message: String,
    date:    String,
}

/// Run a git sub-command in `cwd`, return (stdout, stderr, success).
fn git_run(cwd: &str, args: &[&str]) -> Result<String, String> {
    let out = new_command("git")
        .args(args)
        .current_dir(cwd)
        .output()
        .map_err(|e| format!("git {}: {e}", args.first().unwrap_or(&"")))?;

    if out.status.success() {
        Ok(String::from_utf8_lossy(&out.stdout).to_string())
    } else {
        Err(String::from_utf8_lossy(&out.stderr).trim().to_string())
    }
}

#[tauri::command]
fn git_status(cwd: String) -> Result<Vec<GitFileStatus>, String> {
    let stdout = git_run(&cwd, &["status", "--porcelain"])?;
    let files = stdout
        .lines()
        .filter(|l| l.len() >= 3)
        .map(|line| {
            let xy = &line[..2];
            let raw_path = &line[3..];
            // Renamed files have "old -> new"; take only the new path
            let path = if raw_path.contains(" -> ") {
                raw_path.splitn(2, " -> ").nth(1).unwrap_or(raw_path)
            } else {
                raw_path
            }
            .trim_matches('"')
            .to_string();
            GitFileStatus { path, status: xy.to_string() }
        })
        .collect();
    Ok(files)
}

#[tauri::command]
fn git_diff(cwd: String, file: String) -> Result<String, String> {
    // Try HEAD diff first (covers both staged and unstaged vs last commit)
    let out = new_command("git")
        .args(["diff", "HEAD", "--", &file])
        .current_dir(&cwd)
        .output()
        .map_err(|e| format!("git diff: {e}"))?;
    let s = String::from_utf8_lossy(&out.stdout).to_string();
    if !s.is_empty() { return Ok(s); }

    // Fall back to staged-only diff (new file just added)
    let out2 = new_command("git")
        .args(["diff", "--cached", "--", &file])
        .current_dir(&cwd)
        .output()
        .map_err(|e| format!("git diff --cached: {e}"))?;
    Ok(String::from_utf8_lossy(&out2.stdout).to_string())
}

#[tauri::command]
fn git_stage(cwd: String, files: Vec<String>) -> Result<(), String> {
    let out = new_command("git")
        .arg("add").arg("--").args(&files)
        .current_dir(&cwd).output()
        .map_err(|e| format!("git add: {e}"))?;
    if !out.status.success() {
        return Err(String::from_utf8_lossy(&out.stderr).trim().to_string());
    }
    Ok(())
}

#[tauri::command]
fn git_unstage(cwd: String, files: Vec<String>) -> Result<(), String> {
    let out = new_command("git")
        .arg("restore").arg("--staged").arg("--").args(&files)
        .current_dir(&cwd).output()
        .map_err(|e| format!("git restore: {e}"))?;
    if !out.status.success() {
        return Err(String::from_utf8_lossy(&out.stderr).trim().to_string());
    }
    Ok(())
}

#[tauri::command]
fn git_commit(cwd: String, message: String) -> Result<(), String> {
    git_run(&cwd, &["commit", "-m", &message])?;
    Ok(())
}

#[tauri::command]
fn git_push(cwd: String) -> Result<String, String> {
    git_run(&cwd, &["push"])
}

#[tauri::command]
fn git_pull(cwd: String) -> Result<String, String> {
    git_run(&cwd, &["pull"])
}

#[tauri::command]
fn git_log(cwd: String, limit: u32) -> Result<Vec<GitLogEntry>, String> {
    // Use ASCII unit-separator (0x1f) as field delimiter — very unlikely in messages
    let format = "--pretty=format:%h%x1f%s%x1f%cr";
    let n = format!("-{limit}");
    let stdout = git_run(&cwd, &["log", &n, format])?;
    let entries = stdout
        .lines()
        .filter(|l| !l.is_empty())
        .filter_map(|line| {
            let mut parts = line.splitn(3, '\x1f');
            Some(GitLogEntry {
                hash:    parts.next()?.to_string(),
                message: parts.next()?.to_string(),
                date:    parts.next().unwrap_or("").to_string(),
            })
        })
        .collect();
    Ok(entries)
}

#[tauri::command]
fn git_current_branch(cwd: String) -> Result<String, String> {
    git_run(&cwd, &["branch", "--show-current"])
        .map(|s| s.trim().to_string())
}

/// Returns the contents of `file` (repo-relative path) at HEAD. A newly-added
/// file is not in HEAD, so we return an empty string (diff shows pure additions).
#[tauri::command]
fn git_show_head(cwd: String, file: String) -> Result<String, String> {
    let spec = format!("HEAD:{file}");
    let out = new_command("git")
        .args(["show", &spec])
        .current_dir(&cwd)
        .output()
        .map_err(|e| format!("git show: {e}"))?;
    if out.status.success() {
        Ok(String::from_utf8_lossy(&out.stdout).to_string())
    } else {
        Ok(String::new())
    }
}

// ── Search in files ────────────────────────────────────────────────────

#[derive(Serialize)]
struct SearchHit {
    file:       String,
    line:       u32,    // 1-based
    col:        u32,    // 1-based char column of the match start
    length:     u32,    // match length in chars
    match_text: String, // exact matched text (for safe replace verification)
    preview:    String, // the source line (trimmed/truncated) for display
}

const SEARCH_MAX_HITS:       usize = 2000;
const SEARCH_MAX_FILE_BYTES: u64   = 2_000_000;
const SEARCH_PREVIEW_CHARS:  usize = 400;

fn search_skip_dir(name: &str) -> bool {
    name.starts_with('.')
        || matches!(name, "node_modules" | "__pycache__" | "target" | "dist" | "build")
}

enum Matcher {
    Plain { needle: String, case_sensitive: bool },
    Regex(regex::Regex),
}

fn scan_line(file: &str, line_no: u32, line: &str, matcher: &Matcher, hits: &mut Vec<SearchHit>) {
    let line_chars: Vec<char> = line.chars().collect();
    let preview: String = if line_chars.len() > SEARCH_PREVIEW_CHARS {
        line_chars[..SEARCH_PREVIEW_CHARS].iter().collect()
    } else {
        line.trim_end().to_string()
    };

    let push = |cstart: usize, clen: usize, hits: &mut Vec<SearchHit>| {
        let match_text: String = line_chars.iter().skip(cstart).take(clen).collect();
        hits.push(SearchHit {
            file:       file.to_string(),
            line:       line_no,
            col:        cstart as u32 + 1,
            length:     clen as u32,
            match_text,
            preview:    preview.clone(),
        });
    };

    match matcher {
        Matcher::Plain { needle, case_sensitive } => {
            if needle.is_empty() { return; }
            let (hay, ndl) = if *case_sensitive {
                (line.to_string(), needle.clone())
            } else {
                (line.to_lowercase(), needle.to_lowercase())
            };
            let ndl_chars = ndl.chars().count();
            let mut from = 0;
            while let Some(rel) = hay[from..].find(&ndl) {
                if hits.len() >= SEARCH_MAX_HITS { return; }
                let byte_idx = from + rel;
                let cstart = hay[..byte_idx].chars().count();
                push(cstart, ndl_chars, hits);
                from = byte_idx + ndl.len().max(1);
                if from > hay.len() { break; }
            }
        }
        Matcher::Regex(re) => {
            for m in re.find_iter(line) {
                if hits.len() >= SEARCH_MAX_HITS { return; }
                if m.start() == m.end() { continue; } // skip empty matches
                let cstart = line[..m.start()].chars().count();
                let clen   = line[m.start()..m.end()].chars().count();
                push(cstart, clen, hits);
            }
        }
    }
}

fn search_dir(dir: &Path, matcher: &Matcher, hits: &mut Vec<SearchHit>) {
    if hits.len() >= SEARCH_MAX_HITS { return; }
    let entries = match fs::read_dir(dir) { Ok(e) => e, Err(_) => return };
    for entry in entries.flatten() {
        if hits.len() >= SEARCH_MAX_HITS { return; }
        let path = entry.path();
        let name = entry.file_name().to_string_lossy().to_string();
        if path.is_dir() {
            if search_skip_dir(&name) { continue; }
            search_dir(&path, matcher, hits);
        } else {
            if let Ok(meta) = entry.metadata() {
                if meta.len() > SEARCH_MAX_FILE_BYTES { continue; }
            }
            let bytes = match fs::read(&path) { Ok(b) => b, Err(_) => continue };
            let probe_len = bytes.len().min(8000);
            if bytes[..probe_len].contains(&0) { continue; } // skip binary files
            let text = match String::from_utf8(bytes) { Ok(t) => t, Err(_) => continue };
            let file_str = path.to_string_lossy().to_string();
            for (i, line) in text.lines().enumerate() {
                if hits.len() >= SEARCH_MAX_HITS { return; }
                scan_line(&file_str, (i + 1) as u32, line, matcher, hits);
            }
        }
    }
}

#[tauri::command]
fn search_in_files(
    root:           String,
    query:          String,
    case_sensitive: bool,
    is_regex:       bool,
) -> Result<Vec<SearchHit>, String> {
    if query.is_empty() {
        return Ok(Vec::new());
    }
    let matcher = if is_regex {
        let re = regex::RegexBuilder::new(&query)
            .case_insensitive(!case_sensitive)
            .build()
            .map_err(|e| format!("invalid regex: {e}"))?;
        Matcher::Regex(re)
    } else {
        Matcher::Plain { needle: query, case_sensitive }
    };
    let mut hits = Vec::new();
    let root_path = Path::new(&root);
    if root_path.is_dir() {
        search_dir(root_path, &matcher, &mut hits);
    }
    Ok(hits)
}

/// Replace a single match span (char-based) at `file:line:col`. The caller passes
/// the exact `expected` text it found; if the file changed since the search the
/// replace is refused so we never clobber the wrong content.
#[tauri::command]
fn replace_in_file(
    file:        String,
    line:        u32,
    col:         u32,
    length:      u32,
    expected:    String,
    replacement: String,
) -> Result<(), String> {
    let text = fs::read_to_string(&file).map_err(|e| format!("replace_in_file read: {e}"))?;
    let mut lines: Vec<String> = text.split('\n').map(|s| s.to_string()).collect();
    let idx = (line as usize)
        .checked_sub(1)
        .ok_or_else(|| "replace_in_file: bad line".to_string())?;
    if idx >= lines.len() {
        return Err("replace_in_file: line out of range (file changed)".into());
    }
    let raw = lines[idx].clone();
    let had_cr = raw.ends_with('\r');
    let content_line = if had_cr { &raw[..raw.len() - 1] } else { &raw[..] };
    let chars: Vec<char> = content_line.chars().collect();
    let start = (col as usize).saturating_sub(1);
    let end = start + length as usize;
    if start > chars.len() || end > chars.len() {
        return Err("replace_in_file: column out of range (file changed)".into());
    }
    let found: String = chars[start..end].iter().collect();
    if found != expected {
        return Err("replace_in_file: text changed since search — re-run the search".into());
    }
    let mut new_line: String = chars[..start].iter().collect();
    new_line.push_str(&replacement);
    new_line.extend(chars[end..].iter());
    if had_cr { new_line.push('\r'); }
    lines[idx] = new_line;

    let joined = lines.join("\n");
    let tmp = format!("{file}.vatmp");
    fs::write(&tmp, joined).map_err(|e| format!("replace_in_file write: {e}"))?;
    fs::rename(&tmp, &file).map_err(|e| format!("replace_in_file rename: {e}"))?;
    Ok(())
}

// ── .vagent.json task runner ───────────────────────────────────────────

#[tauri::command]
fn read_vagent_config(path: String) -> Option<String> {
    // Accepts a folder path; reads <path>/.vagent.json
    let p = Path::new(&path).join(".vagent.json");
    fs::read_to_string(&p).ok()
}

#[tauri::command]
fn run_task(
    state: tauri::State<'_, PtyState>,
    pty_id: String,
    command: String,
    cwd: Option<String>,
) -> Result<(), String> {
    let mut map = state.0.lock().map_err(|e| format!("run_task lock: {e}"))?;
    let session = map.get_mut(&pty_id)
        .ok_or_else(|| format!("run_task: PTY session not found: {pty_id}"))?;

    // If a working directory is given, cd there first
    if let Some(dir) = cwd {
        let cd = if cfg!(windows) {
            format!("cd /d \"{dir}\"\r\n")
        } else {
            format!("cd \"{dir}\"\n")
        };
        session.writer.write_all(cd.as_bytes())
            .map_err(|e| format!("run_task cd: {e}"))?;
    }

    let line = if cfg!(windows) {
        format!("{command}\r\n")
    } else {
        format!("{command}\n")
    };
    session.writer.write_all(line.as_bytes())
        .map_err(|e| format!("run_task write: {e}"))
}

// ── PTY terminal ──────────────────────────────────────────────────────

static PTY_COUNTER: AtomicU64 = AtomicU64::new(1);

struct PtySession {
    writer: Box<dyn Write + Send>,
    master: Box<dyn portable_pty::MasterPty>,
    child:  Box<dyn portable_pty::Child + Send + Sync>,
}

// SAFETY: portable-pty's concrete MasterPty implementations (NativePtyMaster /
// ConPtyMaster) are thread-safe internally. The MasterPty trait does not declare
// Send as a supertrait for object-safety reasons, but every concrete impl is Send.
unsafe impl Send for PtySession {}

struct PtyState(Mutex<HashMap<String, PtySession>>);

#[derive(Serialize, Clone)]
struct PtyOutput {
    id:   String,
    data: String,
}

#[derive(Serialize)]
struct PtyCreateResult {
    id:    String,
    shell: String,
}

fn default_shell() -> String {
    #[cfg(windows)]
    { "cmd.exe".to_string() }
    #[cfg(not(windows))]
    {
        if Path::new("/bin/bash").exists() {
            "/bin/bash".to_string()
        } else {
            "/bin/sh".to_string()
        }
    }
}

#[tauri::command]
fn pty_create(
    app:   tauri::AppHandle,
    state: tauri::State<'_, PtyState>,
    shell: Option<String>,
    cols:  u16,
    rows:  u16,
) -> Result<PtyCreateResult, String> {
    let shell_path = shell.unwrap_or_else(default_shell);
    let id = format!("pty-{}", PTY_COUNTER.fetch_add(1, Ordering::SeqCst));

    let pty_system = native_pty_system();
    let cols = cols.max(10);
    let rows = rows.max(2);

    let pair = pty_system
        .openpty(PtySize { rows, cols, pixel_width: 0, pixel_height: 0 })
        .map_err(|e| format!("pty open: {e}"))?;

    let mut cmd = CommandBuilder::new(&shell_path);
    // Start in the user's home directory
    if let Ok(home) = std::env::var("USERPROFILE").or_else(|_| std::env::var("HOME")) {
        cmd.cwd(home);
    }

    let child = pair.slave
        .spawn_command(cmd)
        .map_err(|e| format!("pty spawn: {e}"))?;

    // Drop slave — child owns everything it needs from it
    drop(pair.slave);

    let mut reader = pair.master
        .try_clone_reader()
        .map_err(|e| format!("pty reader: {e}"))?;

    let writer = pair.master
        .take_writer()
        .map_err(|e| format!("pty writer: {e}"))?;

    // Spawn a background thread that streams PTY output to the frontend
    let id_for_output = id.clone();
    let id_for_close  = id.clone();
    let app_clone     = app.clone();
    std::thread::spawn(move || {
        let mut buf = vec![0u8; 4096];
        loop {
            match reader.read(&mut buf) {
                Ok(0) | Err(_) => break,
                Ok(n) => {
                    let data = String::from_utf8_lossy(&buf[..n]).to_string();
                    let _ = app_clone.emit("pty-output", PtyOutput {
                        id:   id_for_output.clone(),
                        data,
                    });
                }
            }
        }
        // Shell process exited — notify the frontend
        let _ = app_clone.emit("pty-closed", id_for_close);
    });

    state.0
        .lock()
        .map_err(|e| format!("pty state lock: {e}"))?
        .insert(id.clone(), PtySession { writer, master: pair.master, child });

    Ok(PtyCreateResult { id, shell: shell_path })
}

#[tauri::command]
fn pty_write(
    state: tauri::State<'_, PtyState>,
    id:    String,
    data:  String,
) -> Result<(), String> {
    let mut map = state.0.lock().map_err(|e| format!("pty state lock: {e}"))?;
    match map.get_mut(&id) {
        Some(s) => s.writer.write_all(data.as_bytes()).map_err(|e| format!("pty_write: {e}")),
        None    => Err(format!("pty_write: session {id} not found")),
    }
}

#[tauri::command]
fn pty_resize(
    state: tauri::State<'_, PtyState>,
    id:    String,
    cols:  u16,
    rows:  u16,
) -> Result<(), String> {
    let map = state.0.lock().map_err(|e| format!("pty state lock: {e}"))?;
    if let Some(s) = map.get(&id) {
        s.master
            .resize(PtySize { rows, cols, pixel_width: 0, pixel_height: 0 })
            .map_err(|e| format!("pty_resize: {e}"))?;
    }
    Ok(())
}

#[tauri::command]
fn pty_kill(
    state: tauri::State<'_, PtyState>,
    id:    String,
) -> Result<(), String> {
    let mut map = state.0.lock().map_err(|e| format!("pty state lock: {e}"))?;
    if let Some(mut session) = map.remove(&id) {
        let _ = session.child.kill();
    }
    Ok(())
}

// ── Persistent agent bridge (bidirectional) ────────────────────────────
// A single long-lived sidecar process. The frontend sends newline-delimited
// JSON requests via `agent_send` and receives every output line as an
// "agent-event" Tauri event. This powers the agentic tool-calling loop.

struct AgentState(Arc<Mutex<Option<CommandChild>>>);

#[tauri::command]
fn agent_start(app: tauri::AppHandle, state: tauri::State<'_, AgentState>) -> Result<(), String> {
    {
        let guard = state.0.lock().map_err(|e| format!("agent lock: {e}"))?;
        if guard.is_some() {
            return Ok(()); // already running
        }
    }

    let sidecar = app
        .shell()
        .sidecar("vagent-sidecar")
        .map_err(|e| format!("agent sidecar: {e}"))?;
    let (mut rx, child) = sidecar.spawn().map_err(|e| format!("agent spawn: {e}"))?;

    {
        let mut guard = state.0.lock().map_err(|e| format!("agent lock: {e}"))?;
        *guard = Some(child);
    }

    let app2 = app.clone();
    let slot = state.0.clone();
    tauri::async_runtime::spawn(async move {
        // Re-frame the byte stream into complete JSON lines before emitting.
        let mut buf = String::new();
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    buf.push_str(&String::from_utf8_lossy(&bytes));
                    while let Some(idx) = buf.find('\n') {
                        let line: String = buf.drain(..=idx).collect();
                        let line = line.trim_end().to_string();
                        if !line.is_empty() {
                            let _ = app2.emit("agent-event", line);
                        }
                    }
                }
                CommandEvent::Terminated(_) => {
                    if let Ok(mut g) = slot.lock() { *g = None; }
                    let _ = app2.emit("agent-event", "{\"type\":\"exit\"}".to_string());
                    break;
                }
                _ => {}
            }
        }
    });

    Ok(())
}

#[tauri::command]
fn agent_send(state: tauri::State<'_, AgentState>, line: String) -> Result<(), String> {
    let mut guard = state.0.lock().map_err(|e| format!("agent lock: {e}"))?;
    match guard.as_mut() {
        Some(child) => {
            let mut data = line.into_bytes();
            data.push(b'\n');
            child.write(&data).map_err(|e| format!("agent_send: {e}"))
        }
        None => Err("agent not running".into()),
    }
}

// ── Sidecar chat bridge (legacy single-shot) ───────────────────────────
// Sends one JSON request line to the Python sidecar and streams tokens back
// to the frontend via the "ai-token" event. Returns when the sidecar emits
// a line with {"done": true}.

#[tauri::command]
async fn ai_chat(
    app: tauri::AppHandle,
    payload: String,
) -> Result<(), String> {
    let sidecar = app
        .shell()
        .sidecar("vagent-sidecar")
        .map_err(|e| format!("sidecar spawn: {e}"))?;

    let (mut rx, mut child) = sidecar
        .spawn()
        .map_err(|e| format!("sidecar run: {e}"))?;

    // write the request as one line to the sidecar's stdin
    child
        .write(format!("{payload}\n").as_bytes())
        .map_err(|e| format!("sidecar stdin: {e}"))?;

    while let Some(event) = rx.recv().await {
        if let CommandEvent::Stdout(line) = event {
            let text = String::from_utf8_lossy(&line).to_string();
            let _ = app.emit("ai-token", text.clone());
            if text.contains("\"done\": true") || text.contains("\"done\":true") {
                break;
            }
        }
    }
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .manage(PtyState(Mutex::new(HashMap::new())))
        .manage(AgentState(Arc::new(Mutex::new(None))))
        .invoke_handler(tauri::generate_handler![
            read_file,
            write_file,
            list_dir,
            path_exists,
            create_file,
            delete_file,
            rename_file,
            create_dir,
            write_env_key,
            get_system_info,
            get_config,
            save_config,
            get_os_name,
            send_heartbeat,
            get_file_line_count,
            arduino_list_ports,
            arduino_compile,
            arduino_upload,
            install_extension,
            uninstall_extension,
            list_extensions,
            git_status,
            git_diff,
            git_stage,
            git_unstage,
            git_commit,
            git_push,
            git_pull,
            git_log,
            git_current_branch,
            git_show_head,
            search_in_files,
            replace_in_file,
            read_vagent_config,
            run_task,
            pty_create,
            pty_write,
            pty_resize,
            pty_kill,
            agent_start,
            agent_send,
            ai_chat
        ])
        .run(tauri::generate_context!())
        .expect("error while running V-Agent");
}
