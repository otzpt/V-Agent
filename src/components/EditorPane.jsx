import { Editor, useMonaco } from "@monaco-editor/react";
import { useState, useCallback, useEffect, useRef, memo } from "react";
import { writeFile, sendHeartbeat, getOsName } from "../lib/tauri.js";
import { defineEnhancedLanguages } from "../lib/monacoLangs.js";
import LivePreview from "./LivePreview.jsx";
import ArduinoPanel from "./ArduinoPanel.jsx";

// Editor font-size bounds (mirrors App's editorPrefsFromConfig clamp)
const FONT_MIN = 10;
const FONT_MAX = 24;
const FONT_DEFAULT = 13;
const clampFont = (n) => Math.min(FONT_MAX, Math.max(FONT_MIN, n));

// Editor background per app theme so the editor blends with the app chrome.
// Token colors are shared (One-Dark-style — the user-preferred scheme).
const EDITOR_BG = {
  dark:          "#0a0a16",   // Aether default
  dracula:       "#282a36",
  "one-dark":    "#282c34",
  nord:          "#2e3440",
  catppuccin:    "#1e1e2e",
  "github-dark": "#0d1117",
  solarized:     "#002b36",
};

// Monaco custom theme to use for a given app theme (defined in defineEditorThemes).
function monacoThemeFor(appTheme) {
  if (appTheme === "light") return "vagent-light";
  return EDITOR_BG[appTheme] ? `vagent-${appTheme}` : "vagent-dark";
}

// One-shot Monaco setup: custom themes + enhanced language grammars. Runs in
// the Editor's beforeMount (synchronous, before the first render/setTheme) and
// again from the monaco effect as an idempotent safety net.
function setupMonaco(monaco) {
  defineEditorThemes(monaco);
  defineEnhancedLanguages(monaco);
}

// ── Theme factory ─────────────────────────────────────────────────────────────
// One shared token scheme (One-Dark-style: blue keywords, pink operators, gold
// types, green strings) with the editor background matched to each app theme.
// MUST run in the Editor's beforeMount: if the theme prop names a theme that is
// not registered yet, Monaco silently falls back to "vs" — a white editor on
// every cold app start. beforeMount is synchronous, so the name always exists
// by the time the first setTheme happens. Safe to call repeatedly.
function defineEditorThemes(monaco) {
  const TOKEN_RULES = [
    { token: "comment",          foreground: "7f848e", fontStyle: "italic" },
    { token: "keyword",          foreground: "61afef" },
    { token: "operator",         foreground: "e06c75" },
    { token: "delimiter",        foreground: "c8ccd4" },
    { token: "type",             foreground: "e5c07b" },
    { token: "type.identifier",  foreground: "e5c07b" },
    { token: "string",           foreground: "98c379" },
    { token: "string.escape",    foreground: "d19a66" },
    { token: "number",           foreground: "d19a66" },
    { token: "constant",         foreground: "d19a66" },
    { token: "function",         foreground: "e5c07b" },
    { token: "identifier",       foreground: "d7dbe0" },
    { token: "tag",              foreground: "e06c75" },
    { token: "attribute.name",   foreground: "d19a66" },
    { token: "attribute.value",  foreground: "98c379" },
  ];
  const BRACKET_COLORS = {
    "editorBracketHighlight.foreground1": "#e5c07b",
    "editorBracketHighlight.foreground2": "#c678dd",
    "editorBracketHighlight.foreground3": "#61afef",
    "editorBracketHighlight.foreground4": "#98c379",
    "editorBracketHighlight.unexpectedBracket.foreground": "#f06060",
  };
  for (const [name, bg] of Object.entries(EDITOR_BG)) {
    monaco.editor.defineTheme(`vagent-${name}`, {
      base: "vs-dark",
      inherit: true,
      rules: TOKEN_RULES,
      colors: {
        "editor.background":              bg,
        "editor.foreground":              "#d7dbe0",
        "editorLineNumber.foreground":    "#5c6370",
        "editor.lineHighlightBackground": "#ffffff08",
        ...BRACKET_COLORS,
      },
    });
  }
  monaco.editor.defineTheme("vagent-light", {
    base: "vs",
    inherit: true,
    rules: [
      { token: "comment",         foreground: "6a737d", fontStyle: "italic" },
      { token: "keyword",         foreground: "0550ae" },
      { token: "operator",        foreground: "cf222e" },
      { token: "type",            foreground: "953800" },
      { token: "type.identifier", foreground: "953800" },
      { token: "string",          foreground: "116329" },
      { token: "number",          foreground: "b76b01" },
      { token: "function",        foreground: "8250df" },
    ],
    colors: {
      "editor.background": "#ffffff",
      "editorBracketHighlight.foreground1": "#b76b01",
      "editorBracketHighlight.foreground2": "#8250df",
      "editorBracketHighlight.foreground3": "#0550ae",
      "editorBracketHighlight.unexpectedBracket.foreground": "#d03020",
    },
  });
}

// ── Lightweight syntax lint (brace-family languages) ─────────────────────────
// Monaco has no diagnostics for C/C++/Java/etc — this catches the common
// structural errors safely: unmatched ( [ {, unclosed block comments, and
// string/char literals left open at end of line. No style opinions.
const BRACE_LANGS = new Set(["c", "cpp", "csharp", "java", "kotlin", "swift", "dart", "go"]);

