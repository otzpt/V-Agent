import { memo } from "react";

const LANG_DISPLAY = {
  js: "JavaScript", jsx: "JavaScript", ts: "TypeScript", tsx: "TypeScript",
  py: "Python", rs: "Rust", c: "C", h: "C", cpp: "C++", cs: "C#",
  go: "Go", java: "Java", rb: "Ruby", php: "PHP", html: "HTML",
  css: "CSS", json: "JSON", md: "Markdown", sh: "Shell",
  ps1: "PowerShell", yaml: "YAML", yml: "YAML", toml: "TOML", xml: "XML",
  kt: "Kotlin", swift: "Swift", dart: "Dart", lua: "Lua", r: "R",
  scala: "Scala", groovy: "Groovy", coffee: "CoffeeScript",
  sql: "SQL", graphql: "GraphQL", ino: "Arduino",
};

function langFor(fileName) {
  if (!fileName) return null;
  const ext = fileName.split(".").pop().toLowerCase();
  return LANG_DISPLAY[ext] || null;
}

function timeAgo(ms) {
  if (!ms) return null;
  const s = Math.floor((Date.now() - ms) / 1000);
  if (s < 5)    return "just now";
  if (s < 60)   return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

// Thin vertical separator between status bar sections
function Sep() {
  return <div style={{ width: 1, height: 12, background: "rgba(255,255,255,0.18)", margin: "0 3px", flexShrink: 0 }} />;
}

// ── Hackatime indicator ───────────────────────────────────────────────────────

function HkIndicator({ hackatimeStatus, onOpenSettings }) {
  if (!hackatimeStatus) return null;

  const { status, error, lastSent } = hackatimeStatus;

  let color, label, tooltip;
  if (status === "tracking") {
    color   = "var(--ok)";
    label   = "tracking";
    tooltip = lastSent ? `Last heartbeat: ${timeAgo(lastSent)}` : "Hackatime active";
  } else if (status === "paused") {
    color   = "var(--warn)";
    label   = "paused";
    tooltip = "Hackatime is disabled — click to open Settings";
  } else {
    color   = "var(--err)";
    label   = "error";
    tooltip = error ? `Hackatime error: ${error}` : "Heartbeat failed — click to open Settings";
  }

  return (
    <div
      className="va-status-item"
      title={tooltip}
      onClick={onOpenSettings}
      style={{ cursor: "pointer", gap: 5 }}
    >
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none"
        stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </svg>
      <span style={{ color, fontSize: 10, fontFamily: "var(--font-mono)" }}>
        {label}
      </span>
    </div>
  );
}

// ── StatusBar ─────────────────────────────────────────────────────────────────

export default memo(function StatusBar({ cursorPos, activeFile, provider, hackatimeStatus, onOpenSettings, gitBranch, problemCount }) {
  const lang = activeFile ? langFor(activeFile.name) : null;
  const hasErrors   = problemCount?.errors   > 0;
  const hasWarnings = problemCount?.warnings > 0;

  return (
    <div className="va-status-bar">
      {/* ── Left ── */}
      <div style={{ display: "flex", alignItems: "center" }}>
        <div className="va-status-item" style={{ fontWeight: 700, letterSpacing: "0.1em", fontSize: 10, opacity: 0.75, fontFamily: "var(--font-mono)", textTransform: "uppercase" }}>
          V-Agent
        </div>

        {/* Git branch */}
        {gitBranch && (
          <>
            <Sep />
            <div className="va-status-item" title={`Branch: ${gitBranch}`}>
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="6" y1="3" x2="6" y2="15"/>
                <circle cx="18" cy="6" r="3"/>
                <circle cx="6" cy="18" r="3"/>
                <path d="M18 9a9 9 0 01-9 9"/>
              </svg>
              {gitBranch}
            </div>
          </>
        )}

        {/* Problem counts */}
        {(hasErrors || hasWarnings) && (
          <>
            <Sep />
            {hasErrors && (
              <div className="va-status-item" title={`${problemCount.errors} error(s)`}
                style={{ color: "#ffc0c0" }}>
                ⊗ {problemCount.errors}
              </div>
            )}
            {hasWarnings && (
              <div className="va-status-item" title={`${problemCount.warnings} warning(s)`}
                style={{ color: "#ffe8a0" }}>
                ⚠ {problemCount.warnings}
              </div>
            )}
          </>
        )}

        {provider && provider !== "backend" && (
          <>
            <Sep />
            <div className="va-status-item" title="Active AI provider">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="3" />
                <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M17.66 6.34l-1.41 1.41M4.93 19.07l1.41-1.41" />
              </svg>
              {provider}
            </div>
          </>
        )}
      </div>

      {/* ── Right ── */}
      <div style={{ display: "flex", alignItems: "center" }}>
        <HkIndicator hackatimeStatus={hackatimeStatus} onOpenSettings={onOpenSettings} />

        {lang && (
          <>
            <Sep />
            <div className="va-status-item" title="File language">{lang}</div>
          </>
        )}

        {cursorPos && (
          <>
            <Sep />
            <div className="va-status-item" title="Cursor position" style={{ fontFamily: "var(--font-mono)", fontSize: 10 }}>
              Ln {cursorPos.line}, Col {cursorPos.col}
            </div>
          </>
        )}

        <Sep />
        <div className="va-status-item" title="File encoding">UTF-8</div>
      </div>
    </div>
  );
});
