import { useState, useCallback, useEffect, useRef } from "react";
import ActivityBar from "./components/ActivityBar.jsx";
import FileTree from "./components/FileTree.jsx";
import EditorPane from "./components/EditorPane.jsx";
import Terminal, { TerminalTabs } from "./components/Terminal.jsx";
import AIPanel from "./components/AIPanel.jsx";
import Settings from "./components/Settings.jsx";
import Onboarding from "./components/Onboarding.jsx";
import TaskBar from "./components/TaskBar.jsx";
import GitPanel from "./components/GitPanel.jsx";
import SearchPanel from "./components/SearchPanel.jsx";
import ProjectsPanel from "./components/ProjectsPanel.jsx";
import ExtensionStore from "./components/ExtensionStore.jsx";
import CommandPalette from "./components/CommandPalette.jsx";
import Notifications from "./components/Notifications.jsx";
import StatusBar from "./components/StatusBar.jsx";
import { open } from "@tauri-apps/plugin-dialog";
import { readFile, getConfig, saveConfig, readVagentConfig, runTask, createFile, gitCurrentBranch } from "./lib/tauri.js";

// ── Reduced-motion check (module-level, stable) ───────────────────────────────
const PRM =
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const GRID_TRANSITION = PRM ? "none" : "grid-template-columns 150ms ease";

// Editor preferences — persisted in config.json under these exact keys
const EDITOR_FONT_DEFAULT = 13;
const EDITOR_FONT_MIN = 10;
const EDITOR_FONT_MAX = 24;
function editorPrefsFromConfig(c = {}) {
  return {
    minimap_enabled:  c.minimap_enabled  ?? false,
    word_wrap:        c.word_wrap         ?? false,
    editor_font_size: Math.min(EDITOR_FONT_MAX, Math.max(EDITOR_FONT_MIN, c.editor_font_size ?? EDITOR_FONT_DEFAULT)),
    editor_font:      c.editor_font       || "JetBrains Mono",
    tab_size:         c.tab_size           ?? 2,
    auto_save:        c.auto_save         ?? false,
  };
}

// ── Layout constants ──────────────────────────────────────────────────────────
const SIDEBAR_MIN = 150;
const SIDEBAR_MAX = 400;
const SIDEBAR_DEFAULT = 220;
const AI_MIN = 200;
const AI_MAX = 700;
const AI_DEFAULT = 340;
const TERM_MIN = 80;
const TERM_MAX = 500;
const TERM_DEFAULT = 200;

// ── VDivider: vertical drag/collapse bar ──────────────────────────────────────
//   Always in the DOM at its grid column.
//   When collapsed: transparent + pointer-events:none (takes 0px from grid).
//   Collapse arrow direction: "left" for sidebar ("‹"), "right" for AI panel ("›").
function VDivider({ onMouseDown, onToggle, collapsed, arrowDir }) {
  const arrow = arrowDir === "left" ? "‹" : "›";
  return (
    <div
      aria-hidden={collapsed}
      style={{
        position: "relative",
        background: "transparent",
        borderLeft: collapsed ? "none" : "1px solid var(--border)",
        cursor: collapsed ? "default" : "col-resize",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        opacity: collapsed ? 0 : 1,
        pointerEvents: collapsed ? "none" : "auto",
        zIndex: 10,
        overflow: "visible",
      }}
      onMouseDown={collapsed ? undefined : onMouseDown}
    >
      {!collapsed && (
        <button
          style={vDivBtnStyle}
          onMouseDown={(e) => e.stopPropagation()}
          onClick={(e) => { e.stopPropagation(); onToggle(); }}
          title="Collapse panel"
        >
          {arrow}
        </button>
      )}
    </div>
  );
}

const vDivBtnStyle = {
  position: "absolute",
  top: "50%",
  left: "50%",
  transform: "translate(-50%, -50%)",
  width: 16,
  height: 36,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: "var(--bg-2)",
  border: "1px solid var(--border)",
  borderRadius: "var(--r-xs)",
  boxShadow: "var(--shadow-sm)",
  fontSize: 11,
  color: "var(--text-2)",
  cursor: "pointer",
  padding: 0,
  zIndex: 20,
};

// ── HDivider: horizontal drag/collapse bar above terminal ─────────────────────
//   Collapsed → renders as a full-width clickable "TERMINAL" tab.
//   Expanded → thin drag strip with a collapse button.
function HDivider({ onMouseDown, onToggle, collapsed }) {
  return (
    <div
      style={collapsed ? hdStyles.collapsed : hdStyles.expanded}
      onMouseDown={collapsed ? undefined : onMouseDown}
      onClick={collapsed ? onToggle : undefined}
    >
      <span style={hdStyles.label}>Terminal</span>
      <button
        style={hdStyles.btn}
        onMouseDown={(e) => e.stopPropagation()}
        onClick={(e) => { e.stopPropagation(); onToggle(); }}
        title={collapsed ? "Expand terminal" : "Collapse terminal"}
      >
        {collapsed ? "▲" : "▼"}
      </button>
    </div>
  );
}

