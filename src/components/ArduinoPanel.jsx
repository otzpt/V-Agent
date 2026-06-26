import { useState, useEffect, useRef } from "react";
import { arduinoListPorts, arduinoCompile, arduinoUpload, openExternal } from "../lib/tauri.js";

const BOARDS = [
  { label: "Arduino Uno",          fqbn: "arduino:avr:uno" },
  { label: "Arduino Mega 2560",    fqbn: "arduino:avr:mega" },
  { label: "Arduino Nano",         fqbn: "arduino:avr:nano" },
  { label: "Arduino Nano Every",   fqbn: "arduino:megaavr:nona4809" },
  { label: "Arduino Leonardo",     fqbn: "arduino:avr:leonardo" },
  { label: "Arduino Due",          fqbn: "arduino:sam:arduino_due_x" },
  { label: "Arduino Micro",        fqbn: "arduino:avr:micro" },
  { label: "ESP32",                fqbn: "esp32:esp32:esp32" },
  { label: "ESP8266 Generic",      fqbn: "esp8266:esp8266:generic" },
  { label: "Raspberry Pi Pico",    fqbn: "rp2040:rp2040:rpipico" },
  { label: "STM32 (Generic F1)",   fqbn: "STMicroelectronics:stm32:GenF1" },
];

const BAUDS = ["9600", "19200", "38400", "57600", "115200", "250000", "500000", "1000000"];

const INSTALL_URL = "https://arduino.github.io/arduino-cli/latest/installation/";

