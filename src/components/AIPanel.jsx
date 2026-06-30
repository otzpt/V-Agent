import { useState, useRef, useCallback, useEffect, memo } from "react";
import { DiffEditor } from "@monaco-editor/react";
import { aiChat, getConfig, listDir, agentStart, agentSend, onAgentEvent, readFile, writeFile } from "../lib/tauri.js";

// ── Project-context helpers ──────────────────────────────────────────────────

const CTX_EXT_LANG = {
  js: "javascript", jsx: "javascript", ts: "typescript", tsx: "typescript",
  py: "python", rs: "rust", c: "c", h: "c", cpp: "cpp", cs: "csharp", go: "go",
  java: "java", rb: "ruby", php: "php", html: "html", css: "css", json: "json",
  md: "markdown", sh: "shell", ps1: "powershell", yaml: "yaml", yml: "yaml", toml: "toml",
};
function ctxLangFor(name) {
  if (!name) return "text";
  return CTX_EXT_LANG[name.split(".").pop().toLowerCase()] || "text";
}

// Indented 2-level tree of the workspace (listDir already skips heavy dirs).
async function buildTree(root) {
  const lines = [];
  async function walk(dir, prefix, depth) {
    if (lines.length > 200) return;
    let items;
    try { items = await listDir(dir); } catch { return; }
    for (const it of items.slice(0, 40)) {
      lines.push(`${prefix}${it.name}${it.is_dir ? "/" : ""}`);
      if (it.is_dir && depth > 1) await walk(it.path, prefix + "  ", depth - 1);
    }
  }
  await walk(root, "", 2);
  return lines.slice(0, 200).join("\n");
}

// Assemble a project-aware system prompt from the workspace + open file.
function systemPromptFrom(rootDir, treeText, openFile, planMode) {
  let p =
    "You are V-Agent, an AI assistant embedded in a local code editor. " +
    "Be concise and practical. When proposing changes, show the full updated code in a fenced block with its language.";
  if (planMode) p += "\n\nPLAN MODE: Output a short step-by-step plan only. Do NOT write code.";
  if (rootDir)  p += `\n\nWorkspace root: ${rootDir}\nProject files (2 levels):\n${treeText}`;
  if (openFile) {
    const lang = ctxLangFor(openFile.name);
    const body = (openFile.content || "").slice(0, 8000);
    p += `\n\nThe user is currently viewing "${openFile.name}" (${lang}):\n\`\`\`${lang}\n${body}\n\`\`\``;
  }
  return p;
}

// Lighter context for agent mode — the model uses tools to read the rest.
function contextPrompt(rootDir, openFile) {
  let p = "";
  if (rootDir) p += `Workspace root: ${rootDir}.`;
  if (openFile) {
    const lang = ctxLangFor(openFile.name);
    const body = (openFile.content || "").slice(0, 6000);
    p += `\nThe user is currently viewing "${openFile.name}":\n\`\`\`${lang}\n${body}\n\`\`\``;
  }
  return p;
}

const diffTheme = (appTheme) => (appTheme === "light" ? "vs" : "vs-dark");

// Append streamed text to the current assistant message (or start a new one).
function appendAssistant(messages, text) {
  const last = messages[messages.length - 1];
  if (last && last.role === "assistant" && last.streaming) {
    const copy = [...messages];
    copy[copy.length - 1] = { ...last, content: last.content + text };
    return copy;
  }
  return [...messages, { role: "assistant", content: text, streaming: true }];
}

// ── Tool activity + proposal cards ───────────────────────────────────────────

const ToolLine = memo(function ToolLine({ msg }) {
  const arg = msg.args ? (msg.args.path || msg.args.query || msg.args.command || "") : "";
  return (
    <div style={agStyles.toolLine}>
      <span style={{ ...agStyles.toolIcon, color: msg.status === "done" ? "var(--ok)" : "var(--text-2)" }}>
        {msg.status === "done" ? "✓" : "⋯"}
      </span>
      <span style={agStyles.toolName}>{msg.tool}</span>
      {arg && <span style={agStyles.toolArg}>{arg}</span>}
    </div>
  );
});

function ProposalCard({ msg, appTheme, onAccept, onReject, onRun }) {
  const done = msg.status !== "pending";
  if (msg.kind === "command") {
    return (
      <div style={agStyles.card}>
        <div style={agStyles.cardHead}>
          <span style={agStyles.badge}>run</span>
          <code style={agStyles.cmd}>{msg.command}</code>
        </div>
        <div style={agStyles.cardActions}>
          {!done ? (
            <>
              <button style={agStyles.accept} onClick={() => onRun(msg)}>▶ Run in terminal</button>
              <button style={agStyles.reject} onClick={() => onReject(msg)}>Dismiss</button>
            </>
          ) : <span style={agStyles.doneTag}>{msg.status}</span>}
        </div>
      </div>
    );
  }
  return (
    <div style={agStyles.card}>
      <div style={agStyles.cardHead}>
        <span style={agStyles.badge}>edit</span>
        <span style={agStyles.file}>{msg.path}</span>
      </div>
      <div style={agStyles.diffBox}>
        <DiffEditor
          height="100%"
          theme={diffTheme(appTheme)}
          language={ctxLangFor(msg.path)}
          original={msg.original || ""}
          modified={msg.content || ""}
          options={{ readOnly: true, renderSideBySide: false, minimap: { enabled: false }, fontSize: 11, scrollBeyondLastLine: false, automaticLayout: true, lineNumbers: "off" }}
        />
      </div>
      <div style={agStyles.cardActions}>
        {!done ? (
          <>
            <button style={agStyles.accept} onClick={() => onAccept(msg)}>✓ Accept</button>
            <button style={agStyles.reject} onClick={() => onReject(msg)}>✗ Reject</button>
          </>
        ) : <span style={agStyles.doneTag}>{msg.status}</span>}
      </div>
    </div>
  );
}

// Progress bar shown during autonomous runs
function AutonomousBar({ progress, onPause }) {
  if (!progress) return null;
  return (
    <div style={autoBarStyle.wrap}>
      <div style={autoBarStyle.track}>
        <div style={{ ...autoBarStyle.fill, width: `${Math.min(100, (progress.step || 1) * 5)}%` }} />
      </div>
      <span style={autoBarStyle.label}>
        Step {progress.step} — {progress.description}
      </span>
      <button style={autoBarStyle.pause} onClick={onPause} title="Pause autonomous run">⏸</button>
    </div>
  );
}

