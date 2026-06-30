// Thin wrappers around the Rust commands. Keeps invoke() calls in one place.

import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { open as shellOpen } from "@tauri-apps/plugin-shell";

// Open a URL (or path) in the user's default browser / app.
export async function openExternal(url) {
  return shellOpen(url);
}

export async function readFile(path) {
  return invoke("read_file", { path });
}

export async function writeFile(path, content) {
  return invoke("write_file", { path, content });
}

export async function listDir(path) {
  return invoke("list_dir", { path });
}

export async function pathExists(path) {
  return invoke("path_exists", { path });
}

export async function createFile(path, content = "") {
  return invoke("create_file", { path, content });
}

export async function deleteFile(path) {
  return invoke("delete_file", { path });
}

export async function renameFile(oldPath, newPath) {
  return invoke("rename_file", { oldPath, newPath });
}

export async function createDir(path) {
  return invoke("create_dir", { path });
}

export async function writeEnvKey(key, value) {
  return invoke("write_env_key", { key, value });
}

export async function getSystemInfo() {
  return invoke("get_system_info");
}

// Returns the parsed config object, or null if no config exists yet.
export async function getConfig() {
  const json = await invoke("get_config");
  if (!json) return null;
  try { return JSON.parse(json); } catch { return null; }
}

export async function saveConfig(configObj) {
  return invoke("save_config", { json: JSON.stringify(configObj) });
}

// ── Hackatime / WakaTime ─────────────────────────────────────────────────────

export async function getOsName() {
  return invoke("get_os_name");
}

// Send a coding heartbeat. api_key and api_url must be provided by the caller.
// extra = { lines?, lineno?, cursorpos?, branch? } — all optional WakaTime fields.
export async function sendHeartbeat(entity, project, language, isWrite, apiKey, apiUrl, extra = {}) {
  if (!apiKey || !apiUrl) return;
  return invoke("send_heartbeat", {
    entity,
    project:   project  || "",
    language:  language || "Other",
    isWrite:   isWrite  ?? false,
    apiKey,
    apiUrl,
    lines:     extra.lines     ?? null,
    lineno:    extra.lineno    ?? null,
    cursorpos: extra.cursorpos ?? null,
    branch:    extra.branch    ?? null,
  });
}

export async function getFileLineCount(path) {
  return invoke("get_file_line_count", { path });
}

// ── Arduino CLI ──────────────────────────────────────────────────────────────

export async function arduinoListPorts() {
  return invoke("arduino_list_ports");
}

export async function arduinoCompile(fqbn, filePath) {
  return invoke("arduino_compile", { fqbn, filePath });
}

export async function arduinoUpload(port, fqbn, filePath) {
  return invoke("arduino_upload", { port, fqbn, filePath });
}

// ── Extension store ──────────────────────────────────────────────────────────

export async function installExtension(id, url) {
  return invoke("install_extension", { id, url });
}

export async function uninstallExtension(id) {
  return invoke("uninstall_extension", { id });
}

export async function listExtensions() {
  return invoke("list_extensions");
}

// ── Git commands ─────────────────────────────────────────────────────────────
// Each returns the parsed result or throws a string error message.

export async function gitStatus(cwd) {
  return invoke("git_status", { cwd });
}

export async function gitDiff(cwd, file) {
  return invoke("git_diff", { cwd, file });
}

export async function gitStage(cwd, files) {
  return invoke("git_stage", { cwd, files });
}

export async function gitUnstage(cwd, files) {
  return invoke("git_unstage", { cwd, files });
}

export async function gitCommit(cwd, message) {
  return invoke("git_commit", { cwd, message });
}

export async function gitPush(cwd) {
  return invoke("git_push", { cwd });
}

export async function gitPull(cwd) {
  return invoke("git_pull", { cwd });
}

export async function gitLog(cwd, limit = 10) {
  return invoke("git_log", { cwd, limit });
}

export async function gitCurrentBranch(cwd) {
  return invoke("git_current_branch", { cwd });
}

