import { useState, useCallback, useEffect, useRef, memo } from "react";
import { open, save } from "@tauri-apps/plugin-dialog";
import { listDir, createFile, deleteFile, renameFile, createDir } from "../lib/tauri.js";

// Poll interval (ms) for live folder refresh. Keeps the tree in sync with files
// created outside the app — the in-app terminal, git, other editors — without an
// OS-level watcher. Only expanded folders poll, and only while the window is visible.
const POLL_MS = 1500;

// Stable signature of a directory listing (list_dir is already sorted), used to
// skip state updates — and re-renders — when a folder's contents are unchanged.
function listingSig(items) {
  return items.map((x) => (x.is_dir ? "d:" : "f:") + x.path).join("\n");
}

// ── Language badges ───────────────────────────────────────────────────────────

const FILE_BADGES = {
  // Web / JS
  js:          { text: "JS",   color: "#F7DF1E" },
  jsx:         { text: "JSX",  color: "#61DAFB" },
  mjs:         { text: "JS",   color: "#F7DF1E" },
  cjs:         { text: "JS",   color: "#F7DF1E" },
  ts:          { text: "TS",   color: "#3178C6" },
  tsx:         { text: "TSX",  color: "#3178C6" },
  css:         { text: "CSS",  color: "#563d7c" },
  html:        { text: "HTML", color: "#e34c26" },
  htm:         { text: "HTML", color: "#e34c26" },
  coffee:      { text: "CF",   color: "#244776" },
  // Systems
  c:           { text: "C",    color: "#555555" },
  h:           { text: "H",    color: "#555555" },
  cpp:         { text: "C++",  color: "#f34b7d" },
  hpp:         { text: "H++",  color: "#f34b7d" },
  cs:          { text: "C#",   color: "#178600" },
  rs:          { text: "RS",   color: "#DEA584" },
  java:        { text: "JV",   color: "#b07219" },
  kt:          { text: "KT",   color: "#A97BFF" },
  swift:       { text: "SW",   color: "#F05138" },
  go:          { text: "GO",   color: "#00ADD8" },
  ino:         { text: "INO",  color: "#bd79d1" },
  // Scripting
  py:          { text: "PY",   color: "#3572A5" },
  rb:          { text: "RB",   color: "#701516" },
  php:         { text: "PHP",  color: "#4F5D95" },
  pl:          { text: "PL",   color: "#0298c3" },
  lua:         { text: "LUA",  color: "#000080" },
  r:           { text: "R",    color: "#198CE7" },
  sh:          { text: "SH",   color: "#89e051" },
  ps1:         { text: "PS",   color: "#012456" },
  // Functional / JVM
  scala:       { text: "SC",   color: "#c22d40" },
  groovy:      { text: "GRV",  color: "#4298b8" },
  gradle:      { text: "GR",   color: "#4298b8" },
  fs:          { text: "FS",   color: "#b845fc" },
  vb:          { text: "VB",   color: "#945db7" },
  hs:          { text: "HS",   color: "#5e5086" },
  ex:          { text: "EX",   color: "#6e4a7e" },
  exs:         { text: "EXS",  color: "#6e4a7e" },
  erl:         { text: "ERL",  color: "#B83998" },
  clj:         { text: "CLJ",  color: "#db5855" },
  ml:          { text: "ML",   color: "#3be133" },
  // Mobile
  dart:        { text: "DRT",  color: "#00B4AB" },
  // Data / Query
  sql:         { text: "SQL",  color: "#e38c00" },
  graphql:     { text: "GQL",  color: "#e10098" },
  json:        { text: "{}",   color: "#cbcb41" },
  yaml:        { text: "YML",  color: "#cb171e" },
  yml:         { text: "YML",  color: "#cb171e" },
  toml:        { text: "TML",  color: "#9c4221" },
  xml:         { text: "XML",  color: "#0060ac" },
  // Infrastructure
  tf:          { text: "TF",   color: "#7B42BC" },
  proto:       { text: "PB",   color: "#4285F4" },
  dockerfile:  { text: "DF",   color: "#384d54" },
  makefile:    { text: "MK",   color: "#427819" },
  cmake:       { text: "CM",   color: "#064F8C" },
  nginx:       { text: "NGX",  color: "#009900" },
  // Docs / misc
  md:          { text: "MD",   color: "#083fa1" },
  asm:         { text: "ASM",  color: "#6E4C13" },
  s:           { text: "ASM",  color: "#6E4C13" },
  vim:         { text: "VIM",  color: "#199f4b" },
};