// Summary card shown after autonomous run completes
function AutonomousSummary({ summary, backups, onRevertAll, onDismiss }) {
  if (!summary) return null;
  return (
    <div style={autoSumStyle.card}>
      <div style={autoSumStyle.head}>
        <span style={autoSumStyle.title}>⚡ Autonomous run complete</span>
        <button style={autoSumStyle.dismiss} onClick={onDismiss}>×</button>
      </div>
      <p style={autoSumStyle.body}>{summary}</p>
      {backups.length > 0 && (
        <button style={autoSumStyle.revert} onClick={onRevertAll}>
          ↩ Revert all {backups.length} change{backups.length > 1 ? "s" : ""}
        </button>
      )}
    </div>
  );
}

const autoBarStyle = {
  wrap:  { display: "flex", alignItems: "center", gap: 8, padding: "6px 4px", flexShrink: 0 },
  track: { flex: 1, height: 3, background: "var(--bg-3)", borderRadius: 2, overflow: "hidden" },
  fill:  { height: "100%", background: "#f5a623", borderRadius: 2, transition: "width 300ms ease" },
  label: { fontSize: 11, color: "var(--text-2)", fontFamily: "var(--font-mono)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "55%" },
  pause: { fontSize: 13, background: "transparent", border: "none", color: "var(--text-2)", cursor: "pointer", padding: "2px 4px", flexShrink: 0 },
};

const autoSumStyle = {
  card:    { margin: "8px 0", border: "1px solid #f5a62355", borderRadius: 8, background: "var(--bg-2)", overflow: "hidden" },
  head:    { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 12px", borderBottom: "1px solid var(--border)" },
  title:   { fontSize: 12, fontWeight: 600, color: "#f5a623", fontFamily: "var(--font-ui)" },
  dismiss: { fontSize: 16, background: "transparent", border: "none", color: "var(--text-2)", cursor: "pointer", lineHeight: 1 },
  body:    { fontSize: 12, color: "var(--text-1)", padding: "8px 12px", margin: 0, whiteSpace: "pre-wrap", fontFamily: "var(--font-ui)" },
  revert:  { display: "block", margin: "0 12px 10px", fontSize: 12, color: "var(--err)", background: "transparent", border: "1px solid var(--err)", borderRadius: 6, padding: "4px 12px", cursor: "pointer", fontFamily: "var(--font-ui)" },
};

const agStyles = {
  toolLine: { display: "flex", alignItems: "center", gap: 6, padding: "2px 4px", fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-2)" },
  toolIcon: { width: 12, flexShrink: 0 },
  toolName: { color: "var(--accent)" },
  toolArg: { color: "var(--text-2)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  card: { border: "1px solid var(--border)", borderRadius: 8, overflow: "hidden", margin: "6px 0", background: "var(--bg-2)" },
  cardHead: { display: "flex", alignItems: "center", gap: 8, padding: "6px 10px", borderBottom: "1px solid var(--border)" },
  badge: { fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--accent)", background: "var(--accent-dim)", padding: "1px 6px", borderRadius: 4 },
  file: { fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--text-0)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  cmd: { fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--text-0)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  diffBox: { height: 220 },
  cardActions: { display: "flex", gap: 8, padding: "8px 10px", alignItems: "center" },
  accept: { fontSize: 12, fontWeight: 600, fontFamily: "var(--font-ui)", color: "var(--ok)", background: "transparent", border: "1px solid var(--ok)", borderRadius: 6, padding: "4px 12px", cursor: "pointer" },
  reject: { fontSize: 12, fontFamily: "var(--font-ui)", color: "var(--text-2)", background: "transparent", border: "1px solid var(--border)", borderRadius: 6, padding: "4px 12px", cursor: "pointer" },
  doneTag: { fontSize: 11, color: "var(--text-2)", fontFamily: "var(--font-ui)", textTransform: "capitalize" },
};

const agentToggleStyle = {
  fontSize: 11,
  fontFamily: "var(--font-ui)",
  fontWeight: 600,
  padding: "2px 8px",
  borderRadius: 5,
  border: "1px solid",
  background: "transparent",
  cursor: "pointer",
  whiteSpace: "nowrap",
};

// Strip lines where the entire line is wrapped in ** or __ (e.g. "**Title**")
// Models like Qwen use these as prose headers; they look bad without a renderer.
function stripExcessiveBold(text) {
  return text.replace(/^(\*{2}|_{2})([^*_\n]+?)(\*{2}|_{2})\s*$/gm, "$2");
}

// Minimal, dependency-free markdown renderer focused on what an AI returns:
// fenced code blocks ```lang ... ```, inline `code`, and plain paragraphs.

function renderContent(rawText) {
  const text = stripExcessiveBold(rawText);
  const parts = [];
  const fence = /```(\w+)?\n?([\s\S]*?)```/g;
  let last = 0;
  let m;
  let key = 0;

  while ((m = fence.exec(text)) !== null) {
    if (m.index > last) {
      parts.push(
        <Paragraph key={key++} text={text.slice(last, m.index)} />
      );
    }
    parts.push(
      <CodeBlock key={key++} lang={m[1] || ""} code={m[2].replace(/\n$/, "")} />
    );
    last = fence.lastIndex;
  }
  if (last < text.length) {
    parts.push(<Paragraph key={key++} text={text.slice(last)} />);
  }
  return parts;
}

const Paragraph = memo(function Paragraph({ text }) {
  const segs = text.split(/(`[^`]+`)/g);
  return (
    <p style={pStyles.paragraph}>
      {segs.map((s, i) =>
        s.startsWith("`") && s.endsWith("`") ? (
          <code key={i} style={pStyles.inlineCode}>
            {s.slice(1, -1)}
          </code>
        ) : (
          <span key={i}>{s}</span>
        )
      )}
    </p>
  );
});

const CodeBlock = memo(function CodeBlock({ lang, code }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };
  return (
    <div style={pStyles.codeBlock}>
      <div style={pStyles.codeHeader}>
        <span style={pStyles.codeLang}>{lang || "code"}</span>
        <button style={pStyles.copyBtn} onClick={copy}>
          {copied ? "copied" : "copy"}
        </button>
      </div>
      <pre style={pStyles.pre}>
        <code>{code}</code>
      </pre>
    </div>
  );
});

// Animated streaming dots — three dots that fade in sequence
function StreamingDots() {
  return (
    <span style={dotStyles.wrap} aria-label="Streaming">
      <span style={{ ...dotStyles.dot, animationDelay: "0ms" }}>•</span>
      <span style={{ ...dotStyles.dot, animationDelay: "160ms" }}>•</span>
      <span style={{ ...dotStyles.dot, animationDelay: "320ms" }}>•</span>
      <style>{`
        @keyframes vaBlink {
          0%, 80%, 100% { opacity: 0.2; }
          40% { opacity: 1; }
        }
        @media (prefers-reduced-motion: reduce) {
          .va-dot { animation: none !important; opacity: 1; }
        }
      `}</style>
    </span>
  );
}

const dotStyles = {
  wrap: { display: "inline-flex", gap: "2px", alignItems: "center", padding: "2px 4px" },
  dot: {
    display: "inline-block",
    animation: "vaBlink 1.2s infinite ease-in-out",
    color: "var(--accent)",
    fontSize: "18px",
    lineHeight: 1,
  },
};

// Avatar circle: "U" for user, "A" for assistant
function Avatar({ role }) {
  return (
    <div style={{
      ...avatarStyles.circle,
      background: role === "user" ? "var(--accent-dim)" : "var(--bg-3)",
    }}>
      {role === "user" ? "U" : "A"}
    </div>
  );
}

const avatarStyles = {
  circle: {
    width: "28px",
    height: "28px",
    minWidth: "28px",
    borderRadius: "50%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "11px",
    fontWeight: 600,
    color: "var(--text-0)",
    fontFamily: "var(--font-ui)",
  },
};

// ── Model picker dropdown (inline, above input) ──────────────────────────────

const QUICK_PROVIDERS = [
  { id: "backend",     label: "Backend",     hasModel: false },
  { id: "groq",        label: "Groq",        hasModel: true  },
  { id: "openrouter",  label: "OpenRouter",  hasModel: true  },
  { id: "ollama",      label: "Ollama",      hasModel: true  },
];

function ModelPicker({ provider, model, onApply, onClose }) {
  const [selProvider, setSelProvider] = useState(provider);
  const [selModel, setSelModel] = useState(model);
  const [ollamaModels, setOllamaModels] = useState(null);
  const ref = useRef(null);

  useEffect(() => {
    if (selProvider === "ollama" && ollamaModels === null) {
      fetch("http://localhost:11434/api/tags")
        .then((r) => r.json())
        .then((d) => setOllamaModels((d.models || []).map((m) => m.name)))
        .catch(() => setOllamaModels([]));
    }
  }, [selProvider]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose(); };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [onClose]);

  const current = QUICK_PROVIDERS.find((p) => p.id === selProvider);

  return (
    <div ref={ref} style={mpStyles.wrap}>
      <div style={mpStyles.row}>
        {QUICK_PROVIDERS.map((p) => (
          <button
            key={p.id}
            style={{
              ...mpStyles.provBtn,
              background: selProvider === p.id ? "var(--accent-dim)" : "var(--bg-3)",
              color: selProvider === p.id ? "var(--text-0)" : "var(--text-1)",
            }}
            onClick={() => { setSelProvider(p.id); setSelModel(""); }}
          >
            {p.label}
          </button>
        ))}
      </div>

      {current?.hasModel && (
        selProvider === "ollama" ? (
          <select
            style={mpStyles.select}
            value={selModel}
            onChange={(e) => setSelModel(e.target.value)}
          >
            <option value="">-- select model --</option>
            {(ollamaModels || []).map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
            {ollamaModels === null && <option disabled>Loading…</option>}
            {ollamaModels?.length === 0 && <option disabled>No models / Ollama offline</option>}
          </select>
        ) : (
          <input
            style={mpStyles.input}
            placeholder={selProvider === "groq" ? "e.g. llama3-8b-8192" : "e.g. mistralai/mistral-7b"}
            value={selModel}
            onChange={(e) => setSelModel(e.target.value)}
          />
        )
      )}

      <button
        style={mpStyles.applyBtn}
        onClick={() => onApply(selProvider, selModel)}
      >
        Apply
      </button>
    </div>
  );
}

const mpStyles = {
  wrap: {
    background: "var(--bg-2)",
    border: "1px solid var(--border)",
    borderRadius: "10px",
    padding: "12px",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  row: { display: "flex", gap: "6px", flexWrap: "wrap" },
  provBtn: {
    padding: "4px 10px",
    borderRadius: "6px",
    border: "1px solid var(--border)",
    fontSize: "12px",
    fontFamily: "var(--font-ui)",
    cursor: "pointer",
  },
  select: {
    background: "var(--bg-3)",
    border: "1px solid var(--border)",
    borderRadius: "6px",
    padding: "6px 8px",
    fontSize: "12px",
    color: "var(--text-0)",
    fontFamily: "var(--font-mono)",
  },
  input: {
    background: "var(--bg-3)",
    border: "1px solid var(--border)",
    borderRadius: "6px",
    padding: "6px 8px",
    fontSize: "12px",
    color: "var(--text-0)",
    fontFamily: "var(--font-mono)",
    width: "100%",
    boxSizing: "border-box",
  },
  applyBtn: {
    alignSelf: "flex-end",
    background: "var(--accent)",
    color: "#fff",
    padding: "5px 14px",
    borderRadius: "6px",
    fontSize: "12px",
    fontFamily: "var(--font-ui)",
    cursor: "pointer",
  },
};

// ── Panel ─────────────────────────────────────────────────────────────────────

export default function AIPanel({ openFile, mode = "ide", providerCmd, rootDirs = [], askCmd, onRunCommand, reloadFile, appTheme = "dark" }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [sessionProvider, setSessionProvider] = useState("backend");
  const [sessionModel, setSessionModel] = useState("");
  const [showModelPicker, setShowModelPicker] = useState(false);
  const [inputFocused, setInputFocused] = useState(false);
  const [planMode, setPlanMode] = useState(false);
  const [agentMode, setAgentMode] = useState(true);
  const [terminalMode, setTerminalMode] = useState(false);
  const [termLines, setTermLines] = useState([]);   // PTY output lines in /terminal mode
  const [autonomousMode, setAutonomousMode] = useState(false);
  const [autoProgress, setAutoProgress] = useState(null);  // {step, description} | null
  const [autoSummary, setAutoSummary] = useState(null);    // summary text after auto run
  const [autoBackups, setAutoBackups] = useState([]);      // [{path, content}] for revert-all
  const scrollRef          = useRef(null);
  const pinnedRef          = useRef(true);
  const currentReqRef      = useRef(null);
  const lastContextFileRef = useRef(null);
  const lastWriteBackupRef = useRef(null);          // {path, content} for /undo
  const isChat = mode === "chat";

  // Derive a session_id from the active project root (stable across renders)
  const sessionId = rootDirs[0]
    ? rootDirs[0].replace(/[^a-zA-Z0-9_.-]/g, "_").slice(-60)
    : "default";

  // ── Agent channel: start the persistent sidecar + route its events ──────────
  useEffect(() => {
    let alive = true;
    let unlisten = null;
    agentStart().catch(() => {});

    const handle = (ev) => {
      const reqId = currentReqRef.current;
      if (ev.id && reqId && ev.id !== reqId) return;  // ignore stale requests
      switch (ev.type) {
        case "token":
          setMessages((m) => appendAssistant(m, ev.text));
          break;
        case "tool_call":
          setMessages((m) => [...m, { role: "tool", call_id: ev.call_id, tool: ev.tool, args: ev.args, status: "running" }]);
          break;
        case "tool_result":
          setMessages((m) => m.map((x) => (x.role === "tool" && x.call_id === ev.call_id ? { ...x, result: ev.result, status: "done" } : x)));
          break;
        case "propose_write":
          setMessages((m) => [...m, { role: "proposal", kind: "write", call_id: ev.call_id, path: ev.path, content: ev.content, original: ev.original || "", status: "pending" }]);
          break;
        case "propose_command":
          setMessages((m) => [...m, { role: "proposal", kind: "command", call_id: ev.call_id, command: ev.command, status: "pending" }]);
          break;
        case "info":
          setMessages((m) => [...m, { role: "info", content: ev.text }]);
          break;
        case "memory_data": {
          const mem = ev.data || {};
          const facts = (mem.learned_facts || []).join("\n• ") || "(none)";
          const projs = (mem.known_projects || []).map((p) => p.name).join(", ") || "(none)";
          const prefs = mem.user_preferences || {};
          setMessages((m) => [...m, {
            role: "info",
            content: `[V-Agent Memory]\nLanguage: ${prefs.language || "?"} | Remember me: ${mem.remember_me ? "yes" : "no"}\nProjects: ${projs}\nLearned facts:\n• ${facts}`,
          }]);
          break;
        }
        case "progress":
          setAutoProgress({ step: ev.step, description: ev.description });
          break;
        case "propose_plan":
          setMessages((m) => [...m, {
            role: "proposal", kind: "plan", call_id: ev.call_id,
            content: ev.content, status: "pending",
          }]);
          break;
        case "auto_write":
          setAutoBackups((prev) => [...prev, { path: ev.path, content: ev.original || "" }]);
          setMessages((m) => [...m, {
            role: "info",
            content: `✓ Auto-applied: ${ev.path}`,
          }]);
          break;
        case "autonomous_done":
          setAutoProgress(null);
          setAutoSummary(ev.summary || "Task complete.");
          break;
        case "provider_switch":
          setMessages((m) => [...m, { role: "info", content: `⇄ Provider auto-switched: ${ev.from} → ${ev.to}` }]);
          if (ev.to) setSessionProvider(ev.to);
          break;
        case "error":
          setMessages((m) => appendAssistant(m, `\n⚠ ${ev.error}`));
          break;
        case "done":
          setMessages((m) => m.map((x, i) => (i === m.length - 1 && x.role === "assistant" ? { ...x, streaming: false } : x)));
          setStreaming(false);
          setAutoProgress(null);
          currentReqRef.current = null;
          break;
        case "exit":
          setStreaming(false);
          // Only surface a notice if the process died mid-request; otherwise
          // the user would never know why streaming stopped.
          if (currentReqRef.current) {
            currentReqRef.current = null;
            setMessages((m) => {
              const next = appendAssistant(m, "\n⚠ The agent process stopped unexpectedly. It will restart on your next message.");
              return next.map((x, i) => (i === next.length - 1 && x.role === "assistant" ? { ...x, streaming: false } : x));
            });
          }
          break;
        default:
          break;
      }
    };

    onAgentEvent(handle).then((fn) => { if (alive) unlisten = fn; else fn(); }).catch(() => {});
    return () => { alive = false; if (unlisten) unlisten(); };
  }, []);

  // Initialise the session provider from saved config (onboarding / settings)
  useEffect(() => {
    let alive = true;
    getConfig().then((cfg) => {
      if (alive && cfg?.ai_provider) setSessionProvider(cfg.ai_provider);
    }).catch(() => {});
    return () => { alive = false; };
  }, []);

  // /terminal mode: subscribe to PTY output and show it in this panel
  useEffect(() => {
    if (!terminalMode) return;
    const onOutput = (e) => {
      const raw = e.detail?.data || "";
      // Strip ANSI codes for display in the chat panel
      const text = raw.replace(/\x1b\[[0-9;]*[A-Za-z]/g, "");
      if (text) setTermLines((prev) => [...prev.slice(-300), text]);
    };
    window.addEventListener("vagent-terminal-output", onOutput);
    return () => window.removeEventListener("vagent-terminal-output", onOutput);
  }, [terminalMode]);

  // Track whether the user has scrolled up (unpin) or is near the bottom (pin)
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => {
      pinnedRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  // Auto-scroll only when pinned to bottom
  useEffect(() => {
    const el = scrollRef.current;
    if (el && pinnedRef.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setInput("");
    setTermLines([]);
    setTerminalMode(false);
    setAutoProgress(null);
    setAutoSummary(null);
    setAutoBackups([]);
    lastWriteBackupRef.current = null;
  }, []);

  // Push a system info message (not sent to AI)
  const pushInfo = useCallback((content) => {
    setMessages((prev) => [...prev, { role: "info", content }]);
  }, []);

  const handleSlashCommand = useCallback((text) => {
    const [cmd] = text.slice(1).trim().split(/\s+/);
    switch ((cmd || "").toLowerCase()) {
      case "clear":
        setMessages([]);
        setInput("");
        lastContextFileRef.current = null;
        agentSend({ type: "clear_session" }).catch(() => {});
        return true;
      case "model":
        setShowModelPicker(true);
        setInput("");
        return true;
      case "plan": {
        const next = !planMode;
        setPlanMode(next);
        pushInfo(`Plan mode ${next ? "ON — I'll outline a plan before writing code" : "OFF"}`);
        setInput("");
        return true;
      }
      case "context": {
        const root = rootDirs[0] || "(none)";
        pushInfo(
          "Context the AI receives:\n" +
          `• provider: ${sessionProvider}${sessionModel ? ` / ${sessionModel}` : ""}\n` +
          `• workspace: ${root}\n` +
          `• open file: ${openFile?.name || "(none)"}\n` +
          `• plan mode: ${planMode ? "on" : "off"}`
        );
        setInput("");
        return true;
      }
      case "files": {
        pushInfo(
          openFile?.name
            ? `Files in context:\n• ${openFile.name}\n(plus the project file tree, 2 levels)`
            : "No file open. The project file tree is still included."
        );
        setInput("");
        return true;
      }
      case "compact": {
        agentSend({ type: "compact_session", session_id: sessionId }).catch(() => {});
        setMessages((prev) => {
          const conv = prev.filter((m) => m.role !== "info");
          const keep = conv.slice(-3);
          const dropped = conv.length - keep.length;
          return [{ role: "info", content: `Compacted ${dropped} earlier message(s).` }, ...keep];
        });
        setInput("");
        return true;
      }
      case "undo": {
        const bk = lastWriteBackupRef.current;
        if (!bk) {
          pushInfo("Nothing to undo — no file was written this session.");
        } else {
          writeFile(bk.path, bk.content)
            .then(() => {
              reloadFile?.(bk.path);
              pushInfo(`↩ Reverted ${bk.path}`);
              lastWriteBackupRef.current = null;
            })
            .catch((e) => pushInfo(`✗ Undo failed: ${e}`));
        }
        setInput("");
        return true;
      }
      case "terminal": {
        const arg = text.slice(1).trim().split(/\s+/)[1]?.toLowerCase();
        if (arg === "off" || (terminalMode && !arg)) {
          setTerminalMode(false);
          setTermLines([]);
          pushInfo("Terminal mode OFF.");
        } else {
          setTerminalMode(true);
          setTermLines([]);
          pushInfo("Terminal mode ON — PTY output appears here. Type commands or ask the AI to run them.");
        }
        setInput("");
        return true;
      }
      case "memory":
        agentSend({ type: "get_memory" }).catch(() => {});
        pushInfo("Fetching memory…");
        setInput("");
        return true;
      case "forget":
        agentSend({ type: "clear_memory" }).catch(() => {});
        pushInfo("Memory cleared.");
        setInput("");
        return true;
      case "help":
        pushInfo(
          "/model — switch AI provider/model\n" +
          "/context — what the AI currently sees\n" +
          "/files — files included in context\n" +
          "/plan — toggle plan-only mode\n" +
          "/compact — shrink the conversation history\n" +
          "/undo — revert last accepted file write\n" +
          "/terminal — toggle terminal-observer mode\n" +
          "/memory — show what V-Agent remembers about you\n" +
          "/forget — clear V-Agent's memory\n" +
          "/clear — clear conversation\n" +
          "/help — show this message"
        );
        setInput("");
        return true;
      default:
        return false;
    }
  }, [pushInfo, planMode, rootDirs, sessionProvider, sessionModel, openFile, terminalMode, sessionId, reloadFile]);

  const sendText = useCallback(async (raw) => {
    const text = (raw ?? "").trim();
    if (!text || streaming) return;
    if (text.startsWith("/")) { handleSlashCommand(text); return; }

    // Clean history for the model: only user/assistant text turns.
    const history = messages
      .filter((m) => m.role === "user" || m.role === "assistant")
      .map((m) => ({ role: m.role, content: m.content }));
    history.push({ role: "user", content: text });

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setStreaming(true);
    pinnedRef.current = true;

    // In /terminal mode: route input as a PTY command, not to the AI
    if (terminalMode) {
      window.dispatchEvent(new CustomEvent("vagent-run-in-terminal", { detail: { command: text } }));
      setMessages((prev) => [...prev, { role: "user", content: `$ ${text}` }]);
      setInput("");
      setStreaming(false);
      return;
    }

    const reqId = `r${Date.now()}`;
    currentReqRef.current = reqId;
    const config = { ai_provider: sessionProvider, ...(sessionModel ? { model: sessionModel } : {}) };
    const histLen = messages.filter((m) => m.role === "user" || m.role === "assistant").length;
    const fileChanged = openFile?.path !== lastContextFileRef.current;
    const includeFile = histLen === 0 || fileChanged;
    if (includeFile) lastContextFileRef.current = openFile?.path ?? null;
    const sys = contextPrompt(rootDirs[0] || null, includeFile ? openFile : null);

    try {
      await agentStart();
      if (autonomousMode) { setAutoProgress({ step: 0, description: "Starting…" }); setAutoSummary(null); setAutoBackups([]); }
      await agentSend({
        type: "chat", id: reqId, session_id: sessionId,
        messages: history, config,
        cwd: rootDirs[0] || null, system_prompt: sys,
        agent: agentMode, plan: planMode, autonomous: autonomousMode,
      });
    } catch (e) {
      currentReqRef.current = null;
      setStreaming(false);
      setMessages((m) => [...m, { role: "assistant", content: "⚠ Agent unavailable. Build the sidecar (sidecar/build.sh) and restart.", streaming: false }]);
    }
  }, [messages, streaming, sessionProvider, sessionModel, handleSlashCommand, rootDirs, openFile, agentMode, planMode]);

  // No-arg send used by the input box / Enter key.
  const send = useCallback(() => sendText(input), [sendText, input]);

  const stop = useCallback(() => {
    const reqId = currentReqRef.current;
    if (reqId) agentSend({ type: "cancel", id: reqId }).catch(() => {});
    setStreaming(false);
  }, []);

  // ── Proposal actions (diff accept/reject, command run) ──────────────────────
  const acceptWrite = useCallback(async (msg) => {
    const root = rootDirs[0];
    const sep = root && root.includes("\\") ? "\\" : "/";
    const isAbs = /^([A-Za-z]:[/\\]|\/)/.test(msg.path);
    const abs = isAbs ? msg.path.replace(/[\\/]/g, sep) : (root ? root + sep + msg.path.replace(/[\\/]/g, sep) : msg.path);
    try {
      const originalContent = await readFile(abs).catch(() => "");
      lastWriteBackupRef.current = { path: abs, content: originalContent };
      await writeFile(abs, msg.content);
      reloadFile?.(abs);
      setMessages((m) => m.map((x) => (x === msg ? { ...x, status: "accepted" } : x)));
      window.notify?.(`Applied ${msg.path}`, "success");
      const lastSep = Math.max(abs.lastIndexOf("/"), abs.lastIndexOf("\\"));
      const dir = lastSep > 0 ? abs.substring(0, lastSep) : abs;
      window.dispatchEvent(new CustomEvent("vagent-fs-changed", { detail: { path: dir } }));
    } catch (e) {
      window.notify?.(String(e), "error");
    }
  }, [rootDirs, reloadFile]);

  const rejectProposal = useCallback((msg) => {
    setMessages((m) => m.map((x) => (x === msg ? { ...x, status: "rejected" } : x)));
  }, []);

  const revertAll = useCallback(async () => {
    for (const bk of autoBackups) {
      try { await writeFile(bk.path, bk.content); reloadFile?.(bk.path); } catch { /* skip */ }
    }
    pushInfo(`↩ Reverted ${autoBackups.length} file(s).`);
    setAutoBackups([]);
    setAutoSummary(null);
  }, [autoBackups, reloadFile, pushInfo]);

  const runProposal = useCallback((msg) => {
    onRunCommand?.(msg.command);
    setMessages((m) => m.map((x) => (x === msg ? { ...x, status: "ran" } : x)));
  }, [onRunCommand]);

  // Auto-resize textarea: grows with content, capped at 5 lines (~120px)
  const autoResize = useCallback((el) => {
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 120) + "px";
  }, []);

  const applyModel = useCallback((prov, mdl) => {
    setSessionProvider(prov);
    setSessionModel(mdl);
    setShowModelPicker(false);
    const label = mdl ? `${prov} / ${mdl}` : prov;
    pushInfo(`Switched to ${label}`);
  }, [pushInfo]);

  // External provider switch (Command Palette "Switch Provider"). providerCmd.n
  // changes each invocation so re-selecting the same provider still fires.
  useEffect(() => {
    if (!providerCmd?.provider) return;
    setSessionProvider(providerCmd.provider);
    setSessionModel("");
    pushInfo(`Switched to ${providerCmd.provider}`);
  }, [providerCmd?.n]);  // eslint-disable-line react-hooks/exhaustive-deps

  // "Ask AI" from an editor selection — compose a message and send it.
  useEffect(() => {
    if (!askCmd?.code) return;
    const intro = {
      explain:  "Explain this code",
      fix:      "Find and fix any issues in this code",
      refactor: "Refactor this code for clarity",
    }[askCmd.action] || "Help me with this code";
    const where = askCmd.file ? ` (from ${askCmd.file})` : "";
    sendText(`${intro}${where}:\n\`\`\`\n${askCmd.code}\n\`\`\``);
  }, [askCmd?.n]);  // eslint-disable-line react-hooks/exhaustive-deps

  const onKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  // ── IDE mode (side panel, compact) ──────────────────────────────────────────
  if (!isChat) {
    return (
      <div style={ideStyles.wrap}>
        <div style={ideStyles.header}>
          <span style={ideStyles.label}>Assistant</span>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <button
              onClick={() => setAgentMode((v) => !v)}
              title={agentMode ? "Agent tools ON — can read files and propose edits" : "Agent tools OFF — plain chat"}
              style={{ ...agentToggleStyle, color: agentMode ? "var(--accent)" : "var(--text-2)", borderColor: agentMode ? "var(--accent)" : "var(--border)" }}
            >⚒ Agent</button>
            <button
              onClick={() => setAutonomousMode((v) => !v)}
              title={autonomousMode ? "Autonomous mode ON — V-Agent runs without pausing for approval" : "Autonomous mode OFF"}
              style={{ ...agentToggleStyle, color: autonomousMode ? "#f5a623" : "var(--text-2)", borderColor: autonomousMode ? "#f5a623" : "var(--border)" }}
            >⚡ Auto</button>
            <span style={ideStyles.provBadge}>{sessionProvider}{sessionModel ? ` · ${sessionModel}` : ""}{planMode ? " · plan" : ""}</span>
            {openFile && <span style={ideStyles.context}>{openFile.name}</span>}
          </div>
        </div>

        <div ref={scrollRef} style={ideStyles.messages}>
          {messages.length === 0 && (
            <div style={ideStyles.empty}>Ask about your code, or request a change.<br /><span style={{opacity:0.6}}>Type /help for commands.</span></div>
          )}
          {messages.map((msg, i) => {
            if (msg.role === "info") return <div key={i} style={ideStyles.infoMsg}>{msg.content}</div>;
            if (msg.role === "tool") return <ToolLine key={i} msg={msg} />;
            if (msg.role === "proposal") return (
              <ProposalCard key={i} msg={msg} appTheme={appTheme} onAccept={acceptWrite} onReject={rejectProposal} onRun={runProposal} />
            );
            return (
              <div key={i} style={msg.role === "user" ? ideStyles.userMsg : ideStyles.aiMsg}>
                {msg.role === "user" ? (
                  <p style={ideStyles.userText}>{msg.content}</p>
                ) : (
                  <div style={ideStyles.aiText}>{renderContent(msg.content || "…")}</div>
                )}
              </div>
            );
          })}
          {streaming && messages[messages.length - 1]?.role !== "assistant" && (
            <div style={ideStyles.aiMsg}><div style={ideStyles.aiText}><StreamingDots /></div></div>
          )}
          {terminalMode && termLines.length > 0 && (
            <div style={termDisplayStyle}>
              {termLines.map((ln, i) => <div key={i} style={termLineStyle}>{ln}</div>)}
            </div>
          )}
        </div>

        {autoProgress && streaming && (
          <div style={{ padding: "0 12px" }}>
            <AutonomousBar progress={autoProgress} onPause={stop} />
          </div>
        )}
        {autoSummary && !streaming && (
          <div style={{ padding: "0 8px" }}>
            <AutonomousSummary
              summary={autoSummary} backups={autoBackups}
              onRevertAll={revertAll} onDismiss={() => setAutoSummary(null)}
            />
          </div>
        )}

        {showModelPicker && (
          <div style={{ padding: "8px" }}>
            <ModelPicker
              provider={sessionProvider}
              model={sessionModel}
              onApply={applyModel}
              onClose={() => setShowModelPicker(false)}
            />
          </div>
        )}

        <div style={ideStyles.inputBar}>
          <textarea
            style={{
              ...ideStyles.textarea,
              borderColor: inputFocused ? "var(--accent)" : "var(--border)",
              height: "auto",
              minHeight: "40px",
              maxHeight: "120px",
              overflowY: "auto",
            }}
            placeholder={terminalMode ? "$ terminal mode — /terminal to exit" : "Ask anything · /model /clear /help"}
            value={input}
            onChange={(e) => { setInput(e.target.value); autoResize(e.target); }}
            onKeyDown={onKeyDown}
            onFocus={() => setInputFocused(true)}
            onBlur={() => setInputFocused(false)}
            disabled={streaming}
          />
          <button
            style={{ ...ideStyles.sendBtn, background: streaming ? "var(--err)" : "var(--accent-dim)" }}
            onClick={streaming ? stop : send}
          >
            {streaming ? "Stop" : "Send"}
          </button>
        </div>
      </div>
    );
  }

  // ── Chat mode (centered, Claude/Cursor style) ────────────────────────────────
  return (
    <div style={chatStyles.wrap}>
      <div style={chatStyles.header}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={chatStyles.label}>Assistant</span>
          <span style={chatStyles.provBadge}>{sessionProvider}{sessionModel ? ` · ${sessionModel}` : ""}{planMode ? " · plan" : ""}</span>
          <button
            onClick={() => setAgentMode((v) => !v)}
            title={agentMode ? "Agent tools ON" : "Agent tools OFF"}
            style={{ ...agentToggleStyle, color: agentMode ? "var(--accent)" : "var(--text-2)", borderColor: agentMode ? "var(--accent)" : "var(--border)" }}
          >⚒ Agent</button>
          <button
            onClick={() => setAutonomousMode((v) => !v)}
            title={autonomousMode ? "Autonomous ON — runs without pausing" : "Autonomous OFF"}
            style={{ ...agentToggleStyle, color: autonomousMode ? "#f5a623" : "var(--text-2)", borderColor: autonomousMode ? "#f5a623" : "var(--border)" }}
          >⚡ Auto</button>
        </div>
        <button style={chatStyles.clearBtn} onClick={clearMessages} title="Clear conversation">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6l-1 14H6L5 6" />
            <path d="M10 11v6M14 11v6" />
            <path d="M9 6V4h6v2" />
          </svg>
          Clear
        </button>
      </div>

      <div ref={scrollRef} style={chatStyles.messages}>
        <div style={chatStyles.inner}>
          {messages.length === 0 && (
            <div style={chatStyles.empty}>
              <div style={chatStyles.emptyIcon}>
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none"
                  stroke="var(--accent)" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
                </svg>
              </div>
              <p style={chatStyles.emptyText}>How can I help you today?</p>
              <p style={{ ...chatStyles.emptyText, fontSize: "12px", opacity: 0.6 }}>Type /help for commands</p>
            </div>
          )}
          {messages.map((msg, i) => {
            if (msg.role === "info") return <div key={i} style={chatStyles.infoMsg}>{msg.content}</div>;
            if (msg.role === "tool") return <div key={i} style={chatStyles.extraRow}><ToolLine msg={msg} /></div>;
            if (msg.role === "proposal") return (
              <div key={i} style={chatStyles.extraRow}>
                <ProposalCard msg={msg} appTheme={appTheme} onAccept={acceptWrite} onReject={rejectProposal} onRun={runProposal} />
              </div>
            );
            const isUser = msg.role === "user";
            return (
              <div key={i} style={isUser ? chatStyles.userRow : chatStyles.aiRow}>
                <Avatar role={msg.role} />
                <div style={isUser ? chatStyles.userBubble : chatStyles.aiBubble}>
                  {isUser ? (
                    <p style={chatStyles.userText}>{msg.content}</p>
                  ) : (
                    <div style={chatStyles.aiText}>{renderContent(msg.content || "…")}</div>
                  )}
                </div>
              </div>
            );
          })}
          {streaming && messages[messages.length - 1]?.role !== "assistant" && (
            <div style={chatStyles.aiRow}><Avatar role="assistant" /><div style={chatStyles.aiBubble}><StreamingDots /></div></div>
          )}
          {terminalMode && termLines.length > 0 && (
            <div style={termDisplayStyle}>
              {termLines.map((ln, i) => <div key={i} style={termLineStyle}>{ln}</div>)}
            </div>
          )}
        </div>
      </div>

      {autoProgress && streaming && (
        <div style={{ padding: "0 20px" }}>
          <AutonomousBar progress={autoProgress} onPause={stop} />
        </div>
      )}
      {autoSummary && !streaming && (
        <div style={{ padding: "0 20px 12px" }}>
          <AutonomousSummary
            summary={autoSummary} backups={autoBackups}
            onRevertAll={revertAll} onDismiss={() => setAutoSummary(null)}
          />
        </div>
      )}

      <div style={chatStyles.inputOuter}>
        <div style={chatStyles.inputInner}>
          {showModelPicker && (
            <div style={{ padding: "12px 12px 0" }}>
              <ModelPicker
                provider={sessionProvider}
                model={sessionModel}
                onApply={applyModel}
                onClose={() => setShowModelPicker(false)}
              />
            </div>
          )}
          {openFile && (
            <div style={chatStyles.fileCtx}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              {openFile.name}
            </div>
          )}
          <div style={{
            ...chatStyles.textareaRow,
            borderTop: inputFocused ? "1px solid var(--accent)" : "1px solid transparent",
            transition: "border-color 120ms ease",
          }}>
            <textarea
              style={{
                ...chatStyles.textarea,
                height: "auto",
                minHeight: "52px",
                maxHeight: "120px",
                overflowY: "auto",
              }}
              placeholder={terminalMode ? "$ terminal mode — /terminal to exit" : "Ask anything… · /model /clear /help"}
              value={input}
              onChange={(e) => { setInput(e.target.value); autoResize(e.target); }}
              onKeyDown={onKeyDown}
              onFocus={() => setInputFocused(true)}
              onBlur={() => setInputFocused(false)}
              disabled={streaming}
            />
            <button
              style={{ ...chatStyles.sendBtn, background: streaming ? "var(--err)" : "var(--accent)" }}
              onClick={streaming ? stop : send}
              title={streaming ? "Stop" : "Send"}
            >
              {streaming ? (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                  <rect x="6" y="6" width="12" height="12" rx="2" />
                </svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                  stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              )}
            </button>
          </div>
          <p style={chatStyles.hint}>Enter to send · Shift+Enter for newline</p>
        </div>
      </div>
    </div>
  );
}

// ── Shared paragraph/code styles ─────────────────────────────────────────────
const pStyles = {
  paragraph: { margin: "0 0 8px", whiteSpace: "pre-wrap" },
  inlineCode: {
    fontFamily: "var(--font-mono)",
    background: "var(--bg-2)",
    padding: "1.5px 6px",
    borderRadius: "var(--r-xs)",
    fontSize: "12px",
    color: "var(--accent)",
    border: "1px solid var(--border)",
  },
  codeBlock: {
    background: "var(--bg-2)",
    border: "1px solid var(--border)",
    borderLeft: "3px solid var(--accent)",
    borderRadius: "0 var(--r-sm) var(--r-sm) 0",
    overflow: "hidden",
    margin: "10px 0",
  },
  codeHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "5px 12px",
    borderBottom: "1px solid var(--border)",
    background: "var(--bg-1)",
  },
  codeLang: { fontSize: "10.5px", color: "var(--text-2)", fontFamily: "var(--font-mono)", textTransform: "lowercase", letterSpacing: "0.04em" },
  copyBtn: { fontSize: "11px", color: "var(--text-1)", padding: "2px 8px", borderRadius: "var(--r-xs)" },
  pre: {
    margin: 0,
    padding: "12px",
    overflow: "auto",
    fontFamily: "var(--font-mono)",
    fontSize: "12px",
    color: "var(--text-0)",
    lineHeight: 1.6,
  },
};

const termDisplayStyle = {
  margin: "8px 0",
  background: "#0a0a16",
  border: "1px solid var(--border)",
  borderRadius: "var(--r-sm)",
  padding: "8px 10px",
  fontFamily: "var(--font-mono)",
  fontSize: "11px",
  color: "#a0f0a0",
  maxHeight: "240px",
  overflowY: "auto",
  whiteSpace: "pre",
};
const termLineStyle = { lineHeight: 1.45 };

// ── IDE mode styles ──────────────────────────────────────────────────────────
const ideStyles = {
  wrap: { display: "flex", flexDirection: "column", height: "100%" },
  header: {
    padding: "10px 14px",
    borderBottom: "1px solid var(--border)",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  },
  label: {
    fontSize: "11px",
    letterSpacing: "0.06em",
    textTransform: "uppercase",
    color: "var(--text-2)",
  },
  context: {
    fontSize: "11px",
    color: "var(--text-2)",
    fontFamily: "var(--font-mono)",
  },
  messages: { flex: 1, overflow: "auto", padding: "12px" },
  empty: { fontSize: "12px", color: "var(--text-2)", padding: "8px 4px" },
  infoMsg: {
    fontSize: "11px",
    color: "var(--accent)",
    background: "var(--bg-2)",
    padding: "7px 11px",
    borderRadius: "var(--r-sm)",
    border: "1px solid var(--border)",
    marginBottom: "8px",
    whiteSpace: "pre-wrap",
    fontFamily: "var(--font-mono)",
  },
  provBadge: {
    fontSize: "10px",
    color: "var(--text-2)",
    fontFamily: "var(--font-mono)",
    background: "var(--bg-2)",
    padding: "2px 7px",
    borderRadius: "var(--r-xs)",
    border: "1px solid var(--border)",
  },
  userMsg: {
    background: "var(--bg-2)",
    borderLeft: "2px solid var(--accent)",
    borderRadius: "0 var(--r-md) var(--r-md) 0",
    padding: "9px 12px",
    marginBottom: "10px",
  },
  aiMsg: { padding: "2px 2px 10px" },
  userText: { fontSize: "13px", color: "var(--text-0)", whiteSpace: "pre-wrap" },
  aiText: { fontSize: "13px", color: "var(--text-1)", lineHeight: 1.6 },
  inputBar: {
    borderTop: "1px solid var(--border)",
    padding: "10px",
    display: "flex",
    gap: "8px",
    alignItems: "flex-end",
  },
  textarea: {
    flex: 1,
    background: "var(--bg-2)",
    borderRadius: "var(--r-md)",
    padding: "9px 12px",
    fontSize: "13px",
    resize: "none",
    border: "1px solid var(--border)",
    lineHeight: 1.5,
  },
  sendBtn: {
    color: "#fff",
    padding: "9px 16px",
    borderRadius: "var(--r-md)",
    fontSize: "13px",
    fontWeight: 600,
  },
};

// ── Chat mode styles ─────────────────────────────────────────────────────────
const chatStyles = {
  wrap: { display: "flex", flexDirection: "column", height: "100%", background: "var(--bg-0)" },
  header: {
    padding: "12px 20px",
    borderBottom: "1px solid var(--border)",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    flexShrink: 0,
  },
  label: {
    fontSize: "13px",
    fontWeight: 600,
    color: "var(--text-0)",
    fontFamily: "var(--font-ui)",
  },
  clearBtn: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    fontSize: "12px",
    color: "var(--text-2)",
    padding: "4px 10px",
    borderRadius: "6px",
    border: "1px solid var(--border)",
    background: "transparent",
    cursor: "pointer",
  },
  messages: { flex: 1, overflow: "auto", padding: "24px 20px" },
  inner: {
    maxWidth: "720px",
    margin: "0 auto",
    display: "flex",
    flexDirection: "column",
    gap: "20px",
  },
  empty: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "12px",
    padding: "64px 0",
  },
  emptyIcon: { opacity: 0.6 },
  emptyText: {
    fontSize: "15px",
    color: "var(--text-2)",
    fontFamily: "var(--font-ui)",
  },
  infoMsg: {
    fontSize: "12px",
    color: "var(--accent)",
    background: "var(--bg-2)",
    padding: "8px 14px",
    borderRadius: "8px",
    whiteSpace: "pre-wrap",
    fontFamily: "var(--font-mono)",
    maxWidth: "720px",
    margin: "0 auto",
    width: "100%",
    boxSizing: "border-box",
  },
  provBadge: {
    fontSize: "11px",
    color: "var(--text-2)",
    fontFamily: "var(--font-mono)",
    background: "var(--bg-2)",
    padding: "2px 8px",
    borderRadius: "4px",
  },
  extraRow: { maxWidth: "720px", margin: "0 auto", width: "100%" },
  userRow: {
    display: "flex",
    gap: "12px",
    alignItems: "flex-start",
    flexDirection: "row-reverse",
  },
  aiRow: {
    display: "flex",
    gap: "12px",
    alignItems: "flex-start",
  },
  userBubble: {
    background: "var(--bg-2)",
    border: "1px solid var(--border)",
    borderRadius: "14px 14px 4px 14px",
    padding: "12px 16px",
    maxWidth: "80%",
  },
  aiBubble: {
    flex: 1,
    minWidth: 0,
    paddingTop: "4px",
  },
  userText: {
    fontSize: "14px",
    color: "var(--text-0)",
    whiteSpace: "pre-wrap",
    lineHeight: 1.6,
    margin: 0,
  },
  aiText: {
    fontSize: "14px",
    color: "var(--text-1)",
    lineHeight: 1.7,
  },
  inputOuter: {
    borderTop: "1px solid var(--border)",
    padding: "20px",
    flexShrink: 0,
  },
  inputInner: {
    maxWidth: "720px",
    margin: "0 auto",
    background: "var(--bg-1)",
    border: "1px solid var(--border)",
    borderRadius: "var(--r-lg)",
    overflow: "hidden",
    boxShadow: "var(--shadow-md)",
  },
  fileCtx: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    padding: "8px 14px",
    borderBottom: "1px solid var(--border)",
    fontSize: "11px",
    color: "var(--text-2)",
    fontFamily: "var(--font-mono)",
  },
  textareaRow: {
    display: "flex",
    alignItems: "flex-end",
    gap: "8px",
    padding: "8px 8px 8px 14px",
  },
  textarea: {
    flex: 1,
    background: "transparent",
    border: "none",
    outline: "none",
    fontSize: "14px",
    resize: "none",
    color: "var(--text-0)",
    fontFamily: "var(--font-ui)",
    lineHeight: 1.6,
    padding: "4px 0",
  },
  sendBtn: {
    width: "36px",
    height: "36px",
    minWidth: "36px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "var(--accent)",
    color: "#fff",
    borderRadius: "var(--r-md)",
    flexShrink: 0,
  },
  hint: {
    fontSize: "11px",
    color: "var(--text-2)",
    padding: "0 14px 8px",
    margin: 0,
  },
};
