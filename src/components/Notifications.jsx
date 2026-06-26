// Toast notifications. Mounted once; exposes a global `window.notify(msg, type)`.
// Types: success | warning | error | info. Auto-dismiss after 3s (paused on hover),
// max 4 visible (oldest dropped), slide in/out unless reduced-motion is requested.

import { useState, useEffect, useRef, useCallback } from "react";

const PRM =
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const MAX_TOASTS = 4;
const DISMISS_MS = 3000;
const ANIM_MS    = 200;

const TYPES = {
  success: { color: "var(--ok)",     icon: "✓" },
  warning: { color: "var(--warn)",   icon: "⚠" },
  error:   { color: "var(--err)",    icon: "⊗" },
  info:    { color: "var(--accent)", icon: "ℹ" },
};

let idCounter = 0;

function Toast({ toast, onClose, onPause, onResume }) {
  const [shown, setShown] = useState(false);

  // Trigger the slide-in on the frame after mount.
  useEffect(() => {
    const r = requestAnimationFrame(() => setShown(true));
    return () => cancelAnimationFrame(r);
  }, []);

  const conf    = TYPES[toast.type] || TYPES.info;
  const visible = shown && !toast.leaving;

  return (
    <div
      style={{
        ...ns.toast,
        borderLeft: `3px solid ${conf.color}`,
        transform:  PRM ? "none" : (visible ? "translateX(0)" : "translateX(120%)"),
        opacity:    visible ? 1 : 0,
        transition: PRM ? "none" : `transform ${ANIM_MS}ms ease, opacity ${ANIM_MS}ms ease`,
      }}
      onMouseEnter={onPause}
      onMouseLeave={onResume}
      role="status"
    >
      <span style={{ ...ns.icon, color: conf.color }}>{conf.icon}</span>
      <span style={ns.msg}>{toast.message}</span>
      <button style={ns.close} onClick={onClose} title="Dismiss">×</button>
    </div>
  );
}

export default function Notifications() {
  const [toasts, setToasts] = useState([]); // { id, message, type, leaving }
  const timersRef = useRef(new Map());      // id -> dismiss timeout handle

  const remove = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    clearTimeout(timersRef.current.get(id));
    timersRef.current.delete(id);
  }, []);

  // Mark a toast as leaving (plays the slide-out) then remove it.
  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, leaving: true } : t)));
    setTimeout(() => remove(id), PRM ? 0 : ANIM_MS);
  }, [remove]);

  const scheduleDismiss = useCallback((id) => {
    clearTimeout(timersRef.current.get(id));
    timersRef.current.set(id, setTimeout(() => dismiss(id), DISMISS_MS));
  }, [dismiss]);

  const add = useCallback((message, type = "info") => {
    const id = ++idCounter;
    setToasts((prev) => [...prev, { id, message: String(message), type, leaving: false }].slice(-MAX_TOASTS));
    scheduleDismiss(id);
  }, [scheduleDismiss]);

  // Expose the global entry point used across the app.
  useEffect(() => {
    window.notify = (message, type) => add(message, type);
    return () => { delete window.notify; };
  }, [add]);

  // Clear any pending timers on unmount.
  useEffect(() => () => {
    timersRef.current.forEach((h) => clearTimeout(h));
    timersRef.current.clear();
  }, []);

  const pause  = useCallback((id) => clearTimeout(timersRef.current.get(id)), []);
  const resume = useCallback((id) => scheduleDismiss(id), [scheduleDismiss]);

  return (
    <div style={ns.container}>
      {toasts.map((t) => (
        <Toast
          key={t.id}
          toast={t}
          onClose={() => dismiss(t.id)}
          onPause={() => pause(t.id)}
          onResume={() => resume(t.id)}
        />
      ))}
    </div>
  );
}

const ns = {
  container: {
    position: "fixed",
    right: 16,
    bottom: 16,
    zIndex: 11000,
    display: "flex",
    flexDirection: "column",
    gap: 8,
    maxWidth: 360,
    pointerEvents: "none", // clicks pass through gaps; toasts re-enable below
  },
  toast: {
    pointerEvents: "auto",
    display: "flex",
    alignItems: "center",
    gap: 10,
    minWidth: 240,
    maxWidth: 360,
    padding: "11px 13px",
    background: "var(--bg-2)",
    border: "1px solid var(--border)",
    borderRadius: "var(--r-md)",
    boxShadow: "var(--shadow-md)",
    fontFamily: "var(--font-ui)",
    fontSize: 13,
  },
  icon: { fontSize: 14, flexShrink: 0, fontWeight: 700 },
  msg:  { flex: 1, color: "var(--text-1)", wordBreak: "break-word", lineHeight: 1.35 },
  close: {
    flexShrink: 0,
    fontSize: 16,
    lineHeight: 1,
    color: "var(--text-2)",
    background: "none",
    border: "none",
    cursor: "pointer",
    padding: 0,
  },
};
