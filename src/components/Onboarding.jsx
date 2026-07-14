import { useState, useEffect } from "react";
import { getSystemInfo, sendHeartbeat, writeEnvKey, openExternal } from "../lib/tauri.js";

const DEFAULT_HACKATIME_URL = "https://hackatime.hackclub.com/api/hackatime/v1/users/current/heartbeats";
const HACKATIME_SETUP_URL = "https://hackatime.hackclub.com/my/wakatime_setup";

const prefersReducedMotion =
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Theme preview colours mirror the CSS variables in styles.css.
const THEME_CARDS = [
  { id: "dark",        label: "Dark",        bg: "#0b0b0f", panel: "#1c1c2a", accent: "#9088cc", text: "#e8e8f0", kw: "#9088cc", str: "#5dcaa5" },
  { id: "light",       label: "Light",       bg: "#f5f5f2", panel: "#edede9", accent: "#6258a8", text: "#18181e", kw: "#6258a8", str: "#1d9e75" },
  { id: "dracula",     label: "Dracula",     bg: "#282a36", panel: "#343746", accent: "#bd93f9", text: "#f8f8f2", kw: "#ff79c6", str: "#50fa7b" },
  { id: "one-dark",    label: "One Dark",    bg: "#282c34", panel: "#353b45", accent: "#61afef", text: "#d7dae0", kw: "#c678dd", str: "#98c379" },
  { id: "nord",        label: "Nord",        bg: "#2e3440", panel: "#3b4252", accent: "#88c0d0", text: "#eceff4", kw: "#81a1c1", str: "#a3be8c" },
  { id: "catppuccin",  label: "Catppuccin",  bg: "#1e1e2e", panel: "#313244", accent: "#cba6f7", text: "#cdd6f4", kw: "#cba6f7", str: "#a6e3a1" },
  { id: "github-dark", label: "GitHub Dark", bg: "#0d1117", panel: "#161b22", accent: "#58a6ff", text: "#c9d1d9", kw: "#ff7b72", str: "#a5d6ff" },
  { id: "solarized",   label: "Solarized",   bg: "#002b36", panel: "#073642", accent: "#268bd2", text: "#93a1a1", kw: "#859900", str: "#2aa198" },
];

const EDITOR_FONTS = ["JetBrains Mono", "Fira Code", "Cascadia Code", "Source Code Pro", "Inconsolata"];

function maxParamsForVram(vramMb) {
  if (vramMb <= 0) return Infinity;
  if (vramMb < 4096) return 3;
  if (vramMb < 8192) return 7;
  return Infinity;
}
function parseParams(name) {
  const m = name.match(/:(\d+(?:\.\d+)?)b/i) || name.match(/(\d+(?:\.\d+)?)b/i);
  return m ? parseFloat(m[1]) : Infinity;
}

// ── Horizontal slide transition ───────────────────────────────────────────────

function Slide({ step, children }) {
  const [shown, setShown] = useState(step);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    if (step === shown) return;
    setVisible(false);
    const t = setTimeout(() => { setShown(step); setVisible(true); }, prefersReducedMotion ? 0 : 140);
    return () => clearTimeout(t);
  }, [step, shown]);

  return (
    <div style={{
      opacity: prefersReducedMotion ? 1 : (visible ? 1 : 0),
      transform: prefersReducedMotion ? "none" : (visible ? "translateX(0)" : "translateX(16px)"),
      transition: prefersReducedMotion ? "none" : "opacity 0.16s ease, transform 0.16s ease",
    }}>
      {children}
    </div>
  );
}

function Steps({ current, total }) {
  return (
    <div style={s.steps}>
      {Array.from({ length: total }, (_, i) => (
        <div key={i} style={{ ...s.dot, background: i === current ? "var(--accent)" : "var(--bg-3)", width: i === current ? "20px" : "8px" }} />
      ))}
    </div>
  );
}

// ── Screen 0: Welcome ─────────────────────────────────────────────────────────