function lintBraces(text) {
  const out = [];
  const pairs = { ")": "(", "]": "[", "}": "{" };
  const stack = [];
  let mode = null;            // null | "line" | "block" | "triple" | '"' | "'" | "`"
  let line = 1, col = 1, strLine = 0, strCol = 0, blkLine = 0, blkCol = 0;
  for (let i = 0; i < text.length; i++, col++) {
    const c = text[i], n = text[i + 1];
    if (c === "\n") {
      if (mode === "line") mode = null;
      if (mode === '"' || mode === "'") {
        out.push({ line: strLine, col: strCol, msg: mode === '"' ? "String literal is not closed" : "Character literal is not closed" });
        mode = null;
      }
      line++; col = 0; continue;
    }
    if (mode === "line") continue;
    if (mode === "block") {
      if (c === "*" && n === "/") { mode = null; i++; col++; }
      continue;
    }
    if (mode === "triple") {
      if (c === '"' && n === '"' && text[i + 2] === '"') { mode = null; i += 2; col += 2; }
      continue;
    }
    if (mode === "`") { if (c === "`") mode = null; continue; }
    if (mode === '"' || mode === "'") {
      if (c === "\\") {
        if (n === "\n") { line++; col = 0; }
        i++; col++;
      } else if (c === mode) mode = null;
      continue;
    }
    if (c === "/" && n === "/") { mode = "line"; i++; col++; continue; }
    if (c === "/" && n === "*") { mode = "block"; blkLine = line; blkCol = col; i++; col++; continue; }
    if (c === '"' && n === '"' && text[i + 2] === '"') { mode = "triple"; i += 2; col += 2; continue; }
    if (c === '"' || c === "'") { mode = c; strLine = line; strCol = col; continue; }
    if (c === "`") { mode = "`"; continue; }
    if (c === "(" || c === "[" || c === "{") { stack.push({ ch: c, line, col }); continue; }
    if (c === ")" || c === "]" || c === "}") {
      const top = stack[stack.length - 1];
      if (top && top.ch === pairs[c]) stack.pop();
      else out.push({ line, col, msg: `Unmatched '${c}'` });
    }
  }
  if (mode === "block") out.push({ line: blkLine, col: blkCol, msg: "Block comment is not closed" });
  for (const o of stack) out.push({ line: o.line, col: o.col, msg: `Unclosed '${o.ch}'` });
  return out.slice(0, 20);
}

// WakaTime language names (as accepted by the Hackatime API)
const WAKA_LANG = {
  // Web / JS
  js: "JavaScript", jsx: "JavaScript", mjs: "JavaScript", cjs: "JavaScript",
  ts: "TypeScript", tsx: "TypeScript",
  html: "HTML", htm: "HTML", css: "CSS", coffee: "CoffeeScript",
  // Systems
  c: "C", h: "C", cpp: "C++", hpp: "C++",
  cs: "C#", rs: "Rust", java: "Java", kt: "Kotlin", swift: "Swift",
  go: "Go", ino: "Arduino",
  // Scripting
  py: "Python", rb: "Ruby", php: "PHP", pl: "Perl", lua: "Lua", r: "R",
  sh: "Shell Script", ps1: "PowerShell",
  // Functional / JVM
  scala: "Scala", groovy: "Groovy", gradle: "Groovy",
  fs: "F#", vb: "Visual Basic", hs: "Haskell",
  ex: "Elixir", exs: "Elixir", erl: "Erlang",
  clj: "Clojure", ml: "OCaml",
  // Mobile
  dart: "Dart",
  // Data / Query
  sql: "SQL", graphql: "GraphQL",
  json: "JSON", yaml: "YAML", yml: "YAML", toml: "TOML", xml: "XML",
  // Infrastructure
  tf: "HCL", proto: "Protocol Buffer",
  dockerfile: "Dockerfile", makefile: "Makefile", cmake: "CMake", nginx: "Nginx",
  // Docs / misc
  md: "Markdown",
  asm: "Assembly", s: "Assembly", nasm: "Assembly",
  vim: "Vim Script",
};

function wakaLangFor(name) {
  if (!name) return "Other";
  const ext = name.split(".").pop().toLowerCase();
  return WAKA_LANG[ext] || "Other";
}

const EXT_LANG = {
  // Web / JS ecosystem
  js: "javascript", jsx: "javascript", mjs: "javascript", cjs: "javascript",
  ts: "typescript", tsx: "typescript",
  html: "html", htm: "html", css: "css", coffee: "coffeescript",
  // Systems
  c: "c", h: "c", cpp: "cpp", hpp: "cpp",
  cs: "csharp", rs: "rust", java: "java", kt: "kotlin", swift: "swift",
  go: "go", ino: "cpp",
  // Scripting
  py: "python", rb: "ruby", php: "php", pl: "perl", lua: "lua", r: "r",
  sh: "shell", ps1: "powershell",
  // Functional / JVM
  scala: "scala", groovy: "groovy", gradle: "groovy",
  fs: "fsharp", vb: "vb", hs: "plaintext",
  ex: "elixir", exs: "elixir", erl: "plaintext",
  clj: "clojure", ml: "plaintext",
  // Mobile
  dart: "dart",
  // Data / Query
  sql: "sql", graphql: "graphql",
  json: "json", yaml: "yaml", yml: "yaml", toml: "ini", xml: "xml",
  // Infrastructure / DevOps
  tf: "hcl", proto: "protobuf",
  dockerfile: "dockerfile", makefile: "makefile", cmake: "cmake", nginx: "nginx",
  // Docs / Config / misc
  md: "markdown", editorconfig: "ini",
  gitignore: "plaintext", env: "plaintext", vim: "plaintext",
  asm: "plaintext", s: "plaintext", nasm: "plaintext",
};

const RUN_COMMANDS = {
  py:  (p) => `python "${p}"`,
  js:  (p) => `node "${p}"`,
  ts:  (p) => `npx ts-node "${p}"`,
  rs:  ()  => `cargo run`,
  c:   (p) => `gcc "${p}" -o out && ./out`,
  cpp: (p) => `g++ "${p}" -o out && ./out`,
  sh:  (p) => `bash "${p}"`,
  ps1: (p) => `powershell -File "${p}"`,
};