const hdBase = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "0 12px",
  background: "var(--bg-1)",
  borderTop: "1px solid var(--border)",
  flexShrink: 0,
  userSelect: "none",
};
const hdStyles = {
  collapsed: { ...hdBase, height: 28, cursor: "pointer" },
  expanded:  { ...hdBase, height: 20, cursor: "row-resize" },
  label: {
    fontSize: 10,
    letterSpacing: "0.06em",
    textTransform: "uppercase",
    color: "var(--text-2)",
    fontFamily: "var(--font-ui)",
  },
  btn: {
    fontSize: 10,
    color: "var(--text-2)",
    background: "none",
    border: "none",
    cursor: "pointer",
    padding: "0 2px",
    lineHeight: 1,
  },
};

// ── ExpandBtn: absolute button shown on main area when a side panel is collapsed
function ExpandBtn({ side, onClick }) {
  const isLeft = side === "left";
  return (
    <button
      onClick={onClick}
      title="Expand panel"
      style={{
        position: "absolute",
        top: "50%",
        transform: "translateY(-50%)",
        [isLeft ? "left" : "right"]: 0,
        zIndex: 20,
        width: 16,
        height: 36,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--bg-2)",
        border: "1px solid var(--border)",
        borderRadius: isLeft ? "0 4px 4px 0" : "4px 0 0 4px",
        fontSize: 11,
        color: "var(--text-2)",
        cursor: "pointer",
        padding: 0,
      }}
    >
      {isLeft ? "›" : "‹"}
    </button>
  );
}

// ── App ───────────────────────────────────────────────────────────────────────