export default function ArduinoPanel({ filePath, onClose, onRunInTerminal }) {
  const [ports,        setPorts]        = useState([]);
  const [port,         setPort]         = useState("");
  const [fqbn,         setFqbn]         = useState("arduino:avr:uno");
  const [baud,         setBaud]         = useState("9600");
  const [output,       setOutput]       = useState("");
  const [running,      setRunning]      = useState(null); // "compile"|"upload"|null
  const [notInstalled, setNotInstalled] = useState(false);
  const outputRef = useRef(null);

  // Close on Escape
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  // Load available ports on mount
  useEffect(() => {
    arduinoListPorts()
      .then((list) => {
        setPorts(list);
        if (list.length) setPort(list[0]);
      })
      .catch((err) => {
        const msg = String(err);
        if (msg.includes("not found") || msg.includes("NotFound") || msg.includes("cannot find")) {
          setNotInstalled(true);
        } else {
          setOutput(`Failed to list ports: ${msg}`);
        }
      });
  }, []);

  // Auto-scroll output
  useEffect(() => {
    if (outputRef.current) outputRef.current.scrollTop = outputRef.current.scrollHeight;
  }, [output]);

  const run = async (action) => {
    setRunning(action);
    setOutput(`${action === "compile" ? "Compiling" : "Uploading"}…\n`);
    try {
      const result = action === "compile"
        ? await arduinoCompile(fqbn, filePath)
        : await arduinoUpload(port, fqbn, filePath);
      const label = action === "compile" ? "Compiled" : "Uploaded";
      setOutput(`✓ ${label} successfully.\n\n${result || "(no output)"}`);
    } catch (err) {
      const label = action === "compile" ? "Compile" : "Upload";
      setOutput(`✗ ${label} failed:\n\n${String(err)}`);
    } finally {
      setRunning(null);
    }
  };

  const openSerialMonitor = () => {
    if (!port) { setOutput("Select a port first."); return; }
    onRunInTerminal?.(`arduino-cli monitor -p ${port} --config baudrate=${baud}`);
    onClose();
  };

  const sketchName = filePath?.split(/[/\\]/).pop() ?? "";

  return (
    <div style={ap.overlay} onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={ap.modal}>

        {/* ── Header ── */}
        <div style={ap.header}>
          <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="16 18 22 12 16 6"/>
              <polyline points="8 6 2 12 8 18"/>
            </svg>
            <span style={ap.title}>Arduino</span>
            <span style={{ fontSize: 11, color: "var(--text-2)", fontFamily: "var(--font-mono)" }}>
              {sketchName}
            </span>
          </div>
          <button style={ap.closeBtn} onClick={onClose} title="Close (Esc)">×</button>
        </div>

        {notInstalled ? (
          /* ── Not installed state ── */
          <div style={ap.notInstalled}>
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--warn)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <div style={{ fontSize: 14, color: "var(--text-0)", fontWeight: 600 }}>
              arduino-cli is not installed
            </div>
            <div style={{ fontSize: 12, color: "var(--text-2)", maxWidth: 360, textAlign: "center", lineHeight: 1.6 }}>
              Install arduino-cli to compile and upload Arduino sketches directly from V-Agent.
            </div>
            <button
              style={ap.installBtn}
              onClick={() => openExternal(INSTALL_URL).catch(() => {})}
            >
              Install arduino-cli ↗
            </button>
          </div>
        ) : (
          /* ── Main body ── */
          <div style={ap.body}>

            {/* Selects row */}
            <div style={ap.row}>
              <div style={ap.field}>
                <label style={ap.label}>Port</label>
                <select style={ap.select} value={port} onChange={(e) => setPort(e.target.value)}>
                  {ports.length === 0
                    ? <option value="">No ports detected</option>
                    : ports.map((p) => <option key={p} value={p}>{p}</option>)
                  }
                </select>
              </div>
              <div style={{ ...ap.field, flex: 2 }}>
                <label style={ap.label}>Board</label>
                <select style={ap.select} value={fqbn} onChange={(e) => setFqbn(e.target.value)}>
                  {BOARDS.map((b) => <option key={b.fqbn} value={b.fqbn}>{b.label}</option>)}
                </select>
              </div>
              <div style={{ ...ap.field, maxWidth: 110 }}>
                <label style={ap.label}>Baud rate</label>
                <select style={ap.select} value={baud} onChange={(e) => setBaud(e.target.value)}>
                  {BAUDS.map((b) => <option key={b} value={b}>{b}</option>)}
                </select>
              </div>
            </div>

            {/* Action buttons */}
            <div style={ap.actions}>
              <button
                style={{ ...ap.btn, opacity: running ? 0.5 : 1 }}
                disabled={!!running}
                onClick={() => run("compile")}
              >
                {running === "compile" ? "Compiling…" : "Compile"}
              </button>
              <button
                style={{ ...ap.btn, background: "var(--accent)", color: "#fff", border: "none", opacity: (!port || !!running) ? 0.45 : 1 }}
                disabled={!port || !!running}
                onClick={() => run("upload")}
              >
                {running === "upload" ? "Uploading…" : "⇪ Upload"}
              </button>
              <button
                style={{ ...ap.btn, marginLeft: "auto", opacity: (!port || !!running) ? 0.4 : 1 }}
                disabled={!port || !!running}
                onClick={openSerialMonitor}
                title="Opens arduino-cli monitor in the active terminal"
              >
                Serial Monitor
              </button>
            </div>

            {/* Output panel */}
            {output && (
              <pre ref={outputRef} style={ap.output}>{output}</pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const ap = {
  overlay: {
    position: "fixed", inset: 0,
    background: "rgba(0,0,0,0.50)", backdropFilter: "blur(3px)", WebkitBackdropFilter: "blur(3px)",
    display: "flex", alignItems: "center", justifyContent: "center",
    zIndex: 10000, animation: "va-fade 120ms var(--ease)",
  },
  modal: {
    width: 580, maxWidth: "calc(100vw - 48px)", maxHeight: "calc(100vh - 80px)",
    background: "var(--bg-1)", border: "1px solid var(--border)",
    borderRadius: "var(--r-lg)", boxShadow: "var(--shadow-lg)",
    display: "flex", flexDirection: "column", overflow: "hidden",
    animation: "va-pop 160ms var(--ease)",
  },
  header: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "14px 18px", borderBottom: "1px solid var(--border)", flexShrink: 0,
  },
  title: { fontSize: 14, fontWeight: 600, color: "var(--text-0)", fontFamily: "var(--font-ui)" },
  closeBtn: { fontSize: 20, color: "var(--text-2)", cursor: "pointer", background: "none", border: "none", lineHeight: 1 },
  body: { padding: 18, display: "flex", flexDirection: "column", gap: 14, overflow: "auto", flex: 1 },
  row: { display: "flex", gap: 10 },
  field: { display: "flex", flexDirection: "column", gap: 5, flex: 1 },
  label: {
    fontSize: 10, letterSpacing: "0.06em", textTransform: "uppercase",
    color: "var(--text-2)", fontFamily: "var(--font-ui)",
  },
  select: {
    background: "var(--bg-2)", border: "1px solid var(--border)",
    borderRadius: "var(--r-sm)", padding: "6px 10px",
    fontSize: 12, color: "var(--text-0)", fontFamily: "var(--font-mono)",
    cursor: "pointer", outline: "none",
  },
  actions: { display: "flex", gap: 8 },
  btn: {
    padding: "7px 16px", fontSize: 12, fontFamily: "var(--font-ui)", fontWeight: 500,
    background: "var(--bg-2)", border: "1px solid var(--border)",
    borderRadius: "var(--r-sm)", cursor: "pointer", color: "var(--text-0)",
    transition: "opacity var(--dur) var(--ease)",
    whiteSpace: "nowrap",
  },
  output: {
    background: "var(--bg-0)", border: "1px solid var(--border)",
    borderRadius: "var(--r-sm)", padding: "12px 14px", margin: 0,
    fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--text-1)",
    whiteSpace: "pre-wrap", overflowY: "auto", maxHeight: 200,
    lineHeight: 1.6,
  },
  notInstalled: {
    padding: "36px 24px", display: "flex", flexDirection: "column",
    alignItems: "center", gap: 12, textAlign: "center",
  },
  installBtn: {
    marginTop: 4, padding: "8px 20px", fontSize: 13, fontFamily: "var(--font-ui)",
    background: "var(--accent)", color: "#fff", border: "none",
    borderRadius: "var(--r-sm)", cursor: "pointer",
  },
};
