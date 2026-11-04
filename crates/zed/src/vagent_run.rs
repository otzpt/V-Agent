//! V-Agent: one-click Build & Run for the active file, and the editor toolbar
//! item that holds its Run button. For Arduino files the same toolbar item
//! shows the board selector, Verify and Upload instead (see `vagent_arduino`).

use std::{
    borrow::Cow,
    path::{Path, PathBuf},
};

use editor::Editor;
use gpui::{App, Context, Entity, EventEmitter, Subscription, Window, actions};
use project::TaskSourceKind;
use task::{SaveStrategy, TaskContext, TaskTemplate};
use ui::{IconButton, IconName, IconSize, Tooltip, prelude::*};
use util::shell::{Shell, ShellKind};
use workspace::{
    Toast, ToolbarItemEvent, ToolbarItemLocation, ToolbarItemView, Workspace, item::ItemHandle,
    notifications::NotificationId,
};

use crate::{vagent_arduino, vagent_toolchain};

actions!(
    vagent,
    [
        /// Builds and runs the active file in a terminal, choosing the compiler
        /// or interpreter from the file's extension.
        BuildAndRun,
    ]
);

pub fn init(cx: &mut App) {
    cx.observe_new(|workspace: &mut Workspace, _, _| {
        workspace.register_action(|workspace, _: &BuildAndRun, window, cx| {
            build_and_run(workspace, window, cx);
        });
    })
    .detach();
    vagent_arduino::init(cx);
}

pub(crate) fn file_of_editor(editor: &Entity<Editor>, cx: &App) -> Option<PathBuf> {
    let buffer = editor.read(cx).buffer().read(cx).as_singleton()?;
    let file = buffer.read(cx).file()?;
    Some(file.as_local()?.abs_path(cx))
}

pub(crate) fn active_file(workspace: &Workspace, cx: &App) -> Option<PathBuf> {
    let editor = workspace.active_item(cx)?.act_as::<Editor>(cx)?;
    file_of_editor(&editor, cx)
}

/// Extensions Build & Run handles. Each one has a branch in [`run_plan`].
const RUNNABLE_EXTENSIONS: &[&str] = &[
    "c", "cpp", "cc", "cxx", "c++", "py", "pyw", "js", "mjs", "cjs", "ts", "go", "rs", "java",
    "rb", "php", "lua", "sh",
];

fn extension(file: &Path) -> Option<String> {
    Some(file.extension()?.to_str()?.to_ascii_lowercase())
}

fn is_runnable(file: &Path) -> bool {
    extension(file).is_some_and(|extension| RUNNABLE_EXTENSIONS.contains(&extension.as_str()))
}

/// Tasks run through `sh -c` (or `cmd /C` on Windows) rather than the user's
/// shell, because a compile-then-run line needs `&&`, which fish before 3.0,
/// nushell and Windows PowerShell 5 do not accept.
fn run_shell() -> (Shell, ShellKind) {
    if cfg!(windows) {
        (Shell::Program("cmd".to_owned()), ShellKind::Cmd)
    } else {
        (Shell::Program("sh".to_owned()), ShellKind::Posix)
    }
}

enum RunPlan {
    /// A complete shell command line, run from the file's folder.
    Command(String),
    /// None of the compilers or interpreters for this file are on PATH.
    MissingToolchain,
}