export default function App() {
  // null = still checking, true = show onboarding, false = show IDE
  const [firstRun, setFirstRun] = useState(null);

  const [theme, setTheme] = useState("dark");
  const [rootDirs, setRootDirs] = useState([]);   // multiple workspace roots
  const [openFiles, setOpenFiles] = useState([]);
  const [activeFilePath, setActiveFilePath] = useState(null);
  const [activeView, setActiveView] = useState("files");
  const [chatMode, setChatMode] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Git operates on the first workspace root
  const gitRoot = rootDirs[0] ?? null;

  // Record a folder in the recent-projects list (dedup, keep pinned + 10 recent).
  const recordProject = useCallback(async (path) => {
    try {
      const cfg = (await getConfig()) || {};
      const name = path.split(/[/\\]/).filter(Boolean).pop() || path;
      const list = Array.isArray(cfg.recent_projects) ? cfg.recent_projects : [];
      const prev = list.find((p) => p.path === path);
      const entry = { path, name, lastOpened: Date.now(), pinned: prev?.pinned || false };
      const rest = list.filter((p) => p.path !== path);
      const all = [entry, ...rest];
      const pinned = all.filter((p) => p.pinned);
      const recent = all.filter((p) => !p.pinned).slice(0, 10);
      await saveConfig({ ...cfg, recent_projects: [...pinned, ...recent] });
    } catch { /* silent */ }
  }, []);

  // Root-folder management
  const addRoot = useCallback((p) => {
    setRootDirs((prev) => (prev.includes(p) ? prev : [...prev, p]));
    recordProject(p);
  }, [recordProject]);
  const removeRoot = useCallback((p) => {
    setRootDirs((prev) => prev.filter((d) => d !== p));
  }, []);
  const replaceRoots = useCallback((p) => {
    setRootDirs([p]);
    recordProject(p);
  }, [recordProject]);

  // Open a recent/pinned project from the Projects panel.
  const openProject = useCallback((p) => {
    setRootDirs((prev) => (prev.includes(p) ? prev : [...prev, p]));
    recordProject(p);
    setActiveView("files");
  }, [recordProject]);

  // Reveal-in-tree target (from breadcrumb clicks). nonce re-triggers same path.
  const [reveal, setReveal] = useState(null); // { path, nonce }
  const revealInTree = useCallback((path) => {
    setActiveView("files");
    setReveal({ path, nonce: Date.now() });
  }, []);

  // Editor jump target (from search-result clicks). { path, line, col, length, nonce }
  const [editorJump, setEditorJump] = useState(null);

  // ── Git state ────────────────────────────────────────────────────────────────
  // gitStatusMap: { [absolutePath]: "XY" } — passed to FileTree for badges
  const [gitStatusMap, setGitStatusMap] = useState({});

  const handleGitStatusChange = useCallback((changes) => {
    if (!gitRoot) return;
    const sep = gitRoot.includes("\\") ? "\\" : "/";
    const map = {};
    for (const f of changes) {
      const abs = gitRoot + sep + f.path.replace(/\//g, sep);
      map[abs] = f.status;
    }
    setGitStatusMap(map);
  }, [gitRoot]);

  // ── Hackatime ────────────────────────────────────────────────────────────────
  const HK_DEFAULT_URL = "https://hackatime.hackclub.com/api/hackatime/v1/users/current/heartbeats";

  const [hackatimeConfig, setHackatimeConfig] = useState(null);
  const [hackatimeStatus, setHackatimeStatus] = useState(null);
  // { status: "tracking"|"paused"|"error", error?: string, lastSent?: number }

  const loadHackatime = useCallback((cfg) => {
    if (cfg?.hackatime_enabled && cfg?.hackatime_api_key) {
      setHackatimeConfig({
        enabled:    true,
        apiKey:     cfg.hackatime_api_key,
        apiUrl:     cfg.hackatime_api_url || HK_DEFAULT_URL,
        writesOnly: cfg.hackatime_writes_only ?? false,
      });
      // Preserve tracking/error status from the previous session; don't reset it on reload
    } else {
      setHackatimeConfig(null);
      // Show "paused" if the user has an API key but turned the toggle off
      setHackatimeStatus(cfg?.hackatime_api_key ? { status: "paused" } : null);
    }
  }, [HK_DEFAULT_URL]);

  // Reload hackatime + provider when Settings panel is closed
  useEffect(() => {
    if (!settingsOpen) {
      getConfig().then((cfg) => {
        loadHackatime(cfg);
        if (cfg?.ai_provider) setStatusProvider(cfg.ai_provider);
      }).catch(() => {});
    }
  }, [settingsOpen, loadHackatime]);

  // ── Plugin / task runner state ──────────────────────────────────────────────
  const [vagentConfig, setVagentConfig] = useState(null);

  // ── Terminal tabs ─────────────────────────────────────────────────────────────
  // terminals: [{ id, customTitle, ptyId, shellLabel }]
  const MAX_TERMINALS = 6;
  const termCounterRef = useRef(1);
  const [terminals, setTerminals] = useState([
    { id: "term-1", customTitle: null, ptyId: null, shellLabel: "terminal" },
  ]);
  const [activeTerminalId, setActiveTerminalId] = useState("term-1");

  // Active terminal's PTY session — drives the Run button / TaskBar
  const activePtyId = terminals.find((t) => t.id === activeTerminalId)?.ptyId ?? null;

  const handleTerminalReady = useCallback((id, ptyId, shellLabel) => {
    setTerminals((prev) =>
      prev.map((t) => (t.id === id ? { ...t, ptyId, shellLabel } : t))
    );
  }, []);

  const addTerminal = useCallback(() => {
    setTerminals((prev) => {
      if (prev.length >= MAX_TERMINALS) return prev;
      const id = `term-${++termCounterRef.current}`;
      setActiveTerminalId(id);
      return [...prev, { id, customTitle: null, ptyId: null, shellLabel: "terminal" }];
    });
    // Make sure the terminal panel is visible when adding
    setTerminalCollapsed(false);
  }, []);

  const closeTerminal = useCallback((id) => {
    setTerminals((prev) => {
      const next = prev.filter((t) => t.id !== id);
      setActiveTerminalId((cur) => {
        if (cur !== id) return cur;
        const idx = prev.findIndex((t) => t.id === id);
        return next[Math.min(idx, next.length - 1)]?.id ?? null;
      });
      return next;
    });
  }, []);

  const renameTerminal = useCallback((id, title) => {
    setTerminals((prev) =>
      prev.map((t) => (t.id === id ? { ...t, customTitle: title || null } : t))
    );
  }, []);

  // Load .vagent.json whenever the first root folder changes
  useEffect(() => {
    if (!gitRoot) { setVagentConfig(null); return; }
    readVagentConfig(gitRoot).then(setVagentConfig).catch(() => setVagentConfig(null));
  }, [gitRoot]);

  const refreshVagentConfig = useCallback(() => {
    if (!gitRoot) return;
    readVagentConfig(gitRoot).then(setVagentConfig).catch(() => setVagentConfig(null));
  }, [gitRoot]);

  // Run a shell command in the active terminal (used by TaskBar + EditorPane run button)
  const handleRun = useCallback((command) => {
    if (!activePtyId) return;
    // Ensure terminal is visible
    setTerminalCollapsed(false);
    requestAnimationFrame(() =>
      requestAnimationFrame(() => window.dispatchEvent(new Event("resize")))
    );
    runTask(activePtyId, command, gitRoot).catch(console.error);
  }, [activePtyId, gitRoot]);

  // ── Layout state ────────────────────────────────────────────────────────────
  const [sidebarWidth, setSidebarWidth] = useState(SIDEBAR_DEFAULT);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [aiPanelWidth, setAiPanelWidth] = useState(AI_DEFAULT);
  const [aiPanelCollapsed, setAiPanelCollapsed] = useState(false);
  const [terminalHeight, setTerminalHeight] = useState(TERM_DEFAULT);
  const [terminalCollapsed, setTerminalCollapsed] = useState(false);
  // "col" | "row" | null — renders an invisible overlay during drag
  const [isDragging, setIsDragging] = useState(null);

  // ── Editor preferences ─────────────────────────────────────────────────────────
  const [editorPrefs, setEditorPrefs] = useState(() => editorPrefsFromConfig());

  // ── Config load/save ────────────────────────────────────────────────────────

  // Restore previously open files (silently skipping ones that no longer exist)
  const restoreSession = useCallback(async (config) => {
    if (Array.isArray(config.rootDirs)) setRootDirs(config.rootDirs);

    const paths = Array.isArray(config.openFiles) ? config.openFiles : [];
    const restored = [];
    for (const p of paths) {
      try {
        const content = await readFile(p);
        const name = p.split(/[/\\]/).pop();
        restored.push({ path: p, name, content, savedContent: content });
      } catch { /* file gone — ignore silently */ }
    }
    if (restored.length) {
      setOpenFiles(restored);
      const active = restored.find((f) => f.path === config.activeFilePath);
      setActiveFilePath(active ? active.path : restored[0].path);
    }
  }, []);

  useEffect(() => {
    getConfig()
      .then(async (config) => {
        if (!config) {
          setFirstRun(true);
          return;
        }
        const t = config.theme || "dark";
        setTheme(t);
        document.documentElement.setAttribute("data-theme", t);
        if (config.ai_provider) setStatusProvider(config.ai_provider);
        // Restore saved dimensions (keep defaults if missing)
        if (config.sidebarWidth)   setSidebarWidth(config.sidebarWidth);
        if (config.aiPanelWidth)   setAiPanelWidth(config.aiPanelWidth);
        if (config.terminalHeight) setTerminalHeight(config.terminalHeight);
        setEditorPrefs(editorPrefsFromConfig(config));
        loadHackatime(config);
        await restoreSession(config);
        setFirstRun(false);
      })
      .catch(() => setFirstRun(true));
  }, []);

  // Persists arbitrary keys into the existing config object (read-merge-write)
  const saveLayout = useCallback(async (updates) => {
    try {
      const existing = await getConfig();
      await saveConfig({ ...(existing || {}), ...updates });
    } catch { /* silent */ }
  }, []);

  // Update one editor preference and persist it (config key === pref key)
  const updateEditorPref = useCallback((key, value) => {
    setEditorPrefs((prev) => ({ ...prev, [key]: value }));
    saveLayout({ [key]: value });
  }, [saveLayout]);

  // ── Session persistence ───────────────────────────────────────────────────────
  // Persist workspace + open tabs whenever they change (only once the IDE is up,
  // so we never clobber config during the loading/onboarding phases).
  const openPathsSig = openFiles.map((f) => f.path).join("\n");
  useEffect(() => {
    if (firstRun !== false) return;
    saveLayout({
      rootDirs,
      openFiles: openFiles.map((f) => f.path),
      activeFilePath,
    });
    // openPathsSig captures the set of open paths without depending on content
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [firstRun, rootDirs, openPathsSig, activeFilePath, saveLayout]);

  // ── Theme ────────────────────────────────────────────────────────────────────

  const applyTheme = useCallback((t) => {
    setTheme(t);
    document.documentElement.setAttribute("data-theme", t);
  }, []);

  // Apply + persist a theme (used by Settings cards and the activity-bar toggle).
  const selectTheme = useCallback((t) => {
    applyTheme(t);
    saveLayout({ theme: t });
  }, [applyTheme, saveLayout]);

  const toggleTheme = useCallback(() => {
    selectTheme(theme === "dark" ? "light" : "dark");
  }, [theme, selectTheme]);

  // ── Onboarding complete ──────────────────────────────────────────────────────

  const handleOnboardingComplete = useCallback(async (config) => {
    applyTheme(config.theme || "dark");
    setEditorPrefs(editorPrefsFromConfig(config));
    loadHackatime(config);
    try { await saveConfig(config); } catch {}
    setFirstRun(false);
  }, [applyTheme, loadHackatime]);

  // ── File operations ──────────────────────────────────────────────────────────

  const handleOpenFile = useCallback(async (entry) => {
    if (openFiles.some((f) => f.path === entry.path)) {
      setActiveFilePath(entry.path);
      return;
    }
    try {
      const content = await readFile(entry.path);
      // savedContent tracks the on-disk state for the unsaved-changes indicator
      setOpenFiles((prev) => [...prev, { path: entry.path, name: entry.name, content, savedContent: content }]);
      setActiveFilePath(entry.path);
    } catch (e) {
      console.error("Failed to open file:", e);
    }
  }, [openFiles]);

  // Open a file and jump the editor to a specific line/column (search results).
  const openFileAtLine = useCallback(async (path, line, col, length) => {
    const name = path.split(/[/\\]/).pop();
    await handleOpenFile({ path, name });
    setEditorJump({ path, line, col, length, nonce: Date.now() });
  }, [handleOpenFile]);

  // Called by EditorPane after a successful write — marks the file clean
  const handleSaved = useCallback((path) => {
    setOpenFiles((prev) =>
      prev.map((f) => (f.path === path ? { ...f, savedContent: f.content } : f))
    );
  }, []);

  const handleCloseTab = useCallback((path) => {
    setOpenFiles((prev) => {
      const next = prev.filter((f) => f.path !== path);
      setActiveFilePath((cur) => {
        if (cur !== path) return cur;
        const idx = prev.findIndex((f) => f.path === path);
        return next[Math.min(idx, next.length - 1)]?.path ?? null;
      });
      return next;
    });
  }, []);

  const handleContentChange = useCallback((path, content) => {
    setOpenFiles((prev) =>
      prev.map((f) => (f.path === path ? { ...f, content } : f))
    );
  }, []);

  // Reset cursor position indicator whenever the active tab changes
  useEffect(() => { setCursorPos(null); }, [activeFilePath]);

  // Reload an open file from disk (after the AI agent applies an edit to it).
  const reloadFile = useCallback(async (path) => {
    if (!openFiles.some((f) => f.path === path)) return;
    try {
      const content = await readFile(path);
      setOpenFiles((prev) => prev.map((f) => (f.path === path ? { ...f, content, savedContent: content } : f)));
    } catch { /* ignore */ }
  }, [openFiles]);

  const activeFile = openFiles.find((f) => f.path === activeFilePath) ?? null;

  // ── Drag handlers ────────────────────────────────────────────────────────────

  const startSidebarDrag = useCallback((e) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = sidebarWidth;
    let last = startW;
    setIsDragging("col");

    const onMove = (ev) => {
      // If the button was released outside the window, no mouseup fires; detect
      // it on the next move (buttons===0) and finish the drag.
      if (ev.buttons === 0) { onUp(); return; }
      last = Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, startW + ev.clientX - startX));
      setSidebarWidth(last);
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      setIsDragging(null);
      saveLayout({ sidebarWidth: last });
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, [sidebarWidth, saveLayout]);

  const startAIDrag = useCallback((e) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = aiPanelWidth;
    let last = startW;
    setIsDragging("col");

    const onMove = (ev) => {
      if (ev.buttons === 0) { onUp(); return; }
      // Moving divider left → AI panel grows
      last = Math.min(AI_MAX, Math.max(AI_MIN, startW - (ev.clientX - startX)));
      setAiPanelWidth(last);
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      setIsDragging(null);
      saveLayout({ aiPanelWidth: last });
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, [aiPanelWidth, saveLayout]);

  const startTerminalDrag = useCallback((e) => {
    e.preventDefault();
    const startY = e.clientY;
    const startH = terminalHeight;
    let last = startH;
    setIsDragging("row");

    const onMove = (ev) => {
      if (ev.buttons === 0) { onUp(); return; }
      // Moving divider up → terminal grows
      last = Math.min(TERM_MAX, Math.max(TERM_MIN, startH - (ev.clientY - startY)));
      setTerminalHeight(last);
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      setIsDragging(null);
      saveLayout({ terminalHeight: last });
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, [terminalHeight, saveLayout]);

  // ── Terminal collapse/expand ──────────────────────────────────────────────────

  const toggleTerminal = useCallback(() => {
    setTerminalCollapsed((v) => {
      const next = !v;
      if (!next) {
        // Expanding: let the DOM settle then fire a resize so xterm re-fits
        requestAnimationFrame(() =>
          requestAnimationFrame(() => window.dispatchEvent(new Event("resize")))
        );
      }
      return next;
    });
  }, []);

  // ── Stable toggle/expand callbacks (empty deps — only call stable setters) ───
  const toggleSidebar   = useCallback(() => setSidebarCollapsed((v) => !v), []);
  const expandSidebar   = useCallback(() => setSidebarCollapsed(false), []);
  const toggleAIPanel   = useCallback(() => setAiPanelCollapsed((v) => !v), []);
  const expandAIPanel   = useCallback(() => setAiPanelCollapsed(false), []);
  const openSettings    = useCallback(() => setSettingsOpen(true), []);
  const closeSettings   = useCallback(() => setSettingsOpen(false), []);
  const toggleChatMode  = useCallback(() => setChatMode((v) => !v), []);

  // Selecting an IDE view (files/search/git) always leaves chat mode.
  const handleSelectView = useCallback((view) => {
    setActiveView(view);
    if (view !== "chat") setChatMode(false);
  }, []);

  // Update Hackatime status from EditorPane (tracking / error)
  const handleHackatimeStatus = useCallback((s) => setHackatimeStatus(s), []);

  // ── Problem count (from EditorPane markers) ───────────────────────────────
  const [problemCount, setProblemCount] = useState({ errors: 0, warnings: 0 });
  const handleMarkersChange = useCallback((count) => setProblemCount(count), []);

  // ── Git branch ────────────────────────────────────────────────────────────
  const [gitBranch, setGitBranch] = useState(null);
  useEffect(() => {
    if (!gitRoot) { setGitBranch(null); return; }
    gitCurrentBranch(gitRoot)
      .then((b) => setGitBranch(b?.trim() || null))
      .catch(() => setGitBranch(null));
  }, [gitRoot]);

  // ── Status bar state ─────────────────────────────────────────────────────────
  const [cursorPos,     setCursorPos]       = useState(null);
  const [statusProvider, setStatusProvider] = useState("backend");

  // ── Command palette ───────────────────────────────────────────────────────────
  const [paletteOpen, setPaletteOpen]       = useState(false);
  const [saveSignal, setSaveSignal]         = useState(0);   // → EditorPane
  const [gitFocusSignal, setGitFocusSignal] = useState(0);   // → GitPanel
  const [searchFocusSignal, setSearchFocusSignal] = useState(0); // → SearchPanel
  const [providerCmd, setProviderCmd]       = useState(null); // → AIPanel { provider, n }
  const [askCmd, setAskCmd]                 = useState(null); // → AIPanel { action, code, file, n }

  // "Ask AI" from an editor selection: reveal the AI panel and forward the code.
  const handleAskAI = useCallback(({ action, code, file }) => {
    setAiPanelCollapsed(false);
    setChatMode(false);
    setAskCmd({ action, code, file, n: Date.now() });
  }, []);

  // Global shortcuts: Ctrl/Cmd+Shift+P (palette), Ctrl/Cmd+Shift+F (search)
  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === "p" || e.key === "P")) {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === "f" || e.key === "F")) {
        e.preventDefault();
        setActiveView("search");
        setSearchFocusSignal((n) => n + 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const openFileDialog = useCallback(async () => {
    const sel = await open({ directory: false, multiple: false });
    if (sel && typeof sel === "string") {
      handleOpenFile({ path: sel, name: sel.split(/[/\\]/).pop() });
    }
  }, [handleOpenFile]);

  const openFolderDialog = useCallback(async () => {
    const sel = await open({ directory: true, multiple: false });
    if (sel && typeof sel === "string") replaceRoots(sel);
  }, [replaceRoots]);

  const newFileInWorkspace = useCallback(async () => {
    if (!gitRoot) { window.notify?.("Open a folder first", "warning"); return; }
    const name = window.prompt("New file name:");
    if (!name || !name.trim()) return;
    const sep = gitRoot.includes("\\") ? "\\" : "/";
    const path = gitRoot + sep + name.trim();
    try {
      await createFile(path, "");
      handleOpenFile({ path, name: name.trim() });
    } catch (e) {
      window.notify?.(`Error creating file: ${e}`, "error");
    }
  }, [gitRoot, handleOpenFile]);

  // Build the command list from current state (cheap — only built while open)
  const buildCommands = useCallback(() => {
    const cmds = [
      { id: "open-file",   title: "Open File…",      hint: "dialog", run: openFileDialog },
      { id: "open-folder", title: "Open Folder…",    hint: "dialog", run: openFolderDialog },
      { id: "new-file",    title: "New File",                       run: newFileInWorkspace },
      { id: "save",        title: "Save File",       hint: "Ctrl+S", run: () => setSaveSignal((n) => n + 1) },
      { id: "toggle-term", title: "Toggle Terminal",                run: toggleTerminal },
      { id: "toggle-ai",   title: "Toggle AI Panel",                run: toggleAIPanel },
      { id: "toggle-theme",title: "Toggle Theme",                   run: toggleTheme },
      { id: "git-commit",  title: "Git: Commit…",                   run: () => { setActiveView("git"); setGitFocusSignal((n) => n + 1); } },
    ];
    if (vagentConfig?.tasks) {
      for (const [name, cmd] of Object.entries(vagentConfig.tasks)) {
        cmds.push({ id: `task-${name}`, title: `Run Task: ${name}`, hint: cmd, run: () => handleRun(cmd) });
      }
    }
    for (const p of ["backend", "groq", "openrouter", "ollama"]) {
      cmds.push({ id: `prov-${p}`, title: `Switch Provider: ${p}`, run: () => setProviderCmd({ provider: p, n: Date.now() }) });
    }
    return cmds;
  }, [openFileDialog, openFolderDialog, newFileInWorkspace, toggleTerminal, toggleAIPanel, toggleTheme, vagentConfig, handleRun]);

  // ── Grid computation ─────────────────────────────────────────────────────────

  const gridCols = chatMode
    ? "48px 1fr"
    : [
        "48px",
        sidebarCollapsed ? "0px" : `${sidebarWidth}px`,
        sidebarCollapsed ? "0px" : "4px",
        "1fr",
        aiPanelCollapsed ? "0px" : "4px",
        aiPanelCollapsed ? "0px" : `${aiPanelWidth}px`,
      ].join(" ");

  // ── Render: splash ───────────────────────────────────────────────────────────

  if (firstRun === null) {
    return (
      <div style={splash.wrap}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16 }}>
          <svg width="56" height="56" viewBox="0 0 52 52" fill="none">
            <rect x="2" y="2" width="48" height="48" rx="13" fill="var(--accent-dim)" />
            <path d="M15 18L26 38L37 18" stroke="var(--accent)" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span style={splash.logo}>V-Agent</span>
        </div>
      </div>
    );
  }

  // ── Render: onboarding ───────────────────────────────────────────────────────

  if (firstRun) {
    return <Onboarding onComplete={handleOnboardingComplete} />;
  }

  // ── Render: IDE ──────────────────────────────────────────────────────────────

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "var(--bg-0)" }}>
    <div
      style={{
        flex: 1,
        display: "grid",
        gridTemplateColumns: gridCols,
        minHeight: 0,
        background: "var(--bg-0)",
        transition: GRID_TRANSITION,
        overflow: "hidden",
      }}
    >
      {/* ── Drag overlay: captures all mouse events during drag ────────────── */}
      {isDragging && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 9999,
            cursor: isDragging === "col" ? "col-resize" : "row-resize",
          }}
        />
      )}

      {/* ── Col 1: ActivityBar ────────────────────────────────────────────── */}
      <ActivityBar
        active={activeView}
        onSelect={handleSelectView}
        chatMode={chatMode}
        onToggleChat={toggleChatMode}
        theme={theme}
        onToggleTheme={toggleTheme}
        onOpenSettings={openSettings}
      />

      {/* ── IDE-only panels ───────────────────────────────────────────────── */}
      {!chatMode && (
        <>
          {/* Col 2: Sidebar — FileTree stays mounted (state preserved); GitPanel
              mounts only when active so it shows fresh git status each time. */}
          <aside
            style={{
              gridColumn: 2,
              background: "var(--bg-1)",
              overflow: "hidden",
              display: "flex",
              flexDirection: "column",
            }}
          >
            <div style={{
              display: activeView === "files" ? "flex" : "none",
              flexDirection: "column",
              height: "100%",
              minHeight: 0,
            }}>
              <FileTree
                rootDirs={rootDirs}
                onAddRoot={addRoot}
                onRemoveRoot={removeRoot}
                onReplaceRoots={replaceRoots}
                onOpenFile={handleOpenFile}
                gitStatusMap={gitStatusMap}
                activeFilePath={activeFilePath}
                reveal={reveal}
              />
            </div>
            {activeView === "projects" && (
              <ProjectsPanel onOpenProject={openProject} />
            )}
            {activeView === "search" && (
              <SearchPanel
                rootDirs={rootDirs}
                onOpenResult={openFileAtLine}
                focusSignal={searchFocusSignal}
              />
            )}
            {activeView === "git" && (
              <GitPanel
                rootDir={gitRoot}
                onStatusChange={handleGitStatusChange}
                focusSignal={gitFocusSignal}
              />
            )}
            {activeView === "extensions" && <ExtensionStore />}
          </aside>

          {/* Col 3: Sidebar VDivider */}
          <VDivider
            onMouseDown={startSidebarDrag}
            onToggle={toggleSidebar}
            collapsed={sidebarCollapsed}
            arrowDir="left"
          />

          {/* Col 4: Main (editor + terminal) */}
          <main
            style={{
              gridColumn: 4,
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              position: "relative",
              minWidth: 0,
            }}
          >
            {/* Expand button when sidebar is collapsed */}
            {sidebarCollapsed && (
              <ExpandBtn side="left" onClick={expandSidebar} />
            )}

            {/* Task bar — shown when a project folder is open */}
            <TaskBar
              vagentConfig={vagentConfig}
              rootDir={gitRoot}
              activePtyId={activePtyId}
              onFocusTerminal={() => {
                setTerminalCollapsed(false);
                requestAnimationFrame(() =>
                  requestAnimationFrame(() => window.dispatchEvent(new Event("resize")))
                );
              }}
              onRefresh={refreshVagentConfig}
            />

            {/* Editor region */}
            <div style={{ flex: 1, overflow: "hidden", minHeight: 0 }}>
              <EditorPane
                openFiles={openFiles}
                activeFilePath={activeFilePath}
                onSelectTab={setActiveFilePath}
                onCloseTab={handleCloseTab}
                onChange={(content) => handleContentChange(activeFilePath, content)}
                onSaved={handleSaved}
                saveSignal={saveSignal}
                activePtyId={activePtyId}
                onRun={handleRun}
                hackatimeConfig={hackatimeConfig}
                editorPrefs={editorPrefs}
                onEditorPref={updateEditorPref}
                rootDirs={rootDirs}
                onRevealPath={revealInTree}
                jumpTarget={editorJump}
                appTheme={theme}
                onAskAI={handleAskAI}
                onCursorChange={setCursorPos}
                onHackatimeStatus={handleHackatimeStatus}
                onMarkersChange={handleMarkersChange}
              />
            </div>

            {/* Terminal HDivider (always visible — acts as tab when collapsed) */}
            <HDivider
              onMouseDown={startTerminalDrag}
              onToggle={toggleTerminal}
              collapsed={terminalCollapsed}
            />

            {/* Terminal area — tabs + stacked instances; height 0 when collapsed.
                Each Terminal stays mounted so its scrollback survives tab switches. */}
            <div
              style={{
                height: terminalCollapsed ? 0 : terminalHeight,
                overflow: "hidden",
                flexShrink: 0,
                background: "var(--bg-0)",
                display: "flex",
                flexDirection: "column",
              }}
            >
              <TerminalTabs
                terminals={terminals}
                activeId={activeTerminalId}
                onSelect={setActiveTerminalId}
                onClose={closeTerminal}
                onAdd={addTerminal}
                onRename={renameTerminal}
                maxReached={terminals.length >= MAX_TERMINALS}
              />
              <div style={{ flex: 1, position: "relative", minHeight: 0 }}>
                {terminals.map((t) => (
                  <div
                    key={t.id}
                    style={{
                      position: "absolute",
                      inset: 0,
                      display: t.id === activeTerminalId ? "block" : "none",
                    }}
                  >
                    <Terminal onReady={handleTerminalReady.bind(null, t.id)} />
                  </div>
                ))}
                {terminals.length === 0 && (
                  <div style={{
                    position: "absolute", inset: 0,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: "12px", color: "var(--text-2)", fontFamily: "var(--font-ui)",
                  }}>
                    No terminals — click + to open one
                  </div>
                )}
              </div>
            </div>

            {/* Expand button when AI panel is collapsed */}
            {aiPanelCollapsed && (
              <ExpandBtn side="right" onClick={expandAIPanel} />
            )}
          </main>

          {/* Col 5: AI Panel VDivider */}
          <VDivider
            onMouseDown={startAIDrag}
            onToggle={toggleAIPanel}
            collapsed={aiPanelCollapsed}
            arrowDir="right"
          />
        </>
      )}

      {/* ── Col 6 (IDE) / Col 2 (Chat): AI Panel ─────────────────────────── */}
      <aside
        style={{
          gridColumn: chatMode ? 2 : 6,
          background: chatMode ? "var(--bg-0)" : "var(--bg-1)",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          minWidth: 0,
        }}
      >
        <AIPanel openFile={activeFile} mode={chatMode ? "chat" : "ide"} providerCmd={providerCmd} rootDirs={rootDirs} askCmd={askCmd} onRunCommand={handleRun} reloadFile={reloadFile} appTheme={theme} />
      </aside>

      {/* ── Settings overlay ──────────────────────────────────────────────── */}
      {settingsOpen && (
        <Settings
          theme={theme}
          onToggleTheme={toggleTheme}
          onSelectTheme={selectTheme}
          onClose={closeSettings}
          editorPrefs={editorPrefs}
          onEditorPref={updateEditorPref}
          hackatimeLastSent={hackatimeStatus?.lastSent ?? null}
        />
      )}

      {/* ── Command palette ───────────────────────────────────────────────── */}
      {paletteOpen && (
        <CommandPalette
          commands={buildCommands()}
          onClose={() => setPaletteOpen(false)}
        />
      )}

      {/* ── Toast notifications (registers window.notify) ─────────────────── */}
      <Notifications />
    </div>

    {/* ── Status bar: full-width bottom strip ───────────────────────────── */}
    <StatusBar
      cursorPos={cursorPos}
      activeFile={activeFile}
      provider={statusProvider}
      hackatimeStatus={hackatimeStatus}
      onOpenSettings={openSettings}
      gitBranch={gitBranch}
      problemCount={problemCount}
    />
    </div>
  );
}

// ── Static styles ─────────────────────────────────────────────────────────────

const splash = {
  wrap: {
    height: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "var(--bg-0)",
  },
  logo: {
    fontFamily: "var(--font-mono)",
    fontSize: "16px",
    color: "var(--text-2)",
    letterSpacing: "0.12em",
    textTransform: "uppercase",
  },
};