// Contents of a repo-relative file at HEAD ("" if the file is newly added).
export async function gitShowHead(cwd, file) {
  return invoke("git_show_head", { cwd, file });
}

// ── Search in files ──────────────────────────────────────────────────────────
// Returns an array of { file, line, col, length, match_text, preview }.
export async function searchInFiles(root, query, caseSensitive, isRegex) {
  return invoke("search_in_files", { root, query, caseSensitive, isRegex });
}

// Replaces one match span; `expected` must equal the text originally found there.
export async function replaceInFile(file, line, col, length, expected, replacement) {
  return invoke("replace_in_file", { file, line, col, length, expected, replacement });
}

// ── .vagent.json / task runner ────────────────────────────────────────────
// Returns the parsed .vagent.json object, or null if not found / invalid.
export async function readVagentConfig(folderPath) {
  const json = await invoke("read_vagent_config", { path: folderPath });
  if (!json) return null;
  try { return JSON.parse(json); } catch { return null; }
}

// Writes a command to an active PTY session; optionally cd-s to cwd first.
export async function runTask(ptyId, command, cwd = null) {
  return invoke("run_task", { ptyId, command, cwd: cwd ?? null });
}

// ── PTY wrappers ────────────────────────────────────────────────────────
// ptyCreate returns { id: string, shell: string }
export async function ptyCreate(shell, cols, rows) {
  return invoke("pty_create", { shell: shell ?? null, cols, rows });
}

export async function ptyWrite(id, data) {
  return invoke("pty_write", { id, data });
}

export async function ptyResize(id, cols, rows) {
  return invoke("pty_resize", { id, cols, rows });
}

export async function ptyKill(id) {
  return invoke("pty_kill", { id });
}

// Subscribes to PTY output events. callback receives event.payload = { id, data }.
// Returns an unlisten function.
export async function onPtyOutput(callback) {
  return listen("pty-output", callback);
}

// Fires when the shell process exits. payload = session id string.
export async function onPtyClosed(callback) {
  return listen("pty-closed", callback);
}

// ── Persistent agent bridge ──────────────────────────────────────────────────
// Bidirectional channel to the long-lived sidecar. Requests are JSON objects;
// every output line arrives as an "agent-event".

export async function agentStart() {
  return invoke("agent_start");
}

export async function agentSend(obj) {
  return invoke("agent_send", { line: JSON.stringify(obj) });
}

// Subscribe to agent output. callback receives the parsed JSON event object.
// Returns an unlisten function.
export async function onAgentEvent(callback) {
  return listen("agent-event", (event) => {
    try { callback(JSON.parse(event.payload)); }
    catch { /* ignore non-JSON lines */ }
  });
}

// ── MCP client ───────────────────────────────────────────────────────────────

// ── Memory (Jarvis) ───────────────────────────────────────────────────────────

export async function getVagentMemory() {
  const raw = await invoke("get_vagent_memory");
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

export async function clearVagentMemory() {
  return invoke("clear_vagent_memory");
}

// ── MCP client ────────────────────────────────────────────────────────────────

export async function mcpCheckServer(serverUrl) {
  return invoke("mcp_check_server", { serverUrl });
}

// Returns parsed tool list array, or throws.
export async function mcpListTools(serverUrl) {
  const raw = await invoke("mcp_list_tools", { serverUrl });
  try { return JSON.parse(raw); } catch { return []; }
}

export async function mcpCallTool(serverUrl, toolName, args = {}) {
  return invoke("mcp_call_tool", { serverUrl, toolName, argsJson: JSON.stringify(args) });
}

// Starts an AI chat. Tokens arrive via the "ai-token" event.
// onToken(text) is called for each streamed JSON line; returns an unlisten fn.
export async function aiChat(messages, config, systemPrompt, onToken) {
  const unlisten = await listen("ai-token", (event) => {
    onToken(event.payload);
  });

  const payload = JSON.stringify({
    messages,
    config,
    system_prompt: systemPrompt || "",
  });

  try {
    await invoke("ai_chat", { payload });
  } finally {
    unlisten();
  }
}
