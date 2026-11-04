use anyhow::{Context as _, Result, bail};
use async_trait::async_trait;
use collections::HashMap;
use futures::StreamExt as _;
use gpui::{App, AppContext as _, AsyncApp, Entity, Task};
use http_client::github::{AssetKind, GitHubLspBinaryVersion, latest_github_release};
use http_client::github_download::download_server_binary;
use language::{
    Buffer, CodeLabel, ContextLocation, ContextProvider, Language, LanguageToolchainStore,
    LspAdapter, LspAdapterDelegate, LspInstaller, Toolchain,
};
use lsp::{LanguageServerBinary, LanguageServerName};
use serde::Deserialize;
use std::{
    borrow::Cow,
    env::consts,
    ffi::OsString,
    path::{Path, PathBuf},
    sync::Arc,
};
use task::{TaskTemplate, TaskTemplates, TaskVariables, VariableName};
use util::{ResultExt, fs::remove_matching};

use crate::c::{self, CLspAdapter};

const ARDUINO_PORT_TASK_VARIABLE: VariableName =
    VariableName::Custom(Cow::Borrowed("ARDUINO_PORT"));
const ARDUINO_FQBN_TASK_VARIABLE: VariableName =
    VariableName::Custom(Cow::Borrowed("ARDUINO_FQBN"));
const ARDUINO_PLATFORM_TASK_VARIABLE: VariableName =
    VariableName::Custom(Cow::Borrowed("ARDUINO_PLATFORM"));
const ARDUINO_MONITOR_CONFIG_TASK_VARIABLE: VariableName =
    VariableName::Custom(Cow::Borrowed("ARDUINO_MONITOR_CONFIG"));

/// Compile, upload and serial-monitor tasks for Arduino sketches (`.ino`),
/// driven by `arduino-cli`, the same backend Arduino IDE 2 uses.
pub(crate) struct ArduinoContextProvider;

fn is_arduino_sketch(path: &Path) -> bool {
    path.extension()
        .is_some_and(|extension| extension.eq_ignore_ascii_case("ino"))
}

#[derive(Deserialize)]
struct BoardList {
    #[serde(default)]
    detected_ports: Vec<DetectedPort>,
}

#[derive(Deserialize)]
struct DetectedPort {
    #[serde(default)]
    matching_boards: Vec<MatchingBoard>,
    port: Option<Port>,
}

#[derive(Deserialize)]
struct MatchingBoard {
    name: Option<String>,
    fqbn: Option<String>,
}

#[derive(Deserialize)]
struct Port {
    address: String,
    #[serde(default)]
    properties: HashMap<String, String>,
}

/// A port `arduino-cli board list` reports, with the board on it when an
/// installed core recognises the USB IDs.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DetectedBoard {
    pub port: String,
    pub name: Option<String>,
    pub fqbn: Option<String>,
}

/// The ports in `arduino-cli board list --format json` that can be a board:
/// recognised boards, and USB serial devices (they have a `vid`, e.g. a CH340
/// clone) that no core recognises. Bare UARTs such as /dev/ttyS0 are always
/// listed on Linux and are never a board, so they are skipped.
pub fn detected_boards(board_list_json: &[u8]) -> Result<Vec<DetectedBoard>> {
    let board_list: BoardList =
        serde_json::from_slice(board_list_json).context("parsing arduino-cli board list")?;
    Ok(board_list
        .detected_ports
        .into_iter()
        .filter_map(|detected| {
            let port = detected.port?;
            let board = detected
                .matching_boards
                .into_iter()
                .find(|board| board.fqbn.is_some());
            if board.is_none() && !port.properties.contains_key("vid") {
                return None;
            }
            let (name, fqbn) = board.map_or((None, None), |board| (board.name, board.fqbn));
            Some(DetectedBoard {
                port: port.address,
                name,
                fqbn,
            })
        })
        .collect())
}

/// The port and FQBN to use when nothing was chosen: a recognised board wins,
/// otherwise the first USB serial port, which gives a port but no FQBN.
pub fn pick_board(board_list_json: &[u8]) -> Result<(Option<String>, Option<String>)> {
    let boards = detected_boards(board_list_json)?;
    let picked = boards
        .iter()
        .find(|board| board.fqbn.is_some())
        .or(boards.first());
    Ok(picked.map_or((None, None), |board| {
        (Some(board.port.clone()), board.fqbn.clone())
    }))
}

