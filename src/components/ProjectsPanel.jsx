// Recent / pinned projects — shown in the sidebar when activeView === "projects".
// Stored in config.json under `recent_projects: [{ path, name, lastOpened, pinned }]`.

import { useState, useEffect, useCallback } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { getConfig, saveConfig, listDir } from "../lib/tauri.js";

// extension → display language (for the "main language" badge)
const EXT_LANG = {
  py: "Python", js: "JavaScript", jsx: "JavaScript", ts: "TypeScript", tsx: "TypeScript",
  rs: "Rust", c: "C", h: "C", cpp: "C++", cs: "C#", go: "Go", java: "Java", rb: "Ruby",
  php: "PHP", html: "HTML", css: "CSS", json: "JSON", md: "Markdown", sh: "Shell",
  ps1: "PowerShell", yaml: "YAML", yml: "YAML", toml: "TOML", swift: "Swift", kt: "Kotlin",
};

// Detect the dominant language by counting file extensions (top level + one deep).
async function detectLanguage(path) {
  const counts = {};
  const bump = (name) => {
    const ext = name.includes(".") ? name.split(".").pop().toLowerCase() : "";
    const lang = EXT_LANG[ext];
    if (lang) counts[lang] = (counts[lang] || 0) + 1;
  };
  try {
    const top = await listDir(path);
    const subdirs = [];
    for (const e of top) {
      if (e.is_dir) { if (subdirs.length < 4) subdirs.push(e.path); }
      else bump(e.name);
    }
    for (const d of subdirs) {
      try { (await listDir(d)).forEach((e) => { if (!e.is_dir) bump(e.name); }); } catch { /* ignore */ }
    }
  } catch { return null; }
  let best = null, max = 0;
  for (const [lang, n] of Object.entries(counts)) if (n > max) { max = n; best = lang; }
  return best;
}

