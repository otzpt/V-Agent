import { memo, useState, useEffect, useRef, useCallback } from "react";
import { openExternal } from "../lib/tauri.js";

// ── Content builder ───────────────────────────────────────────────────────────

const CSS_SCAFFOLD = `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>*{box-sizing:border-box}CONTENT</style></head><body>
<h1>Heading 1</h1><h2>Heading 2</h2><h3>Heading 3</h3>
<p>Paragraph with a <a href="#">link</a>, <strong>bold</strong>, <em>italic</em>.</p>
<ul><li>List item one</li><li>List item two</li><li>List item three</li></ul>
<ol><li>Ordered one</li><li>Ordered two</li></ol>
<p><button>Button</button> <input type="text" placeholder="Text input" /></p>
<div class="container"><div class="card"><div class="box">div.box › div.card › div.container</div></div></div>
</body></html>`;

function buildSrcDoc(content, fileName, injectScript) {
  if (!content && content !== "") return "";
  const ext     = (fileName ?? "").split(".").pop().toLowerCase();
  const scriptTag = injectScript ? `\n<script>${injectScript}<\/script>` : "";
  if (ext === "css") {
    const base = CSS_SCAFFOLD.replace("CONTENT", content);
    return scriptTag ? base.replace("</body></html>", `${scriptTag}\n</body></html>`) : base;
  }
  if (ext === "js" || ext === "mjs" || ext === "cjs") {
    return `<!doctype html><html><head><meta charset="utf-8"></head><body><script>${content}<\/script>${scriptTag}</body></html>`;
  }
  // html / htm
  if (scriptTag) {
    const idx = content.lastIndexOf("</body>");
    if (idx !== -1) return content.slice(0, idx) + scriptTag + content.slice(idx);
    return content + scriptTag;
  }
  return content;
}

// ── Device presets ────────────────────────────────────────────────────────────

const DEVICES = [
  { label: "Desktop", width: "100%" },
  { label: "Tablet",  width: "768px" },
  { label: "Mobile",  width: "375px" },
];

// ── Inspect: script injected into the iframe ──────────────────────────────────

const INSPECT_SCRIPT = `(function(){
  var sel=null;
  var ov='2px solid #7c6ef8';
  document.addEventListener('mouseover',function(e){
    if(e.target===document.body||e.target===document.documentElement)return;
    if(e.target!==sel){e.target.style.outline=ov;e.target.style.outlineOffset='-1px';}
  },true);
  document.addEventListener('mouseout',function(e){
    if(e.target!==sel){e.target.style.outline='';e.target.style.outlineOffset='';}
  },true);
  document.addEventListener('click',function(e){
    e.preventDefault();e.stopPropagation();
    if(sel&&sel!==e.target){sel.style.outline='';sel.style.outlineOffset='';}
    sel=e.target;
    sel.style.outline=ov;sel.style.outlineOffset='-1px';
    var cs=window.getComputedStyle(sel);
    var keys=['color','backgroundColor','fontSize','padding','margin','borderRadius','width','height'];
    var styles={};
    keys.forEach(function(k){styles[k]=cs[k];});
    var tag=sel.tagName.toLowerCase();
    var cls=typeof sel.className==='string'?sel.className.trim():'';
    var id=sel.id||'';
    var selector=id?('#'+id):(cls?(tag+'.'+cls.split(/\\s+/).join('.')):tag);
    window.parent.postMessage({type:'hk-select',tag:tag,classes:cls,selector:selector,styles:styles},'*');
  },true);
  window.addEventListener('message',function(e){
    if(!e.data||e.data.type!=='hk-set-style'||!sel)return;
    sel.style.setProperty(e.data.property,e.data.value);
  });
})();`;

// ── Inspect: editable CSS property list ──────────────────────────────────────

const INSPECT_PROPS = [
  { key: "color",           css: "color",            label: "color" },
  { key: "backgroundColor", css: "background-color", label: "background" },
  { key: "fontSize",        css: "font-size",        label: "font-size" },
  { key: "padding",         css: "padding",          label: "padding" },
  { key: "margin",          css: "margin",           label: "margin" },
  { key: "borderRadius",    css: "border-radius",    label: "radius" },
  { key: "width",           css: "width",            label: "width" },
  { key: "height",          css: "height",           label: "height" },
];

// ── Component ─────────────────────────────────────────────────────────────────