/// A board from `arduino-cli board search --format json`. Boards of platforms
/// that are not installed come without an FQBN; installing `platform` gives
/// them one.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct KnownBoard {
    pub name: String,
    pub fqbn: Option<String>,
    pub platform: String,
}

#[derive(Deserialize)]
struct BoardSearch {
    #[serde(default)]
    boards: Vec<SearchedBoard>,
}

#[derive(Deserialize)]
struct SearchedBoard {
    name: String,
    fqbn: Option<String>,
    platform: SearchedPlatform,
}

#[derive(Deserialize)]
struct SearchedPlatform {
    metadata: PlatformMetadata,
}

#[derive(Deserialize)]
struct PlatformMetadata {
    id: String,
}

pub fn known_boards(board_search_json: &[u8]) -> Result<Vec<KnownBoard>> {
    let search: BoardSearch =
        serde_json::from_slice(board_search_json).context("parsing arduino-cli board search")?;
    Ok(search
        .boards
        .into_iter()
        .map(|board| KnownBoard {
            name: board.name,
            fqbn: board.fqbn.filter(|fqbn| !fqbn.is_empty()),
            platform: board.platform.metadata.id,
        })
        .collect())
}

/// The `default_fqbn` and `default_port` that `arduino-cli board attach` writes
/// to a sketch's `sketch.yaml`.
///
/// sketch.yaml comes with the project, which may be someone else's, and both
/// values end up in commands run through a shell. Values with characters no
/// FQBN or port uses are ignored, as if nothing were attached.
// SIMPLIFICATION: matches the two top-level keys by prefix instead of parsing
// YAML. Enough for what `board attach` writes; a hand-written file that quotes
// keys or nests them under a profile is not read.
pub fn attached_board(sketch_yaml: &str) -> (Option<String>, Option<String>) {
    let value = |key: &str, allowed: fn(char) -> bool| {
        sketch_yaml.lines().find_map(|line| {
            let value = line.strip_prefix(key)?.trim().trim_matches(['"', '\'']);
            (!value.is_empty() && value.chars().all(allowed)).then(|| value.to_owned())
        })
    };
    // `vendor:arch:board:option=value,option=value`
    let fqbn_char = |c: char| c.is_ascii_alphanumeric() || "_.-:=,".contains(c);
    // `/dev/ttyACM0`, `COM3`, `\\.\COM10`, or a network board's `192.168.1.20`
    let port_char = |c: char| c.is_ascii_alphanumeric() || "_.-:/\\".contains(c);
    (
        value("default_fqbn:", fqbn_char),
        value("default_port:", port_char),
    )
}

/// The `vendor:architecture` platform an FQBN belongs to, which is the argument
/// `arduino-cli core install` takes: `arduino:avr:nano:cpu=atmega328old` gives
/// `arduino:avr`.
pub fn platform_of(fqbn: &str) -> Option<String> {
    let mut parts = fqbn.split(':').map(str::trim);
    let vendor = parts.next().filter(|part| !part.is_empty())?;
    let architecture = parts.next().filter(|part| !part.is_empty())?;
    parts.next().filter(|board| !board.is_empty())?;
    Some(format!("{vendor}:{architecture}"))
}

/// The baud rate the sketch opens `Serial` with. arduino-cli's monitor
/// defaults to 9600, so without this a sketch calling `Serial.begin(115200)`
/// prints garbage.
// SIMPLIFICATION: a text scan for the first `Serial.begin(<number>)` outside a
// `//` comment. A rate passed through a constant or macro, or a call inside a
// `/* */` block, is missed or misread and falls back to the 9600 default. A
// tree-sitter query over the parsed sketch would handle both.
pub fn serial_baud_rate(sketch: &str) -> Option<u32> {
    const CALL: &str = "Serial.begin(";
    sketch.lines().find_map(|line| {
        let code = line.split("//").next().unwrap_or_default();
        code.match_indices(CALL).find_map(|(start, _)| {
            // `mySerial.begin(9600)` is a SoftwareSerial port, not the USB one.
            let is_other_port = code[..start]
                .chars()
                .next_back()
                .is_some_and(|previous| previous.is_alphanumeric() || previous == '_');
            if is_other_port {
                return None;
            }
            let digits: String = code[start + CALL.len()..]
                .trim_start()
                .chars()
                .take_while(char::is_ascii_digit)
                .collect();
            digits.parse().ok()
        })
    })
}

