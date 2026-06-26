// Search-in-files panel — shown in the sidebar when activeView === "search".
// Backed by the Rust `search_in_files` / `replace_in_file` commands.

import { useState, useCallback, useEffect, useRef, useMemo, memo } from "react";
import { searchInFiles, replaceInFile } from "../lib/tauri.js";

const MAX_HITS = 2000;

// Relative path + file name of a hit, w.r.t. the deepest matching workspace root.
function relDisplay(file, rootDirs) {
  const fwd = (p) => p.replace(/\\/g, "/");
  const f = fwd(file);
  let best = null;
  for (const r of rootDirs) {
    const rr = fwd(r);
    if (f.toLowerCase().startsWith(rr.toLowerCase() + "/") && (!best || rr.length > best.length)) {
      best = rr;
    }
  }
  const name = file.split(/[/\\]/).pop();
  if (!best) return { name, dir: "" };
  const rel = f.slice(best.length + 1);
  const dir = rel.slice(0, rel.length - name.length).replace(/\/+$/, "");
  return { name, dir };
}

// Small square toggle button (case-sensitive / regex).
function Toggle({ on, onClick, title, children }) {
  return (
    <button
      title={title}
      onClick={onClick}
      style={{
        width: "22px",
        height: "22px",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: "4px",
        fontSize: "11px",
        fontFamily: "var(--font-mono)",
        flexShrink: 0,
        color: on ? "var(--accent)" : "var(--text-2)",
        background: on ? "var(--accent-dim)" : "transparent",
        border: on ? "1px solid var(--accent)" : "1px solid transparent",
        cursor: "pointer",
      }}
    >
      {children}
    </button>
  );
}

// Renders a result line with the matched span highlighted. Leading indentation is
// trimmed for readability and the column adjusted accordingly.
function Preview({ preview, col, length }) {
  const lead = preview.length - preview.trimStart().length;
  const text = preview.slice(lead);
  const start = Math.max(0, col - 1 - lead);
  const end = Math.min(text.length, start + length);
  return (
    <span style={rs.preview}>
      <span>{text.slice(0, start)}</span>
      <span style={rs.hit}>{text.slice(start, end)}</span>
      <span>{text.slice(end)}</span>
    </span>
  );
}

const Group = memo(function Group({
  file, hits, rootDirs, collapsed, onToggleCollapse, onOpenHit, replaceEnabled, onReplaceHit,
}) {
  const { name, dir } = relDisplay(file, rootDirs);
  return (
    <div style={gs.group}>
      <div style={gs.header} onClick={() => onToggleCollapse(file)} title={file}>
        <span style={gs.chevron}>{collapsed ? "▸" : "▾"}</span>
        <span style={gs.fileName}>{name}</span>
        {dir && <span style={gs.fileDir}>{dir}</span>}
        <span style={gs.count}>{hits.length}</span>
      </div>
      {!collapsed && hits.map((h, i) => (
        <div
          key={`${h.line}:${h.col}:${i}`}
          style={rs.row}
          onClick={() => onOpenHit(h)}
          title={`${file}:${h.line}:${h.col}`}
        >
          <span style={rs.line}>{h.line}</span>
          <Preview preview={h.preview} col={h.col} length={h.length} />
          {replaceEnabled && (
            <button
              style={rs.replaceBtn}
              title="Replace this occurrence"
              onClick={(e) => { e.stopPropagation(); onReplaceHit(h); }}
            >
              ⇄
            </button>
          )}
        </div>
      ))}
    </div>
  );
});