const FileBadge = memo(function FileBadge({ name }) {
  // For files like "Makefile" or "Dockerfile" (no dot), use the full lowercased name as key.
  const ext = name.split(".").pop().toLowerCase();
  const b = FILE_BADGES[ext] || { text: "•", color: "var(--text-2)" };
  return (
    <span style={{
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      minWidth: "24px",
      height: "16px",
      fontFamily: "var(--font-mono)",
      fontSize: "8px",
      fontWeight: "bold",
      color: b.color,
      flexShrink: 0,
      letterSpacing: "-0.02em",
      userSelect: "none",
    }}>
      {b.text}
    </span>
  );
});

const FolderIcon = memo(function FolderIcon({ open: isOpen }) {
  return (
    <svg
      width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke="var(--text-2)" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round"
      style={{ flexShrink: 0 }}
    >
      <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
      {isOpen && <path d="M2 10h20" />}
    </svg>
  );
});

// ── New-item icons + inline input ─────────────────────────────────────────────

const FilePlusIcon = memo(function FilePlusIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8z" />
      <path d="M14 3v5h5" />
      <line x1="12" y1="12" x2="12" y2="18" />
      <line x1="9" y1="15" x2="15" y2="15" />
    </svg>
  );
});

const FolderPlusIcon = memo(function FolderPlusIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
      <line x1="12" y1="11" x2="12" y2="17" />
      <line x1="9" y1="14" x2="15" y2="14" />
    </svg>
  );
});

const OpenFileIcon = memo(function OpenFileIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  );
});

// Hover-revealed "New File" / "New Folder" buttons shown on any folder row, so
// items can be created inside that specific folder (not just the first root).
const RowActions = memo(function RowActions({ dirPath, onStartCreate }) {
  return (
    <span className="ft-row-actions">
      <button
        className="va-btn" style={styles.rowActionBtn} title="New File"
        onClick={(e) => { e.stopPropagation(); onStartCreate(dirPath, "file"); }}
      >
        <FilePlusIcon />
      </button>
      <button
        className="va-btn" style={styles.rowActionBtn} title="New Folder"
        onClick={(e) => { e.stopPropagation(); onStartCreate(dirPath, "folder"); }}
      >
        <FolderPlusIcon />
      </button>
    </span>
  );
});

// Create a file/folder under parentPath, re-list that folder, open new files.
async function performCreate(parentPath, kind, name, refresh, onOpenFile) {
  const sep = parentPath.includes("\\") ? "\\" : "/";
  const full = parentPath + sep + name;
  if (kind === "file") {
    await createFile(full, "");
    await refresh();
    onOpenFile?.({ path: full, name });
  } else {
    await createDir(full);
    await refresh();
  }
}

// Inline input rendered among a folder's children while naming a new item.
function NewItemInput({ kind, depth, onConfirm, onCancel }) {
  const [value, setValue] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy]   = useState(false);
  const submittingRef = useRef(false); // set synchronously so onBlur never cancels mid-submit
  const inputRef = useRef(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  const submit = async () => {
    if (submittingRef.current) return;
    const name = value.trim();
    if (!name) { onCancel(); return; }
    if (/[\\/]/.test(name)) { setError("Name can't contain / or \\"); return; }
    submittingRef.current = true;
    setBusy(true);
    try {
      await onConfirm(name);                                 // success → parent unmounts this input
    } catch (e) {
      const msg = String(e).replace(/^[^:]*:\s*/, "");       // strip "command: " prefix
      setError(msg);
      window.notify?.(`Could not create ${kind}: ${msg}`, "error");
      submittingRef.current = false;
      setBusy(false);
    }
  };

  return (
    <div style={{ ...styles.row, paddingLeft: 8 + depth * 12, cursor: "default" }}>
      <span style={styles.caret} />
      {kind === "folder" ? <FolderIcon open={false} /> : <FileBadge name={value || "new"} />}
      <input
        ref={inputRef}
        value={value}
        onChange={(e) => { setValue(e.target.value); setError(null); }}
        onKeyDown={(e) => {
          // Keep keystrokes inside the input: stops any global window keydown
          // handler (Ctrl+S, palette, etc.) from swallowing Enter/typing here.
          e.stopPropagation();
          if (e.key === "Enter") { e.preventDefault(); submit(); }
          else if (e.key === "Escape") { e.preventDefault(); onCancel(); }
        }}
        onBlur={() => { if (!submittingRef.current) onCancel(); }}
        placeholder={kind === "folder" ? "folder name" : "file name"}
        spellCheck={false}
        style={{ ...niStyles.input, opacity: busy ? 0.6 : 1 }}
      />
      {error && <span style={niStyles.error} title={error}>{error}</span>}
    </div>
  );
}