// Compact relative time ("just now", "5m ago", "3d ago", or a date).
function relTime(ms) {
  if (!ms) return "";
  const diff = Date.now() - ms;
  const s = Math.floor(diff / 1000);
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d}d ago`;
  return new Date(ms).toLocaleDateString();
}

const MAX_RECENT = 10;

// Normalise + cap the list: all pinned kept, unpinned trimmed to MAX_RECENT.
function normaliseList(list) {
  const arr = Array.isArray(list) ? list : [];
  const pinned   = arr.filter((p) => p.pinned);
  const unpinned = arr.filter((p) => !p.pinned).slice(0, MAX_RECENT);
  return [...pinned, ...unpinned];
}

function ProjectRow({ proj, lang, onOpen, onRemove, onTogglePin }) {
  return (
    <div style={ps.row} onClick={() => onOpen(proj.path)} title={proj.path}>
      <div style={ps.rowMain}>
        <div style={ps.rowTop}>
          <span style={ps.name}>{proj.name}</span>
          {lang && <span style={ps.lang}>{lang}</span>}
        </div>
        <span style={ps.path}>{proj.path}</span>
        <span style={ps.meta}>{relTime(proj.lastOpened)}</span>
      </div>
      <div style={ps.rowActions}>
        <button
          className="va-btn"
          style={{ ...ps.iconBtn, color: proj.pinned ? "var(--accent)" : "var(--text-2)" }}
          title={proj.pinned ? "Unpin" : "Pin"}
          onClick={(e) => { e.stopPropagation(); onTogglePin(proj.path); }}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill={proj.pinned ? "currentColor" : "none"}
            stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2l2.4 7.4H22l-6 4.6 2.3 7.4L12 17l-6.3 4.4L8 14 2 9.4h7.6z" />
          </svg>
        </button>
        <button
          className="va-btn"
          style={{ ...ps.iconBtn, color: "var(--text-2)" }}
          title="Remove from list"
          onClick={(e) => { e.stopPropagation(); onRemove(proj.path); }}
        >×</button>
      </div>
    </div>
  );
}

export default function ProjectsPanel({ onOpenProject }) {
  const [projects, setProjects] = useState([]);
  const [langs, setLangs]       = useState({}); // path -> language

  // Load list from config on mount.
  useEffect(() => {
    let alive = true;
    getConfig().then((cfg) => {
      if (!alive) return;
      const list = normaliseList(cfg?.recent_projects);
      setProjects(list);
      list.forEach((p) => {
        detectLanguage(p.path).then((lang) => {
          if (alive && lang) setLangs((prev) => ({ ...prev, [p.path]: lang }));
        });
      });
    }).catch(() => {});
    return () => { alive = false; };
  }, []);

  const persist = useCallback(async (next) => {
    setProjects(next);
    try {
      const cfg = (await getConfig()) || {};
      await saveConfig({ ...cfg, recent_projects: next });
    } catch { /* silent */ }
  }, []);

  const removeProject = useCallback((path) => {
    persist(projects.filter((p) => p.path !== path));
  }, [projects, persist]);

  const togglePin = useCallback((path) => {
    persist(normaliseList(projects.map((p) => (p.path === path ? { ...p, pinned: !p.pinned } : p))));
  }, [projects, persist]);

  const openDialog = useCallback(async () => {
    const sel = await open({ directory: true, multiple: false });
    if (sel && typeof sel === "string") onOpenProject(sel);
  }, [onOpenProject]);

  const pinned   = projects.filter((p) => p.pinned);
  const recent   = projects.filter((p) => !p.pinned);

  const renderRow = (p) => (
    <ProjectRow
      key={p.path}
      proj={p}
      lang={langs[p.path]}
      onOpen={onOpenProject}
      onRemove={removeProject}
      onTogglePin={togglePin}
    />
  );

  return (
    <div style={ps.wrap}>
      <div style={ps.header}>
        <span style={ps.headerLabel}>Projects</span>
        <button style={ps.openBtn} onClick={openDialog} title="Open a folder">Open folder…</button>
      </div>

      <div style={ps.body}>
        {projects.length === 0 && (
          <div style={ps.empty}>No recent projects yet.<br />Open a folder to get started.</div>
        )}

        {pinned.length > 0 && (
          <section>
            <div style={ps.sectionHead}>Pinned</div>
            {pinned.map(renderRow)}
          </section>
        )}

        {recent.length > 0 && (
          <section>
            <div style={ps.sectionHead}>Recent</div>
            {recent.map(renderRow)}
          </section>
        )}
      </div>
    </div>
  );
}

const ps = {
  wrap: { display: "flex", flexDirection: "column", height: "100%", minHeight: 0 },
  header: {
    height: 38,
    flexShrink: 0,
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 12px",
    borderBottom: "1px solid var(--border)",
  },
  headerLabel: {
    fontSize: 11,
    letterSpacing: "0.06em",
    textTransform: "uppercase",
    color: "var(--text-2)",
    fontFamily: "var(--font-ui)",
  },
  openBtn: {
    fontSize: 11,
    color: "var(--text-1)",
    padding: "3px 8px",
    borderRadius: 6,
    border: "1px solid var(--border)",
    cursor: "pointer",
    whiteSpace: "nowrap",
  },
  body: { flex: 1, overflow: "auto", minHeight: 0, padding: "4px 0" },
  empty: { padding: "16px 12px", fontSize: 12, color: "var(--text-2)", fontFamily: "var(--font-ui)", lineHeight: 1.6 },
  sectionHead: {
    fontSize: 10,
    letterSpacing: "0.06em",
    textTransform: "uppercase",
    color: "var(--text-2)",
    padding: "8px 12px 4px",
  },
  row: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    padding: "7px 8px 7px 12px",
    margin: "0 6px",
    cursor: "pointer",
    borderRadius: "var(--r-sm)",
    transition: "background var(--dur) var(--ease)",
  },
  rowMain: { flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 1 },
  rowTop: { display: "flex", alignItems: "center", gap: 8 },
  name: { fontSize: 13, color: "var(--text-0)", fontFamily: "var(--font-ui)", fontWeight: 500, whiteSpace: "nowrap" },
  lang: {
    fontSize: 9,
    color: "var(--accent)",
    background: "var(--accent-dim)",
    padding: "1px 5px",
    borderRadius: 4,
    fontFamily: "var(--font-mono)",
    flexShrink: 0,
  },
  path: {
    fontSize: 10,
    color: "var(--text-2)",
    fontFamily: "var(--font-mono)",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  meta: { fontSize: 10, color: "var(--text-2)", fontFamily: "var(--font-ui)" },
  rowActions: { display: "flex", gap: 2, flexShrink: 0 },
  iconBtn: {
    width: 22, height: 22,
    display: "flex", alignItems: "center", justifyContent: "center",
    borderRadius: 5, cursor: "pointer", fontSize: 15, lineHeight: 1,
    background: "transparent", border: "none",
  },
};
