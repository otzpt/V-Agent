//! V-Agent: Arduino controls modelled on Arduino IDE 2's toolbar (Verify,
//! Upload, a board selector and Serial Monitor) and their Tools menu entries.
//! Everything runs arduino-cli, the backend IDE 2 is built on. The controls
//! show for `.ino` sketches, and for plain C/C++ files when "Arduino Upload for
//! C/C++ Files" is checked in the Tools menu.

use std::{
    hash::{DefaultHasher, Hash, Hasher},
    path::{Path, PathBuf},
    rc::Rc,
};

use anyhow::{Context as _, Result};
use collections::HashMap;
use db::kvp::KeyValueStore;
use editor::{Editor, actions::RestartLanguageServer};
use fuzzy::{StringMatch, StringMatchCandidate, match_strings};
use gpui::{
    AnyElement, AnyWindowHandle, App, AppContext as _, Context, DismissEvent, Entity, EventEmitter,
    FocusHandle, Focusable, Global, Subscription, Task, TaskExt as _, WeakEntity, Window, actions,
};
use languages::arduino::{self, DetectedBoard, KnownBoard};
use picker::{Picker, PickerDelegate};
use project::TaskSourceKind;
use task::{SaveStrategy, TaskContext, TaskTemplate};
use ui::{
    Button, ContextMenu, HighlightedLabel, IconButton, IconName, IconPosition, IconSize, ListItem,
    ListItemSpacing, PopoverMenu, Tooltip, prelude::*,
};
use util::ResultExt as _;
use workspace::{
    ModalView, SaveIntent, Toast, Workspace, notifications::DetachAndPromptErr as _,
    notifications::NotificationId, tasks::ScheduledTaskResult,
};

use crate::vagent_run;

actions!(
    vagent,
    [
        /// Compiles the active Arduino sketch without uploading it.
        ArduinoVerify,
        /// Compiles the active Arduino sketch and uploads it to the board.
        ArduinoUpload,
        /// Opens arduino-cli's serial monitor on the board's port.
        ArduinoSerialMonitor,
        /// Chooses the board the active Arduino sketch is built for.
        ArduinoSelectBoard,
        /// Shows the Arduino controls for C and C++ files as well as sketches.
        ToggleArduinoForCFiles,
    ]
);

const C_FILES_KEY: &str = "vagent_arduino_c_files";
const C_EXTENSIONS: &[&str] = &["c", "cpp", "cc", "cxx"];

#[derive(Default)]
struct ArduinoState {
    c_files_enabled: bool,
    detected: Vec<DetectedBoard>,
    detecting: Option<Task<()>>,
    /// Board names by FQBN, so an attached board is shown by name.
    board_names: HashMap<String, String>,
    /// `default_fqbn` and `default_port` from each sketch's sketch.yaml.
    attached: HashMap<PathBuf, (Option<String>, Option<String>)>,
    /// The port a "pick the board on this port" menu entry hands to the
    /// board picker, which is opened through an action.
    picker_port: Option<String>,
}

struct GlobalArduinoState(Entity<ArduinoState>);

impl Global for GlobalArduinoState {}

fn state(cx: &App) -> Option<Entity<ArduinoState>> {
    cx.try_global::<GlobalArduinoState>()
        .map(|global| global.0.clone())
}

pub fn init(cx: &mut App) {
    let c_files_enabled = KeyValueStore::global(cx)
        .read_kvp(C_FILES_KEY)
        .log_err()
        .flatten()
        .is_some_and(|value| value == "true");
    let state = cx.new(|_| ArduinoState {
        c_files_enabled,
        ..ArduinoState::default()
    });
    cx.set_global(GlobalArduinoState(state));

    cx.observe_new(|workspace: &mut Workspace, _, _| {
        workspace
            .register_action(|workspace, _: &ArduinoVerify, window, cx| {
                run(workspace, Command::Verify, window, cx)
            })
            .register_action(|workspace, _: &ArduinoUpload, window, cx| {
                run(workspace, Command::Upload, window, cx)
            })
            .register_action(|workspace, _: &ArduinoSerialMonitor, window, cx| {
                run(workspace, Command::SerialMonitor, window, cx)
            })
            .register_action(|workspace, _: &ArduinoSelectBoard, window, cx| {
                select_board(workspace, window, cx)
            })
            .register_action(|_, _: &ToggleArduinoForCFiles, _, cx| toggle_c_files(cx));
    })
    .detach();
}

