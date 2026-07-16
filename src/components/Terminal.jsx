import { useEffect, useRef, useState } from "react";
import { Terminal as XTerm } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebglAddon } from "@xterm/addon-webgl";
import "@xterm/xterm/css/xterm.css";
import { ptyCreate, ptyWrite, ptyResize, ptyKill, onPtyOutput, onPtyClosed } from "../lib/tauri.js";

// Normalise a shell path to a short, friendly tab label.
function shellLabelFor(shellPath) {
  const base = shellPath.split(/[/\\]/).pop().replace(/\.exe$/i, "").toLowerCase();
  if (base.includes("powershell") || base === "pwsh") return "pwsh";
  return base || "shell";
}

// ── Single terminal instance (no header — tabs live in the parent) ────────────

export default function Terminal({ onReady }) {
  const containerRef  = useRef(null);
  const termRef       = useRef(null);
  const sessionIdRef  = useRef(null);
  const unlistenRef   = useRef(null);  // unlisten pty-output
  const unlistenClRef = useRef(null);  // unlisten pty-closed
  const terminatedRef = useRef(false); // true when shell has exited

  useEffect(() => {
    if (!containerRef.current) return;

    // Shared handler ref so both init() and cleanup use the same function.
    let runCmdHandler = null;

    const term = new XTerm({
      fontFamily: "JetBrains Mono, Consolas, monospace",
      fontSize: 12,
      cursorBlink: true,
      scrollback: 5000,
      theme: {
        background:          "#080812",
        foreground:          "#e8e8f4",
        cursor:              "#7c6ef8",
        cursorAccent:        "#080812",
        selectionBackground: "#28215a",
        black:   "#141428", red:     "#f06060",
        green:   "#4de8a0", yellow:  "#f5c040",
        blue:    "#5b8af5", magenta: "#c085f5",
        cyan:    "#50d8f0", white:   "#e8e8f4",
        brightBlack:   "#484870", brightRed:    "#f07878",
        brightGreen:   "#70f0b0", brightYellow: "#f8d870",
        brightBlue:    "#80a8f8", brightMagenta:"#d0a0f8",
        brightCyan:    "#78e8f8", brightWhite:  "#ffffff",
      },
    });

    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(containerRef.current);

    // GPU-rendered terminal (Zed-style speed). WebGL contexts can be lost
    // (driver reset, too many contexts) — dispose the addon and xterm falls
    // back to its DOM renderer automatically. Never fatal.
    try {
      const webgl = new WebglAddon();
      webgl.onContextLoss(() => webgl.dispose());
      term.loadAddon(webgl);
    } catch { /* no WebGL available — DOM renderer is fine */ }

    fit.fit();

    termRef.current = term;

    const startSession = async () => {
      terminatedRef.current = false;

      if (!unlistenRef.current) {
        unlistenRef.current = await onPtyOutput((event) => {
          if (event.payload.id === sessionIdRef.current) {
            term.write(event.payload.data);
            // Bridge: let AIPanel observe output when in /terminal mode
            window.dispatchEvent(new CustomEvent("vagent-terminal-output", {
              detail: { data: event.payload.data },
            }));
          }
        });
      }

      const cols = Math.max(term.cols, 10);
      const rows = Math.max(term.rows, 2);
      const result = await ptyCreate(null, cols, rows);

      sessionIdRef.current = result.id;
      onReady?.(result.id, shellLabelFor(result.shell));
    };

    const init = async () => {
      try {
        await startSession();

        unlistenClRef.current = await onPtyClosed((event) => {
          if (event.payload !== sessionIdRef.current) return;
          terminatedRef.current = true;
          sessionIdRef.current  = null;
          term.writeln("\r\n\x1b[33m─── Shell terminated. Press any key to restart ───\x1b[0m");
        });

        term.onData(async (data) => {
          if (terminatedRef.current) {
            terminatedRef.current = false;
            term.writeln("\r");
            try { await startSession(); }
            catch (e) { term.writeln(`\r\n\x1b[31mFailed to restart: ${e}\x1b[0m`); }
            return;
          }
          const id = sessionIdRef.current;
          if (id) ptyWrite(id, data).catch(() => {});
        });

        // Listen for commands dispatched by AIPanel in /terminal mode
        runCmdHandler = (e) => {
          const id = sessionIdRef.current;
          if (id && e.detail?.command) {
            ptyWrite(id, e.detail.command + "\r").catch(() => {});
          }
        };
        window.addEventListener("vagent-run-in-terminal", runCmdHandler);
      } catch (e) {
        term.writeln(`\r\n\x1b[31mFailed to start terminal: ${e}\x1b[0m`);
      }
    };

    init();

    const refit = () => {
      try {
        fit.fit();
        const id = sessionIdRef.current;
        if (id) ptyResize(id, term.cols, term.rows).catch(() => {});
      } catch { /* ignore */ }
    };

    // ResizeObserver catches panel-drag + tab show/hide (display:none → block)
    const ro = new ResizeObserver(refit);
    ro.observe(containerRef.current);
    window.addEventListener("resize", refit);

    return () => {
      window.removeEventListener("resize", refit);
      if (runCmdHandler) window.removeEventListener("vagent-run-in-terminal", runCmdHandler);
      ro.disconnect();
      if (unlistenRef.current)   { unlistenRef.current();   unlistenRef.current   = null; }
      if (unlistenClRef.current) { unlistenClRef.current(); unlistenClRef.current = null; }
      if (sessionIdRef.current)  { ptyKill(sessionIdRef.current).catch(() => {}); sessionIdRef.current = null; }
      term.dispose();
      termRef.current = null;
    };
  }, []);

  return <div ref={containerRef} style={styles.term} />;
}

