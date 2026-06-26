import { useState, useEffect, useRef, useMemo } from "react";

// Highlights the matched substring of a command title.
function Highlight({ text, query }) {
  const q = query.trim();
  if (!q) return text;
  const idx = text.toLowerCase().indexOf(q.toLowerCase());
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <span style={{ color: "var(--accent)", fontWeight: 600 }}>{text.slice(idx, idx + q.length)}</span>
      {text.slice(idx + q.length)}
    </>
  );
}

// Centered command palette. `commands` is [{ id, title, hint?, run }].
// Pure substring fuzzy match (case-insensitive). Keyboard: ↑/↓ navigate,
// Enter executes, Escape closes.

export default function CommandPalette({ commands, onClose }) {
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const inputRef = useRef(null);
  const listRef  = useRef(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return commands;
    return commands.filter((c) => c.title.toLowerCase().includes(q));
  }, [query, commands]);

  // Keep selection in range whenever the filtered list changes
  useEffect(() => { setIndex(0); }, [query]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Scroll the selected item into view
  useEffect(() => {
    const el = listRef.current?.children[index];
    el?.scrollIntoView({ block: "nearest" });
  }, [index]);

  const run = (cmd) => {
    onClose();
    // Defer so the overlay unmounts before the action (dialogs, prompts, etc.)
    setTimeout(() => cmd?.run?.(), 0);
  };

  const onKeyDown = (e) => {
    if (e.key === "Escape") { e.preventDefault(); onClose(); }
    else if (e.key === "ArrowDown") {
      e.preventDefault();
      setIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const cmd = filtered[index];
      if (cmd) run(cmd);
    }
  };

  return (
    <div style={s.overlay} onMouseDown={onClose}>
      <div style={s.panel} onMouseDown={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          style={s.input}
          placeholder="Type a command…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <div ref={listRef} style={s.list}>
          {filtered.length === 0 && (
            <div style={s.empty}>No matching commands</div>
          )}
          {filtered.map((c, i) => (
            <div
              key={c.id}
              style={{
                ...s.item,
                background: i === index ? "var(--accent-dim)" : "transparent",
                boxShadow: i === index ? "inset 2px 0 0 0 var(--accent)" : "none",
              }}
              onMouseEnter={() => setIndex(i)}
              onClick={() => run(c)}
            >
              <span style={{ ...s.itemTitle, color: i === index ? "var(--text-0)" : "var(--text-1)" }}>
                <Highlight text={c.title} query={query} />
              </span>
              {c.hint && <span style={s.itemHint}>{c.hint}</span>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const s = {
  overlay: {
    position: "fixed",
    inset: 0,
    background: "rgba(0,0,0,0.42)",
    backdropFilter: "blur(3px)",
    WebkitBackdropFilter: "blur(3px)",
    zIndex: 10001,
    display: "flex",
    justifyContent: "center",
    alignItems: "flex-start",
    paddingTop: "12vh",
    animation: "va-fade 120ms var(--ease)",
  },
  panel: {
    width: "580px",
    maxWidth: "calc(100vw - 32px)",
    background: "var(--bg-1)",
    border: "1px solid var(--border)",
    borderRadius: "var(--r-lg)",
    boxShadow: "var(--shadow-lg)",
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
    animation: "va-pop 150ms var(--ease)",
  },
  input: {
    padding: "14px 18px",
    fontSize: "15px",
    fontFamily: "var(--font-ui)",
    color: "var(--text-0)",
    background: "transparent",
    border: "none",
    borderBottom: "1px solid var(--border)",
    outline: "none",
  },
  list: { maxHeight: "340px", overflowY: "auto", padding: "6px" },
  empty: { padding: "20px", fontSize: "13px", color: "var(--text-2)", fontFamily: "var(--font-ui)", textAlign: "center" },
  item: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "12px",
    padding: "9px 12px",
    borderRadius: "var(--r-sm)",
    cursor: "pointer",
    transition: "background var(--dur) var(--ease)",
  },
  itemTitle: { fontSize: "13px", fontFamily: "var(--font-ui)" },
  itemHint: {
    fontSize: "10.5px",
    color: "var(--text-2)",
    fontFamily: "var(--font-mono)",
    flexShrink: 0,
    background: "var(--bg-2)",
    padding: "2px 7px",
    borderRadius: "var(--r-xs)",
    border: "1px solid var(--border)",
  },
};