function runCommandFor(filePath) {
  if (!filePath) return null;
  const ext = filePath.split(".").pop().toLowerCase();
  const fn = RUN_COMMANDS[ext];
  return fn ? fn(filePath) : null;
}

function langFor(name) {
  if (!name) return "plaintext";
  const ext = name.split(".").pop().toLowerCase();
  return EXT_LANG[ext] || "plaintext";
}

// Normalise a path string for comparison (forward slashes, lowercase, strip
// leading slash before Windows drive letter e.g. /C:/... → c:/...)
function normPath(p) {
  return p.replace(/\\/g, "/").replace(/^\/([A-Za-z]:)/, "$1").toLowerCase();
}

// Build clickable breadcrumb segments for a file, relative to its workspace root.
// Each segment carries the absolute path it points to.
function breadcrumbSegments(filePath, rootDirs = []) {
  const sep = filePath.includes("\\") ? "\\" : "/";
  const fwd = (p) => p.replace(/\\/g, "/");
  const root = rootDirs.find((r) => fwd(filePath).toLowerCase().startsWith(fwd(r).toLowerCase() + "/"));
  if (!root) {
    return [{ label: filePath.split(/[/\\]/).pop(), path: filePath }];
  }
  const rel = filePath.slice(root.length).replace(/^[/\\]+/, "");
  const segs = [{ label: root.split(/[/\\]/).filter(Boolean).pop(), path: root }];
  let acc = root;
  for (const part of rel.split(/[/\\]/)) {
    acc = acc + sep + part;
    segs.push({ label: part, path: acc });
  }
  return segs;
}

function Breadcrumbs({ filePath, rootDirs, onReveal }) {
  if (!filePath) return null;
  const segs = breadcrumbSegments(filePath, rootDirs);
  return (
    <div style={bcStyles.bar}>
      {segs.map((s, i) => (
        <span key={s.path} style={{ display: "inline-flex", alignItems: "center" }}>
          {i > 0 && <span style={bcStyles.sep}>/</span>}
          <span
            style={{ ...bcStyles.seg, color: i === segs.length - 1 ? "var(--text-1)" : "var(--text-2)" }}
            onClick={() => onReveal?.(s.path)}
            onMouseEnter={(e) => (e.currentTarget.style.color = "var(--accent)")}
            onMouseLeave={(e) => (e.currentTarget.style.color = i === segs.length - 1 ? "var(--text-1)" : "var(--text-2)")}
            title={s.path}
          >
            {s.label}
          </span>
        </span>
      ))}
    </div>
  );
}

const bcStyles = {
  bar: {
    display: "flex",
    alignItems: "center",
    height: "24px",
    padding: "0 12px",
    background: "var(--bg-1)",
    borderBottom: "1px solid var(--border)",
    fontSize: "11px",
    fontFamily: "var(--font-mono)",
    flexShrink: 0,
    overflowX: "auto",
    whiteSpace: "nowrap",
  },
  seg: { cursor: "pointer", transition: "color 80ms ease" },
  sep: { color: "var(--text-2)", margin: "0 6px", opacity: 0.6 },
};

// ── Tab bar ───────────────────────────────────────────────────────────────────

// Small icon toggle button for the tab bar controls cluster
function EditorToggle({ on, onClick, title, children }) {
  return (
    <button
      title={title}
      onClick={onClick}
      style={{
        width: "24px",
        height: "24px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: "var(--r-sm)",
        flexShrink: 0,
        color: on ? "var(--accent)" : "var(--text-2)",
        background: on ? "var(--accent-dim)" : "transparent",
        cursor: "pointer",
      }}
    >
      {children}
    </button>
  );
}

const PREVIEW_EXTS = new Set(["html", "htm", "css", "js"]);

const TabBar = memo(function TabBar({ openFiles, activeFilePath, onSelectTab, onCloseTab, runCmd, onRun, canRun, minimapOn, onToggleMinimap, wrapOn, onToggleWrap, previewOn, onTogglePreview, isPreviewable, showUpload, onOpenUpload }) {
  if (openFiles.length === 0) return null;
  return (
    <div style={tabStyles.bar}>
      {openFiles.map((file) => {
        const active = file.path === activeFilePath;
        const dirty  = file.content !== file.savedContent;
        return (
          <div
            key={file.path}
            className="tab"
            style={{
              ...tabStyles.tab,
              background: active ? "var(--bg-0)" : "transparent",
              borderBottom: active ? "2px solid var(--accent)" : "2px solid transparent",
              opacity: active ? 1 : 0.62,
            }}
            onClick={() => onSelectTab(file.path)}
            title={dirty ? `${file.path} — unsaved changes` : file.path}
          >
            <span style={tabStyles.name}>{file.name}</span>
            {dirty && <span style={tabStyles.dirty} title="Unsaved changes">●</span>}
            <button
              style={tabStyles.close}
              title="Close tab (Ctrl+W)"
              onClick={(e) => { e.stopPropagation(); onCloseTab(file.path); }}
            >
              ×
            </button>
          </div>
        );
      })}
      <div style={tabStyles.controls}>
        {isPreviewable && (
          <EditorToggle on={previewOn} onClick={onTogglePreview} title="Toggle live preview">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
              <circle cx="12" cy="12" r="3"/>
            </svg>
          </EditorToggle>
        )}
        <EditorToggle on={wrapOn} onClick={onToggleWrap} title="Toggle word wrap">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <line x1="3" y1="6" x2="21" y2="6" />
            <path d="M3 12h15a3 3 0 010 6h-4" />
            <polyline points="16 16 14 18 16 20" />
            <line x1="3" y1="18" x2="9" y2="18" />
          </svg>
        </EditorToggle>
        <EditorToggle on={minimapOn} onClick={onToggleMinimap} title="Toggle minimap">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="1.6" strokeLinecap="round">
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <line x1="15" y1="3" x2="15" y2="21" />
            <line x1="17.5" y1="7" x2="19" y2="7" />
            <line x1="17.5" y1="11" x2="19" y2="11" />
            <line x1="17.5" y1="15" x2="18.5" y2="15" />
          </svg>
        </EditorToggle>
        {runCmd && (
          <button
            style={{
              ...tabStyles.runBtn,
              opacity: canRun ? 1 : 0.4,
              cursor: canRun ? "pointer" : "not-allowed",
            }}
            onClick={canRun ? onRun : undefined}
            title={canRun ? runCmd : "Open a terminal first"}
          >
            ▶ Run
          </button>
        )}
        {showUpload && (
          <button
            style={{ ...tabStyles.runBtn, color: "var(--warn)", borderColor: "var(--warn)", background: "rgba(245,192,64,0.12)" }}
            onClick={onOpenUpload}
            title="Arduino: Compile & Upload"
          >
            ⇪ Upload
          </button>
        )}
      </div>
    </div>
  );
});