impl ContextProvider for ArduinoContextProvider {
    fn build_context(
        &self,
        _: &TaskVariables,
        location: ContextLocation<'_>,
        project_env: Option<HashMap<String, String>>,
        _: Arc<dyn LanguageToolchainStore>,
        cx: &mut App,
    ) -> Task<Result<TaskVariables>> {
        let buffer = location.file_location.buffer.read(cx);
        let Some(sketch_dir) = buffer
            .file()
            .and_then(|file| Some(file.as_local()?.abs_path(cx)))
            .filter(|path| is_arduino_sketch(path))
            .and_then(|path| Some(path.parent()?.to_path_buf()))
        else {
            return Task::ready(Ok(TaskVariables::default()));
        };
        let baud_rate = serial_baud_rate(&buffer.text());

        cx.background_spawn(async move {
            let mut variables = TaskVariables::default();
            if let Some(baud_rate) = baud_rate {
                variables.insert(
                    ARDUINO_MONITOR_CONFIG_TASK_VARIABLE,
                    format!("baudrate={baud_rate}"),
                );
            }
            // Detection is best effort: without it the tasks still run, and
            // arduino-cli reports the missing board or port itself.
            let detected = async {
                let mut command = util::command::new_command("arduino-cli");
                if let Some(env) = &project_env {
                    command.envs(env);
                }
                let output = command
                    .args(["board", "list", "--format", "json"])
                    .output()
                    .await
                    .context("running arduino-cli board list")?;
                anyhow::ensure!(
                    output.status.success(),
                    "arduino-cli board list failed: {}",
                    String::from_utf8_lossy(&output.stderr)
                );
                pick_board(&output.stdout)
            }
            .await
            .log_err();
            let Some((port, fqbn)) = detected else {
                return Ok(variables);
            };

            // A board attached with `arduino-cli board attach` is a deliberate
            // choice, so it overrides detection. A missing sketch.yaml is the
            // normal case and means nothing is attached.
            let sketch_yaml = smol::fs::read_to_string(sketch_dir.join("sketch.yaml"))
                .await
                .unwrap_or_default();
            let (attached_fqbn, attached_port) = attached_board(&sketch_yaml);

            if let Some(port) = port.filter(|_| attached_port.is_none()) {
                variables.insert(ARDUINO_PORT_TASK_VARIABLE, port);
            }
            if attached_fqbn.is_none()
                && let Some(fqbn) = &fqbn
            {
                variables.insert(ARDUINO_FQBN_TASK_VARIABLE, fqbn.clone());
            }
            if let Some(platform) = attached_fqbn.or(fqbn).as_deref().and_then(platform_of) {
                variables.insert(ARDUINO_PLATFORM_TASK_VARIABLE, platform);
            }
            Ok(variables)
        })
    }

    fn associated_tasks(
        &self,
        buffer: Option<Entity<Buffer>>,
        cx: &App,
    ) -> Task<Option<TaskTemplates>> {
        let is_sketch = buffer
            .and_then(|buffer| Some(buffer.read(cx).file()?.as_local()?.abs_path(cx)))
            .is_some_and(|path| is_arduino_sketch(&path));
        if !is_sketch {
            return Task::ready(None);
        }
        Task::ready(Some(arduino_task_templates()))
    }
}

/// Runs arduino-language-server, which Arduino IDE 2 uses for completions and
/// diagnostics. It turns the sketch into the C++ that arduino-cli builds and
/// hands that to clangd, so `Serial`, `pinMode` and friends resolve and
/// `setup()`/`loop()` need no prototypes.
pub(crate) struct ArduinoLspAdapter;

impl ArduinoLspAdapter {
    const SERVER_NAME: LanguageServerName =
        LanguageServerName::new_static("arduino-language-server");
    /// The server needs a board to start. With none attached or plugged in it
    /// starts for the Uno, whose core (arduino:avr) most sketches target, so
    /// completions still work before a board is chosen.
    const FALLBACK_FQBN: &str = "arduino:avr:uno";
}