export default memo(function LivePreview({ content, fileName, filePath, orientation, onOrientationChange }) {
  const [deviceIdx,      setDeviceIdx]      = useState(0);
  const [srcDoc,         setSrcDoc]         = useState("");
  const [refreshNonce,   setRefreshNonce]   = useState(0);
  const [inspectOn,      setInspectOn]      = useState(false);
  const [selectedEl,     setSelectedEl]     = useState(null); // { tag, classes, selector }
  const [inspectValues,  setInspectValues]  = useState({});
  const debounceRef = useRef(null);
  const isFirst     = useRef(true);
  const iframeRef   = useRef(null);

  // Build srcdoc immediately on first render, debounce subsequent changes.
  // Re-builds when inspectOn changes so the inspect script is added/removed.
  useEffect(() => {
    const delay = isFirst.current ? 0 : 500;
    isFirst.current = false;
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setSrcDoc(buildSrcDoc(content, fileName, inspectOn ? INSPECT_SCRIPT : null));
    }, delay);
    return () => clearTimeout(debounceRef.current);
  }, [content, fileName, inspectOn]);

  // Clear selection when inspect mode is toggled off
  useEffect(() => {
    if (!inspectOn) { setSelectedEl(null); setInspectValues({}); }
  }, [inspectOn]);

  // Listen for postMessage events from the iframe (inspect selections)
  useEffect(() => {
    const handler = (e) => {
      if (!e.data || e.data.type !== "hk-select") return;
      const { tag, classes, selector, styles } = e.data;
      setSelectedEl({ tag, classes, selector });
      const vals = {};
      INSPECT_PROPS.forEach(({ key }) => { vals[key] = styles?.[key] || ""; });
      setInspectValues(vals);
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, []);

  const handleStyleChange = useCallback((prop, value) => {
    setInspectValues((prev) => ({ ...prev, [prop.key]: value }));
    iframeRef.current?.contentWindow?.postMessage(
      { type: "hk-set-style", property: prop.css, value },
      "*"
    );
  }, []);

  const refresh = () => {
    setSrcDoc(buildSrcDoc(content, fileName, inspectOn ? INSPECT_SCRIPT : null));
    setRefreshNonce((n) => n + 1);
  };

  const openBrowser = () => filePath && openExternal(filePath).catch(() => {});
  const toggleInspect = () => setInspectOn((v) => !v);

  const device     = DEVICES[deviceIdx];
  const isVertical = orientation !== "horizontal";

  return (
    <div style={{
      display: "flex", flexDirection: "column",
      flex: 1, minWidth: 0, minHeight: 0,
      borderLeft:  isVertical ? "1px solid var(--border)" : "none",
      borderTop:  !isVertical ? "1px solid var(--border)" : "none",
    }}>
      {/* ── Toolbar ── */}
      <div style={lp.toolbar}>
        {/* Left: orientation + device toggles */}
        <div style={{ display: "flex", alignItems: "center", gap: 2 }}>
          <button
            className="va-btn"
            style={lp.iconBtn}
            title={isVertical ? "Switch to horizontal split" : "Switch to vertical split"}
            onClick={onOrientationChange}
          >
            {isVertical
              ? <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="12" x2="21" y2="12"/></svg>
              : <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="12" y1="3" x2="12" y2="21"/></svg>
            }
          </button>
          <div style={lp.divider} />
          {DEVICES.map((d, i) => (
            <button
              key={d.label}
              onClick={() => setDeviceIdx(i)}
              title={`${d.label} — ${d.width}`}
              style={{
                ...lp.deviceBtn,
                background: deviceIdx === i ? "var(--accent-dim)" : "transparent",
                color:      deviceIdx === i ? "var(--accent)"     : "var(--text-2)",
              }}
            >
              {d.label}
            </button>
          ))}
        </div>

        {/* Center: fake address bar */}
        <div style={lp.address}>
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" style={{ flexShrink: 0 }}>
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
          </svg>
          <span style={{ color: "var(--text-2)", fontSize: 11, fontFamily: "var(--font-mono)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {fileName || "preview"}
          </span>
        </div>

        {/* Right: inspect + refresh + open in browser */}
        <div style={{ display: "flex", alignItems: "center", gap: 2 }}>
          <button
            className="va-btn"
            style={{
              ...lp.iconBtn,
              color:      inspectOn ? "var(--accent)"     : "var(--text-2)",
              background: inspectOn ? "var(--accent-dim)" : "transparent",
            }}
            title={inspectOn ? "Exit inspect mode" : "Inspect elements"}
            onClick={toggleInspect}
          >
            {/* Crosshair icon */}
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <circle cx="12" cy="12" r="3"/>
              <line x1="12" y1="2" x2="12" y2="7"/>
              <line x1="12" y1="17" x2="12" y2="22"/>
              <line x1="2" y1="12" x2="7" y2="12"/>
              <line x1="17" y1="12" x2="22" y2="12"/>
            </svg>
          </button>
          <div style={lp.divider} />
          <button className="va-btn" style={lp.iconBtn} title="Refresh preview" onClick={refresh}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="23 4 23 10 17 10"/>
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
            </svg>
          </button>
          <button className="va-btn" style={lp.iconBtn} title="Open in browser" onClick={openBrowser}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
              <polyline points="15 3 21 3 21 9"/>
              <line x1="10" y1="14" x2="21" y2="3"/>
            </svg>
          </button>
        </div>
      </div>

      {/* ── Main: viewport + inspect panel ── */}
      <div style={{ flex: 1, minHeight: 0, display: "flex", overflow: "hidden" }}>
        {/* Viewport */}
        <div style={lp.viewport}>
          <div style={{
            width: device.width, height: "100%",
            margin: "0 auto", overflow: "hidden",
            transition: "width 180ms var(--ease)",
          }}>
            <iframe
              key={refreshNonce}
              ref={iframeRef}
              srcDoc={srcDoc}
              sandbox="allow-scripts allow-forms"
              style={{
                ...lp.iframe,
                cursor: inspectOn ? "crosshair" : "auto",
                pointerEvents: inspectOn ? "auto" : "auto",
              }}
              title="live-preview"
            />
          </div>
        </div>

        {/* Inspect properties panel — visible when in inspect mode and element selected */}
        {inspectOn && selectedEl && (
          <div style={lp.inspectPanel}>
            {/* Element header */}
            <div style={lp.inspectHeader}>
              <span style={{ color: "var(--accent)", fontFamily: "var(--font-mono)", fontSize: 11 }}>
                &lt;{selectedEl.tag}&gt;
              </span>
              {selectedEl.classes && (
                <span style={{ color: "var(--text-2)", fontSize: 10, marginTop: 1, fontFamily: "var(--font-mono)", wordBreak: "break-all" }}>
                  .{selectedEl.classes.split(/\s+/).join(".")}
                </span>
              )}
            </div>
            {/* Editable properties */}
            <div style={{ overflow: "auto", flex: 1 }}>
              {INSPECT_PROPS.map((prop) => (
                <div key={prop.key} style={lp.inspectRow}>
                  <div style={lp.inspectLabel}>{prop.label}</div>
                  <input
                    style={lp.inspectInput}
                    value={inspectValues[prop.key] || ""}
                    onChange={(e) => handleStyleChange(prop, e.target.value)}
                    spellCheck={false}
                    autoComplete="off"
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Inspect hint when no element selected yet */}
        {inspectOn && !selectedEl && (
          <div style={lp.inspectHint}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
              <circle cx="12" cy="12" r="3"/>
              <line x1="12" y1="2" x2="12" y2="7"/>
              <line x1="12" y1="17" x2="12" y2="22"/>
              <line x1="2" y1="12" x2="7" y2="12"/>
              <line x1="17" y1="12" x2="22" y2="12"/>
            </svg>
            <span>Click an element in the preview</span>
          </div>
        )}
      </div>
    </div>
  );
});

// ── Styles ────────────────────────────────────────────────────────────────────

const lp = {
  toolbar: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    height: 32, padding: "0 8px", flexShrink: 0, gap: 6,
    background: "var(--bg-1)", borderBottom: "1px solid var(--border)",
  },
  iconBtn: {
    width: 24, height: 24,
    display: "flex", alignItems: "center", justifyContent: "center",
    borderRadius: "var(--r-sm)", color: "var(--text-2)", cursor: "pointer",
  },
  deviceBtn: {
    padding: "2px 7px", fontSize: 10, borderRadius: "var(--r-sm)", cursor: "pointer",
    fontFamily: "var(--font-ui)", border: "none",
    transition: "background var(--dur) var(--ease), color var(--dur) var(--ease)",
  },
  divider: { width: 1, height: 14, background: "var(--border)", margin: "0 2px", flexShrink: 0 },
  address: {
    flex: 1, maxWidth: 280,
    display: "flex", alignItems: "center", gap: 5,
    background: "var(--bg-2)", border: "1px solid var(--border)",
    borderRadius: "var(--r-md)", padding: "3px 10px", overflow: "hidden",
  },
  viewport: { flex: 1, minHeight: 0, overflow: "auto", background: "#ffffff" },
  iframe:   { width: "100%", height: "100%", border: "none", display: "block" },

  // Inspect panel
  inspectPanel: {
    width: 160, flexShrink: 0,
    display: "flex", flexDirection: "column",
    borderLeft: "1px solid var(--border)",
    background: "var(--bg-1)",
    overflow: "hidden",
  },
  inspectHeader: {
    padding: "8px 10px",
    borderBottom: "1px solid var(--border)",
    display: "flex", flexDirection: "column", gap: 2,
    flexShrink: 0,
  },
  inspectRow: {
    display: "flex", flexDirection: "column",
    padding: "4px 8px",
    borderBottom: "1px solid var(--border)",
  },
  inspectLabel: {
    fontSize: 9, color: "var(--text-2)",
    letterSpacing: "0.05em", textTransform: "uppercase",
    marginBottom: 2, fontFamily: "var(--font-ui)",
  },
  inspectInput: {
    width: "100%",
    background: "var(--bg-2)",
    border: "1px solid var(--border)",
    borderRadius: "var(--r-xs)",
    padding: "2px 5px",
    fontSize: 10, fontFamily: "var(--font-mono)",
    color: "var(--text-0)", outline: "none",
  },
  inspectHint: {
    width: 160, flexShrink: 0,
    display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
    gap: 8,
    borderLeft: "1px solid var(--border)",
    background: "var(--bg-1)",
    color: "var(--text-2)",
    fontSize: 10, fontFamily: "var(--font-ui)",
    textAlign: "center", padding: "0 12px",
  },
};