export default function SearchPanel({ rootDirs = [], onOpenResult, focusSignal }) {
  const [query, setQuery]               = useState("");
  const [replaceText, setReplaceText]   = useState("");
  const [caseSensitive, setCaseSensitive] = useState(false);
  const [isRegex, setIsRegex]           = useState(false);
  const [results, setResults]           = useState([]);
  const [collapsed, setCollapsed]       = useState(() => new Set());
  const [loading, setLoading]           = useState(false);
  const [error, setError]               = useState(null);
  const [searched, setSearched]         = useState(false);

  const inputRef = useRef(null);

  // Autofocus on mount and whenever the activity bar re-triggers Search.
  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, [focusSignal]);

  const runSearch = useCallback(async (q, cs, rx) => {
    if (!q) { setResults([]); setError(null); setSearched(false); return; }
    if (!rootDirs.length) { setResults([]); setError("Open a folder first"); setSearched(true); return; }
    setLoading(true);
    setError(null);
    try {
      const all = [];
      for (const root of rootDirs) {
        const hits = await searchInFiles(root, q, cs, rx);
        all.push(...hits);
      }
      setResults(all);
      setSearched(true);
    } catch (e) {
      setError(String(e));
      setResults([]);
      setSearched(true);
    } finally {
      setLoading(false);
    }
  }, [rootDirs]);

  // Debounced search on query / toggle changes.
  useEffect(() => {
    const t = setTimeout(() => runSearch(query, caseSensitive, isRegex), 300);
    return () => clearTimeout(t);
  }, [query, caseSensitive, isRegex, runSearch]);

  const groups = useMemo(() => {
    const m = new Map();
    for (const h of results) {
      if (!m.has(h.file)) m.set(h.file, []);
      m.get(h.file).push(h);
    }
    return Array.from(m.entries());
  }, [results]);

  const toggleCollapse = useCallback((file) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      next.has(file) ? next.delete(file) : next.add(file);
      return next;
    });
  }, []);

  const replaceHit = useCallback(async (h) => {
    const short = h.file.split(/[/\\]/).pop();
    const ok = window.confirm(
      `Replace "${h.match_text}" → "${replaceText}"\nin ${short}:${h.line}?`
    );
    if (!ok) return;
    try {
      await replaceInFile(h.file, h.line, h.col, h.length, h.match_text, replaceText);
      window.notify?.("Replaced 1 occurrence", "success");
      runSearch(query, caseSensitive, isRegex); // refresh results
    } catch (e) {
      window.notify?.(String(e), "error");
    }
  }, [replaceText, query, caseSensitive, isRegex, runSearch]);

  const onKeyDown = useCallback((e) => {
    if (e.key === "Enter") { e.preventDefault(); runSearch(query, caseSensitive, isRegex); }
    if (e.key === "Escape") { setQuery(""); }
  }, [query, caseSensitive, isRegex, runSearch]);

  const total = results.length;
  const replaceEnabled = replaceText.length > 0;

  return (
    <div style={st.wrap}>
      <div style={st.header}>
        <span style={st.headerLabel}>Search</span>
      </div>

      <div style={st.controls}>
        <div style={st.inputRow}>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search"
            spellCheck={false}
            style={st.input}
          />
          <Toggle on={caseSensitive} onClick={() => setCaseSensitive((v) => !v)} title="Match case">Aa</Toggle>
          <Toggle on={isRegex} onClick={() => setIsRegex((v) => !v)} title="Use regular expression">.*</Toggle>
        </div>
        <div style={st.inputRow}>
          <input
            value={replaceText}
            onChange={(e) => setReplaceText(e.target.value)}
            placeholder="Replace"
            spellCheck={false}
            style={st.input}
          />
        </div>
      </div>

      <div style={st.status}>
        {loading
          ? "Searching…"
          : error
            ? <span style={{ color: "var(--err)" }}>{error}</span>
            : searched
              ? (total === 0
                  ? "No results"
                  : `${total}${total >= MAX_HITS ? "+" : ""} result${total === 1 ? "" : "s"} in ${groups.length} file${groups.length === 1 ? "" : "s"}`)
              : "Type to search across the workspace"}
      </div>

      <div style={st.results}>
        {groups.map(([file, hits]) => (
          <Group
            key={file}
            file={file}
            hits={hits}
            rootDirs={rootDirs}
            collapsed={collapsed.has(file)}
            onToggleCollapse={toggleCollapse}
            onOpenHit={(h) => onOpenResult?.(h.file, h.line, h.col, h.length)}
            replaceEnabled={replaceEnabled}
            onReplaceHit={replaceHit}
          />
        ))}
      </div>
    </div>
  );
}

const st = {
  wrap: { display: "flex", flexDirection: "column", height: "100%", minHeight: 0 },
  header: {
    height: "32px",
    display: "flex",
    alignItems: "center",
    padding: "0 12px",
    flexShrink: 0,
    borderBottom: "1px solid var(--border)",
  },
  headerLabel: {
    fontSize: "10px",
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    color: "var(--text-2)",
    fontFamily: "var(--font-ui)",
  },
  controls: { padding: "8px", display: "flex", flexDirection: "column", gap: "6px", flexShrink: 0 },
  inputRow: { display: "flex", alignItems: "center", gap: "4px" },
  input: {
    flex: 1,
    minWidth: 0,
    height: "28px",
    padding: "0 9px",
    fontSize: "12px",
    fontFamily: "var(--font-mono)",
    color: "var(--text-0)",
    background: "var(--bg-0)",
    border: "1px solid var(--border)",
    borderRadius: "var(--r-sm)",
    outline: "none",
  },
  status: {
    padding: "2px 12px 6px",
    fontSize: "11px",
    color: "var(--text-2)",
    fontFamily: "var(--font-ui)",
    flexShrink: 0,
  },
  results: { flex: 1, overflow: "auto", minHeight: 0 },
};

const gs = {
  group: { marginBottom: "2px" },
  header: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    padding: "3px 10px",
    cursor: "pointer",
    userSelect: "none",
    position: "sticky",
    top: 0,
    background: "var(--bg-1)",
    zIndex: 1,
  },
  chevron: { fontSize: "9px", color: "var(--text-2)", width: "10px", flexShrink: 0 },
  fileName: { fontSize: "12px", color: "var(--text-0)", fontFamily: "var(--font-mono)", flexShrink: 0 },
  fileDir: {
    fontSize: "10px",
    color: "var(--text-2)",
    fontFamily: "var(--font-mono)",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    flex: 1,
  },
  count: {
    marginLeft: "auto",
    fontSize: "10px",
    color: "var(--text-2)",
    fontFamily: "var(--font-mono)",
    flexShrink: 0,
  },
};

const rs = {
  row: {
    display: "flex",
    alignItems: "baseline",
    gap: "8px",
    padding: "2px 10px 2px 26px",
    cursor: "pointer",
    fontSize: "11px",
    fontFamily: "var(--font-mono)",
  },
  line: { color: "var(--text-2)", flexShrink: 0, minWidth: "26px", textAlign: "right" },
  preview: {
    color: "var(--text-1)",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    flex: 1,
  },
  hit: { background: "var(--accent-dim)", color: "var(--accent)", borderRadius: "2px" },
  replaceBtn: {
    flexShrink: 0,
    width: "18px",
    height: "18px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "12px",
    color: "var(--text-2)",
    background: "transparent",
    border: "none",
    borderRadius: "3px",
    cursor: "pointer",
  },
};