fn language_server_file_name() -> String {
    format!("arduino-language-server{}", consts::EXE_SUFFIX)
}

/// The newest downloaded copy in `container_dir`, if any.
async fn downloaded_language_server(container_dir: &Path) -> Option<PathBuf> {
    let mut newest = None;
    let mut entries = smol::fs::read_dir(container_dir).await.ok()?;
    while let Some(entry) = entries.next().await {
        let path = entry.ok()?.path();
        let binary = path.join(language_server_file_name());
        if binary.is_file() {
            newest = Some(binary);
        }
    }
    newest
}

async fn command_output(
    program: &Path,
    args: &[&str],
    env: &HashMap<String, String>,
) -> Result<String> {
    let output = util::command::new_command(program)
        .args(args)
        .envs(env)
        .output()
        .await
        .with_context(|| format!("running {}", program.display()))?;
    anyhow::ensure!(
        output.status.success(),
        "{} {} failed: {}",
        program.display(),
        args.join(" "),
        String::from_utf8_lossy(&output.stderr)
    );
    Ok(String::from_utf8_lossy(&output.stdout).trim().to_owned())
}

/// The server with the arguments for this worktree. They are worked out on
/// every start, so a board chosen since the last start is picked up when the
/// server restarts.
async fn arduino_language_server(
    path: PathBuf,
    delegate: &dyn LspAdapterDelegate,
) -> Result<LanguageServerBinary> {
    let env = delegate.shell_env().await;
    let arduino_cli = delegate
        .which("arduino-cli".as_ref())
        .await
        .context("arduino-cli is not installed")?;
    let clangd = match delegate.which("clangd".as_ref()).await {
        Some(clangd) => clangd,
        None => {
            let clangd_dir = delegate
                .language_server_download_dir(&CLspAdapter::SERVER_NAME)
                .await
                .context("no download folder for clangd")?;
            c::get_cached_server_binary(clangd_dir.to_path_buf())
                .await
                .context("clangd is not installed or downloaded yet")?
                .path
        }
    };

    // The server refuses to start without arduino-cli's config file, which
    // `config init` creates in the data folder (~/.arduino15 on Linux).
    let data_dir =
        command_output(&arduino_cli, &["config", "get", "directories.data"], &env).await?;
    let cli_config = Path::new(&data_dir).join("arduino-cli.yaml");
    if !cli_config.exists() {
        command_output(&arduino_cli, &["config", "init"], &env).await?;
    }

    let root = delegate.worktree_root_path();
    let sketch_yaml = smol::fs::read_to_string(root.join("sketch.yaml"))
        .await
        .unwrap_or_default();
    let fqbn = match attached_board(&sketch_yaml).0 {
        Some(fqbn) => fqbn,
        None => command_output(&arduino_cli, &["board", "list", "--format", "json"], &env)
            .await
            .and_then(|board_list| pick_board(board_list.as_bytes()))
            .log_err()
            .and_then(|(_, fqbn)| fqbn)
            .unwrap_or_else(|| ArduinoLspAdapter::FALLBACK_FQBN.to_owned()),
    };

    let flag = |name: &str, value: &Path| [OsString::from(name), value.as_os_str().to_owned()];
    let mut arguments = Vec::new();
    arguments.extend(flag("-clangd", &clangd));
    arguments.extend(flag("-cli", &arduino_cli));
    arguments.extend(flag("-cli-config", &cli_config));
    arguments.extend([OsString::from("-fqbn"), OsString::from(fqbn)]);
    Ok(LanguageServerBinary {
        path,
        arguments,
        env: Some(env),
    })
}

impl LspInstaller for ArduinoLspAdapter {
    type BinaryVersion = GitHubLspBinaryVersion;