const tabStyles = {
  bar: {
    display: "flex",
    background: "var(--bg-1)",
    borderBottom: "1px solid var(--border)",
    minHeight: "38px",
    overflowX: "auto",
    overflowY: "hidden",
    alignItems: "stretch",
  },
  tab: {
    display: "flex",
    alignItems: "center",
    gap: "7px",
    padding: "0 8px 0 14px",
    borderRight: "1px solid var(--border)",
    fontSize: "12px",
    fontFamily: "var(--font-mono)",
    cursor: "pointer",
    whiteSpace: "nowrap",
    flexShrink: 0,
    maxWidth: "160px",
    height: "100%",
    transition: "background var(--dur) var(--ease), opacity var(--dur) var(--ease)",
  },
  name: { color: "var(--text-0)", overflow: "hidden", textOverflow: "ellipsis", flex: 1 },
  dirty: { color: "var(--accent)", fontSize: "11px", lineHeight: 1, marginLeft: "-3px" },
  close: {
    width: "18px",
    height: "18px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "15px",
    color: "var(--text-2)",
    borderRadius: "var(--r-xs)",
    lineHeight: 1,
    padding: 0,
    cursor: "pointer",
  },
  controls: {
    marginLeft: "auto",
    display: "flex",
    alignItems: "center",
    gap: "4px",
    padding: "0 10px",
    flexShrink: 0,
  },
  runBtn: {
    padding: "4px 12px",
    fontSize: "11px",
    fontFamily: "var(--font-ui)",
    fontWeight: 600,
    color: "var(--accent)",
    background: "var(--accent-dim)",
    border: "1px solid var(--accent)",
    borderRadius: "var(--r-sm)",
    whiteSpace: "nowrap",
    flexShrink: 0,
  },
};

// ── Problems panel ────────────────────────────────────────────────────────────

const SEV_ERROR   = 8;
const SEV_WARNING = 4;