// ── Terminal tab bar ──────────────────────────────────────────────────────────

export function TerminalTabs({ terminals, activeId, onSelect, onClose, onAdd, onRename, maxReached }) {
  const [editingId, setEditingId] = useState(null);
  const [draft, setDraft] = useState("");

  const startEdit = (t) => {
    setEditingId(t.id);
    setDraft(t.customTitle ?? t.shellLabel ?? "terminal");
  };
  const commitEdit = () => {
    if (editingId != null) onRename(editingId, draft.trim());
    setEditingId(null);
  };

  return (
    <div style={tabStyles.bar}>
      {terminals.map((t) => {
        const active = t.id === activeId;
        const title = t.customTitle ?? t.shellLabel ?? "terminal";
        return (
          <div
            key={t.id}
            className="tab"
            style={{
              ...tabStyles.tab,
              background: active ? "var(--bg-0)" : "transparent",
              borderBottom: active ? "2px solid var(--accent)" : "2px solid transparent",
              opacity: active ? 1 : 0.6,
            }}
            onClick={() => onSelect(t.id)}
            onDoubleClick={() => startEdit(t)}
            title="Double-click to rename"
          >
            {editingId === t.id ? (
              <input
                autoFocus
                style={tabStyles.editInput}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onBlur={commitEdit}
                onKeyDown={(e) => {
                  if (e.key === "Enter") commitEdit();
                  if (e.key === "Escape") setEditingId(null);
                }}
                onClick={(e) => e.stopPropagation()}
              />
            ) : (
              <span style={tabStyles.name}>{title}</span>
            )}
            <button
              style={tabStyles.close}
              title="Close terminal"
              onClick={(e) => { e.stopPropagation(); onClose(t.id); }}
            >
              ×
            </button>
          </div>
        );
      })}
      <button
        style={{ ...tabStyles.add, opacity: maxReached ? 0.35 : 1, cursor: maxReached ? "not-allowed" : "pointer" }}
        onClick={maxReached ? undefined : onAdd}
        title={maxReached ? "Maximum 6 terminals" : "New terminal"}
      >
        +
      </button>
    </div>
  );
}

const tabStyles = {
  bar: {
    display: "flex",
    alignItems: "stretch",
    background: "var(--bg-1)",
    borderBottom: "1px solid var(--border)",
    minHeight: "30px",
    overflowX: "auto",
    overflowY: "hidden",
    flexShrink: 0,
  },
  tab: {
    display: "flex",
    alignItems: "center",
    gap: "7px",
    padding: "0 8px 0 13px",
    borderRight: "1px solid var(--border)",
    fontSize: "11px",
    fontFamily: "var(--font-mono)",
    color: "var(--text-1)",
    cursor: "pointer",
    whiteSpace: "nowrap",
    flexShrink: 0,
    userSelect: "none",
    transition: "background var(--dur) var(--ease), opacity var(--dur) var(--ease)",
  },
  name: { color: "var(--text-0)" },
  editInput: {
    width: "84px",
    fontSize: "11px",
    fontFamily: "var(--font-mono)",
    color: "var(--text-0)",
    background: "var(--bg-2)",
    border: "1px solid var(--accent)",
    borderRadius: "var(--r-xs)",
    padding: "1px 5px",
    outline: "none",
  },
  close: {
    width: "17px",
    height: "17px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "14px",
    color: "var(--text-2)",
    borderRadius: "var(--r-xs)",
    lineHeight: 1,
    padding: 0,
    cursor: "pointer",
  },
  add: {
    width: "28px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "14px",
    color: "var(--text-2)",
    background: "transparent",
    border: "none",
    flexShrink: 0,
    opacity: 0.7,
    transition: "opacity var(--dur) var(--ease)",
  },
};

const styles = {
  term: { width: "100%", height: "100%", minHeight: 0, padding: "6px 0 0 8px", overflow: "hidden" },
};