const niStyles = {
  input: {
    flex: 1,
    minWidth: 0,
    background: "var(--bg-0)",
    border: "1px solid var(--accent)",
    borderRadius: 4,
    color: "var(--text-0)",
    fontFamily: "var(--font-mono)",
    fontSize: 12,
    padding: "1px 5px",
    outline: "none",
  },
  error: {
    fontSize: 10,
    color: "var(--err)",
    fontFamily: "var(--font-ui)",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
    maxWidth: 90,
    flexShrink: 0,
    marginLeft: 4,
  },
};

// ── Context menu ─────────────────────────────────────────────────────────────

function ContextMenu({ x, y, entry, parentPath, refreshParent, refreshSelf, onClose, onStartCreate }) {
  const ref = useRef(null);

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

  // When right-clicking a dir, create inside it; for a file, create in its parent.
  const containerPath = entry.is_dir ? entry.path : parentPath;

  const sep = parentPath.includes("\\") ? "\\" : "/";

  // Open an inline naming input inside the target folder.
  const newFile   = () => { onClose(); onStartCreate(containerPath, "file"); };
  const newFolder = () => { onClose(); onStartCreate(containerPath, "folder"); };

  const rename = async () => {
    onClose();
    const newName = window.prompt("Rename to:", entry.name);
    if (!newName || !newName.trim() || newName.trim() === entry.name) return;
    const newPath = parentPath + sep + newName.trim();
    try {
      await renameFile(entry.path, newPath);
      refreshParent();
    } catch (e) {
      alert(`Error renaming: ${e}`);
    }
  };

  const remove = async () => {
    onClose();
    if (!window.confirm(`Delete "${entry.name}"? This cannot be undone.`)) return;
    try {
      await deleteFile(entry.path);
      refreshParent();
    } catch (e) {
      alert(`Error deleting: ${e}`);
    }
  };

  // Clamp menu so it doesn't go off screen bottom/right
  const viewW = window.innerWidth;
  const viewH = window.innerHeight;
  const menuW = 168;
  const menuH = 148;
  const left = x + menuW > viewW ? viewW - menuW - 8 : x;
  const top  = y + menuH > viewH ? viewH - menuH - 8 : y;

  const items = [
    { label: "New File",   action: newFile },
    { label: "New Folder", action: newFolder },
    null,
    { label: "Rename",  action: rename },
    { label: "Delete",  action: remove, danger: true },
  ];

  return (
    <div ref={ref} style={{ ...cmStyles.menu, top, left }}>
      {items.map((item, i) =>
        item === null ? (
          <div key={i} style={cmStyles.sep} />
        ) : (
          <button
            key={i}
            style={{ ...cmStyles.item, color: item.danger ? "var(--error, #e06c75)" : "var(--text-0)" }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-3)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            onClick={item.action}
          >
            {item.label}
          </button>
        )
      )}
    </div>
  );
}

const cmStyles = {
  menu: {
    position: "fixed",
    background: "var(--bg-2)",
    border: "1px solid var(--border)",
    borderRadius: "8px",
    padding: "4px",
    zIndex: 9999,
    minWidth: "168px",
    boxShadow: "0 4px 20px rgba(0,0,0,0.35)",
  },
  sep: { height: "1px", background: "var(--border)", margin: "4px 0" },
  item: {
    display: "block",
    width: "100%",
    textAlign: "left",
    padding: "6px 10px",
    fontSize: "13px",
    fontFamily: "var(--font-ui)",
    borderRadius: "5px",
    background: "transparent",
    cursor: "pointer",
  },
};

// ── Git status dot ────────────────────────────────────────────────────────────

const GitDot = memo(function GitDot({ xy }) {
  if (!xy) return null;
  const color = xy === "??" ? "#888"
    : xy.includes("A") ? "#4CAF50"
    : xy.includes("D") ? "#e06c75"
    : "#e5c07b";  // M
  return (
    <span style={{
      display: "inline-block",
      width: 6, height: 6,
      borderRadius: "50%",
      background: color,
      flexShrink: 0,
      marginLeft: 4,
    }} title={xy} />
  );
});