pub fn c_files_enabled(cx: &App) -> bool {
    state(cx).is_some_and(|state| state.read(cx).c_files_enabled)
}

fn toggle_c_files(cx: &mut App) {
    let Some(state) = state(cx) else {
        return;
    };
    let enabled = state.update(cx, |state, cx| {
        state.c_files_enabled = !state.c_files_enabled;
        cx.notify();
        state.c_files_enabled
    });
    let kvp = KeyValueStore::global(cx);
    cx.background_spawn(async move {
        kvp.write_kvp(C_FILES_KEY.to_owned(), enabled.to_string())
            .await
            .log_err();
    })
    .detach();
    // Rebuild the menus so the Tools menu checkmark follows the setting.
    let menus = crate::zed::app_menus(cx);
    cx.set_menus(menus);
}

/// Calls `on_change` whenever board detection, a board choice or the C/C++
/// toggle changes what the Arduino controls show.
pub(crate) fn observe<T: 'static>(
    cx: &mut Context<T>,
    on_change: impl Fn(&mut T, &mut Context<T>) + 'static,
) -> Option<Subscription> {
    let state = state(cx)?;
    Some(cx.observe(&state, move |this, _, cx| on_change(this, cx)))
}

/// The folder arduino-cli builds for a file.
#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct Sketch {
    dir: PathBuf,
    /// For a plain C/C++ file, the folder whose sources are copied into `dir`
    /// before each build. arduino-cli only builds a folder holding an `.ino`
    /// named after it, so these get a generated sketch outside the project
    /// instead of an extra file in the user's folder.
    copied_from: Option<PathBuf>,
}

pub(crate) fn sketch_for(file: &Path, cx: &App) -> Option<Sketch> {
    let extension = file.extension()?.to_str()?.to_ascii_lowercase();
    let folder = file.parent()?;
    if extension == "ino" {
        return Some(Sketch {
            dir: folder.to_path_buf(),
            copied_from: None,
        });
    }
    if !C_EXTENSIONS.contains(&extension.as_str()) || !c_files_enabled(cx) {
        return None;
    }
    // Only needs to be stable between runs of the same build, so the chosen
    // board (kept in the generated sketch's sketch.yaml) is found again.
    let mut hasher = DefaultHasher::new();
    folder.hash(&mut hasher);
    Some(Sketch {
        dir: paths::data_dir()
            .join("arduino-sketches")
            .join(format!("{:016x}", hasher.finish()))
            .join("sketch"),
        copied_from: Some(folder.to_path_buf()),
    })
}

fn is_copied_source(path: &Path) -> bool {
    path.extension()
        .and_then(|extension| extension.to_str())
        .is_some_and(|extension| {
            matches!(
                extension.to_ascii_lowercase().as_str(),
                "c" | "cpp" | "cc" | "cxx" | "h" | "hpp" | "hh" | "s"
            )
        })
}

/// Makes `sketch_dir` a sketch holding a copy of `source`'s C/C++ files.
// SIMPLIFICATION: copies only the source folder's top-level files. A project
// that keeps code in subfolders has to be a real sketch (`Name/Name.ino` with
// the code under `Name/src/`, which arduino-cli compiles recursively).
fn sync_sources(source: &Path, sketch_dir: &Path) -> Result<()> {
    std::fs::create_dir_all(sketch_dir)
        .with_context(|| format!("creating {}", sketch_dir.display()))?;
    let main_file = sketch_dir.join("sketch.ino");
    if !main_file.exists() {
        std::fs::write(
            &main_file,
            "// Generated by V-Agent. The code is in the .c/.cpp files copied next to it.\n",
        )
        .with_context(|| format!("writing {}", main_file.display()))?;
    }
    for entry in std::fs::read_dir(sketch_dir)? {
        let path = entry?.path();
        if is_copied_source(&path) {
            std::fs::remove_file(&path).with_context(|| format!("removing {}", path.display()))?;
        }
    }
    for entry in std::fs::read_dir(source)? {
        let path = entry?.path();
        if let Some(name) = path.file_name()
            && path.is_file()
            && is_copied_source(&path)
        {
            std::fs::copy(&path, sketch_dir.join(name))
                .with_context(|| format!("copying {}", path.display()))?;
        }
    }
    Ok(())
}

