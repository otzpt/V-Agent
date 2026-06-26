import { useState, useEffect, useCallback } from "react";
import { pathExists, createFile, writeFile } from "../lib/tauri.js";
import { runTask } from "../lib/tauri.js";

// ── Auto-detect project type ──────────────────────────────────────────────────

async function detectProject(rootDir) {
  const sep = rootDir.includes("\\") ? "\\" : "/";
  const j = (name) => rootDir + sep + name;

  if (await pathExists(j("package.json"))) {
    return {
      label: "Node.js project",
      tasks: { dev: "npm run dev", build: "npm run build", test: "npm test" },
    };
  }
  if (await pathExists(j("Cargo.toml"))) {
    return {
      label: "Rust project",
      tasks: { run: "cargo run", build: "cargo build", test: "cargo test" },
    };
  }
  if (await pathExists(j("requirements.txt")) || await pathExists(j("pyproject.toml"))) {
    return {
      label: "Python project",
      tasks: { run: "python main.py", test: "pytest" },
    };
  }
  return null;
}

// ── TaskBar ───────────────────────────────────────────────────────────────────

export default function TaskBar({ vagentConfig, rootDir, activePtyId, onFocusTerminal, onRefresh }) {
  const [detection, setDetection] = useState(null);
  const [addingTask, setAddingTask] = useState(false);
  const [newName, setNewName] = useState("");
  const [newCmd, setNewCmd]   = useState("");

  useEffect(() => {
    if (!rootDir || vagentConfig) { setDetection(null); return; }
    detectProject(rootDir).then(setDetection).catch(() => setDetection(null));
  }, [rootDir, vagentConfig]);

  const run = useCallback(async (command) => {
    if (!activePtyId) return;
    onFocusTerminal?.();
    try {
      await runTask(activePtyId, command, rootDir);
    } catch (e) {
      console.error("runTask failed:", e);
    }
  }, [activePtyId, rootDir, onFocusTerminal]);

  // Create .vagent.json from detected tasks
  const createVagentJson = useCallback(async () => {
    if (!detection || !rootDir) return;
    const sep = rootDir.includes("\\") ? "\\" : "/";
    const name = rootDir.split(sep).pop() || "Project";
    const content = JSON.stringify({ name, tasks: detection.tasks, env: {} }, null, 2);
    try {
      await createFile(rootDir + sep + ".vagent.json", content);
      onRefresh?.();
    } catch (e) {
      alert(`Failed to create .vagent.json: ${e}`);
    }
  }, [detection, rootDir, onRefresh]);

  // Add a new task to existing .vagent.json
  const commitNewTask = useCallback(async () => {
    if (!vagentConfig || !newName.trim() || !newCmd.trim()) {
      setAddingTask(false);
      return;
    }
    const sep = rootDir.includes("\\") ? "\\" : "/";
    const updated = {
      ...vagentConfig,
      tasks: { ...vagentConfig.tasks, [newName.trim()]: newCmd.trim() },
    };
    try {
      await writeFile(rootDir + sep + ".vagent.json", JSON.stringify(updated, null, 2));
      onRefresh?.();
    } catch (e) {
      alert(`Failed to update .vagent.json: ${e}`);
    }
    setAddingTask(false);
    setNewName("");
    setNewCmd("");
  }, [vagentConfig, newName, newCmd, rootDir, onRefresh]);

  // ── Render: nothing ────────────────────────────────────────────────────────
  if (!rootDir) return null;

  // ── Render: has .vagent.json ───────────────────────────────────────────────
  if (vagentConfig) {
    const tasks = vagentConfig.tasks || {};
    return (
      <div style={ts.bar}>
        <span style={ts.projectName}>
          {vagentConfig.name || "Project"}
        </span>
        <div style={ts.right}>
          {Object.entries(tasks).map(([name, cmd]) => (
            <button
              key={name}
              style={ts.taskBtn}
              onClick={() => run(cmd)}
              title={cmd}
            >
              ▶ {name}
            </button>
          ))}

          {addingTask ? (
            <>
              <input
                autoFocus
                style={ts.addInput}
                placeholder="name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
              />
              <input
                style={{ ...ts.addInput, minWidth: 120 }}
                placeholder="command"
                value={newCmd}
                onChange={(e) => setNewCmd(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") commitNewTask();
                  if (e.key === "Escape") setAddingTask(false);
                }}
              />
              <button style={ts.taskBtn} onClick={commitNewTask}>✓</button>
              <button style={ts.taskBtn} onClick={() => setAddingTask(false)}>✗</button>
            </>
          ) : (
            <button
              style={{ ...ts.taskBtn, opacity: 0.5 }}
              onClick={() => setAddingTask(true)}
              title="Add task"
            >
              +
            </button>
          )}
        </div>
      </div>
    );
  }

  // ── Render: auto-detected project, no .vagent.json ─────────────────────────
  if (detection) {
    return (
      <div style={{ ...ts.bar, background: "var(--bg-2)" }}>
        <span style={ts.detectLabel}>
          {detection.label} detected
        </span>
        <div style={ts.right}>
          {Object.entries(detection.tasks).map(([name, cmd]) => (
            <button
              key={name}
              style={ts.taskBtn}
              onClick={() => run(cmd)}
              title={cmd}
            >
              ▶ {name}
            </button>
          ))}
          <button
            style={{ ...ts.taskBtn, color: "var(--accent)", borderColor: "var(--accent)" }}
            onClick={createVagentJson}
          >
            Create .vagent.json
          </button>
        </div>
      </div>
    );
  }

  return null;
}

// ── Styles ────────────────────────────────────────────────────────────────────

const ts = {
  bar: {
    display: "flex",
    alignItems: "center",
    height: "32px",
    padding: "0 12px",
    gap: "10px",
    background: "var(--bg-1)",
    borderBottom: "1px solid var(--border)",
    flexShrink: 0,
    overflow: "hidden",
  },
  projectName: {
    fontSize: "11px",
    fontWeight: 600,
    color: "var(--text-1)",
    fontFamily: "var(--font-ui)",
    whiteSpace: "nowrap",
    letterSpacing: "0.02em",
  },
  detectLabel: {
    fontSize: "11px",
    color: "var(--text-2)",
    fontFamily: "var(--font-ui)",
    whiteSpace: "nowrap",
  },
  right: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    overflow: "hidden",
  },
  taskBtn: {
    padding: "2px 8px",
    fontSize: "11px",
    fontFamily: "var(--font-ui)",
    fontWeight: 500,
    color: "var(--text-1)",
    background: "var(--bg-2)",
    border: "1px solid var(--border)",
    borderRadius: "4px",
    cursor: "pointer",
    whiteSpace: "nowrap",
  },
  addInput: {
    height: "22px",
    padding: "0 6px",
    fontSize: "11px",
    fontFamily: "var(--font-mono)",
    color: "var(--text-0)",
    background: "var(--bg-2)",
    border: "1px solid var(--border)",
    borderRadius: "4px",
    minWidth: 72,
    outline: "none",
  },
};
