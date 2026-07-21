#![allow(
    clippy::disallowed_methods,
    reason = "build helper used only from build scripts"
)]
#![cfg(target_os = "windows")]

use std::process::Command;

fn git_sha() -> Option<String> {
    if let Ok(sha) = std::env::var("ZED_COMMIT_SHA") {
        return Some(sha);
    }

    Command::new("git")
        .args(["rev-parse", "HEAD"])
        .output()
        .ok()
        .filter(|output| output.status.success())
        .map(|output| String::from_utf8_lossy(&output.stdout).trim().to_string())
}

fn product_version() -> String {
    let commit_sha = git_sha();
    let pkg_version = std::env::var("CARGO_PKG_VERSION").unwrap_or_default();
    // Same source as the app's own version and the product name: the
    // RELEASE_CHANNEL file, not an unset env var that defaulted to "dev" and
    // stamped a stable build's file properties "1.0.0+dev.<sha>".
    let channel = std::fs::read_to_string(RELEASE_CHANNEL_FILE)
        .map(|s| s.trim().to_string())
        .ok()
        .filter(|s| !s.is_empty())
        .or_else(|| std::env::var("RELEASE_CHANNEL").ok())
        .unwrap_or_else(|| "dev".into());
    let build_id = std::env::var("GITHUB_RUN_NUMBER").ok();

    let mut metadata = channel;
    if let Some(build_id) = &build_id {
        metadata.push('.');
        metadata.push_str(build_id);
    }
    if let Some(sha) = &commit_sha {
        metadata.push('.');
        metadata.push_str(sha);
    }

    format!("{pkg_version}+{metadata}")
}

/// Find `rc.exe` from the newest installed Windows SDK (x64), if any.
fn find_rc_exe() -> Option<std::path::PathBuf> {
    for root in [
        r"C:\Program Files (x86)\Windows Kits\10\bin",
        r"C:\Program Files\Windows Kits\10\bin",
    ] {
        let Ok(entries) = std::fs::read_dir(root) else {
            continue;
        };
        let mut versions: Vec<_> = entries
            .flatten()
            .map(|e| e.path())
            .filter(|p| p.is_dir())
            .collect();
        versions.sort();
        for dir in versions.into_iter().rev() {
            let candidate = dir.join("x64").join("rc.exe");
            if candidate.exists() {
                return Some(candidate);
            }
        }
    }
    None
}

const ICON_DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../zed/resources/windows");
const MANIFEST_PATH: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/resources/manifest.xml");

const RELEASE_CHANNEL_FILE: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../zed/RELEASE_CHANNEL");

pub fn compile(manifest: bool) -> Result<(), Box<dyn std::error::Error>> {
    // The release channel lives in crates/zed/RELEASE_CHANNEL, which is what
    // the running app reads (via release_channel's include_str!). Upstream read
    // the RELEASE_CHANNEL *env var* here instead, which our builds don't set, so
    // a stable build was stamped "V-Agent Dev" in its Windows file properties
    // while the app itself reported stable. Read the same file both use, and
    // fall back to the env var only if the file is somehow absent.
    println!("cargo:rerun-if-changed={RELEASE_CHANNEL_FILE}");
    let channel = std::fs::read_to_string(RELEASE_CHANNEL_FILE)
        .map(|s| s.trim().to_string())
        .ok()
        .or_else(|| option_env!("RELEASE_CHANNEL").map(str::to_string))
        .unwrap_or_else(|| "dev".to_string());
    let (icon_filename, product_name) = match channel.as_str() {
        "stable" => ("app-icon.ico", "V-Agent"),
        "preview" => ("app-icon-preview.ico", "V-Agent Preview"),
        "nightly" => ("app-icon-nightly.ico", "V-Agent Nightly"),
        _ => ("app-icon-dev.ico", "V-Agent Dev"),
    };
    let icon = std::path::PathBuf::from(ICON_DIR).join(icon_filename);
    // Track the icon (and manifest) as build inputs so regenerating the .ico
    // triggers a rebuild + re-embed instead of silently keeping the old icon.
    println!("cargo:rerun-if-changed={}", icon.display());
    println!("cargo:rerun-if-changed={MANIFEST_PATH}");

    let out_dir = std::path::PathBuf::from(std::env::var("OUT_DIR")?);
    // rc.exe mishandles non-ASCII characters in resource paths (e.g. a project
    // under "…\Programação\…"). OUT_DIR lives under the ASCII build target, so
    // copy resources next to the generated .rc and reference them by bare
    // filename — rc.exe resolves those relative to the .rc file.
    std::fs::copy(&icon, out_dir.join(icon_filename)).ok();
    let icon_escaped = icon_filename;

    let manifest_line = if manifest {
        std::fs::copy(MANIFEST_PATH, out_dir.join("manifest.xml")).ok();
        "1 24 \"manifest.xml\"".to_string()
    } else {
        String::new()
    };

    let pkg_version = std::env::var("CARGO_PKG_VERSION").unwrap_or_default();
    let product_version = product_version();
    let mut version_parts = pkg_version
        .split('.')
        .map(|part| part.parse::<u16>().unwrap_or(0))
        .chain(std::iter::repeat(0));
    let file_version = format!(
        "{},{},{},{}",
        version_parts.next().unwrap_or(0),
        version_parts.next().unwrap_or(0),
        version_parts.next().unwrap_or(0),
        version_parts.next().unwrap_or(0),
    );

    let rc_content = format!(
        r#"1 ICON "{icon_escaped}"
{manifest_line}

1 VERSIONINFO
FILEVERSION {file_version}
PRODUCTVERSION {file_version}
FILEFLAGSMASK 0x3fL
FILEFLAGS 0x0L
FILEOS 0x40004L
FILETYPE 0x1L
FILESUBTYPE 0x0L
BEGIN
    BLOCK "StringFileInfo"
    BEGIN
        BLOCK "040904b0"
        BEGIN
            VALUE "FileDescription", "{product_name}\0"
            VALUE "FileVersion", "{pkg_version}\0"
            VALUE "ProductName", "{product_name}\0"
            VALUE "ProductVersion", "{product_version}\0"
            VALUE "CompanyName", "V-Agent\0"
            VALUE "LegalCopyright", "Based on Zed. Copyright 2022 - 2025 Zed Industries, Inc. (GPL-3.0)\0"
        END
    END
    BLOCK "VarFileInfo"
    BEGIN
        VALUE "Translation", 0x0409, 1200
    END
END
"#
    );

    let rc_path = out_dir.join("zed_resources.rc");
    std::fs::write(&rc_path, rc_content)?;

    // Point embed_resource at the SDK resource compiler. Prefer an explicit
    // ZED_RC_TOOLKIT_PATH; otherwise auto-detect the newest Windows 10/11 SDK so
    // the icon embeds on any dev box without extra setup.
    let rc_exe = std::env::var("ZED_RC_TOOLKIT_PATH")
        .ok()
        .map(|p| std::path::Path::new(&p).join("rc.exe"))
        .filter(|p| p.exists())
        .or_else(find_rc_exe);
    if let Some(rc_exe) = rc_exe {
        unsafe {
            std::env::set_var("RC", rc_exe);
        }
    }

    // Non-fatal: embedding the icon/version resource needs the SDK resource
    // compiler set up just right. If it can't run, skip it (cosmetic only) so
    // the build still produces a working binary.
    if let Err(e) = embed_resource::compile(&rc_path, embed_resource::NONE).manifest_optional() {
        println!("cargo:warning=windows resource embed skipped: {e:?}");
    }

    Ok(())
}