async fn run_arduino_cli(args: Vec<String>) -> Result<Vec<u8>> {
    let output = util::command::new_command("arduino-cli")
        .args(&args)
        .output()
        .await
        .context("running arduino-cli")?;
    anyhow::ensure!(
        output.status.success(),
        "arduino-cli {} failed: {}",
        args.join(" "),
        String::from_utf8_lossy(&output.stderr)
    );
    Ok(output.stdout)
}

fn owned_args(args: &[&str]) -> Vec<String> {
    args.iter().map(|arg| (*arg).to_owned()).collect()
}

impl ArduinoState {
    fn load_attached(&mut self, sketch_dir: PathBuf, cx: &mut Context<Self>) {
        cx.spawn(async move |this, cx| {
            // A sketch without sketch.yaml has no board attached.
            let sketch_yaml = smol::fs::read_to_string(sketch_dir.join("sketch.yaml"))
                .await
                .unwrap_or_default();
            let attached = arduino::attached_board(&sketch_yaml);
            this.update(cx, |state, cx| {
                state.attached.insert(sketch_dir, attached);
                cx.notify();
            })
        })
        .detach_and_log_err(cx);
    }

    fn detect(&mut self, cx: &mut Context<Self>) {
        if self.detecting.is_some() {
            return;
        }
        self.detecting = Some(cx.spawn(async move |this, cx| {
            let boards = run_arduino_cli(owned_args(&["board", "list", "--format", "json"]))
                .await
                .and_then(|stdout| arduino::detected_boards(&stdout));
            this.update(cx, |state, cx| {
                state.detecting = None;
                match boards {
                    Ok(boards) => {
                        for board in &boards {
                            if let (Some(name), Some(fqbn)) = (&board.name, &board.fqbn) {
                                state.board_names.insert(fqbn.clone(), name.clone());
                            }
                        }
                        state.detected = boards;
                    }
                    // A missing arduino-cli is reported by the install prompt
                    // when the sketch is opened, and by the task when it runs.
                    Err(error) => {
                        log::warn!("Arduino board detection failed: {error:#}");
                        state.detected.clear();
                    }
                }
                cx.notify();
            })
            .log_err();
        }));
        cx.notify();
    }

    /// The board and port a build uses: the ones attached to the sketch, else
    /// what is plugged in, preferring a board a core recognises.
    fn board_for(&self, sketch: &Sketch) -> (Option<String>, Option<String>) {
        let (attached_fqbn, attached_port) =
            self.attached.get(&sketch.dir).cloned().unwrap_or_default();
        let detected = self
            .detected
            .iter()
            .find(|board| {
                board.fqbn.is_some() && (attached_fqbn.is_none() || board.fqbn == attached_fqbn)
            })
            .or(self.detected.first());
        let fqbn = attached_fqbn.or_else(|| detected.and_then(|board| board.fqbn.clone()));
        let port = attached_port.or_else(|| detected.map(|board| board.port.clone()));
        (fqbn, port)
    }
}

/// Re-reads the sketch's attached board and rescans the USB ports.
pub(crate) fn refresh(sketch: &Sketch, cx: &mut App) {
    let Some(state) = state(cx) else {
        return;
    };
    let sketch_dir = sketch.dir.clone();
    state.update(cx, |state, cx| {
        state.load_attached(sketch_dir, cx);
        state.detect(cx);
    });
}