    /// Zed caches what the other methods return for the whole session, but
    /// calls this one on every start. Finding the downloaded copy here too
    /// keeps the per-sketch board argument current.
    async fn check_if_user_installed(
        &self,
        delegate: &Arc<dyn LspAdapterDelegate>,
        _: Option<Toolchain>,
        _: &AsyncApp,
    ) -> Option<LanguageServerBinary> {
        let path = match delegate.which(Self::SERVER_NAME.as_ref()).await {
            Some(path) => path,
            None => {
                let container_dir = delegate
                    .language_server_download_dir(&Self::SERVER_NAME)
                    .await?;
                downloaded_language_server(&container_dir).await?
            }
        };
        arduino_language_server(path, delegate.as_ref())
            .await
            .log_err()
    }

    async fn fetch_latest_server_version(
        &self,
        delegate: &Arc<dyn LspAdapterDelegate>,
        pre_release: bool,
        _: &mut AsyncApp,
    ) -> Result<GitHubLspBinaryVersion> {
        let platform = match (consts::OS, consts::ARCH) {
            ("linux", "x86_64") => "Linux_64bit",
            ("linux", "aarch64") => "Linux_ARM64",
            ("macos", "x86_64") => "macOS_64bit",
            ("macos", "aarch64") => "macOS_ARM64",
            ("windows", "x86_64") => "Windows_64bit",
            (os, arch) => bail!("arduino-language-server has no release for {os} {arch}"),
        };
        let extension = if consts::OS == "windows" {
            "zip"
        } else {
            "tar.gz"
        };
        let release = latest_github_release(
            "arduino/arduino-language-server",
            true,
            pre_release,
            delegate.http_client(),
        )
        .await?;
        let asset_name = format!(
            "arduino-language-server_{}_{platform}.{extension}",
            release.tag_name
        );
        let asset = release
            .assets
            .iter()
            .find(|asset| asset.name == asset_name)
            .with_context(|| format!("no asset found matching {asset_name:?}"))?;
        Ok(GitHubLspBinaryVersion {
            name: release.tag_name,
            url: asset.browser_download_url.clone(),
            digest: asset.digest.clone(),
        })
    }

    fn fetch_server_binary(
        &self,
        version: GitHubLspBinaryVersion,
        container_dir: PathBuf,
        delegate: &Arc<dyn LspAdapterDelegate>,
    ) -> impl Send + Future<Output = Result<LanguageServerBinary>> + use<> {
        let delegate = delegate.clone();
        async move {
            let version_dir =
                container_dir.join(format!("arduino-language-server_{}", version.name));
            let binary_path = version_dir.join(language_server_file_name());
            if !binary_path.is_file() {
                let kind = if consts::OS == "windows" {
                    AssetKind::Zip
                } else {
                    AssetKind::TarGz
                };
                download_server_binary(
                    &*delegate.http_client(),
                    &version.url,
                    version.digest.as_deref(),
                    &version_dir,
                    kind,
                )
                .await?;
                remove_matching(&container_dir, |entry| entry != version_dir).await;
            }

            // The server runs clangd underneath; fetch the same build V-Agent
            // uses for C++ when nothing else provides one.
            if delegate.which("clangd".as_ref()).await.is_none() {
                let clangd_dir = delegate
                    .language_server_download_dir(&CLspAdapter::SERVER_NAME)
                    .await
                    .context("no download folder for clangd")?;
                if c::get_cached_server_binary(clangd_dir.to_path_buf())
                    .await
                    .is_none()
                {
                    let clangd_version = c::latest_clangd_version(&delegate, false).await?;
                    CLspAdapter
                        .fetch_server_binary(clangd_version, clangd_dir.to_path_buf(), &delegate)
                        .await?;
                }
            }

            arduino_language_server(binary_path, delegate.as_ref()).await
        }
    }

    async fn cached_server_binary(
        &self,
        container_dir: PathBuf,
        delegate: &dyn LspAdapterDelegate,
    ) -> Option<LanguageServerBinary> {
        let path = downloaded_language_server(&container_dir).await?;
        arduino_language_server(path, delegate).await.log_err()
    }
}

#[async_trait(?Send)]
impl LspAdapter for ArduinoLspAdapter {
    fn name(&self) -> LanguageServerName {
        Self::SERVER_NAME
    }

    async fn label_for_completion(
        &self,
        completion: &lsp::CompletionItem,
        language: &Arc<Language>,
    ) -> Option<CodeLabel> {
        // The completions are clangd's, passed through.
        CLspAdapter.label_for_completion(completion, language).await
    }
}

