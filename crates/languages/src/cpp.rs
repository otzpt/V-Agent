use anyhow::{Context as _, Result};
use collections::HashMap;
use gpui::{App, AppContext as _, Entity, Task};
use language::{Buffer, ContextLocation, ContextProvider, LanguageToolchainStore};
use serde::Deserialize;
use settings::SemanticTokenRules;
use std::{borrow::Cow, path::Path, sync::Arc};
use task::{TaskTemplate, TaskTemplates, TaskVariables, VariableName};
use util::ResultExt;

const ARDUINO_PORT_TASK_VARIABLE: VariableName =
    VariableName::Custom(Cow::Borrowed("ARDUINO_PORT"));
const ARDUINO_FQBN_TASK_VARIABLE: VariableName =
    VariableName::Custom(Cow::Borrowed("ARDUINO_FQBN"));

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
    fqbn: Option<String>,
}

#[derive(Deserialize)]
struct Port {
    address: String,
    #[serde(default)]
    properties: HashMap<String, String>,
}

/// Picks the port and FQBN to use from `arduino-cli board list --format json`.
/// A recognised board wins. Otherwise a USB serial device (has a `vid`, e.g. a
/// CH340 clone) gives a port but no FQBN. Bare UARTs such as /dev/ttyS0 are
/// always listed on Linux and are never a board, so they are skipped.
fn pick_board(board_list_json: &[u8]) -> Result<(Option<String>, Option<String>)> {
    let board_list: BoardList =
        serde_json::from_slice(board_list_json).context("parsing arduino-cli board list")?;
    let recognised = board_list.detected_ports.iter().find_map(|detected| {
        let port = detected.port.as_ref()?;
        let fqbn = detected
            .matching_boards
            .iter()
            .find_map(|board| board.fqbn.clone())?;
        Some((Some(port.address.clone()), Some(fqbn)))
    });
    if let Some(recognised) = recognised {
        return Ok(recognised);
    }
    let usb_port = board_list.detected_ports.iter().find_map(|detected| {
        let port = detected.port.as_ref()?;
        port.properties
            .contains_key("vid")
            .then(|| port.address.clone())
    });
    Ok((usb_port, None))
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
        let Some(sketch_dir) = location
            .file_location
            .buffer
            .read(cx)
            .file()
            .and_then(|file| Some(file.as_local()?.abs_path(cx)))
            .filter(|path| is_arduino_sketch(path))
            .and_then(|path| Some(path.parent()?.to_path_buf()))
        else {
            return Task::ready(Ok(TaskVariables::default()));
        };

        cx.background_spawn(async move {
            let mut variables = TaskVariables::default();
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
            // choice, so it overrides detection.
            // SIMPLIFICATION: matches top-level keys by prefix instead of parsing
            // YAML. Enough for the two keys `board attach` writes.
            let sketch_yaml = smol::fs::read_to_string(sketch_dir.join("sketch.yaml"))
                .await
                .unwrap_or_default();
            let attached = |key: &str| sketch_yaml.lines().any(|line| line.starts_with(key));

            if let Some(port) = port.filter(|_| !attached("default_port:")) {
                variables.insert(ARDUINO_PORT_TASK_VARIABLE, port);
            }
            if let Some(fqbn) = fqbn.filter(|_| !attached("default_fqbn:")) {
                variables.insert(ARDUINO_FQBN_TASK_VARIABLE, fqbn);
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

fn arduino_task_templates() -> TaskTemplates {
    // Empty `--port=` / `--fqbn=` mean "not given" to arduino-cli, which then
    // falls back to sketch.yaml's default_port / default_fqbn.
    let port = format!("--port=${{{}:}}", ARDUINO_PORT_TASK_VARIABLE);
    let fqbn = format!("--fqbn=${{{}:}}", ARDUINO_FQBN_TASK_VARIABLE);
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
            vec!["monitor".to_owned(), port, fqbn],
        ),
    ])
}

pub(crate) fn semantic_token_rules() -> SemanticTokenRules {
    let content = grammars::get_file("cpp/semantic_token_rules.json")
        .expect("missing cpp/semantic_token_rules.json");
    let json = std::str::from_utf8(&content.data).expect("invalid utf-8 in semantic_token_rules");
    settings::parse_json_with_comments::<SemanticTokenRules>(json)
        .expect("failed to parse cpp semantic_token_rules.json")
}

#[cfg(test)]
mod tests {
    use super::*;
    use gpui::{BorrowAppContext, TestAppContext};
    use task::TaskContext;

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
    fn test_arduino_tasks_resolve_with_and_without_a_detected_board() {
        let upload = arduino_task_templates()
            .0
            .into_iter()
            .find(|template| template.label == "Arduino: Upload")
            .unwrap();
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
    }
    use language::{AutoindentMode, Buffer};
    use settings::SettingsStore;
    use std::num::NonZeroU32;
    use unindent::Unindent;

    #[gpui::test]
    async fn test_cpp_autoindent_switch_case(cx: &mut TestAppContext) {
        cx.update(|cx| {
            let test_settings = SettingsStore::test(cx);
            cx.set_global(test_settings);
            cx.update_global::<SettingsStore, _>(|store, cx| {
                store.update_user_settings(cx, |s| {
                    s.project.all_languages.defaults.tab_size = NonZeroU32::new(2);
                });
            });
        });
        let language = crate::language("cpp", tree_sitter_cpp::LANGUAGE.into());

        cx.new(|cx| {
            let mut buffer = Buffer::local("", cx).with_language(language, cx);

            buffer.edit(
                [(
                    0..0,
                    r#"
                    int main() {
                    switch (a) {
                    case 1:
                    b++;
                    break;
                    case 2:
                    case 3:
                    c++;
                    break;
                    default:
                    d++;
                    }
                    }
                    "#
                    .unindent(),
                )],
                Some(AutoindentMode::EachLine),
                cx,
            );
            assert_eq!(
                buffer.text(),
                r#"
                int main() {
                  switch (a) {
                    case 1:
                      b++;
                      break;
                    case 2:
                    case 3:
                      c++;
                      break;
                    default:
                      d++;
                  }
                }
                "#
                .unindent(),
                "statements under a case label should be indented, and the next label outdented"
            );

            buffer
        });
    }

    #[gpui::test]
    async fn test_cpp_autoindent_access_specifier(cx: &mut TestAppContext) {
        cx.update(|cx| {
            let test_settings = SettingsStore::test(cx);
            cx.set_global(test_settings);
            cx.update_global::<SettingsStore, _>(|store, cx| {
                store.update_user_settings(cx, |s| {
                    s.project.all_languages.defaults.tab_size = NonZeroU32::new(2);
                });
            });
        });
        let language = crate::language("cpp", tree_sitter_cpp::LANGUAGE.into());

        cx.new(|cx| {
            let mut buffer = Buffer::local("", cx).with_language(language, cx);

            buffer.edit(
                [(
                    0..0,
                    r#"
                    class Foo {
                    public:
                    void bar();
                    private:
                    int x;
                    };
                    "#
                    .unindent(),
                )],
                Some(AutoindentMode::EachLine),
                cx,
            );
            assert_eq!(
                buffer.text(),
                r#"
                class Foo {
                  public:
                    void bar();
                  private:
                    int x;
                };
                "#
                .unindent(),
                "members after access specifiers should be indented one level deeper than the specifier"
            );

            buffer
        });
    }

    #[gpui::test]
    async fn test_cpp_autoindent_access_specifier_next_line(cx: &mut TestAppContext) {
        cx.update(|cx| {
            let test_settings = SettingsStore::test(cx);
            cx.set_global(test_settings);
            cx.update_global::<SettingsStore, _>(|store, cx| {
                store.update_user_settings(cx, |s| {
                    s.project.all_languages.defaults.tab_size = NonZeroU32::new(2);
                });
            });
        });
        let language = crate::language("cpp", tree_sitter_cpp::LANGUAGE.into());

        cx.new(|cx| {
            let mut buffer = Buffer::local("", cx).with_language(language, cx);

            buffer.edit(
                [(
                    0..0,
                    r#"
                    class Foo {
                    public:
                      void bar();
                    void baz();
                    private:
                      int x;
                    };
                    "#
                    .unindent(),
                )],
                Some(AutoindentMode::EachLine),
                cx,
            );
            assert_eq!(
                buffer.text(),
                r#"
                class Foo {
                  public:
                    void bar();
                    void baz();
                  private:
                    int x;
                };
                "#
                .unindent(),
                "members after access specifiers should be indented one level deeper than the specifier"
            );

            buffer
        });
    }

    #[gpui::test]
    async fn test_cpp_autoindent_nested_class_access_specifiers(cx: &mut TestAppContext) {
        cx.update(|cx| {
            let test_settings = SettingsStore::test(cx);
            cx.set_global(test_settings);
            cx.update_global::<SettingsStore, _>(|store, cx| {
                store.update_user_settings(cx, |s| {
                    s.project.all_languages.defaults.tab_size = NonZeroU32::new(2);
                });
            });
        });
        let language = crate::language("cpp", tree_sitter_cpp::LANGUAGE.into());

        cx.new(|cx| {
            let mut buffer = Buffer::local("", cx).with_language(language, cx);

            buffer.edit(
                [(
                    0..0,
                    r#"
                    class Outer {
                    public:
                    class Inner {
                    public:
                    void inner_pub();
                    private:
                    int inner_priv;
                    };
                    private:
                    int outer_priv;
                    };
                    "#
                    .unindent(),
                )],
                Some(AutoindentMode::EachLine),
                cx,
            );
            assert_eq!(
                buffer.text(),
                r#"
                class Outer {
                  public:
                    class Inner {
                      public:
                        void inner_pub();
                      private:
                        int inner_priv;
                    };
                  private:
                    int outer_priv;
                };
                "#
                .unindent(),
                "nested class access specifiers should indent independently at each nesting level"
            );

            buffer
        });
    }

    #[gpui::test]
    async fn test_cpp_autoindent_consecutive_access_specifiers(cx: &mut TestAppContext) {
        cx.update(|cx| {
            let test_settings = SettingsStore::test(cx);
            cx.set_global(test_settings);
            cx.update_global::<SettingsStore, _>(|store, cx| {
                store.update_user_settings(cx, |s| {
                    s.project.all_languages.defaults.tab_size = NonZeroU32::new(2);
                });
            });
        });
        let language = crate::language("cpp", tree_sitter_cpp::LANGUAGE.into());

        cx.new(|cx| {
            let mut buffer = Buffer::local("", cx).with_language(language, cx);

            buffer.edit(
                [(
                    0..0,
                    r#"
                    class Foo {
                    public:
                    protected:
                    private:
                    int x;
                    };
                    "#
                    .unindent(),
                )],
                Some(AutoindentMode::EachLine),
                cx,
            );
            assert_eq!(
                buffer.text(),
                r#"
                class Foo {
                  public:
                  protected:
                  private:
                    int x;
                };
                "#
                .unindent(),
                "consecutive access specifiers with no members between them should all align at class level"
            );

            buffer
        });
    }

    #[gpui::test]
    async fn test_cpp_autoindent_indented_access_specifiers(cx: &mut TestAppContext) {
        cx.update(|cx| {
            let test_settings = SettingsStore::test(cx);
            cx.set_global(test_settings);
            cx.update_global::<SettingsStore, _>(|store, cx| {
                store.update_user_settings(cx, |s| {
                    s.project.all_languages.defaults.tab_size = NonZeroU32::new(2);
                });
            });
        });
        let language = crate::language("cpp", tree_sitter_cpp::LANGUAGE.into());

        cx.new(|cx| {
            let mut buffer = Buffer::local("", cx).with_language(language, cx);

            buffer.edit(
                [(
                    0..0,
                    r#"
                    class Foo {
                    int default_member;
                    public:
                    void pub_method();
                    private:
                    int priv_member;
                    };
                    "#
                    .unindent(),
                )],
                Some(AutoindentMode::EachLine),
                cx,
            );
            assert_eq!(
                buffer.text(),
                r#"
                class Foo {
                  int default_member;
                  public:
                    void pub_method();
                  private:
                    int priv_member;
                };
                "#
                .unindent(),
                "access specifiers should be indented one level inside class braces"
            );

            buffer
        });
    }

    #[gpui::test]
    async fn test_cpp_autoindent_access_specifier_with_method_bodies(cx: &mut TestAppContext) {
        cx.update(|cx| {
            let test_settings = SettingsStore::test(cx);
            cx.set_global(test_settings);
            cx.update_global::<SettingsStore, _>(|store, cx| {
                store.update_user_settings(cx, |s| {
                    s.project.all_languages.defaults.tab_size = NonZeroU32::new(2);
                });
            });
        });
        let language = crate::language("cpp", tree_sitter_cpp::LANGUAGE.into());

        cx.new(|cx| {
            let mut buffer = Buffer::local("", cx).with_language(language, cx);

            buffer.edit(
                [(
                    0..0,
                    r#"
                    class Foo {
                    public:
                    void bar() {
                    if (x)
                    y++;
                    }
                    private:
                    int get_x() {
                    return x;
                    }
                    int x;
                    };
                    "#
                    .unindent(),
                )],
                Some(AutoindentMode::EachLine),
                cx,
            );
            assert_eq!(
                buffer.text(),
                r#"
                class Foo {
                  public:
                    void bar() {
                      if (x)
                        y++;
                    }
                  private:
                    int get_x() {
                      return x;
                    }
                    int x;
                };
                "#
                .unindent(),
                "method bodies inside access specifier sections should compose brace and specifier indent"
            );

            buffer
        });
    }

    #[gpui::test]
    async fn test_cpp_autoindent_basic(cx: &mut TestAppContext) {
        cx.update(|cx| {
            let test_settings = SettingsStore::test(cx);
            cx.set_global(test_settings);
            cx.update_global::<SettingsStore, _>(|store, cx| {
                store.update_user_settings(cx, |s| {
                    s.project.all_languages.defaults.tab_size = NonZeroU32::new(2);
                });
            });
        });
        let language = crate::language("cpp", tree_sitter_cpp::LANGUAGE.into());

        cx.new(|cx| {
            let mut buffer = Buffer::local("", cx).with_language(language, cx);

            buffer.edit([(0..0, "int main() {}")], None, cx);

            let ix = buffer.len() - 1;
            buffer.edit([(ix..ix, "\n\n")], Some(AutoindentMode::EachLine), cx);
            assert_eq!(
                buffer.text(),
                "int main() {\n  \n}",
                "content inside braces should be indented"
            );

            buffer
        });
    }

    #[gpui::test]
    async fn test_cpp_autoindent_if_else(cx: &mut TestAppContext) {
        cx.update(|cx| {
            let test_settings = SettingsStore::test(cx);
            cx.set_global(test_settings);
            cx.update_global::<SettingsStore, _>(|store, cx| {
                store.update_user_settings(cx, |s| {
                    s.project.all_languages.defaults.tab_size = NonZeroU32::new(2);
                });
            });
        });
        let language = crate::language("cpp", tree_sitter_cpp::LANGUAGE.into());

        cx.new(|cx| {
            let mut buffer = Buffer::local("", cx).with_language(language, cx);

            buffer.edit(
                [(
                    0..0,
                    r#"
                    int main() {
                    if (a)
                    b;
                    }
                    "#
                    .unindent(),
                )],
                Some(AutoindentMode::EachLine),
                cx,
            );
            assert_eq!(
                buffer.text(),
                r#"
                int main() {
                  if (a)
                    b;
                }
                "#
                .unindent(),
                "body of if-statement without braces should be indented"
            );

            let ix = buffer.len() - 4;
            buffer.edit([(ix..ix, "\n.c")], Some(AutoindentMode::EachLine), cx);
            assert_eq!(
                buffer.text(),
                r#"
                int main() {
                  if (a)
                    b
                      .c;
                }
                "#
                .unindent(),
                "field expression (.c) should be indented further than the statement body"
            );

            buffer.edit([(0..buffer.len(), "")], Some(AutoindentMode::EachLine), cx);
            buffer.edit(
                [(
                    0..0,
                    r#"
                    int main() {
                    if (a) a++;
                    else b++;
                    }
                    "#
                    .unindent(),
                )],
                Some(AutoindentMode::EachLine),
                cx,
            );
            assert_eq!(
                buffer.text(),
                r#"
                int main() {
                  if (a) a++;
                  else b++;
                }
                "#
                .unindent(),
                "single-line if/else without braces should align at the same level"
            );

            buffer.edit([(0..buffer.len(), "")], Some(AutoindentMode::EachLine), cx);
            buffer.edit(
                [(
                    0..0,
                    r#"
                    int main() {
                    if (a)
                    b++;
                    else
                    c++;
                    }
                    "#
                    .unindent(),
                )],
                Some(AutoindentMode::EachLine),
                cx,
            );
            assert_eq!(
                buffer.text(),
                r#"
                int main() {
                  if (a)
                    b++;
                  else
                    c++;
                }
                "#
                .unindent(),
                "multi-line if/else without braces should indent statement bodies"
            );

            buffer.edit([(0..buffer.len(), "")], Some(AutoindentMode::EachLine), cx);
            buffer.edit(
                [(
                    0..0,
                    r#"
                    int main() {
                    if (a)
                    if (b)
                    c++;
                    }
                    "#
                    .unindent(),
                )],
                Some(AutoindentMode::EachLine),
                cx,
            );
            assert_eq!(
                buffer.text(),
                r#"
                int main() {
                  if (a)
                    if (b)
                      c++;
                }
                "#
                .unindent(),
                "nested if statements without braces should indent properly"
            );

            buffer.edit([(0..buffer.len(), "")], Some(AutoindentMode::EachLine), cx);
            buffer.edit(
                [(
                    0..0,
                    r#"
                    int main() {
                    if (a)
                    b++;
                    else if (c)
                    d++;
                    else
                    f++;
                    }
                    "#
                    .unindent(),
                )],
                Some(AutoindentMode::EachLine),
                cx,
            );
            assert_eq!(
                buffer.text(),
                r#"
                int main() {
                  if (a)
                    b++;
                  else if (c)
                    d++;
                  else
                    f++;
                }
                "#
                .unindent(),
                "else-if chains should align all conditions at same level with indented bodies"
            );

            buffer.edit([(0..buffer.len(), "")], Some(AutoindentMode::EachLine), cx);
            buffer.edit(
                [(
                    0..0,
                    r#"
                    int main() {
                    if (a) {
                    b++;
                    } else
                    c++;
                    }
                    "#
                    .unindent(),
                )],
                Some(AutoindentMode::EachLine),
                cx,
            );
            assert_eq!(
                buffer.text(),
                r#"
                int main() {
                  if (a) {
                    b++;
                  } else
                    c++;
                }
                "#
                .unindent(),
                "mixed braces should indent properly"
            );

            buffer
        });
    }
}