/// Attaches a board to the sketch with `arduino-cli board attach`. `window` is
/// where to restart the Arduino language server afterwards, so it picks up
/// the new board.
fn attach(
    sketch: &Sketch,
    fqbn: Option<String>,
    port: Option<String>,
    window: Option<AnyWindowHandle>,
    cx: &mut App,
) {
    let Some(state) = state(cx) else {
        return;
    };
    let sketch = sketch.clone();
    state.update(cx, |_, cx| {
        cx.spawn(async move |this, cx| {
            if let Some(source) = sketch.copied_from.clone() {
                // `board attach` needs the generated sketch to exist.
                let sketch_dir = sketch.dir.clone();
                cx.background_spawn(async move { sync_sources(&source, &sketch_dir) })
                    .await?;
            }
            let mut args = owned_args(&["board", "attach"]);
            if let Some(port) = &port {
                args.push(format!("--port={port}"));
            }
            if let Some(fqbn) = &fqbn {
                args.push(format!("--fqbn={fqbn}"));
            }
            args.push(sketch.dir.to_string_lossy().into_owned());
            run_arduino_cli(args).await?;
            this.update(cx, |state, cx| {
                let attached = state.attached.entry(sketch.dir.clone()).or_default();
                if fqbn.is_some() {
                    attached.0 = fqbn;
                }
                if port.is_some() {
                    attached.1 = port;
                }
                cx.notify();
            })?;
            // The language server reads the board when it starts. Copied C/C++
            // files are not Arduino files and use clangd, which has no board.
            if let Some(window) = window
                && sketch.copied_from.is_none()
            {
                window
                    .update(cx, |_, window, cx| {
                        window.dispatch_action(Box::new(RestartLanguageServer), cx)
                    })
                    .log_err();
            }
            anyhow::Ok(())
        })
        .detach_and_log_err(cx);
    });
}

pub(crate) fn render_controls<T: 'static>(
    sketch: &Sketch,
    _window: &mut Window,
    cx: &mut Context<T>,
) -> AnyElement {
    let Some(state) = state(cx) else {
        return div().into_any_element();
    };
    let state = state.read(cx);
    let (fqbn, port) = state.board_for(sketch);
    let board_label: SharedString = match &fqbn {
        Some(fqbn) => state
            .board_names
            .get(fqbn)
            .cloned()
            .unwrap_or_else(|| fqbn.clone())
            .into(),
        None if state.detecting.is_some() => "Detecting boards…".into(),
        None => "Select Board".into(),
    };
    let board_tooltip = match &port {
        Some(port) => format!("Board and port ({port})"),
        None => "Board and port (no port found)".to_owned(),
    };

    let menu_sketch = sketch.clone();
    let open_sketch = sketch.clone();
    let board_selector = PopoverMenu::new("vagent-arduino-board")
        .menu(move |window, cx| Some(board_menu(&menu_sketch, window, cx)))
        // Rescan when the list is opened, as a board may have been plugged in.
        .on_open(Rc::new(move |_, cx| refresh(&open_sketch, cx)))
        .trigger_with_tooltip(
            Button::new("vagent-arduino-board-button", board_label)
                .label_size(LabelSize::Small)
                .end_icon(Icon::new(IconName::ChevronDown).size(IconSize::XSmall)),
            Tooltip::text(board_tooltip),
        );

    h_flex()
        .gap_0p5()
        .child(
            IconButton::new("vagent-arduino-verify", IconName::Check)
                .icon_size(IconSize::Small)
                .tooltip(Tooltip::for_action_title("Verify", &ArduinoVerify))
                .on_click(|_, window, cx| window.dispatch_action(Box::new(ArduinoVerify), cx)),
        )
        .child(
            IconButton::new("vagent-arduino-upload", IconName::ArrowRight)
                .icon_size(IconSize::Small)
                .icon_color(Color::Success)
                .tooltip(Tooltip::for_action_title("Upload", &ArduinoUpload))
                .on_click(|_, window, cx| window.dispatch_action(Box::new(ArduinoUpload), cx)),
        )
        .child(board_selector)
        .child(
            IconButton::new("vagent-arduino-monitor", IconName::Terminal)
                .icon_size(IconSize::Small)
                .tooltip(Tooltip::for_action_title(
                    "Serial Monitor",
                    &ArduinoSerialMonitor,
                ))
                .on_click(|_, window, cx| {
                    window.dispatch_action(Box::new(ArduinoSerialMonitor), cx)
                }),
        )
        .into_any_element()
}

