import { useState, useEffect, useCallback, useRef } from "react";
import { DiffEditor } from "@monaco-editor/react";
import {
  gitStatus, gitStage, gitUnstage, gitShowHead,
  gitCommit, gitPush, gitPull, gitLog, gitCurrentBranch,
  readFile,
} from "../lib/tauri.js";

// Map a file extension to a Monaco language id (mirrors EditorPane's table).
const DIFF_EXT_LANG = {
  js: "javascript", jsx: "javascript", ts: "typescript", tsx: "typescript",
  py: "python", rs: "rust", c: "c", h: "c", cpp: "cpp", cs: "csharp",
  html: "html", css: "css", json: "json", md: "markdown",
  sh: "shell", ps1: "powershell", xml: "xml", yaml: "yaml", yml: "yaml",
  toml: "ini", go: "go", java: "java",
};
function diffLangFor(path) {
  if (!path) return "plaintext";
  const ext = path.split(".").pop().toLowerCase();
  return DIFF_EXT_LANG[ext] || "plaintext";
}

// ── Diff viewer (Monaco DiffEditor) ─────────────────────────────────────────────

function DiffViewer({ file, original, modified, language, onStage, staging, onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div style={dm.overlay} onClick={onClose}>
      <div style={dm.modal} onClick={(e) => e.stopPropagation()}>
        <div style={dm.header}>
          <span style={dm.title}>{file.split(/[/\\]/).pop()}</span>
          <div style={dm.actions}>
            <button
              style={{ ...dm.stageBtn, opacity: staging ? 0.5 : 1 }}
              onClick={onStage}
              disabled={staging}
              title="Stage this file"
            >
              {staging ? "Staging…" : "Stage"}
            </button>
            <button style={dm.close} onClick={onClose} title="Close (Esc)">×</button>
          </div>
        </div>
        <div style={dm.body}>
          <DiffEditor
            height="100%"
            theme="vs-dark"
            language={language}
            original={original}
            modified={modified}
            options={{
              readOnly: true,
              renderSideBySide: true,
              minimap: { enabled: false },
              fontFamily: "JetBrains Mono, monospace",
              fontSize: 12,
              scrollBeyondLastLine: false,
              automaticLayout: true,
            }}
          />
        </div>
      </div>
    </div>
  );
}

const dm = {
  overlay: {
    position: "fixed",
    inset: 0,
    background: "rgba(0,0,0,0.55)",
    backdropFilter: "blur(3px)",
    WebkitBackdropFilter: "blur(3px)",
    zIndex: 10000,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    animation: "va-fade 120ms var(--ease)",
  },
  modal: {
    width: "80vw",
    maxWidth: 1100,
    height: "80vh",
    background: "var(--bg-1)",
    border: "1px solid var(--border)",
    borderRadius: "var(--r-lg)",
    boxShadow: "var(--shadow-lg)",
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    animation: "va-pop 160ms var(--ease)",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "10px 16px",
    borderBottom: "1px solid var(--border)",
    flexShrink: 0,
  },
  title: { fontSize: 13, fontFamily: "var(--font-mono)", color: "var(--text-0)" },
  actions: { display: "flex", alignItems: "center", gap: 12 },
  stageBtn: {
    padding: "4px 12px",
    fontSize: 12,
    fontFamily: "var(--font-ui)",
    fontWeight: 600,
    color: "var(--accent)",
    background: "var(--accent-dim)",
    border: "1px solid var(--accent)",
    borderRadius: 5,
    cursor: "pointer",
  },
  close: { fontSize: 18, color: "var(--text-2)", cursor: "pointer", lineHeight: 1, background: "none", border: "none" },
  body: { flex: 1, minHeight: 0, background: "var(--bg-0)" },
};

// ── Status helpers ────────────────────────────────────────────────────────────

function statusInfo(xy) {
  if (xy === "??") return { label: "U", color: "#888888" };
  const ch = xy[0] !== " " ? xy[0] : xy[1];
  if (ch === "A") return { label: "A", color: "#4CAF50" };
  if (ch === "D") return { label: "D", color: "#e06c75" };
  return { label: "M", color: "#e5c07b" };
}

// ── File row ──────────────────────────────────────────────────────────────────