function ScreenWelcome({ onNext }) {
  const [show, setShow] = useState(false);
  useEffect(() => { const r = requestAnimationFrame(() => setShow(true)); return () => cancelAnimationFrame(r); }, []);
  return (
    <div style={{ textAlign: "center", padding: "20px 0" }}>
      <div style={{
        opacity: prefersReducedMotion ? 1 : (show ? 1 : 0),
        transform: prefersReducedMotion ? "none" : (show ? "translateY(0)" : "translateY(8px)"),
        transition: prefersReducedMotion ? "none" : "opacity 0.5s ease, transform 0.5s ease",
      }}>
        <div style={s.welcomeLogo}>V-Agent</div>
        <h2 style={{ ...s.heading, textAlign: "center" }}>Welcome to V-Agent</h2>
        <p style={{ ...s.sub, textAlign: "center" }}>A local-first, AI-powered code editor that runs on your machine.</p>
        <button style={{ ...s.nextBtn, marginTop: 8 }} onClick={onNext}>Get started</button>
      </div>
    </div>
  );
}

// ── Screen 1: Theme + font ─────────────────────────────────────────────────────

function ScreenTheme({ theme, font, onTheme, onFont }) {
  return (
    <div>
      <h2 style={s.heading}>Pick a look</h2>
      <p style={s.sub}>Theme and editor font — change them anytime in Settings.</p>
      <div style={s.themeGrid}>
        {THEME_CARDS.map((t) => {
          const active = theme === t.id;
          return (
            <button key={t.id}
              style={{ ...s.themeCard, borderColor: active ? "var(--accent)" : "var(--border)" }}
              onClick={() => { onTheme(t.id); document.documentElement.setAttribute("data-theme", t.id); }}
              title={t.label}>
              <div style={{ ...s.themeMock, background: t.bg }}>
                <div style={{ width: 16, background: t.panel }} />
                <div style={{ flex: 1, padding: "6px 7px", display: "flex", flexDirection: "column", gap: 3 }}>
                  <div style={{ display: "flex", gap: 4 }}>
                    <span style={{ height: 3, width: "22%", background: t.kw, borderRadius: 2 }} />
                    <span style={{ height: 3, width: "30%", background: t.text, opacity: 0.5, borderRadius: 2 }} />
                  </div>
                  <span style={{ height: 3, width: "60%", background: t.str, borderRadius: 2 }} />
                  <span style={{ height: 3, width: "45%", background: t.text, opacity: 0.3, borderRadius: 2 }} />
                  <span style={{ height: 3, width: "35%", background: t.accent, borderRadius: 2 }} />
                </div>
              </div>
              <span style={{ ...s.themeName, color: active ? "var(--text-0)" : "var(--text-1)" }}>
                {t.label}{active && " ✓"}
              </span>
            </button>
          );
        })}
      </div>

      <div style={{ marginTop: 18 }}>
        <span style={s.fieldLabel}>Editor font</span>
        <div style={s.fontList}>
          {EDITOR_FONTS.map((f) => {
            const active = font === f;
            return (
              <button key={f}
                style={{ ...s.fontRow, borderColor: active ? "var(--accent)" : "var(--border)", background: active ? "var(--accent-dim)" : "var(--bg-2)" }}
                onClick={() => onFont(f)}>
                <span style={{ fontFamily: `${f}, monospace`, fontSize: 13, color: "var(--text-0)" }}>const hello = () =&gt; {"{}"}</span>
                <span style={{ fontSize: 11, color: "var(--text-2)", fontFamily: "var(--font-ui)" }}>{f}{active && " ✓"}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Screen 2: AI provider ──────────────────────────────────────────────────────

function ScreenProvider({ value, apiKey, apiProvider, ollamaStatus, ollamaModels, sysInfo, onChange, onApiKey, onApiProvider }) {
  const [testMsg, setTestMsg] = useState("");
  const options = [
    { id: "backend", label: "V-Agent Cloud", desc: "No setup. Shared server with fair-use limits.", badge: "Recommended" },
    { id: "apikey",  label: "My API key",    desc: "Use Groq or OpenRouter with your own account.", badge: null },
    { id: "ollama",  label: "Local (Ollama)", desc: "Runs fully offline on your machine. Private.", badge: null },
  ];
  const maxParams = sysInfo ? maxParamsForVram(sysInfo.vram_mb) : Infinity;
  const fitModels = (ollamaModels || []).filter((m) => parseParams(m) <= maxParams);

  return (
    <div>
      <h2 style={s.heading}>How do you want to use AI?</h2>
      <p style={s.sub}>You can switch providers any time.</p>
      <div style={s.optionList}>
        {options.map((opt) => (
          <button key={opt.id}
            style={{ ...s.optionCard, borderColor: value === opt.id ? "var(--accent)" : "var(--border)", background: value === opt.id ? "var(--bg-2)" : "var(--bg-1)" }}
            onClick={() => onChange(opt.id)}>
            <div style={s.optionDot}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: value === opt.id ? "var(--accent)" : "transparent", border: `2px solid ${value === opt.id ? "var(--accent)" : "var(--text-2)"}` }} />
            </div>
            <div style={{ flex: 1, textAlign: "left" }}>
              <div style={s.optionLabel}>
                {opt.label}
                {opt.badge && <span style={s.badge}>{opt.badge}</span>}
              </div>
              <div style={s.optionDesc}>{opt.desc}</div>
            </div>
          </button>
        ))}
      </div>

      {value === "apikey" && (
        <div style={s.subSection}>
          <div style={s.subRow}>
            {["groq", "openrouter"].map((p) => (
              <button key={p}
                style={{ ...s.subToggle, background: apiProvider === p ? "var(--accent-dim)" : "var(--bg-3)", color: apiProvider === p ? "var(--text-0)" : "var(--text-2)", borderColor: apiProvider === p ? "var(--accent)" : "var(--border)" }}
                onClick={() => onApiProvider(p)}>
                {p === "groq" ? "Groq" : "OpenRouter"}
              </button>
            ))}
          </div>
          <input type="password" style={s.keyInput} autoComplete="off"
            placeholder={apiProvider === "groq" ? "gsk_..." : "sk-or-..."}
            value={apiKey} onChange={(e) => onApiKey(e.target.value)} />
          <button style={s.testBtn} onClick={async () => {
            setTestMsg("Testing…");
            try {
              // Reuse the heartbeat endpoint only as a connectivity check would be wrong;
              // instead just validate key shape (full test happens on first chat).
              if (!apiKey.trim()) { setTestMsg("Enter a key first."); return; }
              const ok = apiProvider === "groq" ? apiKey.startsWith("gsk_") : apiKey.startsWith("sk-or-");
              setTestMsg(ok ? "✓ Key looks valid" : "✗ Unexpected key format");
            } catch (e) { setTestMsg(`✗ ${e}`); }
          }}>Test key</button>
          {testMsg && <span style={{ fontSize: 12, color: testMsg.startsWith("✓") ? "var(--ok)" : "var(--text-2)", fontFamily: "var(--font-ui)" }}>{testMsg}</span>}
        </div>
      )}

      {value === "ollama" && (
        <div style={s.subSection}>
          <div style={{ ...s.ollamaStatus, color: ollamaStatus === "running" ? "var(--accent)" : "var(--text-2)" }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: ollamaStatus === "running" ? "var(--accent)" : "var(--border)", flexShrink: 0 }} />
            {ollamaStatus === "checking" && "Checking Ollama…"}
            {ollamaStatus === "running"  && "Ollama is running"}
            {ollamaStatus === "offline"  && (
              <>Not detected.{" "}<a href="https://ollama.com/download" target="_blank" rel="noreferrer" style={s.link}>Install Ollama ↗</a></>
            )}
          </div>
          {sysInfo && (sysInfo.total_ram_mb > 0 || sysInfo.vram_mb > 0) && (
            <div style={s.hwBadge}>
              {sysInfo.total_ram_mb > 0 && `RAM ${(sysInfo.total_ram_mb / 1024).toFixed(1)} GB`}
              {sysInfo.vram_mb > 0 && ` · VRAM ${(sysInfo.vram_mb / 1024).toFixed(1)} GB · models ≤ ${maxParams === Infinity ? "all" : maxParams + "B"}`}
            </div>
          )}
          {ollamaStatus === "running" && (
            <div style={{ fontSize: 12, color: "var(--text-2)", fontFamily: "var(--font-ui)" }}>
              {ollamaModels === null ? "Loading models…"
                : fitModels.length === 0 ? "No compatible models. Try: ollama pull llama3.2"
                : `Available: ${fitModels.slice(0, 6).join(", ")}`}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Screen 3: Hackatime ────────────────────────────────────────────────────────

function ScreenHackatime({ enabled, apiKey, onEnabled, onApiKey, onAdvance }) {
  const [state, setState] = useState("idle"); // idle | testing | ok | error
  const [msg, setMsg] = useState("");

  const test = async () => {
    if (!apiKey.trim()) { setState("error"); setMsg("Enter your API key first."); return; }
    setState("testing"); setMsg("");
    try {
      await sendHeartbeat("test", "V-Agent", "Text", false, apiKey.trim(), DEFAULT_HACKATIME_URL);
      setState("ok"); setMsg("Connected ✓");
      window.notify?.("Connected ✓", "success");
      setTimeout(() => onAdvance?.(), 900);   // auto-advance on success
    } catch (e) {
      setState("error"); setMsg(`Couldn't connect: ${e}`);
    }
  };

  return (
    <div>
      <h2 style={s.heading}>Track your coding time?</h2>
      <p style={s.sub}>Hackatime tracks the time you spend coding across all your editors. Optional — you can skip this.</p>
      <div style={s.toggleRow}>
        <span style={{ fontSize: 13, color: "var(--text-1)", fontFamily: "var(--font-ui)" }}>Enable time tracking</span>
        <button onClick={() => onEnabled(!enabled)} style={{ ...s.switch, background: enabled ? "var(--accent)" : "var(--bg-3)" }}>
          <span style={{ ...s.knob, left: enabled ? 20 : 2 }} />
        </button>
      </div>
      {enabled && (
        <div style={s.subSection}>
          <button style={s.testBtn} onClick={() => openExternal(HACKATIME_SETUP_URL).catch(() => {})}>Get my API key ↗</button>
          <div style={{ display: "flex", gap: 8 }}>
            <input type="password" style={{ ...s.keyInput, flex: 1 }} placeholder="waka_..." autoComplete="off"
              value={apiKey}
              onChange={(e) => { onApiKey(e.target.value); setState("idle"); setMsg(""); }} />
            <button style={s.testInline} disabled={state === "testing"} onClick={test}>
              {state === "testing" ? "…" : "Test"}
            </button>
          </div>
          {msg && (
            <span style={{ fontSize: 12, fontFamily: "var(--font-ui)", color: state === "ok" ? "var(--ok)" : "var(--err)" }}>
              {msg}
              {state === "error" && (
                <>{" · "}
                  <a href={HACKATIME_SETUP_URL} style={s.link}
                    onClick={(e) => { e.preventDefault(); openExternal(HACKATIME_SETUP_URL).catch(() => {}); }}>
                    setup guide ↗
                  </a>
                </>
              )}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// ── Screen 4: Editor preferences ───────────────────────────────────────────────

function ScreenEditor({ fontSize, tabSize, autoSave, wordWrap, font, onFontSize, onTabSize, onAutoSave, onWordWrap }) {
  return (
    <div>
      <h2 style={s.heading}>Editor preferences</h2>
      <p style={s.sub}>Fine-tune how the editor feels.</p>

      <div style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span style={s.fieldLabel}>Font size</span>
          <span style={{ fontSize: 12, color: "var(--text-2)", fontFamily: "var(--font-mono)" }}>{fontSize}px</span>
        </div>
        <input type="range" min={10} max={20} value={fontSize} onChange={(e) => onFontSize(Number(e.target.value))} style={{ width: "100%", accentColor: "var(--accent)" }} />
        <pre style={{ ...s.codePreview, fontFamily: `${font}, monospace`, fontSize }}>
{`function greet(name) {\n  return "Hello, " + name;\n}`}
        </pre>
      </div>

      <div style={s.toggleRow}>
        <span style={s.fieldLabel}>Tab size</span>
        <div style={{ display: "flex", gap: 6 }}>
          {[2, 4].map((n) => (
            <button key={n}
              style={{ ...s.pillBtn, background: tabSize === n ? "var(--accent-dim)" : "var(--bg-2)", borderColor: tabSize === n ? "var(--accent)" : "var(--border)", color: tabSize === n ? "var(--text-0)" : "var(--text-1)" }}
              onClick={() => onTabSize(n)}>{n} spaces</button>
          ))}
        </div>
      </div>

      <div style={s.toggleRow}>
        <span style={s.fieldLabel}>Auto-save</span>
        <button onClick={() => onAutoSave(!autoSave)} style={{ ...s.switch, background: autoSave ? "var(--accent)" : "var(--bg-3)" }}>
          <span style={{ ...s.knob, left: autoSave ? 20 : 2 }} />
        </button>
      </div>

      <div style={s.toggleRow}>
        <span style={s.fieldLabel}>Word wrap</span>
        <button onClick={() => onWordWrap(!wordWrap)} style={{ ...s.switch, background: wordWrap ? "var(--accent)" : "var(--bg-3)" }}>
          <span style={{ ...s.knob, left: wordWrap ? 20 : 2 }} />
        </button>
      </div>
    </div>
  );
}

// ── Screen 5: Ready ────────────────────────────────────────────────────────────

function ScreenReady({ theme, provider, apiProvider, apiKey, hkEnabled }) {
  const providerLabel = {
    backend: "V-Agent Cloud",
    apikey:  `${apiProvider === "groq" ? "Groq" : "OpenRouter"}${apiKey ? " ✓" : " (no key)"}`,
    ollama:  "Local Ollama",
  }[provider];
  const themeLabel = THEME_CARDS.find((t) => t.id === theme)?.label || theme;
  const rows = [
    { label: "Theme", value: themeLabel },
    { label: "AI", value: providerLabel },
    { label: "Time tracking", value: hkEnabled ? "Enabled" : "Off" },
  ];
  return (
    <div>
      <div style={{ textAlign: "center", marginBottom: 16 }}>
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
        </svg>
      </div>
      <h2 style={{ ...s.heading, textAlign: "center" }}>You're all set</h2>
      <p style={{ ...s.sub, textAlign: "center" }}>Here's what you configured:</p>
      <div style={s.summaryList}>
        {rows.map((r) => (
          <div key={r.label} style={s.summaryRow}>
            <span style={s.summaryLabel}>{r.label}</span>
            <span style={s.summaryValue}>{r.value}</span>
          </div>
        ))}
      </div>
      <p style={{ ...s.sub, textAlign: "center", marginTop: 16 }}>
        Open a folder from the Explorer to start coding.{" "}
        <a href="https://github.com/otzpt/V-Agent" target="_blank" rel="noreferrer" style={s.link}>Docs ↗</a>
      </p>
    </div>
  );
}

// ── Main shell ─────────────────────────────────────────────────────────────────

export default function Onboarding({ onComplete }) {
  const [step, setStep] = useState(0);
  const [theme, setTheme] = useState("dark");
  const [font, setFont] = useState("JetBrains Mono");
  const [provider, setProvider] = useState("backend");
  const [apiProvider, setApiProvider] = useState("groq");
  const [apiKey, setApiKey] = useState("");
  const [ollamaStatus, setOllamaStatus] = useState("checking");
  const [ollamaModels, setOllamaModels] = useState(null);
  const [sysInfo, setSysInfo] = useState(null);
  const [hkEnabled, setHkEnabled] = useState(false);
  const [hkKey, setHkKey] = useState("");
  const [fontSize, setFontSize] = useState(13);
  const [tabSize, setTabSize] = useState(4);
  const [autoSave, setAutoSave] = useState(false);
  const [wordWrap, setWordWrap] = useState(false);

  const TOTAL = 6;

  // Hardware info (for Ollama model filtering) — fetched once.
  useEffect(() => {
    getSystemInfo().then(setSysInfo).catch(() => setSysInfo({ total_ram_mb: 0, vram_mb: 0 }));
  }, []);

  // Probe Ollama whenever it's selected.
  useEffect(() => {
    if (provider !== "ollama") return;
    setOllamaStatus("checking");
    fetch("http://localhost:11434/api/tags", { signal: AbortSignal.timeout(3000) })
      .then((r) => r.json())
      .then((d) => { setOllamaStatus("running"); setOllamaModels((d.models || []).map((m) => m.name)); })
      .catch(() => { setOllamaStatus("offline"); setOllamaModels([]); });
  }, [provider]);

  // NOTE: nothing is persisted until finish(), so closing the window mid-flow
  // leaves no partial config behind.
  const finish = () => {
    const cfg = {
      version: 1,
      theme,
      editor_font: font,
      editor_font_size: fontSize,
      tab_size: tabSize,
      auto_save: autoSave,
      word_wrap: wordWrap,
      ai_provider: provider === "apikey" ? apiProvider : provider,
      hackatime_enabled: hkEnabled,
      hackatime_api_key: hkKey.trim(),
      hackatime_api_url: DEFAULT_HACKATIME_URL,
    };
    if (provider === "apikey" && apiKey) {
      cfg.api_key = apiKey;
      cfg[apiProvider === "groq" ? "groq_api_key" : "openrouter_api_key"] = apiKey;
      writeEnvKey(apiProvider === "groq" ? "GROQ_API_KEY" : "OPENROUTER_API_KEY", apiKey).catch(() => {});
    }
    onComplete(cfg);
  };

  const screens = [
    <ScreenWelcome onNext={() => setStep(1)} />,
    <ScreenTheme theme={theme} font={font} onTheme={setTheme} onFont={setFont} />,
    <ScreenProvider value={provider} apiKey={apiKey} apiProvider={apiProvider} ollamaStatus={ollamaStatus} ollamaModels={ollamaModels} sysInfo={sysInfo} onChange={setProvider} onApiKey={setApiKey} onApiProvider={setApiProvider} />,
    <ScreenHackatime enabled={hkEnabled} apiKey={hkKey} onEnabled={setHkEnabled} onApiKey={setHkKey} onAdvance={() => setStep(4)} />,
    <ScreenEditor fontSize={fontSize} tabSize={tabSize} autoSave={autoSave} wordWrap={wordWrap} font={font} onFontSize={setFontSize} onTabSize={setTabSize} onAutoSave={setAutoSave} onWordWrap={setWordWrap} />,
    <ScreenReady theme={theme} provider={provider} apiProvider={apiProvider} apiKey={apiKey} hkEnabled={hkEnabled} />,
  ];

  return (
    <div style={s.overlay}>
      <div style={s.card}>
        <div style={s.logo}>V-Agent</div>
        <div style={s.content}>
          <Slide step={step}>{screens[step]}</Slide>
        </div>
        <div style={s.nav}>
          <Steps current={step} total={TOTAL} />
          <div style={s.navBtns}>
            {step > 0 && <button style={s.backBtn} onClick={() => setStep((n) => n - 1)}>Back</button>}
            {step === 0 ? null : step < TOTAL - 1 ? (
              <button style={s.nextBtn} onClick={() => setStep((n) => n + 1)}>
                {step === 3 && !hkEnabled ? "Skip" : "Next"}
              </button>
            ) : (
              <button style={s.nextBtn} onClick={finish}>Start V-Agent</button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const s = {
  overlay: { position: "fixed", inset: 0, background: "var(--bg-0)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 10000 },
  card: { width: 480, maxWidth: "calc(100vw - 32px)", maxHeight: "calc(100vh - 48px)", background: "var(--bg-1)", border: "1px solid var(--border)", borderRadius: 16, boxShadow: "var(--shadow-lg)", padding: 32, display: "flex", flexDirection: "column", gap: 24, overflow: "hidden", animation: "va-pop 200ms var(--ease)" },
  logo: { fontFamily: "var(--font-mono)", fontSize: 14, color: "var(--accent)", letterSpacing: "0.08em", textAlign: "center" },
  content: { minHeight: 320, maxHeight: "60vh", overflowY: "auto" },
  welcomeLogo: { fontFamily: "var(--font-mono)", fontSize: 36, fontWeight: 700, color: "var(--accent)", letterSpacing: "0.04em", marginBottom: 16 },
  heading: { fontFamily: "var(--font-ui)", fontSize: 20, fontWeight: 700, color: "var(--text-0)", margin: "0 0 8px" },
  sub: { fontFamily: "var(--font-ui)", fontSize: 13, color: "var(--text-2)", margin: "0 0 20px", lineHeight: 1.5 },
  steps: { display: "flex", alignItems: "center", gap: 6 },
  dot: { height: 8, borderRadius: 4, transition: prefersReducedMotion ? "none" : "width 0.2s, background 0.2s" },
  nav: { display: "flex", alignItems: "center", justifyContent: "space-between" },
  navBtns: { display: "flex", gap: 8 },
  backBtn: { padding: "8px 20px", borderRadius: 8, border: "1px solid var(--border)", fontSize: 13, fontFamily: "var(--font-ui)", color: "var(--text-1)", background: "transparent", cursor: "pointer" },
  nextBtn: { padding: "8px 24px", borderRadius: 8, border: "none", fontSize: 13, fontFamily: "var(--font-ui)", color: "#fff", background: "var(--accent)", cursor: "pointer" },

  fieldLabel: { fontSize: 13, color: "var(--text-1)", fontFamily: "var(--font-ui)" },

  // Theme
  themeGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 },
  themeCard: { borderRadius: 10, border: "2px solid", overflow: "hidden", cursor: "pointer", display: "flex", flexDirection: "column", padding: 0, background: "var(--bg-2)" },
  themeMock: { height: 52, display: "flex", flexDirection: "row", overflow: "hidden" },
  themeName: { fontSize: 12, fontWeight: 500, padding: "7px 10px", textAlign: "left", fontFamily: "var(--font-ui)" },
  fontList: { display: "flex", flexDirection: "column", gap: 6, marginTop: 8 },
  fontRow: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 12px", borderRadius: 8, border: "1px solid", cursor: "pointer" },

  // Provider
  optionList: { display: "flex", flexDirection: "column", gap: 8 },
  optionCard: { display: "flex", alignItems: "flex-start", gap: 12, padding: "12px 14px", borderRadius: 10, border: "1.5px solid", cursor: "pointer", textAlign: "left" },
  optionDot: { paddingTop: 2, flexShrink: 0 },
  optionLabel: { fontFamily: "var(--font-ui)", fontSize: 13, fontWeight: 600, color: "var(--text-0)", marginBottom: 2, display: "flex", alignItems: "center", gap: 8 },
  optionDesc: { fontFamily: "var(--font-ui)", fontSize: 12, color: "var(--text-2)" },
  badge: { fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--accent)", background: "var(--accent-dim)", padding: "1px 6px", borderRadius: 4 },
  subSection: { marginTop: 12, padding: 12, background: "var(--bg-2)", borderRadius: 8, display: "flex", flexDirection: "column", gap: 8 },
  subRow: { display: "flex", gap: 8 },
  subToggle: { padding: "5px 14px", borderRadius: 6, border: "1px solid", fontSize: 12, fontFamily: "var(--font-ui)", cursor: "pointer" },
  keyInput: { background: "var(--bg-3)", border: "1px solid var(--border)", borderRadius: 6, padding: "7px 10px", fontSize: 13, color: "var(--text-0)", fontFamily: "var(--font-mono)", width: "100%", boxSizing: "border-box" },
  testBtn: { alignSelf: "flex-start", padding: "5px 14px", fontSize: 12, fontFamily: "var(--font-ui)", color: "var(--text-1)", background: "var(--bg-3)", border: "1px solid var(--border)", borderRadius: 6, cursor: "pointer" },
  testInline: { flexShrink: 0, padding: "0 14px", fontSize: 12, fontFamily: "var(--font-ui)", color: "var(--text-0)", background: "var(--accent-dim)", border: "1px solid var(--accent)", borderRadius: 6, cursor: "pointer" },
  ollamaStatus: { display: "flex", alignItems: "center", gap: 8, fontSize: 13, fontFamily: "var(--font-ui)" },
  hwBadge: { fontSize: 11, color: "var(--accent)", background: "var(--bg-3)", padding: "4px 10px", borderRadius: 6, display: "inline-block", fontFamily: "var(--font-mono)" },
  link: { color: "var(--accent)", textDecoration: "none" },

  // Hackatime / editor toggles
  toggleRow: { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 },
  switch: { width: 40, height: 22, borderRadius: 11, border: "1px solid var(--border)", position: "relative", cursor: "pointer", flexShrink: 0 },
  knob: { position: "absolute", top: 2, width: 16, height: 16, borderRadius: "50%", background: "#fff", transition: prefersReducedMotion ? "none" : "left 0.15s" },
  pillBtn: { padding: "6px 12px", borderRadius: 6, border: "1px solid", fontSize: 12, fontFamily: "var(--font-ui)", cursor: "pointer" },
  codePreview: { margin: "8px 0 0", padding: 12, background: "var(--bg-0)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text-1)", overflowX: "auto", lineHeight: 1.5 },

  // Ready
  summaryList: { background: "var(--bg-2)", borderRadius: 8, overflow: "hidden", border: "1px solid var(--border)" },
  summaryRow: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 14px", borderBottom: "1px solid var(--border)" },
  summaryLabel: { fontSize: 12, color: "var(--text-2)", fontFamily: "var(--font-ui)" },
  summaryValue: { fontSize: 13, color: "var(--text-0)", fontFamily: "var(--font-mono)" },
};