function ProblemsPanel({ markers, onJumpTo }) {
  if (markers.length === 0) return null;

  const errCount  = markers.filter((m) => m.severity === SEV_ERROR).length;
  const warnCount = markers.filter((m) => m.severity === SEV_WARNING).length;

  return (
    <div style={pb.wrap}>
      <div style={pb.header}>
        <span style={pb.title}>Problems</span>
        <span style={pb.counts}>
          {errCount  > 0 && <span style={{ color: "var(--err)" }}>⊗ {errCount}</span>}
          {warnCount > 0 && <span style={{ color: "var(--warn)" }}>⚠ {warnCount}</span>}
        </span>
      </div>
      <div style={pb.list}>
        {markers.map((m, i) => (
          <div
            key={i}
            style={pb.item}
            onClick={() => onJumpTo(m.monacoPath, m.line, m.col)}
            title={`${m.message}\n${m.filename}:${m.line}:${m.col}`}
          >
            <span style={{
              ...pb.icon,
              color: m.severity === SEV_ERROR ? "var(--err)" : "var(--warn)",
            }}>
              {m.severity === SEV_ERROR ? "⊗" : "⚠"}
            </span>
            <span style={pb.msg}>{m.message}</span>
            <span style={pb.loc}>{m.filename}:{m.line}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

const pb = {
  wrap: {
    borderTop: "1px solid var(--border)",
    background: "var(--bg-1)",
    flexShrink: 0,
    maxHeight: "160px",
    display: "flex",
    flexDirection: "column",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "4px 12px",
    borderBottom: "1px solid var(--border)",
    flexShrink: 0,
  },
  title: {
    fontSize: "10px",
    letterSpacing: "0.06em",
    textTransform: "uppercase",
    color: "var(--text-2)",
    fontFamily: "var(--font-ui)",
  },
  counts: {
    display: "flex",
    gap: "10px",
    fontSize: "11px",
    fontFamily: "var(--font-ui)",
    fontWeight: 600,
  },
  list: { overflow: "auto", flex: 1 },
  item: {
    display: "flex",
    alignItems: "baseline",
    gap: "8px",
    padding: "3px 12px",
    fontSize: "11px",
    fontFamily: "var(--font-ui)",
    cursor: "pointer",
    userSelect: "none",
  },
  icon:  { flexShrink: 0, fontSize: "12px" },
  msg:   { flex: 1, color: "var(--text-1)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  loc:   { flexShrink: 0, color: "var(--text-2)", fontFamily: "var(--font-mono)", fontSize: "10px" },
};

// ── Editor pane ───────────────────────────────────────────────────────────────

const HK_DEFAULT_URL = "https://hackatime.hackclub.com/api/hackatime/v1/users/current/heartbeats";

export default function EditorPane({ openFiles, activeFilePath, onSelectTab, onCloseTab, onChange, onSaved, saveSignal, onRun, activePtyId, hackatimeConfig, editorPrefs = {}, onEditorPref, rootDirs = [], onRevealPath, jumpTarget, appTheme = "dark", onAskAI, onCursorChange, onHackatimeStatus, onMarkersChange }) {
  const activeFile = openFiles.find((f) => f.path === activeFilePath) ?? null;
  const runCmd     = runCommandFor(activeFile?.path ?? null);
  const fontSize   = clampFont(editorPrefs.editor_font_size ?? FONT_DEFAULT);

  const editorRef        = useRef(null);
  const closeTabRef      = useRef(onCloseTab);
  const activePathRef    = useRef(activeFilePath);
  const pendingJumpRef   = useRef(null);
  const lastHeartbeatRef = useRef(0);    // ms timestamp of last heartbeat sent
  const cursorPosRef     = useRef({ line: 1, col: 1 }); // local cursor for heartbeats
  const osNameRef        = useRef("Unknown");
  const saveRef          = useRef(null); // always-fresh save handler for keybindings
  const [markers, setMarkers]               = useState([]);
  const [saveError, setSaveError]           = useState(null);
  const [askWidget, setAskWidget]           = useState(null); // { top, left, text } | null
  const [askMenuOpen, setAskMenuOpen]       = useState(false);
  const [previewOn, setPreviewOn]           = useState(false);
  const [previewOrientation, setPreviewOrientation] = useState("vertical");

  const activeExt     = activeFile?.name?.split(".").pop()?.toLowerCase() ?? "";
  const isPreviewable = PREVIEW_EXTS.has(activeExt);
  // Board workflows: .ino → arduino-cli, .py → MicroPython (mpremote)
  const isArduino     = activeExt === "ino" || activeExt === "py";

  const [arduinoPanelOpen, setArduinoPanelOpen] = useState(false);

  // Auto-close preview when switching to a file that doesn't support it
  useEffect(() => { if (!isPreviewable) setPreviewOn(false); }, [isPreviewable]);

  useEffect(() => { closeTabRef.current   = onCloseTab; },    [onCloseTab]);
  useEffect(() => { activePathRef.current = activeFilePath; }, [activeFilePath]);

  // Propagate problem counts to parent (StatusBar)
  useEffect(() => {
    const errors   = markers.filter((m) => m.severity === SEV_ERROR).length;
    const warnings = markers.filter((m) => m.severity === SEV_WARNING).length;
    onMarkersChange?.({ errors, warnings });
  }, [markers, onMarkersChange]);

  // Cache the OS name once on mount (needed for heartbeat payload)
  useEffect(() => { getOsName().then((n) => { osNameRef.current = n; }).catch(() => {}); }, []);

  // ── Hackatime heartbeats ─────────────────────────────────────────────────────
  const sendHB = useCallback(async (isWrite = false) => {
    const cfg = hackatimeConfig;
    if (!cfg?.enabled || !cfg?.apiKey || !activeFile) return;
    if (cfg.writesOnly && !isWrite) return;  // "writes only" mode

    const now = Date.now();
    // 30s debounce: skip non-write heartbeats sent within 30s of the last one
    if (!isWrite && now - lastHeartbeatRef.current < 30_000) return;
    lastHeartbeatRef.current = now;

    const parts = activeFile.path.replace(/\\/g, "/").split("/");
    const project = parts.length >= 2 ? parts[parts.length - 2] : "unknown";
    const lines     = editorRef.current?.getModel()?.getLineCount() ?? undefined;
    const { line: lineno, col: cursorpos } = cursorPosRef.current;
    const apiUrl = cfg.apiUrl || HK_DEFAULT_URL;

    try {
      await sendHeartbeat(
        activeFile.path, project, wakaLangFor(activeFile.name), isWrite,
        cfg.apiKey, apiUrl,
        { lines, lineno, cursorpos, branch: "" },
      );
      onHackatimeStatus?.({ status: "tracking", lastSent: Date.now() });
    } catch (e) {
      onHackatimeStatus?.({ status: "error", error: String(e) });
    }
  }, [hackatimeConfig, activeFile, onHackatimeStatus]);

  // Always-fresh ref so stable closures (handleMount, interval) call the latest sendHB
  const sendHBRef = useRef(sendHB);
  useEffect(() => { sendHBRef.current = sendHB; }, [sendHB]);

  // Heartbeat when switching to a different file (is_write: false)
  useEffect(() => {
    sendHBRef.current(false);
  }, [activeFile?.path]);

  // ── Monaco instance: configure diagnostics + subscribe to markers ────────────
  const monaco = useMonaco();

  useEffect(() => {
    if (!monaco) return;

    // Idempotent — themes are primarily defined in the Editor's beforeMount
    // (synchronously, so the first setTheme never sees an unknown name and
    // falls back to the white "vs" theme); this covers hot-reload paths.
    setupMonaco(monaco);

    const js = monaco.languages.typescript.javascriptDefaults;
    const ts = monaco.languages.typescript.typescriptDefaults;

    // JS/JSX: only syntax errors (no semantic — too many false positives without types)
    js.setDiagnosticsOptions({ noSyntaxValidation: false, noSemanticValidation: true });
    js.setCompilerOptions({
      target:               monaco.languages.typescript.ScriptTarget.ESNext,
      allowNonTsExtensions: true,
      allowJs:              true,
      checkJs:              false,
      jsx:                  monaco.languages.typescript.JsxEmit.React,
      noEmit:               true,
      esModuleInterop:      true,
    });

    // TS/TSX: full diagnostics, lenient settings
    ts.setDiagnosticsOptions({ noSyntaxValidation: false, noSemanticValidation: false });
    ts.setCompilerOptions({
      target:               monaco.languages.typescript.ScriptTarget.ESNext,
      allowNonTsExtensions: true,
      jsx:                  monaco.languages.typescript.JsxEmit.React,
      noEmit:               true,
      esModuleInterop:      true,
      strict:               false,
      skipLibCheck:         true,
    });

    // Collect markers from all models whenever they change (debounced 500ms, max 50)
    let markerTimer = null;
    const disposable = monaco.editor.onDidChangeMarkers(() => {
      clearTimeout(markerTimer);
      markerTimer = setTimeout(() => {
        const raw = monaco.editor.getModelMarkers({})
          .filter((m) => m.severity >= SEV_WARNING)
          .slice(0, 50);
        setMarkers(
          raw.map((m) => ({
            monacoPath: m.resource.path,
            filename:   m.resource.path.split("/").pop() || m.resource.path,
            severity:   m.severity,
            message:    m.message,
            line:       m.startLineNumber,
            col:        m.startColumn,
          }))
        );
      }, 500);
    });

    // ── Structural lint for C-family languages (no built-in diagnostics) ─────
    const lintModel = (model) => {
      if (model.isDisposed()) return;
      const ms = BRACE_LANGS.has(model.getLanguageId())
        ? lintBraces(model.getValue()).map((m) => ({
            severity:        monaco.MarkerSeverity.Error,
            message:         m.msg,
            startLineNumber: m.line,
            startColumn:     m.col,
            endLineNumber:   m.line,
            endColumn:       m.col + 1,
          }))
        : [];
      monaco.editor.setModelMarkers(model, "vagent-syntax", ms);
    };
    const lintDisposables = [];
    const lintTimers = new Map();
    const attachLint = (model) => {
      lintDisposables.push(
        model.onDidChangeContent(() => {
          clearTimeout(lintTimers.get(model));
          lintTimers.set(model, setTimeout(() => lintModel(model), 600));
        }),
        model.onDidChangeLanguage(() => lintModel(model)),
      );
      lintModel(model);
    };
    monaco.editor.getModels().forEach(attachLint);
    lintDisposables.push(monaco.editor.onDidCreateModel(attachLint));

    return () => {
      disposable.dispose();
      clearTimeout(markerTimer);
      lintDisposables.forEach((d) => d.dispose());
      lintTimers.forEach((t) => clearTimeout(t));
    };
  }, [monaco]);

  // ── Execute pending line-jump after a tab switch ──────────────────────────────
  useEffect(() => {
    if (!pendingJumpRef.current || !editorRef.current) return;
    const { line, col } = pendingJumpRef.current;
    pendingJumpRef.current = null;
    // Delay so Monaco finishes loading the new model
    const t = setTimeout(() => {
      const ed = editorRef.current;
      if (!ed) return;
      ed.revealLineInCenter(line);
      ed.setPosition({ lineNumber: line, column: col || 1 });
      ed.focus();
    }, 80);
    return () => clearTimeout(t);
  }, [activeFilePath]);

  // ── External jump (search-result click): reveal + select the match ────────────
  // App opens the file (updating activeFilePath) and then bumps jumpTarget.nonce,
  // so by the time this runs the right model is active; a short delay lets Monaco
  // finish swapping the model before we move the cursor.
  useEffect(() => {
    if (!jumpTarget?.line) return;
    const { line, col, length } = jumpTarget;
    const t = setTimeout(() => {
      const ed = editorRef.current;
      if (!ed) return;
      ed.revealLineInCenter(line);
      const startCol = col || 1;
      if (length) {
        ed.setSelection({
          startLineNumber: line, startColumn: startCol,
          endLineNumber: line,   endColumn: startCol + length,
        });
      } else {
        ed.setPosition({ lineNumber: line, column: startCol });
      }
      ed.focus();
    }, 140);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jumpTarget?.nonce]);

  // ── Jump to a problem location ────────────────────────────────────────────────
  const jumpTo = useCallback((monacoPath, line, col) => {
    // Find the matching open file (normalise slashes + Windows drive prefix)
    const target = openFiles.find(
      (f) => normPath(f.path) === normPath(monacoPath.replace(/^\/([A-Za-z]:)/, "$1"))
    );
    if (!target) return;

    if (target.path === activeFilePath) {
      // Already on this file — jump immediately
      const ed = editorRef.current;
      if (ed) {
        ed.revealLineInCenter(line);
        ed.setPosition({ lineNumber: line, column: col || 1 });
        ed.focus();
      }
    } else {
      // Switch tab first, then jump
      pendingJumpRef.current = { line, col };
      onSelectTab(target.path);
    }
  }, [openFiles, activeFilePath, onSelectTab]);

  // ── Monaco editor event handlers ─────────────────────────────────────────────

  // handleSave is recreated whenever activeFile changes, so it always sees the
  // current content. We keep it in saveRef so the (once-registered) Monaco
  // keybinding and the window fallback always call the latest version.
  const handleSave = useCallback(async () => {
    if (!activeFile) return;
    try {
      await writeFile(activeFile.path, activeFile.content);
      setSaveError(null);
      onSaved?.(activeFile.path);   // tell App this path is now clean
      sendHB(true);                 // is_write heartbeat on every explicit save
    } catch (e) {
      setSaveError(`Save failed: ${e}`);
    }
  }, [activeFile, onSaved, sendHB]);

  useEffect(() => { saveRef.current = handleSave; }, [handleSave]);

  // External save trigger (Command Palette "Save File"). Skip the initial 0.
  useEffect(() => {
    if (saveSignal) saveRef.current?.();
  }, [saveSignal]);

  // ── Auto-save ─────────────────────────────────────────────────────────────────
  // When enabled, persist a *modified* file 1s after the user stops typing. The
  // timer resets on every keystroke (cleanup), so it fires once typing settles.
  useEffect(() => {
    if (!editorPrefs.auto_save || !activeFile) return;
    if (activeFile.content === activeFile.savedContent) return; // not dirty — skip
    const t = setTimeout(() => { saveRef.current?.(); }, 1000);
    return () => clearTimeout(t);
  }, [editorPrefs.auto_save, activeFile?.path, activeFile?.content, activeFile?.savedContent]);

  // Window-level Ctrl/Cmd+S fallback (fires even when focus is outside Monaco)
  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === "s" || e.key === "S")) {
        e.preventDefault();
        saveRef.current?.();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // ── Font-size control: Ctrl/Cmd with +, -, 0 (reset) ──────────────────────────
  useEffect(() => {
    const onKey = (e) => {
      if (!(e.ctrlKey || e.metaKey) || e.altKey) return;
      const k = e.key;
      if (k === "=" || k === "+") {
        e.preventDefault();
        onEditorPref?.("editor_font_size", clampFont(fontSize + 1));
      } else if (k === "-" || k === "_") {
        e.preventDefault();
        onEditorPref?.("editor_font_size", clampFont(fontSize - 1));
      } else if (k === "0") {
        e.preventDefault();
        onEditorPref?.("editor_font_size", FONT_DEFAULT);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fontSize, onEditorPref]);

  const handleMount = useCallback((editor, monacoInst) => {
    editorRef.current = editor;

    editor.addCommand(monacoInst.KeyMod.CtrlCmd | monacoInst.KeyCode.KeyS, () => saveRef.current?.());
    editor.addCommand(monacoInst.KeyMod.CtrlCmd | monacoInst.KeyCode.KeyW, () => {
      const path = activePathRef.current;
      if (path) closeTabRef.current(path);
    });

    // Track cursor position locally (heartbeats) and report to parent (status bar)
    editor.onDidChangeCursorPosition((e) => {
      cursorPosRef.current = { line: e.position.lineNumber, col: e.position.column };
      onCursorChange?.({ line: e.position.lineNumber, col: e.position.column });
    });

    // Typing debounce: send heartbeat at most once per 30s during active editing
    editor.onDidChangeModelContent(() => {
      sendHBRef.current(false);
    });

    // Floating "Ask AI" affordance shown above a non-empty selection.
    const refreshAsk = () => {
      const sel = editor.getSelection();
      const model = editor.getModel();
      if (!sel || sel.isEmpty() || !model) { setAskWidget(null); setAskMenuOpen(false); return; }
      const text = model.getValueInRange(sel);
      if (!text || !text.trim()) { setAskWidget(null); setAskMenuOpen(false); return; }
      const pos = editor.getScrolledVisiblePosition(sel.getStartPosition());
      if (!pos) { setAskWidget(null); return; }
      setAskMenuOpen(false);
      setAskWidget({ top: pos.top, left: pos.left, text });
    };
    editor.onDidChangeCursorSelection(refreshAsk);
    editor.onDidScrollChange(refreshAsk);
  }, []);

  const doAsk = useCallback((action) => {
    if (!askWidget) return;
    onAskAI?.({ action, code: askWidget.text, file: activeFile?.name });
    setAskWidget(null);
    setAskMenuOpen(false);
  }, [askWidget, onAskAI, activeFile]);

  // ── Render ────────────────────────────────────────────────────────────────────

  if (openFiles.length === 0) {
    return (
      <div style={styles.empty}>
        <div style={styles.welcomeCard}>
          <div style={styles.welcomeLogo}>
            <svg width="52" height="52" viewBox="0 0 52 52" fill="none">
              <rect x="2" y="2" width="48" height="48" rx="13" fill="var(--accent-dim)" />
              <path d="M15 18L26 38L37 18" stroke="var(--accent)" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <h1 style={styles.welcomeTitle}>V-Agent</h1>
          <p style={styles.welcomeSub}>AI-powered local coding assistant</p>
          <div style={styles.welcomeDivider} />
          <div style={styles.welcomeShortcuts}>
            {[
              ["Open Folder",      "Ctrl+K, O"],
              ["Command Palette",  "Ctrl+Shift+P"],
              ["Search in Files",  "Ctrl+Shift+F"],
              ["Save File",        "Ctrl+S"],
            ].map(([label, keys]) => (
              <div key={label} style={styles.shortcutRow}>
                <span style={styles.shortcutLabel}>{label}</span>
                <kbd className="va-welcome-kbd">{keys}</kbd>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.wrap}>
      <TabBar
        openFiles={openFiles}
        activeFilePath={activeFilePath}
        onSelectTab={onSelectTab}
        onCloseTab={onCloseTab}
        runCmd={runCmd}
        onRun={() => runCmd && onRun?.(runCmd)}
        canRun={!!activePtyId}
        minimapOn={!!editorPrefs.minimap_enabled}
        onToggleMinimap={() => onEditorPref?.("minimap_enabled", !editorPrefs.minimap_enabled)}
        wrapOn={!!editorPrefs.word_wrap}
        onToggleWrap={() => onEditorPref?.("word_wrap", !editorPrefs.word_wrap)}
        previewOn={previewOn}
        onTogglePreview={() => setPreviewOn((v) => !v)}
        isPreviewable={isPreviewable}
        showUpload={isArduino}
        onOpenUpload={() => setArduinoPanelOpen(true)}
      />
      {saveError && (
        <div style={styles.saveError} onClick={() => setSaveError(null)} title="Dismiss">
          ⚠ {saveError}
        </div>
      )}
      {activeFile && (
        <Breadcrumbs filePath={activeFile.path} rootDirs={rootDirs} onReveal={onRevealPath} />
      )}
      <div style={{
        ...styles.editorBox,
        display: "flex",
        flexDirection: previewOn && previewOrientation === "horizontal" ? "column" : "row",
      }}>
        {/* Editor half */}
        <div style={{ flex: 1, minWidth: 0, minHeight: 0, overflow: "hidden", position: "relative" }}>
          {askWidget && (
            <div style={{ position: "absolute", zIndex: 25, top: Math.max(2, askWidget.top - 30), left: Math.max(2, askWidget.left) }}>
              {!askMenuOpen ? (
                <button style={askStyles.btn} onClick={() => setAskMenuOpen(true)} title="Ask the AI about the selection">
                  ✦ Ask AI
                </button>
              ) : (
                <div style={askStyles.menu}>
                  {[["explain", "Explain"], ["fix", "Fix"], ["refactor", "Refactor"]].map(([a, label]) => (
                    <button key={a} style={askStyles.item} onClick={() => doAsk(a)}>{label}</button>
                  ))}
                </div>
              )}
            </div>
          )}
          {activeFile ? (
            <Editor
              height="100%"
              theme={monacoThemeFor(appTheme)}
              path={activeFile.path}
              language={langFor(activeFile.name)}
              value={activeFile.content}
              onChange={(value) => onChange(value ?? "")}
              beforeMount={setupMonaco}
              onMount={handleMount}
              options={{
                fontFamily:          `${editorPrefs.editor_font || "JetBrains Mono"}, monospace`,
                fontSize:            fontSize,
                tabSize:             editorPrefs.tab_size ?? 4,
                minimap:             { enabled: !!editorPrefs.minimap_enabled },
                wordWrap:            editorPrefs.word_wrap ? "on" : "off",
                stickyScroll:        { enabled: true },
                scrollBeyondLastLine: false,
                smoothScrolling:     true,
                cursorBlinking:      "smooth",
                padding:             { top: 12 },
                renderWhitespace:    "selection",
                matchBrackets:       "always",
                bracketPairColorization: { enabled: true },
                guides:              { bracketPairs: "active" },
              }}
            />
          ) : (
            <div style={styles.noActive} />
          )}
        </div>
        {/* Preview half (visible only when toggled on for previewable files) */}
        {previewOn && activeFile && (
          <LivePreview
            content={activeFile.content}
            fileName={activeFile.name}
            filePath={activeFile.path}
            orientation={previewOrientation}
            onOrientationChange={() => setPreviewOrientation((v) => v === "vertical" ? "horizontal" : "vertical")}
          />
        )}
      </div>
      <ProblemsPanel markers={markers} onJumpTo={jumpTo} />
      {arduinoPanelOpen && activeFile && (
        <ArduinoPanel
          filePath={activeFile.path}
          onClose={() => setArduinoPanelOpen(false)}
          onRunInTerminal={onRun}
        />
      )}
    </div>
  );
}

const askStyles = {
  btn: {
    display: "flex",
    alignItems: "center",
    gap: 4,
    padding: "3px 9px",
    fontSize: 11,
    fontFamily: "var(--font-ui)",
    fontWeight: 600,
    color: "var(--accent)",
    background: "var(--bg-2)",
    border: "1px solid var(--accent)",
    borderRadius: 6,
    cursor: "pointer",
    boxShadow: "0 2px 8px rgba(0,0,0,0.3)",
  },
  menu: {
    display: "flex",
    gap: 2,
    padding: 3,
    background: "var(--bg-2)",
    border: "1px solid var(--accent)",
    borderRadius: 6,
    boxShadow: "0 2px 8px rgba(0,0,0,0.3)",
  },
  item: {
    padding: "3px 8px",
    fontSize: 11,
    fontFamily: "var(--font-ui)",
    color: "var(--text-1)",
    background: "transparent",
    border: "none",
    borderRadius: 4,
    cursor: "pointer",
  },
};

const styles = {
  wrap:       { display: "flex", flexDirection: "column", height: "100%" },
  saveError: {
    padding: "4px 12px",
    fontSize: "11px",
    fontFamily: "var(--font-mono)",
    color: "var(--err)",
    background: "rgba(240,96,96,0.10)",
    borderBottom: "1px solid var(--border)",
    cursor: "pointer",
    flexShrink: 0,
  },
  editorBox:  { flex: 1, minHeight: 0, overflow: "hidden" },
  noActive:   { height: "100%", background: "var(--bg-0)" },

  // ── Welcome / empty state ────────────────────────────────────────────────
  empty: {
    height: "100%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "var(--bg-0)",
  },
  welcomeCard: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 0,
    padding: "40px 48px",
    background: "var(--bg-1)",
    border: "1px solid var(--border)",
    borderRadius: "var(--r-xl)",
    boxShadow: "var(--shadow-md)",
    minWidth: 300,
    animation: "va-pop 220ms var(--ease)",
  },
  welcomeLogo: { marginBottom: 16 },
  welcomeTitle: {
    fontFamily: "var(--font-mono)",
    fontSize: 22,
    fontWeight: 400,
    color: "var(--text-0)",
    letterSpacing: "0.06em",
    margin: "0 0 6px",
  },
  welcomeSub: {
    fontSize: 12,
    color: "var(--text-2)",
    fontFamily: "var(--font-ui)",
    margin: "0 0 24px",
  },
  welcomeDivider: {
    width: "100%",
    height: 1,
    background: "var(--border)",
    marginBottom: 20,
  },
  welcomeShortcuts: {
    display: "flex",
    flexDirection: "column",
    gap: 10,
    width: "100%",
  },
  shortcutRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 16,
  },
  shortcutLabel: {
    fontSize: 12,
    color: "var(--text-2)",
    fontFamily: "var(--font-ui)",
  },
};
