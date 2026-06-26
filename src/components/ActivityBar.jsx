// Left activity bar — pure SVG icons, VS Code-style active indicator.

function Icon({ path, active }) {
  return (
    <svg
      width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke={active ? "var(--text-0)" : "var(--text-2)"}
      strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"
    >
      {path}
    </svg>
  );
}

function IdeIcon({ active }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke={active ? "var(--accent)" : "var(--text-2)"}
      strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="5" width="13" height="10" rx="1.5" />
      <rect x="8" y="9" width="13" height="10" rx="1.5" />
    </svg>
  );
}

function ChatIcon({ active }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
      stroke={active ? "var(--accent)" : "var(--text-2)"}
      strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
    </svg>
  );
}

export default function ActivityBar({
  active,
  onSelect,
  chatMode,
  onToggleChat,
  theme,
  onToggleTheme,
  onOpenSettings,
}) {
  const items = [
    {
      id: "files",
      title: "Explorer",
      path: <><path d="M3 7v13h18V7" /><path d="M3 7l2-3h6l2 3" /></>,
    },
    {
      id: "projects",
      title: "Projects",
      path: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    },
    {
      id: "search",
      title: "Search",
      path: <><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></>,
    },
    {
      id: "git",
      title: "Source control",
      path: <><circle cx="6" cy="6" r="2.5" /><circle cx="6" cy="18" r="2.5" /><circle cx="18" cy="9" r="2.5" /><path d="M6 8.5v7M18 11.5c0 3-4 3.5-9 4" /></>,
    },
    {
      id: "extensions",
      title: "Extensions",
      path: <>
        <rect x="3" y="3" width="8" height="8" rx="1"/>
        <rect x="13" y="3" width="8" height="8" rx="1"/>
        <rect x="3" y="13" width="8" height="8" rx="1"/>
        <path d="M13 17h8M17 13v8"/>
      </>,
    },
  ];

  return (
    <div className="activity-bar" style={styles.bar}>
      <div style={styles.top}>
        {items.map((it) => {
          // In chat mode none of the IDE views count as active.
          const isActive = !chatMode && active === it.id;
          return (
            <button
              key={it.id}
              title={it.title}
              className={`va-btn${isActive ? " va-btn-active" : ""}`}
              style={styles.btn}
              onClick={() => onSelect(it.id)}
            >
              <Icon path={it.path} active={isActive} />
            </button>
          );
        })}

        <div style={styles.divider} />

        <button
          title={chatMode ? "Switch to IDE mode" : "Switch to Chat mode"}
          className={`va-btn${chatMode ? " va-btn-active" : ""}`}
          style={styles.btn}
          onClick={onToggleChat}
        >
          {chatMode ? <IdeIcon active={true} /> : <ChatIcon active={false} />}
        </button>
      </div>

      <div style={styles.bottom}>
        <button
          title="Settings"
          className="va-btn"
          style={styles.btn}
          onClick={onOpenSettings}
        >
          <Icon path={
            <><circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" /></>
          } />
        </button>
        <button
          title="Toggle theme"
          className="va-btn"
          style={styles.btn}
          onClick={onToggleTheme}
        >
          {theme === "dark" ? (
            <Icon path={<><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M19 5l-1.5 1.5M6.5 17.5L5 19" /></>} />
          ) : (
            <Icon path={<path d="M21 12.8A9 9 0 1111.2 3 7 7 0 0021 12.8z" />} />
          )}
        </button>
      </div>
    </div>
  );
}

const styles = {
  bar: {
    background: "var(--bg-1)",
    borderRight: "1px solid var(--border)",
    display: "flex",
    flexDirection: "column",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "10px 4px",
  },
  top: { display: "flex", flexDirection: "column", gap: "6px", alignItems: "center" },
  bottom: { display: "flex", flexDirection: "column", gap: "6px" },
  btn: {
    width: "38px",
    height: "38px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: "var(--r-md)",
  },
  divider: {
    width: "22px",
    height: "1px",
    background: "var(--border)",
    margin: "6px 0",
  },
};