// ── Path helpers (reveal-in-tree) ─────────────────────────────────────────────

const normp = (p) => p.replace(/\\/g, "/").toLowerCase();
function samePath(a, b) { return normp(a) === normp(b); }
function isAncestorPath(dir, target) {
  const d = normp(dir), t = normp(target);
  return t === d || t.startsWith(d + "/");
}

// ── Tree node ────────────────────────────────────────────────────────────────

const TreeNode = memo(function TreeNode({ entry, depth, onOpenFile, parentPath, refreshParent, onContextMenu, onStartCreate, gitStatusMap, activeFilePath, reveal, creating, onClearCreating, selectedPath, onSelect }) {
  const [expanded,      setExpanded]      = useState(false);
  const [children,      setChildren]      = useState(null);
  const [refreshError,  setRefreshError]  = useState(false);
  const rowRef = useRef(null);

  const isCreateTarget = entry.is_dir && creating?.parentPath && samePath(creating.parentPath, entry.path);

  // Reveal-in-tree: expand toward the target path, scroll the target into view
  useEffect(() => {
    if (!reveal?.path) return;
    if (entry.is_dir && isAncestorPath(entry.path, reveal.path) && !samePath(entry.path, reveal.path)) {
      (async () => {
        if (children === null) {
          try { setChildren(await listDir(entry.path)); } catch { setChildren([]); }
        }
        setExpanded(true);
      })();
    }
    if (samePath(entry.path, reveal.path)) {
      rowRef.current?.scrollIntoView({ block: "nearest" });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reveal?.nonce]);

  // When this folder becomes a create target, expand + load so the input shows.
  useEffect(() => {
    if (!isCreateTarget) return;
    (async () => {
      if (children === null) {
        try { setChildren(await listDir(entry.path)); } catch { setChildren([]); }
      }
      setExpanded(true);
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isCreateTarget]);

  // Called when something inside this dir changes and we need to re-read it.
  const refreshSelf = useCallback(async () => {
    setRefreshError(false);
    try {
      const items = await listDir(entry.path);
      setChildren(items);
      setExpanded(true);
    } catch {
      setChildren([]);
      setRefreshError(true);
    }
  }, [entry.path]);

  // Auto-refresh when the AI agent writes a file directly inside this directory.
  useEffect(() => {
    if (!entry.is_dir) return;
    const handler = (e) => { if (samePath(e.detail.path, entry.path)) refreshSelf(); };
    window.addEventListener("vagent-fs-changed", handler);
    return () => window.removeEventListener("vagent-fs-changed", handler);
  }, [entry.is_dir, entry.path, refreshSelf]);

  // Live-refresh: while expanded, poll so files created outside the app (terminal,
  // git, other programs) appear without a manual refresh. Children keep their keys,
  // so expanded sub-folders and edits-in-progress are preserved.
  useEffect(() => {
    if (!entry.is_dir || !expanded) return;
    let cancelled = false;
    const tick = async () => {
      if (document.hidden) return;
      try {
        const items = await listDir(entry.path);
        if (cancelled) return;
        setChildren((prev) => (prev && listingSig(prev) === listingSig(items) ? prev : items));
      } catch { /* dir vanished or transient error — the parent's poll reconciles */ }
    };
    const id = setInterval(tick, POLL_MS);
    window.addEventListener("focus", tick);   // catch changes made in another app
    return () => { cancelled = true; clearInterval(id); window.removeEventListener("focus", tick); };
  }, [entry.is_dir, entry.path, expanded]);

  const toggle = useCallback(async () => {
    if (entry.is_dir) {
      if (!expanded && children === null) {
        try {
          const items = await listDir(entry.path);
          setChildren(items);
        } catch {
          setChildren([]);
        }
      }
      setExpanded((v) => !v);
    } else {
      onOpenFile(entry);
    }
  }, [entry, expanded, children, onOpenFile]);

  const handleContextMenu = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    // VS Code selects the item you right-click, so a follow-up New File
    // from the header targets the same place the menu acted on.
    onSelect?.({ path: entry.path, isDir: entry.is_dir, parentPath });
    onContextMenu(e, entry, parentPath, refreshParent, refreshSelf);
  }, [entry, parentPath, refreshParent, refreshSelf, onContextMenu, onSelect]);

  // Selection (VS Code-style): clicking any row marks it as the target
  // context for the header New File / New Folder buttons.
  const handleClick = useCallback((e) => {
    e.stopPropagation();               // body click clears selection
    onSelect?.({ path: entry.path, isDir: entry.is_dir, parentPath });
    toggle();
  }, [entry, parentPath, onSelect, toggle]);

  const isActive   = !entry.is_dir && entry.path === activeFilePath;
  const isSelected = !!selectedPath && samePath(selectedPath, entry.path);
  const restBg     = isActive ? "var(--accent-dim)" : isSelected ? "var(--bg-3)" : "transparent";

  return (
    <div>
      <div
        ref={rowRef}
        className="file-tree-item"
        style={{
          ...styles.row,
          paddingLeft: 8 + depth * 12,
          background: restBg,
          boxShadow: isActive ? "inset 2px 0 0 var(--accent)" : "none",
        }}
        onClick={handleClick}
        onContextMenu={handleContextMenu}
        onMouseEnter={(e) => {
          if (!isActive) e.currentTarget.style.background = "var(--bg-3)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = restBg;
        }}
      >
        <span style={styles.caret}>
          {entry.is_dir ? (expanded ? "▾" : "▸") : ""}
        </span>
        {entry.is_dir
          ? <FolderIcon open={expanded} />
          : <FileBadge name={entry.name} />
        }
        <span style={{
          ...styles.name,
          textDecoration: gitStatusMap?.[entry.path]?.includes("D") ? "line-through" : "none",
        }}>
          {entry.name}
        </span>
        <GitDot xy={gitStatusMap?.[entry.path]} />
        {entry.is_dir && !refreshError && (
          <RowActions dirPath={entry.path} onStartCreate={onStartCreate} />
        )}
        {refreshError && (
          <button
            style={{ ...styles.rootRemove, color: "var(--err)", marginLeft: "auto" }}
            title="Refresh failed — click to retry"
            onClick={(e) => { e.stopPropagation(); refreshSelf(); }}
          >↺</button>
        )}
      </div>
      {expanded && (
        <>
          {isCreateTarget && (
            <NewItemInput
              kind={creating.kind}
              depth={depth + 1}
              onConfirm={(name) => performCreate(entry.path, creating.kind, name, refreshSelf, onOpenFile).then(onClearCreating)}
              onCancel={onClearCreating}
            />
          )}
          {children &&
            children.map((child) => (
              <TreeNode
                key={child.path}
                entry={child}
                depth={depth + 1}
                onOpenFile={onOpenFile}
                parentPath={entry.path}
                refreshParent={refreshSelf}
                onContextMenu={onContextMenu}
                onStartCreate={onStartCreate}
                gitStatusMap={gitStatusMap}
                activeFilePath={activeFilePath}
                reveal={reveal}
                creating={creating}
                onClearCreating={onClearCreating}
                selectedPath={selectedPath}
                onSelect={onSelect}
              />
            ))}
        </>
      )}
    </div>
  );
});

// ── Root folder node (collapsible, removable) ─────────────────────────────────

function RootNode({ rootDir, onOpenFile, onRemove, onContextMenu, onStartCreate, gitStatusMap, activeFilePath, reveal, creating, onClearCreating, selectedPath, onSelect }) {
  const [expanded,   setExpanded]   = useState(true);
  const [children,   setChildren]   = useState(null);
  const [hover,      setHover]      = useState(false);
  const [loadError,  setLoadError]  = useState(false);

  const name = rootDir.split(/[/\\]/).filter(Boolean).pop() || rootDir;
  const isCreateTarget = creating?.parentPath && samePath(creating.parentPath, rootDir);

  const load = useCallback(async () => {
    setLoadError(false);
    try { setChildren(await listDir(rootDir)); }
    catch { setChildren([]); setLoadError(true); }
  }, [rootDir]);

  // Load once on mount (root shown expanded by default)
  useEffect(() => { load(); }, [load]);

  // Reveal-in-tree: re-expand this root if the target lives under it
  useEffect(() => {
    if (reveal?.path && isAncestorPath(rootDir, reveal.path)) setExpanded(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reveal?.nonce]);

  // Expand when this root becomes the create target.
  useEffect(() => {
    if (isCreateTarget) setExpanded(true);
  }, [isCreateTarget]);

  // Auto-refresh when the AI agent writes a file directly at the root level.
  useEffect(() => {
    const handler = (e) => { if (samePath(e.detail.path, rootDir)) load(); };
    window.addEventListener("vagent-fs-changed", handler);
    return () => window.removeEventListener("vagent-fs-changed", handler);
  }, [rootDir, load]);

  // Live-refresh: while expanded, poll the root so externally-created files
  // (terminal, git, other programs) show up without a manual refresh.
  useEffect(() => {
    if (!expanded) return;
    let cancelled = false;
    const tick = async () => {
      if (document.hidden) return;
      try {
        const items = await listDir(rootDir);
        if (cancelled) return;
        setChildren((prev) => (prev && listingSig(prev) === listingSig(items) ? prev : items));
      } catch { /* transient — keep the last good listing */ }
    };
    const id = setInterval(tick, POLL_MS);
    window.addEventListener("focus", tick);
    return () => { cancelled = true; clearInterval(id); window.removeEventListener("focus", tick); };
  }, [rootDir, expanded]);

  const toggle = useCallback(async () => {
    if (!expanded && children === null) await load();
    setExpanded((v) => !v);
  }, [expanded, children, load]);

  return (
    <div>
      <div
        className="file-tree-item"
        style={{
          ...styles.rootRow,
          background: selectedPath && samePath(selectedPath, rootDir) ? "var(--bg-3)" : "transparent",
        }}
        onClick={(e) => {
          e.stopPropagation();
          onSelect?.({ path: rootDir, isDir: true, parentPath: null });
          toggle();
        }}
        onMouseEnter={(e) => { setHover(true); e.currentTarget.style.background = "var(--bg-3)"; }}
        onMouseLeave={(e) => {
          setHover(false);
          e.currentTarget.style.background =
            selectedPath && samePath(selectedPath, rootDir) ? "var(--bg-3)" : "transparent";
        }}
        title={rootDir}
      >
        <span style={styles.caret}>{expanded ? "▾" : "▸"}</span>
        <span style={styles.rootName}>{name}</span>
        {loadError && (
          <button
            style={{ ...styles.rootRemove, color: "var(--err)" }}
            title="Load failed — click to retry"
            onClick={(e) => { e.stopPropagation(); load(); }}
          >↺</button>
        )}
        {!loadError && (
          <RowActions dirPath={rootDir} onStartCreate={onStartCreate} />
        )}
        {hover && !loadError && (
          <button
            style={styles.rootRemove}
            title="Remove folder from workspace"
            onClick={(e) => { e.stopPropagation(); onRemove(rootDir); }}
          >×</button>
        )}
      </div>
      {expanded && (
        <>
          {isCreateTarget && (
            <NewItemInput
              kind={creating.kind}
              depth={1}
              onConfirm={(name) => performCreate(rootDir, creating.kind, name, load, onOpenFile).then(onClearCreating)}
              onCancel={onClearCreating}
            />
          )}
          {children &&
            children.map((child) => (
              <TreeNode
                key={child.path}
                entry={child}
                depth={1}
                onOpenFile={onOpenFile}
                parentPath={rootDir}
                refreshParent={load}
                onContextMenu={onContextMenu}
                onStartCreate={onStartCreate}
                gitStatusMap={gitStatusMap}
                activeFilePath={activeFilePath}
                reveal={reveal}
                creating={creating}
                onClearCreating={onClearCreating}
                selectedPath={selectedPath}
                onSelect={onSelect}
              />
            ))}
        </>
      )}
    </div>
  );
}

// ── File tree root ────────────────────────────────────────────────────────────

export default function FileTree({ rootDirs, onAddRoot, onRemoveRoot, onReplaceRoots, onOpenFile, gitStatusMap, activeFilePath, reveal }) {
  const [ctxMenu, setCtxMenu]   = useState(null);
  const [creating, setCreating] = useState(null); // { parentPath, kind }
  // Explorer selection — the context the header New File / New Folder buttons
  // act on. { path, isDir, parentPath } | null.
  const [selected, setSelected] = useState(null);

  // Workspace changed → the old selection may not exist anymore.
  useEffect(() => { setSelected(null); }, [rootDirs]);

  const clearCreating = useCallback(() => setCreating(null), []);
  const startCreate   = useCallback((parentPath, kind) => { setCreating({ parentPath, kind }); }, []);

  // Header buttons follow VS Code's rule (fileActions.ts openExplorerAndCreate):
  // selected folder → create inside it; selected file → create in its parent;
  // nothing selected → first workspace root.
  const startCreateAtSelection = useCallback((kind) => {
    if (!rootDirs || !rootDirs.length) return;
    const target = selected
      ? (selected.isDir ? selected.path : (selected.parentPath || rootDirs[0]))
      : rootDirs[0];
    setCreating({ parentPath: target, kind });
  }, [rootDirs, selected]);

  // Open dialog → replace the whole workspace with the picked folder
  const openFolder = useCallback(async () => {
    const selected = await open({ directory: true, multiple: false });
    if (selected && typeof selected === "string") onReplaceRoots(selected);
  }, [onReplaceRoots]);

  // Open dialog → add another folder to the workspace
  const addFolder = useCallback(async () => {
    const selected = await open({ directory: true, multiple: false });
    if (selected && typeof selected === "string") onAddRoot(selected);
  }, [onAddRoot]);

  // Open dialog → open a single file directly in a tab (focuses it if already open)
  const openFileDlg = useCallback(async () => {
    const selected = await open({ directory: false, multiple: false });
    if (selected && typeof selected === "string") {
      onOpenFile({ path: selected, name: selected.split(/[/\\]/).pop() });
    }
  }, [onOpenFile]);

  // No workspace open → create a file anywhere via a Save dialog, then open it.
  const newFileNoWorkspace = useCallback(async () => {
    const path = await save({ title: "New File" });
    if (!path || typeof path !== "string") return;
    try {
      await createFile(path, "");
      onOpenFile({ path, name: path.split(/[/\\]/).pop() });
    } catch (e) {
      window.notify?.(`Could not create file: ${String(e).replace(/^[^:]*:\s*/, "")}`, "error");
    }
  }, [onOpenFile]);

  // No workspace open → pick a location, name a new folder, create it and open it.
  const newFolderNoWorkspace = useCallback(async () => {
    const parent = await open({ directory: true, multiple: false, title: "Choose where to create the folder" });
    if (!parent || typeof parent !== "string") return;
    const name = window.prompt("New folder name:");
    if (!name || !name.trim()) return;
    if (/[\\/]/.test(name.trim())) { window.notify?.("Folder name can't contain / or \\", "error"); return; }
    const sep = parent.includes("\\") ? "\\" : "/";
    const full = parent + sep + name.trim();
    try {
      await createDir(full);
      onReplaceRoots(full);   // open the new folder as the workspace
    } catch (e) {
      window.notify?.(`Could not create folder: ${String(e).replace(/^[^:]*:\s*/, "")}`, "error");
    }
  }, [onReplaceRoots]);

  const handleContextMenu = useCallback((e, entry, parentPath, refreshParent, refreshSelf) => {
    setCtxMenu({ x: e.clientX, y: e.clientY, entry, parentPath, refreshParent, refreshSelf });
  }, []);

  const hasRoots = rootDirs && rootDirs.length > 0;

  return (
    <div style={styles.wrap}>
      <div style={styles.header}>
        <div style={styles.headerTop}>
          <span style={styles.headerLabel}>Explorer</span>
          <div style={{ display: "flex", gap: 2 }}>
            <button className="va-btn" style={styles.iconBtn} onClick={openFileDlg} title="Open File">
              <OpenFileIcon />
            </button>
            {hasRoots && (
              <>
                <button className="va-btn" style={styles.iconBtn} onClick={() => startCreateAtSelection("file")} title="New File">
                  <FilePlusIcon />
                </button>
                <button className="va-btn" style={styles.iconBtn} onClick={() => startCreateAtSelection("folder")} title="New Folder">
                  <FolderPlusIcon />
                </button>
              </>
            )}
          </div>
        </div>
        <div style={styles.headerActions}>
          {hasRoots && (
            <button style={styles.openBtn} onClick={addFolder} title="Add another folder">
              + Add
            </button>
          )}
          <button style={styles.openBtn} onClick={openFolder} title="Open a folder (replaces workspace)">
            Open folder
          </button>
        </div>
      </div>
      {/* Clicking empty space clears the selection (VS Code behavior) */}
      <div style={styles.body} onClick={() => setSelected(null)}>
        {!hasRoots && (
          <div style={styles.empty}>
            <div style={styles.emptyText}>No folder open</div>
            <button style={styles.emptyBtn} onClick={newFileNoWorkspace}>New File…</button>
            <button style={styles.emptyBtn} onClick={newFolderNoWorkspace}>New Folder…</button>
            <button style={styles.emptyBtn} onClick={openFolder}>Open Folder…</button>
          </div>
        )}
        {hasRoots &&
          rootDirs.map((dir) => (
            <RootNode
              key={dir}
              rootDir={dir}
              onOpenFile={onOpenFile}
              onRemove={onRemoveRoot}
              onContextMenu={handleContextMenu}
              onStartCreate={startCreate}
              gitStatusMap={gitStatusMap}
              activeFilePath={activeFilePath}
              reveal={reveal}
              creating={creating}
              onClearCreating={clearCreating}
              selectedPath={selected?.path || null}
              onSelect={setSelected}
            />
          ))}
      </div>

      {ctxMenu && (
        <ContextMenu
          x={ctxMenu.x}
          y={ctxMenu.y}
          entry={ctxMenu.entry}
          parentPath={ctxMenu.parentPath}
          refreshParent={ctxMenu.refreshParent}
          refreshSelf={ctxMenu.refreshSelf}
          onClose={() => setCtxMenu(null)}
          onStartCreate={startCreate}
        />
      )}
    </div>
  );
}

const styles = {
  wrap: { display: "flex", flexDirection: "column", height: "100%" },
  header: {
    padding: "8px 12px",
    display: "flex",
    flexDirection: "column",
    gap: 6,
    borderBottom: "1px solid var(--border)",
  },
  headerTop: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  },
  headerActions: {
    display: "flex",
    gap: 4,
    justifyContent: "flex-end",
  },
  iconBtn: {
    width: 24,
    height: 24,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "var(--text-2)",
    background: "transparent",
    border: "none",
    borderRadius: 5,
    cursor: "pointer",
    flexShrink: 0,
    padding: 0,
  },
  headerLabel: {
    fontSize: "11px",
    letterSpacing: "0.06em",
    textTransform: "uppercase",
    color: "var(--text-2)",
  },
  openBtn: {
    fontSize: "11px",
    color: "var(--text-1)",
    padding: "4px 9px",
    borderRadius: "var(--r-sm)",
    border: "1px solid var(--border)",
    cursor: "pointer",
    whiteSpace: "nowrap",
  },
  body: { flex: 1, overflow: "auto", padding: "6px 0" },
  empty: {
    padding: "12px",
    display: "flex",
    flexDirection: "column",
    alignItems: "stretch",
    gap: 6,
  },
  emptyText: { fontSize: "12px", color: "var(--text-2)", marginBottom: 2 },
  emptyBtn: {
    fontSize: "12px",
    color: "var(--text-1)",
    padding: "6px 9px",
    borderRadius: "var(--r-sm)",
    border: "1px solid var(--border)",
    background: "transparent",
    cursor: "pointer",
    textAlign: "left",
  },
  rowActionBtn: {
    width: 20,
    height: 20,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "var(--text-2)",
    background: "transparent",
    border: "none",
    borderRadius: 4,
    cursor: "pointer",
    padding: 0,
    flexShrink: 0,
  },
  rootRow: {
    display: "flex",
    alignItems: "center",
    gap: "4px",
    padding: "5px 8px",
    margin: "0 6px 2px",
    borderRadius: "var(--r-sm)",
    cursor: "pointer",
    fontSize: "11px",
    fontWeight: 600,
    letterSpacing: "0.05em",
    textTransform: "uppercase",
    color: "var(--text-1)",
    fontFamily: "var(--font-ui)",
    transition: "background var(--dur) var(--ease)",
  },
  rootName: { flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" },
  rootRemove: {
    width: "16px",
    height: "16px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "14px",
    color: "var(--text-2)",
    borderRadius: "4px",
    cursor: "pointer",
    lineHeight: 1,
    padding: 0,
    flexShrink: 0,
  },
  row: {
    display: "flex",
    alignItems: "center",
    gap: "5px",
    padding: "4px 8px",
    margin: "1px 6px",
    borderRadius: "var(--r-sm)",
    cursor: "pointer",
    fontSize: "12.5px",
    color: "var(--text-1)",
    fontFamily: "var(--font-mono)",
    transition: "background var(--dur) var(--ease)",
  },
  caret: { width: "12px", color: "var(--text-2)", fontSize: "10px", transition: "color var(--dur) var(--ease)" },
  name: { whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" },
};