fn run_plan(file: &Path) -> Option<RunPlan> {
    let extension = extension(file)?;
    if !RUNNABLE_EXTENSIONS.contains(&extension.as_str()) {
        return None;
    }
    let (_, shell_kind) = run_shell();
    let quote = |path: &Path| -> String {
        let path = path.to_string_lossy();
        shell_kind
            .try_quote(&path)
            .map_or_else(|| path.to_string(), Cow::into_owned)
    };
    let source = quote(file);
    let first_on_path = |candidates: &[&'static str]| {
        candidates
            .iter()
            .copied()
            .find(|binary| vagent_toolchain::any_on_path(&[binary]))
    };
    let interpret = |candidates: &[&'static str]| match first_on_path(candidates) {
        Some(interpreter) => RunPlan::Command(format!("{interpreter} {source}")),
        None => RunPlan::MissingToolchain,
    };
    // Compiled programs go to the temp folder so the project folder stays clean.
    let binary = std::env::temp_dir().join("vagent-run").join(format!(
        "{}{}",
        file.file_stem()?.to_string_lossy(),
        std::env::consts::EXE_SUFFIX
    ));
    let binary = quote(&binary);
    let compile = |candidates: &[&'static str], link_flags: &str| match first_on_path(candidates) {
        Some(compiler) => RunPlan::Command(format!(
            "{compiler} {source} -o {binary}{link_flags} && {binary}"
        )),
        None => RunPlan::MissingToolchain,
    };

    Some(match extension.as_str() {
        // libm is separate from libc on Linux, so <math.h> users would fail to
        // link without it. MinGW ships a libm too, so the flag is harmless there.
        "c" => compile(&["gcc", "clang", "cc"], " -lm"),
        "cpp" | "cc" | "cxx" | "c++" => compile(&["g++", "clang++", "c++"], ""),
        // On Windows `python3` is often the Microsoft Store stub, so try it last.
        "py" | "pyw" if cfg!(windows) => interpret(&["python", "py", "python3"]),
        "py" | "pyw" => interpret(&["python3", "python"]),
        "js" | "mjs" | "cjs" => interpret(&["node"]),
        // Node runs TypeScript directly from 23.6; Bun always has.
        "ts" => interpret(&["bun", "node"]),
        "go" => match first_on_path(&["go"]) {
            Some(_) => RunPlan::Command(format!("go run {source}")),
            None => RunPlan::MissingToolchain,
        },
        "rs" => match file
            .ancestors()
            .find(|dir| dir.join("Cargo.toml").is_file())
        {
            Some(_) if first_on_path(&["cargo"]).is_some() => {
                RunPlan::Command("cargo run".to_owned())
            }
            Some(_) => RunPlan::MissingToolchain,
            None => compile(&["rustc"], ""),
        },
        // Java 11+ runs a single source file without a separate javac step.
        "java" => interpret(&["java"]),
        "rb" => interpret(&["ruby"]),
        "php" => interpret(&["php"]),
        "lua" => interpret(&["lua"]),
        "sh" => interpret(&["bash", "sh"]),
        _ => return None,
    })
}

fn build_and_run(workspace: &mut Workspace, window: &mut Window, cx: &mut Context<Workspace>) {
    struct BuildAndRunToast;
    let show_toast = |workspace: &mut Workspace, message: String, cx: &mut Context<Workspace>| {
        workspace.show_toast(
            Toast::new(NotificationId::unique::<BuildAndRunToast>(), message),
            cx,
        );
    };

    let Some(file) = active_file(workspace, cx) else {
        show_toast(
            workspace,
            "Open a saved code file to build and run it.".to_owned(),
            cx,
        );
        return;
    };
    if vagent_arduino::sketch_for(&file, cx).is_some() {
        vagent_arduino::upload(workspace, window, cx);
        return;
    }
    let Some(plan) = run_plan(&file) else {
        show_toast(
            workspace,
            format!(
                "Build & Run doesn't know how to run {} files.",
                file.extension()
                    .map_or_else(|| "these".into(), |extension| extension.to_string_lossy())
            ),
            cx,
        );
        return;
    };
    let command = match plan {
        RunPlan::Command(command) => command,
        RunPlan::MissingToolchain => {
            if let Some(extension) = extension(&file) {
                vagent_toolchain::offer_install(workspace, &extension, cx);
            }
            return;
        }
    };
    let output_dir = std::env::temp_dir().join("vagent-run");
    if let Err(error) = std::fs::create_dir_all(&output_dir) {
        show_toast(
            workspace,
            format!("Couldn't create {}: {error}", output_dir.display()),
            cx,
        );
        return;
    }
    let Some(cwd) = file.parent() else {
        return;
    };
    let file_name = file
        .file_name()
        .map_or_else(|| file.to_string_lossy(), |name| name.to_string_lossy());
    let (shell, _) = run_shell();
    let template = TaskTemplate {
        label: format!("Run {file_name}"),
        command,
        cwd: Some(cwd.to_string_lossy().into_owned()),
        shell,
        save: SaveStrategy::Current,
        ..TaskTemplate::default()
    };
    workspace.schedule_task(
        TaskSourceKind::UserInput,
        &template,
        &TaskContext::default(),
        false,
        window,
        cx,
    );
}

