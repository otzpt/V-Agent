import { useState, useEffect, useCallback } from "react";
import { installExtension, uninstallExtension, listExtensions, openExternal } from "../lib/tauri.js";

const REGISTRY_URL = "https://raw.githubusercontent.com/otzpt/vagent-extensions/main/registry.json";
const REGISTRY_REPO = "https://github.com/otzpt/vagent-extensions";

// ── Extension card ────────────────────────────────────────────────────────────

function ExtCard({ ext, isInstalled, busy, onInstall, onUninstall }) {
  return (
    <div style={es.card}>
      <div style={es.cardHeader}>
        <div style={es.cardName}>{ext.name || ext.id}</div>
        <div style={es.cardMeta}>
          {ext.author && <span style={es.author}>{ext.author}</span>}
          {ext.version && <span style={es.version}>v{ext.version}</span>}
        </div>
      </div>
      {ext.description && (
        <div style={es.cardDesc}>{ext.description}</div>
      )}
      {ext.tags?.length > 0 && (
        <div style={es.tags}>
          {ext.tags.map((t) => <span key={t} style={es.tag}>{t}</span>)}
        </div>
      )}
      <div style={es.cardFooter}>
        {ext.repo && (
          <button
            style={es.repoBtn}
            onClick={() => openExternal(ext.repo).catch(() => {})}
            title="View source repository"
          >
            View source ↗
          </button>
        )}
        {isInstalled ? (
          <button
            style={{ ...es.actionBtn, ...es.uninstallBtn, opacity: busy ? 0.5 : 1 }}
            disabled={!!busy}
            onClick={() => onUninstall(ext.id)}
          >
            {busy === "uninstalling" ? "Removing…" : "Uninstall"}
          </button>
        ) : (
          <button
            style={{ ...es.actionBtn, ...es.installBtn, opacity: busy ? 0.5 : 1 }}
            disabled={!!busy}
            onClick={() => onInstall(ext)}
          >
            {busy === "installing" ? "Installing…" : "Install"}
          </button>
        )}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ExtensionStore() {
  const [tab,       setTab]       = useState("store");       // "store" | "installed"
  const [search,    setSearch]    = useState("");
  const [registry,  setRegistry]  = useState(null);          // null=loading, []=loaded
  const [loadError, setLoadError] = useState(null);
  const [installed, setInstalled] = useState([]);            // list of installed IDs
  const [busy,      setBusy]      = useState({});            // { [id]: "installing"|"uninstalling" }

  // Load registry from GitHub
  useEffect(() => {
    fetch(REGISTRY_URL)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => setRegistry(Array.isArray(data) ? data : []))
      .catch((e) => {
        setRegistry([]);
        setLoadError(String(e));
      });
  }, []);

  // Load list of locally installed extension IDs
  const refreshInstalled = useCallback(() => {
    listExtensions().then(setInstalled).catch(() => setInstalled([]));
  }, []);

  useEffect(() => { refreshInstalled(); }, [refreshInstalled]);

  const install = async (ext) => {
    // Build raw GitHub download URL from repo + entry
    const repoPath = ext.repo?.replace("https://github.com/", "") ?? "";
    const rawUrl = `https://raw.githubusercontent.com/${repoPath}/main/${ext.entry || "main.py"}`;
    setBusy((prev) => ({ ...prev, [ext.id]: "installing" }));
    try {
      await installExtension(ext.id, rawUrl);
      await refreshInstalled();
      window.notify?.(`Installed ${ext.name || ext.id}`, "success");
    } catch (e) {
      window.notify?.(`Install failed: ${e}`, "error");
    } finally {
      setBusy((prev) => ({ ...prev, [ext.id]: null }));
    }
  };

  const uninstall = async (id) => {
    setBusy((prev) => ({ ...prev, [id]: "uninstalling" }));
    try {
      await uninstallExtension(id);
      await refreshInstalled();
      window.notify?.(`Uninstalled ${id}`, "success");
    } catch (e) {
      window.notify?.(`Uninstall failed: ${e}`, "error");
    } finally {
      setBusy((prev) => ({ ...prev, [id]: null }));
    }
  };

  const isInstalled = (id) => installed.includes(id);

  // Filter registry by search query
  const filtered = (registry || []).filter((ext) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      ext.name?.toLowerCase().includes(q) ||
      ext.description?.toLowerCase().includes(q) ||
      ext.tags?.some((t) => t.toLowerCase().includes(q))
    );
  });

  // For "Installed" tab: use registry info when available, fallback to bare {id}
  const installedExts = tab === "installed"
    ? installed.map((id) => (registry || []).find((e) => e.id === id) || { id, name: id })
    : [];

  return (
    <div style={es.wrap}>
      {/* ── Header ── */}
      <div style={es.header}>
        <span style={es.title}>Extensions</span>
        <div style={es.tabs}>
          <button
            style={{ ...es.tabBtn, borderBottom: tab === "store" ? "2px solid var(--accent)" : "2px solid transparent", color: tab === "store" ? "var(--text-0)" : "var(--text-2)" }}
            onClick={() => setTab("store")}
          >
            Store
          </button>
          <button
            style={{ ...es.tabBtn, borderBottom: tab === "installed" ? "2px solid var(--accent)" : "2px solid transparent", color: tab === "installed" ? "var(--text-0)" : "var(--text-2)" }}
            onClick={() => setTab("installed")}
          >
            Installed
            {installed.length > 0 && (
              <span style={es.countBadge}>{installed.length}</span>
            )}
          </button>
        </div>
      </div>

      {/* ── Search (store only) ── */}
      {tab === "store" && (
        <div style={es.searchRow}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--text-2)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
            <circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>
          </svg>
          <input
            style={es.searchInput}
            placeholder="Search extensions…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            autoComplete="off"
            spellCheck={false}
          />
          {search && (
            <button style={es.clearBtn} onClick={() => setSearch("")}>×</button>
          )}
        </div>
      )}

      {/* ── Content ── */}
      <div style={es.content}>
        {tab === "store" ? (
          registry === null ? (
            <div style={es.centerMsg}>
              <div style={es.spinner} />
              <span style={{ color: "var(--text-2)", fontSize: 12 }}>Loading registry…</span>
            </div>
          ) : filtered.length === 0 && !search ? (
            /* Empty registry */
            <div style={es.emptyState}>
              <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="var(--text-2)" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="8" height="8" rx="1"/>
                <rect x="13" y="3" width="8" height="8" rx="1"/>
                <rect x="3" y="13" width="8" height="8" rx="1"/>
                <path d="M13 17h8M17 13v8"/>
              </svg>
              <div style={{ fontSize: 13, color: "var(--text-1)", fontWeight: 500 }}>
                No extensions available yet
              </div>
              <div style={{ fontSize: 12, color: "var(--text-2)", textAlign: "center", lineHeight: 1.5 }}>
                {loadError ? `Could not reach registry: ${loadError}` : "The extension registry is empty."}
              </div>
              <button
                style={es.createBtn}
                onClick={() => openExternal(REGISTRY_REPO).catch(() => {})}
              >
                Create the first extension ↗
              </button>
            </div>
          ) : filtered.length === 0 ? (
            <div style={es.centerMsg}>
              <span style={{ color: "var(--text-2)", fontSize: 12 }}>No results for "{search}"</span>
            </div>
          ) : (
            filtered.map((ext) => (
              <ExtCard
                key={ext.id}
                ext={ext}
                isInstalled={isInstalled(ext.id)}
                busy={busy[ext.id]}
                onInstall={install}
                onUninstall={uninstall}
              />
            ))
          )
        ) : (
          /* Installed tab */
          installed.length === 0 ? (
            <div style={es.centerMsg}>
              <span style={{ color: "var(--text-2)", fontSize: 12 }}>No extensions installed.</span>
            </div>
          ) : (
            installedExts.map((ext) => (
              <ExtCard
                key={ext.id}
                ext={ext}
                isInstalled={true}
                busy={busy[ext.id]}
                onInstall={install}
                onUninstall={uninstall}
              />
            ))
          )
        )}
      </div>
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const es = {
  wrap: { display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" },
  header: {
    padding: "10px 12px 0",
    flexShrink: 0,
    borderBottom: "1px solid var(--border)",
  },
  title: {
    display: "block",
    fontSize: 11, letterSpacing: "0.06em", textTransform: "uppercase",
    color: "var(--text-2)", fontFamily: "var(--font-ui)", marginBottom: 8,
  },
  tabs: { display: "flex", gap: 0 },
  tabBtn: {
    padding: "6px 12px", fontSize: 12, fontFamily: "var(--font-ui)",
    background: "none", border: "none", cursor: "pointer",
    display: "flex", alignItems: "center", gap: 5,
    transition: "color var(--dur) var(--ease)",
  },
  countBadge: {
    fontSize: 10, fontFamily: "var(--font-mono)",
    background: "var(--accent-dim)", color: "var(--accent)",
    borderRadius: "var(--r-full)", padding: "1px 6px",
  },
  searchRow: {
    display: "flex", alignItems: "center", gap: 6,
    margin: "8px 10px", padding: "5px 10px",
    background: "var(--bg-2)", border: "1px solid var(--border)",
    borderRadius: "var(--r-sm)", flexShrink: 0,
  },
  searchInput: {
    flex: 1, fontSize: 12, fontFamily: "var(--font-ui)", color: "var(--text-0)",
    background: "transparent", border: "none", outline: "none",
  },
  clearBtn: {
    fontSize: 14, color: "var(--text-2)", background: "none", border: "none",
    cursor: "pointer", lineHeight: 1, padding: "0 2px",
  },
  content: { flex: 1, overflow: "auto", padding: "8px 10px", display: "flex", flexDirection: "column", gap: 8 },
  card: {
    background: "var(--bg-2)", border: "1px solid var(--border)",
    borderRadius: "var(--r-md)", padding: "12px 14px",
    display: "flex", flexDirection: "column", gap: 6,
    transition: "border-color var(--dur) var(--ease)",
  },
  cardHeader: { display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 },
  cardName: { fontSize: 13, fontWeight: 600, color: "var(--text-0)", fontFamily: "var(--font-ui)" },
  cardMeta: { display: "flex", gap: 6, alignItems: "center", flexShrink: 0 },
  author: { fontSize: 10, color: "var(--text-2)", fontFamily: "var(--font-ui)" },
  version: {
    fontSize: 10, color: "var(--accent)", fontFamily: "var(--font-mono)",
    background: "var(--accent-dim)", padding: "1px 5px", borderRadius: "var(--r-xs)",
  },
  cardDesc: { fontSize: 12, color: "var(--text-1)", fontFamily: "var(--font-ui)", lineHeight: 1.5 },
  tags: { display: "flex", flexWrap: "wrap", gap: 4 },
  tag: {
    fontSize: 10, color: "var(--text-2)", background: "var(--bg-3)",
    border: "1px solid var(--border)", borderRadius: "var(--r-xs)", padding: "1px 6px",
    fontFamily: "var(--font-mono)",
  },
  cardFooter: { display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 8, marginTop: 2 },
  repoBtn: {
    fontSize: 11, color: "var(--text-2)", background: "none", border: "none",
    cursor: "pointer", fontFamily: "var(--font-ui)", marginRight: "auto",
    textDecoration: "underline", textDecorationColor: "transparent",
    transition: "color var(--dur) var(--ease)",
  },
  actionBtn: {
    padding: "5px 12px", fontSize: 11, fontFamily: "var(--font-ui)",
    borderRadius: "var(--r-sm)", cursor: "pointer",
    border: "1px solid var(--border)", transition: "opacity var(--dur) var(--ease)",
  },
  installBtn: { background: "var(--accent)", color: "#fff", border: "none" },
  uninstallBtn: { background: "var(--bg-3)", color: "var(--text-1)" },
  centerMsg: { flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 },
  emptyState: {
    flex: 1, display: "flex", flexDirection: "column", alignItems: "center",
    justifyContent: "center", gap: 12, padding: 24, textAlign: "center",
  },
  createBtn: {
    padding: "7px 16px", fontSize: 12, fontFamily: "var(--font-ui)",
    background: "var(--accent)", color: "#fff",
    border: "none", borderRadius: "var(--r-sm)", cursor: "pointer", marginTop: 4,
  },
  spinner: {
    width: 16, height: 16, borderRadius: "50%",
    border: "2px solid var(--border)", borderTopColor: "var(--accent)",
    animation: "spin 0.8s linear infinite",
  },
};