fn arduino_task_templates() -> TaskTemplates {
    // Empty `--port=` / `--fqbn=` mean "not given" to arduino-cli, which then
    // falls back to sketch.yaml's default_port / default_fqbn.
    let port = format!("--port=${{{}:}}", ARDUINO_PORT_TASK_VARIABLE);
    let fqbn = format!("--fqbn=${{{}:}}", ARDUINO_FQBN_TASK_VARIABLE);
    // Empty means arduino-cli's own default, 9600 baud.
    let monitor_config = format!("--config=${{{}:}}", ARDUINO_MONITOR_CONFIG_TASK_VARIABLE);
    let platform = format!("${{{}:}}", ARDUINO_PLATFORM_TASK_VARIABLE);
    let sketch_dir = VariableName::Dirname.template_value_with_whitespace();
    let template = |label: &str, args: Vec<String>| TaskTemplate {
        label: label.to_owned(),
        command: "arduino-cli".to_owned(),
        args,
        cwd: Some(VariableName::Dirname.template_value()),
        ..TaskTemplate::default()
    };
    TaskTemplates(vec![
        template(
            "Arduino: Upload",
            vec![
                "compile".to_owned(),
                "--upload".to_owned(),
                port.clone(),
                fqbn.clone(),
                sketch_dir.clone(),
            ],
        ),
        template(
            "Arduino: Compile",
            vec!["compile".to_owned(), fqbn.clone(), sketch_dir],
        ),
        template(
            "Arduino: Serial Monitor",
            vec!["monitor".to_owned(), port, fqbn, monitor_config],
        ),
        // Uploading to a board whose core is missing fails with "platform not
        // installed". Installing an already installed core is a no-op, so this
        // is safe to run at any time.
        template(
            "Arduino: Install Board Core",
            vec!["core".to_owned(), "install".to_owned(), platform],
        ),
    ])
}

#[cfg(test)]
mod tests {
    use super::*;
    use gpui::Hsla;
    use rope::Rope;
    use task::TaskContext;
    use theme::SyntaxTheme;

    #[test]
    fn test_arduino_highlights() {
        // Loading the language compiles highlights.scm against the C++ grammar,
        // so a broken Arduino rule fails here.
        let language = crate::language("arduino", tree_sitter_cpp::LANGUAGE.into());
        language.set_theme(&SyntaxTheme::new_test([
            ("variable", Hsla::default()),
            ("function", Hsla::default()),
            ("function.builtin", Hsla::default()),
            ("keyword", Hsla::default()),
            ("type", Hsla::default()),
            ("type.builtin", Hsla::default()),
            ("constant", Hsla::default()),
        ]));
        let grammar = language.grammar().unwrap();
        let source = "void setup() {\n  Serial.begin(9600);\n  mySerial.begin(4800);\n  \
                      pinMode(LED_BUILTIN, OUTPUT);\n  helper();\n}\n";
        let runs = language.highlight_text(&Rope::from(source), 0..source.len());
        let highlight_of = |word: &str| {
            let start = source.find(word).unwrap();
            runs.iter()
                .find(|(range, _)| range.contains(&start))
                .map(|(_, id)| *id)
        };
        let id = |name: &str| grammar.highlight_id_for_name(name);

        assert_eq!(highlight_of("setup"), id("keyword"));
        assert_eq!(highlight_of("Serial"), id("type.builtin"));
        assert_eq!(highlight_of("mySerial"), id("variable"));
        assert_eq!(highlight_of("pinMode"), id("function.builtin"));
        assert_eq!(highlight_of("LED_BUILTIN"), id("constant.builtin"));
        assert_eq!(highlight_of("helper"), id("function"));
    }