function FileRow({ file, actionLabel, onAction, onDiff }) {
  const info = statusInfo(file.status);
  const name = file.path.split(/[/\\]/).pop();
  const deleted = file.status.includes("D");

  return (
    <div style={g.fileRow}>
      <span style={{ ...g.badge, color: info.color }}>{info.label}</span>
      <span
        style={{
          ...g.fileName,
          textDecoration: deleted ? "line-through" : "none",
          opacity: deleted ? 0.6 : 1,
        }}
        onClick={onDiff}
        title={`${file.path} — click to view diff`}
      >
        {name}
      </span>
      <button style={g.actionBtn} onClick={onAction} title={actionLabel === "+" ? "Stage" : "Unstage"}>
        {actionLabel}
      </button>
    </div>
  );
}

// ── GitPanel ──────────────────────────────────────────────────────────────────

export default function GitPanel({ rootDir, onStatusChange, focusSignal }) {
  const [branch, setBranch]       = useState("—");
  const [changes, setChanges]     = useState([]);
  const [log, setLog]             = useState([]);
  const [commitMsg, setCommitMsg] = useState("");
  const [diff, setDiff]           = useState(null);  // { file, original, modified, language } | null
  const [staging, setStaging]     = useState(false);
  const [error, setError]         = useState(null);
  const [busy, setBusy]           = useState(false);
  const [notRepo, setNotRepo]     = useState(false);
  const [loading, setLoading]     = useState(false);
  const commitRef                 = useRef(null);

  // Focus the commit input when triggered from the Command Palette
  useEffect(() => {
    if (focusSignal) commitRef.current?.focus();
  }, [focusSignal]);

  const refresh = useCallback(async () => {
    if (!rootDir) return;
    setError(null);
    setLoading(true);
    try {
      // gitCurrentBranch throws "fatal: not a git repository" for non-repos
      const branch = await gitCurrentBranch(rootDir);
      setNotRepo(false);
      const [c, l] = await Promise.all([
        gitStatus(rootDir).catch(() => []),
        gitLog(rootDir, 10).catch(() => []),
      ]);
      setBranch(branch || "—");
      setChanges(c);
      setLog(l);
      onStatusChange?.(c);
    } catch (e) {
      const msg = String(e);
      if (/not a git repository/i.test(msg)) {
        setNotRepo(true);
        setChanges([]);
        setLog([]);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, [rootDir, onStatusChange]);

  useEffect(() => { refresh(); }, [refresh]);

  // Staged = index column (xy[0]) is non-space and non-'?'
  const staged   = changes.filter((f) => f.status[0] !== " " && f.status !== "??");
  // Unstaged = working tree (xy[1]) is non-space, OR file is untracked
  const unstaged = changes.filter((f) => f.status[1] !== " " || f.status === "??");

  async function withBusy(fn) {
    setBusy(true);
    setError(null);
    try { await fn(); await refresh(); }
    catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  const handleStage    = (path)  => withBusy(() => gitStage(rootDir, [path]));
  const handleUnstage  = (path)  => withBusy(() => gitUnstage(rootDir, [path]));
  const handleStageAll = ()      => withBusy(() => gitStage(rootDir, unstaged.map((f) => f.path)));
  const handleUnstagAll= ()      => withBusy(() => gitUnstage(rootDir, staged.map((f) => f.path)));
  const handlePull     = ()      => withBusy(() => gitPull(rootDir));
  const handlePush     = ()      => withBusy(() => gitPush(rootDir));
  const handleCommit   = ()      => withBusy(async () => {
    if (!commitMsg.trim()) return;
    await gitCommit(rootDir, commitMsg.trim());
    setCommitMsg("");
  });

  // Open the inline Monaco diff: HEAD version (original) vs on-disk (modified).
  const showDiff = async (filePath) => {
    setError(null);
    try {
      const sep = rootDir.includes("\\") ? "\\" : "/";
      const abs = rootDir + sep + filePath.replace(/\//g, sep);
      const [original, modified] = await Promise.all([
        gitShowHead(rootDir, filePath).catch(() => ""),
        readFile(abs).catch(() => ""), // deleted file → empty modified side
      ]);
      setDiff({ file: filePath, original, modified, language: diffLangFor(filePath) });
    } catch (e) {
      setError(String(e));
    }
  };

  // Stage the file currently shown in the diff viewer, then refresh + close.
  const stageFromDiff = useCallback(async () => {
    if (!diff) return;
    setStaging(true);
    setError(null);
    try {
      await gitStage(rootDir, [diff.file]);
      setDiff(null);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setStaging(false);
    }
  }, [diff, rootDir, refresh]);

  if (!rootDir) {
    return <div style={g.empty}>No folder open</div>;
  }

  if (notRepo) {
    return (
      <div style={g.wrap}>
        <div style={g.header}>
          <span style={g.branchName}>Source Control</span>
          <button style={g.iconBtn} onClick={refresh} title="Refresh">↺</button>
        </div>
        <div style={g.notRepo}>
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none"
            stroke="var(--text-2)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="18" cy="18" r="3" /><circle cx="6" cy="6" r="3" />
            <path d="M6 9v6a3 3 0 003 3h6" />
          </svg>
          <span>Not a git repository</span>
          <span style={g.notRepoHint}>Run <code style={g.code}>git init</code> in the terminal to start tracking.</span>
        </div>
      </div>
    );
  }

  return (
    <div style={g.wrap}>
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div style={g.header}>
        <div style={g.branchRow}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
            stroke="var(--accent)" strokeWidth="2.2" strokeLinecap="round">
            <line x1="6" y1="3" x2="6" y2="15" />
            <circle cx="18" cy="6" r="3" />
            <circle cx="6" cy="18" r="3" />
            <path d="M18 9a9 9 0 01-9 9" />
          </svg>
          <span style={g.branchName}>{branch}</span>
        </div>
        <div style={g.headerBtns}>
          <button style={g.iconBtn} onClick={handlePull} title="Pull" disabled={busy}>↓</button>
          <button style={g.iconBtn} onClick={handlePush} title="Push" disabled={busy}>↑</button>
          <button style={g.iconBtn} onClick={refresh}    title="Refresh">↺</button>
        </div>
      </div>

      {error && <div style={g.errorBanner}>{error}</div>}

      <div style={g.scroll}>
        {/* ── Staged ────────────────────────────────────────────────────── */}
        {staged.length > 0 && (
          <section>
            <div style={g.sectionHead}>
              <span style={g.sectionLabel}>Staged Changes ({staged.length})</span>
              <button style={g.textBtn} onClick={handleUnstagAll}>Unstage All</button>
            </div>
            {staged.map((f) => (
              <FileRow
                key={f.path + ":staged"}
                file={f}
                actionLabel="−"
                onAction={() => handleUnstage(f.path)}
                onDiff={() => showDiff(f.path)}
              />
            ))}
          </section>
        )}

        {/* ── Unstaged ──────────────────────────────────────────────────── */}
        {unstaged.length > 0 && (
          <section>
            <div style={g.sectionHead}>
              <span style={g.sectionLabel}>Changes ({unstaged.length})</span>
              <button style={g.textBtn} onClick={handleStageAll}>Stage All</button>
            </div>
            {unstaged.map((f) => (
              <FileRow
                key={f.path + ":unstaged"}
                file={f}
                actionLabel="+"
                onAction={() => handleStage(f.path)}
                onDiff={() => showDiff(f.path)}
              />
            ))}
          </section>
        )}

        {changes.length === 0 && (
          <div style={g.empty}>{loading ? "Loading…" : "No changes"}</div>
        )}

        {/* ── Commit ────────────────────────────────────────────────────── */}
        <section style={{ padding: "8px 10px", borderTop: "1px solid var(--border)" }}>
          <textarea
            ref={commitRef}
            style={g.commitInput}
            rows={2}
            placeholder="Commit message…"
            value={commitMsg}
            onChange={(e) => setCommitMsg(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && e.ctrlKey) handleCommit(); }}
          />
          <button
            style={{ ...g.commitBtn, opacity: commitMsg.trim() && !busy ? 1 : 0.4 }}
            onClick={handleCommit}
            disabled={!commitMsg.trim() || busy}
          >
            Commit to {branch}
          </button>
        </section>

        {/* ── Log ───────────────────────────────────────────────────────── */}
        {log.length > 0 && (
          <section>
            <div style={g.sectionHead}>
              <span style={g.sectionLabel}>History</span>
            </div>
            {log.map((entry) => (
              <div key={entry.hash} style={g.logRow}>
                <span style={g.logHash}>{entry.hash}</span>
                <span style={g.logMsg}>{entry.message}</span>
                <span style={g.logDate}>{entry.date}</span>
              </div>
            ))}
          </section>
        )}
      </div>

      {/* ── Diff viewer ───────────────────────────────────────────────────── */}
      {diff && (
        <DiffViewer
          file={diff.file}
          original={diff.original}
          modified={diff.modified}
          language={diff.language}
          onStage={stageFromDiff}
          staging={staging}
          onClose={() => setDiff(null)}
        />
      )}
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const g = {
  wrap: {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    fontSize: 12,
    fontFamily: "var(--font-ui)",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "8px 10px",
    borderBottom: "1px solid var(--border)",
    flexShrink: 0,
  },
  branchRow: { display: "flex", alignItems: "center", gap: 6 },
  branchName: { fontSize: 12, fontWeight: 600, color: "var(--text-0)", fontFamily: "var(--font-mono)" },
  headerBtns: { display: "flex", gap: 4 },
  iconBtn: {
    width: 26, height: 26,
    display: "flex", alignItems: "center", justifyContent: "center",
    fontSize: 14, color: "var(--text-2)",
    borderRadius: "var(--r-sm)", cursor: "pointer",
    background: "transparent", border: "none",
  },
  errorBanner: {
    background: "rgba(224,108,117,0.12)",
    borderLeft: "3px solid #e06c75",
    padding: "6px 10px",
    fontSize: 11,
    color: "#e06c75",
    fontFamily: "var(--font-mono)",
    flexShrink: 0,
    wordBreak: "break-all",
  },
  notRepo: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    padding: "40px 20px",
    textAlign: "center",
    color: "var(--text-1)",
    fontSize: 13,
  },
  notRepoHint: { fontSize: 11, color: "var(--text-2)" },
  code: {
    fontFamily: "var(--font-mono)",
    background: "var(--bg-2)",
    padding: "1px 5px",
    borderRadius: 4,
    color: "var(--accent)",
  },
  scroll: { flex: 1, overflow: "auto" },
  sectionHead: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "6px 10px 3px",
    borderTop: "1px solid var(--border)",
  },
  sectionLabel: {
    fontSize: 10,
    letterSpacing: "0.06em",
    textTransform: "uppercase",
    color: "var(--text-2)",
  },
  textBtn: {
    fontSize: 10,
    color: "var(--accent)",
    cursor: "pointer",
    background: "none",
    border: "none",
    padding: "1px 4px",
  },
  fileRow: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "4px 10px",
    margin: "0 6px",
    borderRadius: "var(--r-sm)",
    cursor: "default",
  },
  badge: {
    fontFamily: "var(--font-mono)",
    fontSize: 10,
    fontWeight: 700,
    width: 12,
    flexShrink: 0,
  },
  fileName: {
    flex: 1,
    fontFamily: "var(--font-mono)",
    fontSize: 11,
    color: "var(--text-0)",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
    cursor: "pointer",
  },
  actionBtn: {
    width: 18, height: 18,
    display: "flex", alignItems: "center", justifyContent: "center",
    fontSize: 14, fontWeight: 400,
    color: "var(--text-2)",
    border: "1px solid var(--border)",
    borderRadius: 3,
    cursor: "pointer",
    background: "transparent",
    flexShrink: 0,
    lineHeight: 1,
    padding: 0,
  },
  commitInput: {
    width: "100%",
    boxSizing: "border-box",
    background: "var(--bg-2)",
    border: "1px solid var(--border)",
    borderRadius: "var(--r-sm)",
    padding: "8px 10px",
    fontSize: 12,
    color: "var(--text-0)",
    fontFamily: "var(--font-ui)",
    resize: "none",
    marginBottom: 6,
    lineHeight: 1.5,
  },
  commitBtn: {
    width: "100%",
    padding: "8px 0",
    background: "var(--accent)",
    color: "#fff",
    border: "none",
    borderRadius: "var(--r-sm)",
    fontSize: 12,
    fontFamily: "var(--font-ui)",
    fontWeight: 600,
    cursor: "pointer",
  },
  logRow: {
    display: "flex",
    alignItems: "baseline",
    gap: 6,
    padding: "3px 10px",
  },
  logHash: {
    fontFamily: "var(--font-mono)",
    fontSize: 10,
    color: "var(--accent)",
    flexShrink: 0,
  },
  logMsg: {
    fontSize: 11,
    color: "var(--text-1)",
    flex: 1,
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  logDate: {
    fontSize: 10,
    color: "var(--text-2)",
    flexShrink: 0,
    whiteSpace: "nowrap",
  },
  empty: {
    padding: "16px 12px",
    fontSize: 12,
    color: "var(--text-2)",
    fontFamily: "var(--font-ui)",
  },
};
