import { useState, useEffect, useRef, useCallback } from "react";
import { writeEnvKey, getSystemInfo, getConfig, saveConfig, sendHeartbeat, openExternal } from "../lib/tauri.js";

const DEFAULT_HACKATIME_URL = "https://hackatime.hackclub.com/api/hackatime/v1/users/current/heartbeats";
const HACKATIME_SETUP_URL = "https://hackatime.hackclub.com/my/wakatime_setup";

// External link that opens in the system browser via the shell plugin.
function Lnk({ url, children }) {
  return (
    <a
      href={url}
      onClick={(e) => { e.preventDefault(); openExternal(url).catch(() => {}); }}
      style={{ color: "var(--accent)", textDecoration: "none", cursor: "pointer" }}
    >
      {children}
    </a>
  );
}

function timeAgo(ms) {
  if (!ms) return null;
  const s = Math.floor((Date.now() - ms) / 1000);
  if (s < 5)    return "just now";
  if (s < 60)   return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

// Step-by-step modal explaining how to get a Hackatime API key.
function HackatimeGuide({ onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const steps = [
    <>Go to <Lnk url="https://hackatime.hackclub.com">hackatime.hackclub.com</Lnk> and log in with your Hack Club account.</>,
    <>Open <Lnk url={HACKATIME_SETUP_URL}>Settings → Setup</Lnk> and copy your API key from the <b>WakaTime Config File</b> block (the <code>api_key</code> value).</>,
    <>Paste it into the <b>API Key</b> field below.</>,
    <>Click <b>Test connection</b> to confirm it works.</>,
  ];

  return (
    <div style={gd.overlay} onClick={onClose}>
      <div style={gd.modal} onClick={(e) => e.stopPropagation()}>
        <div style={gd.header}>
          <span style={gd.title}>Hackatime setup guide</span>
          <button style={gd.close} onClick={onClose} title="Close (Esc)">×</button>
        </div>
        <ol style={gd.list}>
          {steps.map((st, i) => (
            <li key={i} style={gd.step}>
              <span style={gd.num}>{i + 1}</span>
              <span style={gd.stepText}>{st}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

const gd = {
  overlay: { position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)", backdropFilter: "blur(3px)", WebkitBackdropFilter: "blur(3px)", zIndex: 10001, display: "flex", alignItems: "center", justifyContent: "center", animation: "va-fade 120ms var(--ease)" },
  modal: { width: 440, maxWidth: "calc(100vw - 48px)", background: "var(--bg-1)", border: "1px solid var(--border)", borderRadius: "var(--r-lg)", boxShadow: "var(--shadow-lg)", overflow: "hidden", animation: "va-pop 160ms var(--ease)" },
  header: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 18px", borderBottom: "1px solid var(--border)" },
  title: { fontSize: 14, fontWeight: 600, color: "var(--text-0)", fontFamily: "var(--font-ui)" },
  close: { fontSize: 18, color: "var(--text-2)", cursor: "pointer", background: "none", border: "none", lineHeight: 1 },
  list: { listStyle: "none", margin: 0, padding: "16px 18px", display: "flex", flexDirection: "column", gap: 14 },
  step: { display: "flex", gap: 12, alignItems: "flex-start" },
  num: { flexShrink: 0, width: 22, height: 22, borderRadius: "50%", background: "var(--accent-dim)", color: "var(--accent)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700, fontFamily: "var(--font-mono)" },
  stepText: { fontSize: 13, color: "var(--text-1)", fontFamily: "var(--font-ui)", lineHeight: 1.5 },
};

const EDITOR_FONT_MIN = 10;
const EDITOR_FONT_MAX = 24;
const EDITOR_FONT_DEFAULT = 13;

// Theme cards — preview colours mirror the CSS variables in styles.css.
const THEME_CARDS = [
  { id: "dark",        label: "Dark",        bg: "#0b0b0f", panel: "#1c1c2a", accent: "#9088cc", text: "#e8e8f0" },
  { id: "light",       label: "Light",       bg: "#f5f5f2", panel: "#edede9", accent: "#6258a8", text: "#18181e" },
  { id: "dracula",     label: "Dracula",     bg: "#282a36", panel: "#343746", accent: "#bd93f9", text: "#f8f8f2" },
  { id: "one-dark",    label: "One Dark",    bg: "#282c34", panel: "#353b45", accent: "#61afef", text: "#d7dae0" },
  { id: "nord",        label: "Nord",        bg: "#2e3440", panel: "#3b4252", accent: "#88c0d0", text: "#eceff4" },
  { id: "catppuccin",  label: "Catppuccin",  bg: "#1e1e2e", panel: "#313244", accent: "#cba6f7", text: "#cdd6f4" },
  { id: "github-dark", label: "GitHub Dark", bg: "#0d1117", panel: "#161b22", accent: "#58a6ff", text: "#c9d1d9" },
  { id: "solarized",   label: "Solarized",   bg: "#002b36", panel: "#073642", accent: "#268bd2", text: "#93a1a1" },
];

const EDITOR_FONTS = ["JetBrains Mono", "Fira Code", "Cascadia Code", "Source Code Pro", "Inconsolata"];

const PROVIDERS = [
  { id: "backend",    label: "Backend (built-in)", needsKey: false },
  { id: "groq",       label: "Groq",               needsKey: true  },
  { id: "openrouter", label: "OpenRouter",          needsKey: true  },
  { id: "ollama",     label: "Ollama (local)",      needsKey: false },
];

function maxParamsForVram(vramMb) {
  if (vramMb <= 0)    return Infinity;
  if (vramMb < 4096)  return 3;
  if (vramMb < 8192)  return 7;
  return Infinity;
}

function parseParams(name) {
  const m = name.match(/:(\d+(?:\.\d+)?)b/i) || name.match(/(\d+(?:\.\d+)?)b/i);
  return m ? parseFloat(m[1]) : Infinity;
}

// ── Ollama section ─────────────────────────────────────────────────────────

function OllamaSection({ activeModel, onSelectModel }) {
  const [models,  setModels]  = useState(null);
  const [error,   setError]   = useState(null);
  const [sysInfo, setSysInfo] = useState(null);

  useEffect(() => {
    getSystemInfo().then(setSysInfo).catch(() => setSysInfo({ total_ram_mb: 0, vram_mb: 0 }));
    fetch("http://localhost:11434/api/tags")
      .then((r) => r.json())
      .then((data) => setModels(data.models || []))
      .catch(() => { setError("Ollama not running"); setModels([]); });
  }, []);

  const maxParams = sysInfo ? maxParamsForVram(sysInfo.vram_mb) : Infinity;
  const filtered  = (models || []).filter((m) => parseParams(m.name) <= maxParams);

  return (
    <div style={ss.section}>
      <div style={ss.sectionTitle}>Local Models (Ollama)</div>
      {sysInfo && sysInfo.vram_mb > 0 && (
        <div style={ss.hwBadge}>
          VRAM: {Math.round(sysInfo.vram_mb / 1024 * 10) / 10} GB
          {" · "}models ≤ {maxParams === Infinity ? "all" : `${maxParams}B`}
        </div>
      )}
      {error ? (
        <div style={ss.row}>
          <span style={ss.dimText}>{error}</span>
          <a href="https://ollama.com/download" target="_blank" rel="noreferrer" style={ss.link}>
            Install ↗
          </a>
        </div>
      ) : models === null ? (
        <div style={ss.dimText}>Checking Ollama…</div>
      ) : filtered.length === 0 ? (
        <div style={ss.dimText}>{models.length === 0 ? "No models. Run: ollama pull llama3" : "No models fit VRAM."}</div>
      ) : (
        <div style={ss.modelList}>
          {filtered.map((m) => (
            <button key={m.name} style={{ ...ss.modelBtn, background: activeModel === m.name ? "var(--accent-dim)" : "var(--bg-2)" }}
              onClick={() => onSelectModel(m.name)}>
              <span>{m.name}</span>
              <span style={ss.modelSize}>{m.size ? `${(m.size / 1e9).toFixed(1)} GB` : ""}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Hackatime section ─────────────────────────────────────────────────────

function HackatimeSection({ enabled, apiKey, apiUrl, onEnabled, onApiKey, onApiUrl, writesOnly, onWritesOnly, lastSent }) {
  const [testMsg, setTestMsg] = useState("");
  const [testing, setTesting] = useState(false);
  const [guideOpen, setGuideOpen] = useState(false);

  const test = async () => {
    if (!apiKey.trim()) { setTestMsg("Enter an API key first."); return; }
    setTesting(true);
    setTestMsg("");
    try {
      await sendHeartbeat(
        "test-connection",
        "V-Agent",
        "Other",
        false,
        apiKey.trim(),
        apiUrl.trim() || DEFAULT_HACKATIME_URL,
        { lines: 1, lineno: 1, cursorpos: 1, branch: "" },
      );
      setTestMsg("✓ Connected (201)");
    } catch (e) {
      setTestMsg(`✗ ${e}`);
    } finally {
      setTesting(false);
    }
  };

  return (
    <div style={ss.section}>
      <div style={ss.sectionTitle}>Hackatime / WakaTime</div>

      {/* Toggle + setup guide */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <span style={{ fontSize: 13, color: "var(--text-1)", fontFamily: "var(--font-ui)" }}>Enable coding time tracking</span>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button style={ss.guideBtn} onClick={() => setGuideOpen(true)}>Setup guide</button>
          <button
            onClick={() => onEnabled(!enabled)}
            style={{
              width: 40, height: 22,
              borderRadius: 11,
              background: enabled ? "var(--accent)" : "var(--bg-3)",
              border: "1px solid var(--border)",
              position: "relative",
              transition: "background 150ms",
              cursor: "pointer",
              flexShrink: 0,
            }}
          >
            <span style={{
              position: "absolute",
              top: 2,
              left: enabled ? 20 : 2,
              width: 16, height: 16,
              borderRadius: "50%",
              background: "#fff",
              transition: "left 150ms",
            }} />
          </button>
        </div>
      </div>
      {guideOpen && <HackatimeGuide onClose={() => setGuideOpen(false)} />}

      {/* API Key */}
      <label style={ss.label}>API Key</label>
      <input
        type="password"
        style={ss.input}
        placeholder="waka_..."
        value={apiKey}
        onChange={(e) => onApiKey(e.target.value)}
        autoComplete="off"
      />

      {/* API URL */}
      <label style={{ ...ss.label, marginTop: 10 }}>API URL</label>
      <input
        type="text"
        style={ss.input}
        placeholder={DEFAULT_HACKATIME_URL}
        value={apiUrl}
        onChange={(e) => onApiUrl(e.target.value)}
      />

      {/* Writes only */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 12 }}>
        <span style={{ fontSize: 13, color: "var(--text-1)", fontFamily: "var(--font-ui)" }}>
          Writes only
          <span style={{ display: "block", fontSize: 11, color: "var(--text-2)", marginTop: 2 }}>
            Only send heartbeats when saving a file
          </span>
        </span>
        <Switch on={!!writesOnly} onClick={() => onWritesOnly?.(!writesOnly)} />
      </div>

      {/* Test + last sync */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 12 }}>
        <button
          style={{ ...ss.testBtn, opacity: testing ? 0.6 : 1 }}
          onClick={test}
          disabled={testing}
        >
          {testing ? "Testing…" : "Test connection"}
        </button>
        {testMsg && (
          <span style={{ fontSize: 12, fontFamily: "var(--font-ui)", color: testMsg.startsWith("✓") ? "var(--ok)" : "var(--err)" }}>
            {testMsg}
          </span>
        )}
        {!testMsg && lastSent && (
          <span style={{ fontSize: 11, fontFamily: "var(--font-ui)", color: "var(--text-2)" }}>
            Last sync: {timeAgo(lastSent)}
          </span>
        )}
      </div>
    </div>
  );
}

// ── Pill switch ────────────────────────────────────────────────────────────

function Switch({ on, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        width: 40, height: 22,
        borderRadius: 11,
        background: on ? "var(--accent)" : "var(--bg-3)",
        border: "1px solid var(--border)",
        position: "relative",
        transition: "background 150ms",
        cursor: "pointer",
        flexShrink: 0,
      }}
    >
      <span style={{
        position: "absolute",
        top: 2,
        left: on ? 20 : 2,
        width: 16, height: 16,
        borderRadius: "50%",
        background: "#fff",
        transition: "left 150ms",
      }} />
    </button>
  );
}

// ── Main Settings overlay ──────────────────────────────────────────────────

export default function Settings({ theme, onToggleTheme, onSelectTheme, onClose, editorPrefs = {}, onEditorPref, hackatimeLastSent = null }) {
  const [provider,       setProvider]       = useState("backend");
  const [keys,           setKeys]           = useState({ groq: "", openrouter: "" });
  const [ollamaModel,    setOllamaModel]    = useState("");
  const [hkEnabled,      setHkEnabled]      = useState(false);
  const [hkApiKey,       setHkApiKey]       = useState("");
  const [hkApiUrl,       setHkApiUrl]       = useState(DEFAULT_HACKATIME_URL);
  const [hkWritesOnly,   setHkWritesOnly]   = useState(false);
  const [saveMsg,        setSaveMsg]        = useState("");
  const overlayRef = useRef(null);

  const fontSize = Math.min(EDITOR_FONT_MAX, Math.max(EDITOR_FONT_MIN, editorPrefs.editor_font_size ?? EDITOR_FONT_DEFAULT));

  // Load existing config on mount
  useEffect(() => {
    getConfig().then((cfg) => {
      if (!cfg) return;
      if (cfg.ai_provider)                    setProvider(cfg.ai_provider);
      if (cfg.groq_api_key)                   setKeys((prev) => ({ ...prev, groq: cfg.groq_api_key }));
      if (cfg.openrouter_api_key)             setKeys((prev) => ({ ...prev, openrouter: cfg.openrouter_api_key }));
      if (cfg.ollama_model)                   setOllamaModel(cfg.ollama_model);
      if (cfg.hackatime_enabled !== undefined)    setHkEnabled(!!cfg.hackatime_enabled);
      if (cfg.hackatime_api_key)                  setHkApiKey(cfg.hackatime_api_key);
      if (cfg.hackatime_api_url)                  setHkApiUrl(cfg.hackatime_api_url);
      if (cfg.hackatime_writes_only !== undefined) setHkWritesOnly(!!cfg.hackatime_writes_only);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const handleOverlayClick = (e) => {
    if (e.target === overlayRef.current) onClose();
  };

  const save = useCallback(async () => {
    try {
      // AI provider
      await writeEnvKey("AI_PROVIDER", provider);
      if (keys.groq)       await writeEnvKey("GROQ_API_KEY", keys.groq);
      if (keys.openrouter) await writeEnvKey("OPENROUTER_API_KEY", keys.openrouter);
      if (ollamaModel)     await writeEnvKey("OLLAMA_MODEL", ollamaModel);

      // Merge everything into config.json — keys live here so sidecar can always read them
      const existing = await getConfig().catch(() => ({}));
      await saveConfig({
        ...(existing || {}),
        ai_provider: provider,
        ...(keys.groq       ? { groq_api_key:       keys.groq.trim()       } : {}),
        ...(keys.openrouter ? { openrouter_api_key:  keys.openrouter.trim() } : {}),
        ...(ollamaModel     ? { ollama_model:         ollamaModel           } : {}),
        hackatime_enabled:    hkEnabled,
        hackatime_api_key:    hkApiKey.trim(),
        hackatime_api_url:    hkApiUrl.trim() || DEFAULT_HACKATIME_URL,
        hackatime_writes_only: hkWritesOnly,
      });

      setSaveMsg("Saved!");
      setTimeout(() => setSaveMsg(""), 2000);
    } catch (e) {
      setSaveMsg(`Error: ${e}`);
    }
  }, [provider, keys, ollamaModel, hkEnabled, hkApiKey, hkApiUrl, hkWritesOnly]);

  const current = PROVIDERS.find((p) => p.id === provider);

  return (
    <div ref={overlayRef} style={ss.overlay} onClick={handleOverlayClick}>
      <div style={ss.modal}>
        <div style={ss.header}>
          <span style={ss.title}>Settings</span>
          <button style={ss.closeBtn} onClick={onClose} title="Close (Esc)">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <div style={ss.body}>
          {/* AI Provider */}
          <div style={ss.section}>
            <div style={ss.sectionTitle}>AI Provider</div>
            <div style={ss.providerGrid}>
              {PROVIDERS.map((p) => (
                <button key={p.id}
                  style={{ ...ss.providerBtn, background: provider === p.id ? "var(--accent-dim)" : "var(--bg-2)", color: provider === p.id ? "var(--text-0)" : "var(--text-1)", borderColor: provider === p.id ? "var(--accent)" : "var(--border)" }}
                  onClick={() => setProvider(p.id)}>
                  {p.label}
                </button>
              ))}
            </div>
            {current?.needsKey && (
              <div style={ss.keyRow}>
                <label style={ss.label}>{provider === "groq" ? "Groq" : "OpenRouter"} API Key</label>
                <input type="password" style={ss.input} placeholder="sk-..."
                  value={keys[provider] || ""}
                  onChange={(e) => setKeys((prev) => ({ ...prev, [provider]: e.target.value }))} />
              </div>
            )}
          </div>

          {provider === "ollama" && (
            <OllamaSection activeModel={ollamaModel} onSelectModel={setOllamaModel} />
          )}

          {/* Hackatime */}
          <HackatimeSection
            enabled={hkEnabled} apiKey={hkApiKey} apiUrl={hkApiUrl}
            onEnabled={setHkEnabled} onApiKey={setHkApiKey} onApiUrl={setHkApiUrl}
            writesOnly={hkWritesOnly} onWritesOnly={setHkWritesOnly}
            lastSent={hackatimeLastSent}
          />

          {/* Editor */}
          <div style={ss.section}>
            <div style={ss.sectionTitle}>Editor</div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ fontSize: 13, color: "var(--text-1)", fontFamily: "var(--font-ui)" }}>
                Auto-save
                <span style={{ display: "block", fontSize: 11, color: "var(--text-2)", marginTop: 2 }}>
                  Saves a modified file 1s after you stop typing
                </span>
              </span>
              <Switch on={!!editorPrefs.auto_save} onClick={() => onEditorPref?.("auto_save", !editorPrefs.auto_save)} />
            </div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 16 }}>
              <span style={{ fontSize: 13, color: "var(--text-1)", fontFamily: "var(--font-ui)" }}>
                Font size
                <span style={{ display: "block", fontSize: 11, color: "var(--text-2)", marginTop: 2 }}>
                  Ctrl + / Ctrl − to adjust · Ctrl 0 to reset
                </span>
              </span>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <button
                  style={{ ...ss.stepBtn, opacity: fontSize <= EDITOR_FONT_MIN ? 0.4 : 1 }}
                  onClick={() => onEditorPref?.("editor_font_size", Math.max(EDITOR_FONT_MIN, fontSize - 1))}
                  disabled={fontSize <= EDITOR_FONT_MIN}
                >−</button>
                <span style={{ minWidth: 24, textAlign: "center", fontFamily: "var(--font-mono)", fontSize: 13, color: "var(--text-0)" }}>{fontSize}</span>
                <button
                  style={{ ...ss.stepBtn, opacity: fontSize >= EDITOR_FONT_MAX ? 0.4 : 1 }}
                  onClick={() => onEditorPref?.("editor_font_size", Math.min(EDITOR_FONT_MAX, fontSize + 1))}
                  disabled={fontSize >= EDITOR_FONT_MAX}
                >+</button>
              </div>
            </div>
            {/* Editor font family */}
            <div style={{ marginTop: 16 }}>
              <span style={{ fontSize: 13, color: "var(--text-1)", fontFamily: "var(--font-ui)" }}>Font family</span>
              <div style={ss.fontGrid}>
                {EDITOR_FONTS.map((f) => {
                  const active = (editorPrefs.editor_font || "JetBrains Mono") === f;
                  return (
                    <button
                      key={f}
                      style={{ ...ss.fontBtn, fontFamily: `${f}, monospace`,
                        background: active ? "var(--accent-dim)" : "var(--bg-2)",
                        borderColor: active ? "var(--accent)" : "var(--border)",
                        color: active ? "var(--text-0)" : "var(--text-1)" }}
                      onClick={() => onEditorPref?.("editor_font", f)}
                    >{f}</button>
                  );
                })}
              </div>
              <input
                style={{ ...ss.input, marginTop: 8 }}
                placeholder="Custom font name…"
                value={EDITOR_FONTS.includes(editorPrefs.editor_font) ? "" : (editorPrefs.editor_font || "")}
                onChange={(e) => onEditorPref?.("editor_font", e.target.value)}
              />
            </div>
          </div>

          {/* Theme */}
          <div style={ss.section}>
            <div style={ss.sectionTitle}>Theme</div>
            <div style={ss.themeGrid}>
              {THEME_CARDS.map((t) => {
                const active = theme === t.id;
                return (
                  <button
                    key={t.id}
                    style={{ ...ss.themeCard, borderColor: active ? "var(--accent)" : "var(--border)" }}
                    onClick={() => (onSelectTheme ? onSelectTheme(t.id) : onToggleTheme())}
                    title={t.label}
                  >
                    <div style={{ ...ss.themePrev, background: t.bg }}>
                      <div style={{ width: 14, background: t.panel }} />
                      <div style={{ flex: 1, padding: "5px 6px", display: "flex", flexDirection: "column", gap: 3 }}>
                        <div style={{ height: 3, borderRadius: 2, background: t.accent, width: "55%" }} />
                        <div style={{ height: 2, borderRadius: 2, background: t.text, width: "80%", opacity: 0.4 }} />
                        <div style={{ height: 2, borderRadius: 2, background: t.text, width: "45%", opacity: 0.3 }} />
                      </div>
                    </div>
                    <span style={{ ...ss.themeName, color: active ? "var(--text-0)" : "var(--text-1)" }}>
                      {t.label}{active && " ✓"}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <div style={ss.footer}>
          {saveMsg && <span style={ss.saveMsg}>{saveMsg}</span>}
          <button style={ss.saveBtn} onClick={save}>Save</button>
        </div>
      </div>
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const ss = {
  overlay: { position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", backdropFilter: "blur(3px)", WebkitBackdropFilter: "blur(3px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 10000, animation: "va-fade 120ms var(--ease)" },
  modal: { background: "var(--bg-1)", border: "1px solid var(--border)", borderRadius: "var(--r-lg)", boxShadow: "var(--shadow-lg)", width: 480, maxWidth: "calc(100vw - 48px)", maxHeight: "calc(100vh - 80px)", display: "flex", flexDirection: "column", overflow: "hidden", animation: "va-pop 160ms var(--ease)" },
  header: { padding: "16px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 },
  title: { fontSize: 14, fontWeight: 600, color: "var(--text-0)", fontFamily: "var(--font-ui)" },
  closeBtn: { width: 28, height: 28, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-2)", borderRadius: 6, cursor: "pointer" },
  body: { flex: 1, overflow: "auto", padding: 20 },
  section: { marginBottom: 24 },
  sectionTitle: { fontSize: 11, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-2)", marginBottom: 12, fontFamily: "var(--font-ui)" },
  providerGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 },
  providerBtn: { padding: "10px 12px", borderRadius: 8, border: "1px solid", fontSize: 13, fontFamily: "var(--font-ui)", cursor: "pointer", textAlign: "left" },
  keyRow: { marginTop: 12 },
  label: { display: "block", fontSize: 12, color: "var(--text-2)", marginBottom: 6, fontFamily: "var(--font-ui)" },
  input: { width: "100%", background: "var(--bg-2)", border: "1px solid var(--border)", borderRadius: 8, padding: "8px 12px", fontSize: 13, color: "var(--text-0)", fontFamily: "var(--font-mono)", boxSizing: "border-box" },
  hwBadge: { fontSize: 11, color: "var(--accent)", background: "var(--bg-2)", padding: "4px 10px", borderRadius: 6, marginBottom: 12, display: "inline-block", fontFamily: "var(--font-mono)" },
  row: { display: "flex", alignItems: "center", gap: 12 },
  dimText: { fontSize: 13, color: "var(--text-2)", fontFamily: "var(--font-ui)" },
  modelList: { display: "flex", flexDirection: "column", gap: 4 },
  modelBtn: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 12px", borderRadius: 8, border: "1px solid var(--border)", cursor: "pointer", fontFamily: "var(--font-mono)", fontSize: 13 },
  modelSize: { fontSize: 11, color: "var(--text-2)" },
  testBtn: { padding: "6px 14px", fontSize: 12, fontFamily: "var(--font-ui)", color: "var(--text-1)", background: "var(--bg-2)", border: "1px solid var(--border)", borderRadius: 6, cursor: "pointer" },
  guideBtn: { padding: "4px 10px", fontSize: 11, fontFamily: "var(--font-ui)", color: "var(--accent)", background: "transparent", border: "1px solid var(--accent)", borderRadius: 6, cursor: "pointer", whiteSpace: "nowrap" },
  stepBtn: { width: 26, height: 26, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, lineHeight: 1, color: "var(--text-1)", background: "var(--bg-2)", border: "1px solid var(--border)", borderRadius: 6, cursor: "pointer" },
  themeRow: { display: "flex", gap: 8 },
  themeBtn: { padding: "8px 20px", borderRadius: 8, border: "1px solid", fontSize: 13, fontFamily: "var(--font-ui)", cursor: "pointer" },
  themeGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 },
  themeCard: { borderRadius: 10, border: "2px solid", overflow: "hidden", cursor: "pointer", display: "flex", flexDirection: "column", padding: 0, background: "var(--bg-2)" },
  themePrev: { height: 48, display: "flex", flexDirection: "row", overflow: "hidden" },
  themeName: { fontSize: 12, fontWeight: 500, padding: "7px 10px", textAlign: "left", fontFamily: "var(--font-ui)" },
  fontGrid: { display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 },
  fontBtn: { padding: "6px 10px", borderRadius: 6, border: "1px solid", fontSize: 12, cursor: "pointer", whiteSpace: "nowrap" },
  footer: { padding: "12px 20px", borderTop: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 12, flexShrink: 0 },
  saveMsg: { fontSize: 12, color: "var(--accent)", fontFamily: "var(--font-ui)" },
  saveBtn: { background: "var(--accent)", color: "#fff", padding: "8px 20px", borderRadius: 8, fontSize: 13, fontFamily: "var(--font-ui)", cursor: "pointer" },
  link: { color: "var(--accent)", textDecoration: "none", fontSize: 12 },
};