fn board_menu(sketch: &Sketch, window: &mut Window, cx: &mut App) -> Entity<ContextMenu> {
    let state = state(cx);
    let builder_state = state.clone();
    let sketch = sketch.clone();
    // Persistent so it can be rebuilt: opening it starts a rescan, and the
    // boards it finds arrive while the menu is open.
    let menu = ContextMenu::build_persistent(window, cx, move |mut menu, _, cx| {
        menu = menu.keep_open_on_confirm(false);
        let Some(state_handle) = builder_state.clone() else {
            return menu;
        };
        let state = state_handle.read(cx);
        let (fqbn, port) = state.board_for(&sketch);

        menu = menu.header("Connected Boards");
        if state.detected.is_empty() {
            menu = menu.label(if state.detecting.is_some() {
                "Detecting boards…"
            } else {
                "No boards found"
            });
        }
        for board in &state.detected {
            let label = format!(
                "{} ({})",
                board.name.as_deref().unwrap_or("Unknown board"),
                board.port
            );
            let selected = port.as_deref() == Some(board.port.as_str())
                && (board.fqbn.is_none() || board.fqbn == fqbn);
            let board = board.clone();
            let sketch = sketch.clone();
            let state_handle = state_handle.clone();
            menu = menu.toggleable_entry(
                label,
                selected,
                IconPosition::Start,
                None,
                move |window, cx| match &board.fqbn {
                    Some(fqbn) => attach(
                        &sketch,
                        Some(fqbn.clone()),
                        Some(board.port.clone()),
                        Some(window.window_handle()),
                        cx,
                    ),
                    // Clones with a CH340-style USB chip are not recognised,
                    // so the user names the board for this port.
                    None => {
                        let port = board.port.clone();
                        state_handle.update(cx, |state, _| state.picker_port = Some(port));
                        window.dispatch_action(Box::new(ArduinoSelectBoard), cx);
                    }
                },
            );
        }
        let refresh_sketch = sketch.clone();
        let picker_state = state_handle.clone();
        menu.separator()
            .entry("Select Other Board…", None, move |window, cx| {
                let port = port.clone();
                picker_state.update(cx, |state, _| state.picker_port = port);
                window.dispatch_action(Box::new(ArduinoSelectBoard), cx);
            })
            .entry("Refresh", None, move |_, cx| refresh(&refresh_sketch, cx))
    });
    if let Some(state) = state {
        menu.update(cx, |_, cx| {
            cx.observe_in(&state, window, |menu, _, window, cx| {
                menu.rebuild(window, cx)
            })
            .detach();
        });
    }
    menu
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Command {
    Verify,
    Upload,
    SerialMonitor,
}

pub(crate) fn upload(workspace: &mut Workspace, window: &mut Window, cx: &mut Context<Workspace>) {
    run(workspace, Command::Upload, window, cx);
}

struct ArduinoToast;

fn show_toast(
    workspace: &mut Workspace,
    message: impl Into<std::borrow::Cow<'static, str>>,
    cx: &mut Context<Workspace>,
) {
    workspace.show_toast(
        Toast::new(NotificationId::unique::<ArduinoToast>(), message),
        cx,
    );
}

fn active_sketch(workspace: &mut Workspace, cx: &mut Context<Workspace>) -> Option<Sketch> {
    let Some(file) = vagent_run::active_file(workspace, cx) else {
        show_toast(workspace, "Open an Arduino sketch (.ino) first.", cx);
        return None;
    };
    let sketch = sketch_for(&file, cx);
    if sketch.is_none() {
        show_toast(
            workspace,
            "This file isn't an Arduino sketch. Open an .ino file, or check \
             Tools > Arduino Upload for C/C++ Files.",
            cx,
        );
    }
    sketch
}

fn run(
    workspace: &mut Workspace,
    command: Command,
    window: &mut Window,
    cx: &mut Context<Workspace>,
) {
    let Some(sketch) = active_sketch(workspace, cx) else {
        return;
    };
    let Some(state) = state(cx) else {
        return;
    };
    let (fqbn, port) = state.read(cx).board_for(&sketch);
    if fqbn.is_none() && command != Command::SerialMonitor {
        // Like Arduino IDE 2, ask which board it is instead of failing.
        open_board_picker(workspace, sketch, port, window, cx);
        return;
    }

    let (verb, mut args) = match command {
        Command::Verify => ("Verify", owned_args(&["compile"])),
        Command::Upload => ("Upload", owned_args(&["compile", "--upload"])),
        Command::SerialMonitor => ("Serial Monitor", owned_args(&["monitor"])),
    };
    if let Some(fqbn) = &fqbn {
        args.push(format!("--fqbn={fqbn}"));
    }
    if command != Command::Verify {
        let Some(port) = &port else {
            show_toast(
                workspace,
                "No board port found. Plug the board in, then pick it in the board selector.",
                cx,
            );
            return;
        };
        args.push(format!("--port={port}"));
    }
    if command == Command::SerialMonitor {
        // arduino-cli's monitor defaults to 9600 baud; match the sketch instead.
        let baud_rate = workspace
            .active_item(cx)
            .and_then(|item| item.act_as::<Editor>(cx))
            .and_then(|editor| editor.read(cx).buffer().read(cx).as_singleton())
            .and_then(|buffer| arduino::serial_baud_rate(&buffer.read(cx).text()));
        if let Some(baud_rate) = baud_rate {
            args.push(format!("--config=baudrate={baud_rate}"));
        }
    } else {
        args.push(sketch.dir.to_string_lossy().into_owned());
    }

    let sketch_name = sketch
        .copied_from
        .as_deref()
        .unwrap_or(&sketch.dir)
        .file_name()
        .map(|name| name.to_string_lossy().into_owned())
        .unwrap_or_default();
    let template = TaskTemplate {
        label: format!("Arduino: {verb} {sketch_name}"),
        command: "arduino-cli".to_owned(),
        args,
        cwd: Some(sketch.dir.to_string_lossy().into_owned()),
        save: SaveStrategy::All,
        ..TaskTemplate::default()
    };

    // Copied C/C++ sources are read from disk, so the buffer has to be saved
    // before they are copied rather than when the task starts.
    let save = match &sketch.copied_from {
        Some(_) => Some(workspace.save_active_item(SaveIntent::Save, window, cx)),
        None => None,
    };
    cx.spawn_in(window, async move |workspace, cx| {
        if let Some(save) = save {
            save.await?;
        }
        if let Some(source) = sketch.copied_from.clone()
            && command != Command::SerialMonitor
        {
            let sketch_dir = sketch.dir.clone();
            cx.background_spawn(async move { sync_sources(&source, &sketch_dir) })
                .await?;
        }
        workspace.update_in(cx, |workspace, window, cx| {
            workspace.schedule_task(
                TaskSourceKind::UserInput,
                &template,
                &TaskContext::default(),
                false,
                window,
                cx,
            );
        })
    })
    .detach_and_prompt_err("Couldn't start the Arduino task", window, cx, |_, _, _| {
        None
    });
}

fn select_board(workspace: &mut Workspace, window: &mut Window, cx: &mut Context<Workspace>) {
    let Some(sketch) = active_sketch(workspace, cx) else {
        return;
    };
    let Some(state) = state(cx) else {
        return;
    };
    let port = state
        .update(cx, |state, _| state.picker_port.take())
        .or_else(|| state.read(cx).board_for(&sketch).1);
    open_board_picker(workspace, sketch, port, window, cx);
}

fn open_board_picker(
    workspace: &mut Workspace,
    sketch: Sketch,
    port: Option<String>,
    window: &mut Window,
    cx: &mut Context<Workspace>,
) {
    let workspace_handle = cx.weak_entity();
    workspace.toggle_modal(window, cx, move |window, cx| {
        BoardPicker::new(workspace_handle, sketch, port, window, cx)
    });
}

/// Installs a board's core in a terminal, then attaches the board once the
/// install has given it an FQBN, like Arduino IDE 2's boards auto-installer.
fn install_and_attach(
    workspace: WeakEntity<Workspace>,
    sketch: Sketch,
    board: KnownBoard,
    port: Option<String>,
    window: &mut Window,
    cx: &mut App,
) {
    let template = TaskTemplate {
        label: format!("Arduino: Install {}", board.platform),
        command: "arduino-cli".to_owned(),
        args: owned_args(&["core", "install", &board.platform]),
        ..TaskTemplate::default()
    };
    let Some(resolved) = template.resolve_task("vagent-arduino", &TaskContext::default()) else {
        return;
    };
    let window_handle = window.window_handle();
    workspace
        .update(cx, |workspace, cx| {
            workspace.schedule_resolved_task_with_completion(
                TaskSourceKind::UserInput,
                resolved,
                true,
                move |result, cx| {
                    if result != ScheduledTaskResult::Success {
                        return;
                    }
                    cx.update(|_, cx| attach_by_name(sketch, board.name, port, window_handle, cx))
                        .log_err();
                },
                window,
                cx,
            );
        })
        .log_err();
}

fn attach_by_name(
    sketch: Sketch,
    name: String,
    port: Option<String>,
    window: AnyWindowHandle,
    cx: &mut App,
) {
    cx.spawn(async move |cx| {
        let search = run_arduino_cli(owned_args(&["board", "search", "--format", "json"])).await?;
        let fqbn = arduino::known_boards(&search)?
            .into_iter()
            .find(|board| board.name == name)
            .and_then(|board| board.fqbn)
            .with_context(|| format!("{name} still has no FQBN after installing its core"))?;
        cx.update(|cx| attach(&sketch, Some(fqbn), port, Some(window), cx));
        anyhow::Ok(())
    })
    .detach_and_log_err(cx);
}

struct BoardPicker {
    picker: Entity<Picker<BoardPickerDelegate>>,
    _load_boards: Task<Result<()>>,
}

impl BoardPicker {
    fn new(
        workspace: WeakEntity<Workspace>,
        sketch: Sketch,
        port: Option<String>,
        window: &mut Window,
        cx: &mut Context<Self>,
    ) -> Self {
        let delegate = BoardPickerDelegate {
            board_picker: cx.entity().downgrade(),
            workspace,
            sketch,
            port,
            boards: Vec::new(),
            candidates: Vec::new(),
            matches: Vec::new(),
            selected_index: 0,
            status: Some("Loading boards…".into()),
        };
        let picker = cx.new(|cx| Picker::uniform_list(delegate, window, cx));
        let load_boards = cx.spawn_in(window, {
            let picker = picker.downgrade();
            async move |_, cx| {
                let boards = run_arduino_cli(owned_args(&["board", "search", "--format", "json"]))
                    .await
                    .and_then(|stdout| arduino::known_boards(&stdout));
                picker.update_in(cx, |picker, window, cx| {
                    match boards {
                        Ok(boards) => picker.delegate.set_boards(boards),
                        Err(error) => {
                            picker.delegate.status =
                                Some(format!("Couldn't list boards: {error:#}").into())
                        }
                    }
                    picker.refresh(window, cx);
                })
            }
        });
        Self {
            picker,
            _load_boards: load_boards,
        }
    }
}

impl Render for BoardPicker {
    fn render(&mut self, _window: &mut Window, _cx: &mut Context<Self>) -> impl IntoElement {
        v_flex()
            .key_context("ArduinoBoardPicker")
            .w(rems(34.))
            .child(self.picker.clone())
    }
}

impl Focusable for BoardPicker {
    fn focus_handle(&self, cx: &App) -> FocusHandle {
        self.picker.focus_handle(cx)
    }
}

impl EventEmitter<DismissEvent> for BoardPicker {}
impl ModalView for BoardPicker {}

struct BoardPickerDelegate {
    board_picker: WeakEntity<BoardPicker>,
    workspace: WeakEntity<Workspace>,
    sketch: Sketch,
    port: Option<String>,
    boards: Vec<KnownBoard>,
    candidates: Vec<StringMatchCandidate>,
    matches: Vec<StringMatch>,
    selected_index: usize,
    /// Shown instead of "no matches" while loading or after an error.
    status: Option<SharedString>,
}

impl BoardPickerDelegate {
    fn set_boards(&mut self, mut boards: Vec<KnownBoard>) {
        // Boards that can be used right away first, then those that need
        // their core installed.
        boards.sort_by_key(|board| board.fqbn.is_none());
        self.candidates = boards
            .iter()
            .enumerate()
            .map(|(id, board)| StringMatchCandidate::new(id, &board.name))
            .collect();
        self.boards = boards;
        self.status = None;
    }
}

impl PickerDelegate for BoardPickerDelegate {
    type ListItem = ListItem;

    fn name() -> &'static str {
        "Arduino board picker"
    }

    fn placeholder_text(&self, _window: &mut Window, _cx: &mut App) -> std::sync::Arc<str> {
        match &self.port {
            Some(port) => format!("Select the board on {port}…").into(),
            None => "Select a board…".into(),
        }
    }

    fn no_matches_text(&self, _window: &mut Window, _cx: &mut App) -> Option<SharedString> {
        Some(
            self.status
                .clone()
                .unwrap_or_else(|| "No board matches".into()),
        )
    }

    fn match_count(&self) -> usize {
        self.matches.len()
    }

    fn selected_index(&self) -> usize {
        self.selected_index
    }

    fn set_selected_index(
        &mut self,
        index: usize,
        _window: &mut Window,
        _cx: &mut Context<Picker<Self>>,
    ) {
        self.selected_index = index;
    }

    fn update_matches(
        &mut self,
        query: String,
        window: &mut Window,
        cx: &mut Context<Picker<Self>>,
    ) -> Task<()> {
        let background = cx.background_executor().clone();
        let candidates = self.candidates.clone();
        cx.spawn_in(window, async move |this, cx| {
            let matches = if query.is_empty() {
                candidates
                    .into_iter()
                    .enumerate()
                    .map(|(index, candidate)| StringMatch {
                        candidate_id: index,
                        string: candidate.string,
                        positions: Vec::new(),
                        score: 0.0,
                    })
                    .collect()
            } else {
                match_strings(
                    &candidates,
                    &query,
                    false,
                    true,
                    100,
                    &Default::default(),
                    background,
                )
                .await
            };
            this.update(cx, |this, cx| {
                this.delegate.matches = matches;
                this.delegate.selected_index = 0;
                cx.notify();
            })
            .log_err();
        })
    }

    fn confirm(&mut self, _secondary: bool, window: &mut Window, cx: &mut Context<Picker<Self>>) {
        let board = self
            .matches
            .get(self.selected_index)
            .and_then(|mat| self.boards.get(mat.candidate_id))
            .cloned();
        if let Some(board) = board {
            match board.fqbn.clone() {
                Some(fqbn) => attach(
                    &self.sketch,
                    Some(fqbn),
                    self.port.clone(),
                    Some(window.window_handle()),
                    cx,
                ),
                None => install_and_attach(
                    self.workspace.clone(),
                    self.sketch.clone(),
                    board,
                    self.port.clone(),
                    window,
                    cx,
                ),
            }
        }
        self.dismissed(window, cx);
    }

    fn dismissed(&mut self, _window: &mut Window, cx: &mut Context<Picker<Self>>) {
        self.board_picker
            .update(cx, |_, cx| cx.emit(DismissEvent))
            .log_err();
    }

    fn render_match(
        &self,
        index: usize,
        selected: bool,
        _window: &mut Window,
        _cx: &mut Context<Picker<Self>>,
    ) -> Option<Self::ListItem> {
        let mat = self.matches.get(index)?;
        let board = self.boards.get(mat.candidate_id)?;
        let detail = match &board.fqbn {
            Some(fqbn) => fqbn.clone(),
            None => format!("installs {}", board.platform),
        };
        Some(
            ListItem::new(index)
                .inset(true)
                .spacing(ListItemSpacing::Sparse)
                .toggle_state(selected)
                .child(
                    h_flex()
                        .w_full()
                        .justify_between()
                        .gap_2()
                        .child(HighlightedLabel::new(
                            board.name.clone(),
                            mat.positions.clone(),
                        ))
                        .child(
                            Label::new(detail)
                                .size(LabelSize::Small)
                                .color(Color::Muted),
                        ),
                ),
        )
    }
}