/// The editor toolbar's run controls: a Run button for code files, or the
/// Arduino board selector, Verify, Upload and Serial Monitor for sketches.
pub struct RunBar {
    file: Option<PathBuf>,
    _editor_subscription: Option<Subscription>,
    _arduino_subscription: Option<Subscription>,
}

impl RunBar {
    pub fn new(cx: &mut Context<Self>) -> Self {
        // The Tools menu toggle and board detection change what is shown.
        let arduino_subscription = vagent_arduino::observe(cx, |this, cx| {
            cx.emit(ToolbarItemEvent::ChangeLocation(this.location(cx)));
            cx.notify();
        });
        Self {
            file: None,
            _editor_subscription: None,
            _arduino_subscription: arduino_subscription,
        }
    }

    fn location(&self, cx: &App) -> ToolbarItemLocation {
        match &self.file {
            Some(file) if is_runnable(file) || vagent_arduino::sketch_for(file, cx).is_some() => {
                ToolbarItemLocation::PrimaryRight
            }
            _ => ToolbarItemLocation::Hidden,
        }
    }

    fn set_file(&mut self, file: Option<PathBuf>, cx: &mut Context<Self>) {
        if file == self.file {
            return;
        }
        if let Some(sketch) = file
            .as_deref()
            .and_then(|file| vagent_arduino::sketch_for(file, cx))
        {
            vagent_arduino::refresh(&sketch, cx);
        }
        self.file = file;
        cx.emit(ToolbarItemEvent::ChangeLocation(self.location(cx)));
        cx.notify();
    }
}

impl EventEmitter<ToolbarItemEvent> for RunBar {}

impl ToolbarItemView for RunBar {
    fn set_active_pane_item(
        &mut self,
        active_pane_item: Option<&dyn ItemHandle>,
        _window: &mut Window,
        cx: &mut Context<Self>,
    ) -> ToolbarItemLocation {
        self._editor_subscription = None;
        let editor = active_pane_item.and_then(|item| item.act_as::<Editor>(cx));
        let file = editor
            .as_ref()
            .and_then(|editor| file_of_editor(editor, cx));
        if let Some(editor) = editor {
            // "Save As" gives an untitled buffer a path without switching items.
            self._editor_subscription = Some(cx.observe(&editor, |this, editor, cx| {
                let file = file_of_editor(&editor, cx);
                this.set_file(file, cx);
            }));
        }
        self.set_file(file, cx);
        self.location(cx)
    }
}

impl Render for RunBar {
    fn render(&mut self, window: &mut Window, cx: &mut Context<Self>) -> impl IntoElement {
        let Some(file) = self.file.clone() else {
            return div().into_any_element();
        };
        if let Some(sketch) = vagent_arduino::sketch_for(&file, cx) {
            return vagent_arduino::render_controls(&sketch, window, cx).into_any_element();
        }
        if !is_runnable(&file) {
            return div().into_any_element();
        }
        IconButton::new("vagent-build-and-run", IconName::PlayFilled)
            .icon_size(IconSize::Small)
            .icon_color(Color::Success)
            .tooltip(Tooltip::for_action_title("Build & Run", &BuildAndRun))
            .on_click(|_, window, cx| window.dispatch_action(Box::new(BuildAndRun), cx))
            .into_any_element()
    }
}