    #[test]
    fn test_pick_board() {
        let recognised = br#"{"detected_ports":[
            {"port":{"address":"/dev/ttyS0","protocol":"serial","properties":{}}},
            {"port":{"address":"/dev/ttyUSB0","properties":{"vid":"0x1A86","pid":"0x7523"}}},
            {"matching_boards":[{"name":"Arduino Uno","fqbn":"arduino:avr:uno"}],
             "port":{"address":"/dev/ttyACM0","properties":{"vid":"0x2341","pid":"0x0043"}}}
        ]}"#;
        assert_eq!(
            pick_board(recognised).unwrap(),
            (
                Some("/dev/ttyACM0".to_owned()),
                Some("arduino:avr:uno".to_owned())
            )
        );

        let clone_only = br#"{"detected_ports":[
            {"port":{"address":"/dev/ttyS0","properties":{}}},
            {"port":{"address":"/dev/ttyUSB0","properties":{"vid":"0x1A86"}}}
        ]}"#;
        assert_eq!(
            pick_board(clone_only).unwrap(),
            (Some("/dev/ttyUSB0".to_owned()), None)
        );

        let uart_only =
            br#"{"detected_ports":[{"port":{"address":"/dev/ttyS0","properties":{}}}]}"#;
        assert_eq!(pick_board(uart_only).unwrap(), (None, None));
        assert_eq!(pick_board(b"{}").unwrap(), (None, None));
        assert!(pick_board(b"not json").is_err());
    }

    #[test]
    fn test_detected_boards() {
        let board_list = br#"{"detected_ports":[
            {"port":{"address":"/dev/ttyS0","protocol":"serial","properties":{}}},
            {"port":{"address":"/dev/ttyUSB0","properties":{"vid":"0x1A86","pid":"0x7523"}}},
            {"matching_boards":[{"name":"Arduino Uno","fqbn":"arduino:avr:uno"}],
             "port":{"address":"/dev/ttyACM0","properties":{"vid":"0x2341","pid":"0x0043"}}}
        ]}"#;
        assert_eq!(
            detected_boards(board_list).unwrap(),
            [
                DetectedBoard {
                    port: "/dev/ttyUSB0".to_owned(),
                    name: None,
                    fqbn: None,
                },
                DetectedBoard {
                    port: "/dev/ttyACM0".to_owned(),
                    name: Some("Arduino Uno".to_owned()),
                    fqbn: Some("arduino:avr:uno".to_owned()),
                },
            ]
        );
    }

    #[test]
    fn test_known_boards() {
        // Shaped like arduino-cli 1.5.1 output: a board of an uninstalled
        // platform has no "fqbn" key at all.
        let board_search = br#"{"boards":[
            {"name":"Arduino Uno","fqbn":"arduino:avr:uno",
             "platform":{"metadata":{"id":"arduino:avr"},"release":{"installed":true}}},
            {"name":"Arduino Zero (Programming Port)",
             "platform":{"metadata":{"id":"arduino:samd"},"release":{"name":"Arduino SAMD Boards"}}}
        ]}"#;
        assert_eq!(
            known_boards(board_search).unwrap(),
            [
                KnownBoard {
                    name: "Arduino Uno".to_owned(),
                    fqbn: Some("arduino:avr:uno".to_owned()),
                    platform: "arduino:avr".to_owned(),
                },
                KnownBoard {
                    name: "Arduino Zero (Programming Port)".to_owned(),
                    fqbn: None,
                    platform: "arduino:samd".to_owned(),
                },
            ]
        );
        assert!(known_boards(b"{}").unwrap().is_empty());
    }

    #[test]
    fn test_attached_board() {
        // What `arduino-cli board attach -p /dev/ttyUSB0 -b arduino:avr:nano` wrote.
        assert_eq!(
            attached_board("default_fqbn: arduino:avr:nano\ndefault_port: /dev/ttyUSB0\n"),
            (
                Some("arduino:avr:nano".to_owned()),
                Some("/dev/ttyUSB0".to_owned())
            )
        );
        assert_eq!(
            attached_board("default_fqbn: \"esp32:esp32:esp32\"\n"),
            (Some("esp32:esp32:esp32".to_owned()), None)
        );
        assert_eq!(attached_board("default_port: \n"), (None, None));
        assert_eq!(
            attached_board("default_fqbn: arduino:avr:uno; rm -rf ~\ndefault_port: $(reboot)\n"),
            (None, None)
        );
        assert_eq!(
            attached_board("default_port: COM3\n"),
            (None, Some("COM3".to_owned()))
        );
        assert_eq!(attached_board(""), (None, None));
    }

    #[test]
    fn test_platform_of() {
        assert_eq!(
            platform_of("arduino:avr:uno").as_deref(),
            Some("arduino:avr")
        );
        assert_eq!(
            platform_of("arduino:avr:nano:cpu=atmega328old").as_deref(),
            Some("arduino:avr")
        );
        assert_eq!(
            platform_of("esp32:esp32:esp32").as_deref(),
            Some("esp32:esp32")
        );
        assert_eq!(platform_of("arduino:avr"), None);
        assert_eq!(platform_of("arduino::uno"), None);
        assert_eq!(platform_of(""), None);
    }

    #[test]
    fn test_serial_baud_rate() {
        assert_eq!(
            serial_baud_rate("void setup() { Serial.begin(115200); }"),
            Some(115200)
        );
        assert_eq!(
            serial_baud_rate("  Serial.begin( 57600 , SERIAL_8N1);"),
            Some(57600)
        );
        assert_eq!(serial_baud_rate("Serial.begin(9600UL);"), Some(9600));
        assert_eq!(
            serial_baud_rate("// Serial.begin(300);\nSerial.begin(19200);"),
            Some(19200)
        );
        assert_eq!(
            serial_baud_rate("mySerial.begin(4800);\nSerial.begin(38400);"),
            Some(38400)
        );
        assert_eq!(serial_baud_rate("Serial1.begin(4800);"), None);
        assert_eq!(serial_baud_rate("Serial.begin(BAUD);"), None);
        assert_eq!(serial_baud_rate("void setup() {}"), None);
    }

    #[test]
    fn test_arduino_tasks_resolve_with_and_without_a_detected_board() {
        let templates = arduino_task_templates().0;
        let template = |label: &str| {
            templates
                .iter()
                .find(|template| template.label == label)
                .unwrap()
        };
        let upload = template("Arduino: Upload");
        let context = |variables: Vec<(VariableName, &str)>| TaskContext {
            task_variables: TaskVariables::from_iter(
                variables
                    .into_iter()
                    .map(|(name, value)| (name, value.to_owned()))
                    .chain([(VariableName::Dirname, "/sketches/Blink".to_owned())]),
            ),
            ..TaskContext::default()
        };

        let detected = upload
            .resolve_task(
                "test",
                &context(vec![
                    (ARDUINO_PORT_TASK_VARIABLE, "/dev/ttyACM0"),
                    (ARDUINO_FQBN_TASK_VARIABLE, "arduino:avr:uno"),
                ]),
            )
            .unwrap();
        assert_eq!(
            detected.resolved.args,
            [
                "compile",
                "--upload",
                "--port=/dev/ttyACM0",
                "--fqbn=arduino:avr:uno",
                "\"/sketches/Blink\""
            ]
        );

        // Nothing detected must still give a runnable task, so arduino-cli can
        // fall back to sketch.yaml or explain what is missing.
        let undetected = upload.resolve_task("test", &context(vec![])).unwrap();
        assert_eq!(
            undetected.resolved.args,
            [
                "compile",
                "--upload",
                "--port=",
                "--fqbn=",
                "\"/sketches/Blink\""
            ]
        );

        let monitor = template("Arduino: Serial Monitor");
        let configured = monitor
            .resolve_task(
                "test",
                &context(vec![
                    (ARDUINO_PORT_TASK_VARIABLE, "/dev/ttyACM0"),
                    (ARDUINO_MONITOR_CONFIG_TASK_VARIABLE, "baudrate=115200"),
                ]),
            )
            .unwrap();
        assert_eq!(
            configured.resolved.args,
            [
                "monitor",
                "--port=/dev/ttyACM0",
                "--fqbn=",
                "--config=baudrate=115200"
            ]
        );
        // arduino-cli 1.5.1 accepts an empty `--config=` and keeps 9600 baud.
        let unconfigured = monitor.resolve_task("test", &context(vec![])).unwrap();
        assert_eq!(
            unconfigured.resolved.args,
            ["monitor", "--port=", "--fqbn=", "--config="]
        );

        let install_core = template("Arduino: Install Board Core")
            .resolve_task(
                "test",
                &context(vec![(ARDUINO_PLATFORM_TASK_VARIABLE, "arduino:avr")]),
            )
            .unwrap();
        assert_eq!(
            install_core.resolved.args,
            ["core", "install", "arduino:avr"]
        );
    }
}
