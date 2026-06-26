#!/usr/bin/env python3
"""
V-Agent 0.8.0 — Professional Agentic IDE · Voidtune Ecosystem
PySide6 · Cross-platform (Windows & Linux) · Secure backend
"""

import os, sys, json, threading, subprocess, datetime, re, time, logging

# ── Dependency bootstrap ───────────────────────────────────────────────────────
def _bootstrap():
    missing = []
    try: from PySide6.QtWidgets import QApplication
    except ImportError: missing.append("PySide6")
    try: import requests
    except ImportError: missing.append("requests")
    try: import dotenv
    except ImportError: missing.append("python-dotenv")
    if missing:
        print(f"Missing: {', '.join(missing)}")
        ans = input("Install now? [y/N]: ").strip().lower()
        if ans == "y":
            subprocess.run([sys.executable,"-m","pip","install"]+missing, check=True)
            os.execv(sys.executable,[sys.executable]+sys.argv)
        sys.exit(1)

_bootstrap()

# ── Platform utils & LLM providers ────────────────────────────────────────────
from platform_utils import (
    get_config_path, get_base_dir, get_log_dir,
    load_env_file, write_env_key, setup_logging,
    ensure_dir, safe_open, atomic_write, is_windows, is_linux, os_label,
    get_resource_path,
)
from llm_provider import build_provider, LLMError, ALLOWED_GROQ_MODELS, ALLOWED_OPENROUTER_FREE_MODELS

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTextEdit, QPlainTextEdit, QLineEdit, QLabel,
    QPushButton, QFrame, QScrollArea, QComboBox, QCheckBox,
    QSpinBox, QFileDialog, QMessageBox, QTabBar, QStackedWidget,
    QTreeWidget, QTreeWidgetItem, QSizePolicy, QStatusBar,
    QDialog, QDialogButtonBox,
)
from PySide6.QtCore import (
    Qt, QThread, Signal, QTimer, QSize, QObject, Slot,
)
from PySide6.QtGui import (
    QFont, QFontDatabase, QColor, QTextCharFormat,
    QSyntaxHighlighter, QKeySequence, QShortcut,
    QTextCursor, QAction,
)
import requests as _req

# ── Logging ────────────────────────────────────────────────────────────────────
setup_logging()
log = logging.getLogger("vagent")

# ── Constants ──────────────────────────────────────────────────────────────────
VERSION    = "0.8.0"
BASE_DIR   = get_base_dir()
INPUT_DIR  = BASE_DIR / "Input"
OUT_DIR    = BASE_DIR / "Output"

load_env_file()

# ── Config ─────────────────────────────────────────────────────────────────────
DEFAULT_CFG = {
    "model":              "qwen2.5-coder:14b",
    "theme":              "dark",
    "ollama_base_url":    "http://localhost:11434",
    "streaming":          True,
    "font_size":          13,
    "ai_provider":        "backend",
    "vagent_server_url":  "https://vt-inference-relay.vercel.app",
    "groq_api_key":       "",
    "groq_model":         "llama-3.3-70b-versatile",
    "openrouter_api_key": "",
    "openrouter_model":   "meta-llama/llama-3.2-3b-instruct:free",
}

def load_cfg() -> dict:
    load_env_file()
    cfg = dict(DEFAULT_CFG)
    cfg_path = get_config_path()
    if cfg_path.exists():
        try:
            with safe_open(cfg_path, "r") as f:
                cfg.update(json.load(f))
        except Exception as e:
            log.warning("Could not read config: %s", e)
    for env_key, cfg_key in {
        "VAGENT_PROVIDER":    "ai_provider",
        "VAGENT_SERVER_URL":  "vagent_server_url",
        "GROQ_API_KEY":       "groq_api_key",
        "GROQ_MODEL":         "groq_model",
        "OPENROUTER_API_KEY": "openrouter_api_key",
        "OPENROUTER_MODEL":   "openrouter_model",
        "OLLAMA_BASE_URL":    "ollama_base_url",
        "VAGENT_MODEL":       "model",
    }.items():
        val = os.environ.get(env_key, "").strip()
        if val:
            cfg[cfg_key] = val
    return cfg

def save_cfg(cfg: dict):
    """Save config — API keys NEVER written here (stay in .env only)."""
    safe = {k: v for k, v in cfg.items() if "api_key" not in k}
    try:
        atomic_write(get_config_path(), json.dumps(safe, indent=2))
    except Exception as e:
        log.error("Could not save config: %s", e)

# ── Design tokens ──────────────────────────────────────────────────────────────
THEMES = {
    "dark": {
        "bg":"#0D1117","panel":"#161B22","sidebar":"#0D1117",
        "border":"#21262D","text":"#E6EDF3","dim":"#7D8590",
        "accent":"#2F81F7","accent2":"#1F6FEB","green":"#3FB950",
        "red":"#F85149","yellow":"#D29922","orange":"#E3B341",
        "purple":"#BC8CFF","cyan":"#79C0FF","selection":"#1F3358",
        "hover":"#21262D","input_bg":"#161B22","btn_bg":"#21262D",
        "btn_hover":"#30363D","tag_bg":"#1C2128","code_bg":"#161B22",
        "user_bg":"#1C2128","ai_bg":"#161B22","scrollbar":"#30363D",
    },
    "light": {
        "bg":"#FFFFFF","panel":"#F6F8FA","sidebar":"#F6F8FA",
        "border":"#D0D7DE","text":"#1F2328","dim":"#636C76",
        "accent":"#0969DA","accent2":"#0550AE","green":"#1A7F37",
        "red":"#CF222E","yellow":"#9A6700","orange":"#BC4C00",
        "purple":"#8250DF","cyan":"#0550AE","selection":"#DDF4FF",
        "hover":"#F3F4F6","input_bg":"#FFFFFF","btn_bg":"#F6F8FA",
        "btn_hover":"#EAEEF2","tag_bg":"#EFF1F3","code_bg":"#F6F8FA",
        "user_bg":"#EFF1F3","ai_bg":"#FFFFFF","scrollbar":"#D0D7DE",
    },
}

# ── Language maps ──────────────────────────────────────────────────────────────
LANG_EXT = {
    ".py":"python",".pyw":"python",
    ".js":"javascript",".jsx":"javascript",".mjs":"javascript",
    ".ts":"typescript",".tsx":"typescript",
    ".html":"html",".htm":"html",".css":"css",".scss":"css",
    ".json":"json",".sh":"bash",".bash":"bash",".zsh":"bash",
    ".bat":"batch",".cmd":"batch",".ps1":"powershell",
    ".md":"markdown",".c":"c",".h":"c",
    ".cpp":"cpp",".cxx":"cpp",".hpp":"cpp",
    ".rs":"rust",".go":"go",".rb":"ruby",
    ".java":"java",".kt":"kotlin",".swift":"swift",
    ".sql":"sql",".yaml":"yaml",".yml":"yaml",".toml":"toml",
    ".txt":"text",".env":"text",".gitignore":"text",
}
FILE_ICONS = {
    ".py":"🐍",".js":"🟨",".jsx":"⚛",".ts":"🔷",".tsx":"⚛",
    ".html":"🌐",".css":"🎨",".json":"{}",".md":"📝",
    ".sh":"⚙",".bat":"⚙",".rs":"🦀",".go":"🐹",
    ".cpp":"⚡",".c":"⚡",".java":"☕",".rb":"💎",
    ".sql":"🗄",".yaml":"📐",".yml":"📐",".txt":"📄",
    ".env":"🔑",".gitignore":"🔍",
}

# ── Agent system prompt ────────────────────────────────────────────────────────
AGENT_SYSTEM = """You are V-Agent, an expert agentic AI coding assistant.
You think carefully and produce clean, correct, idiomatic code.

## TOOLS — use XML tags to act directly

Read file:     <vagent:read path="path/to/file"/>
Write file:    <vagent:write path="path/to/file">content</vagent:write>
Edit open file:<vagent:edit>complete new content</vagent:edit>
List dir:      <vagent:ls path="."/>
Run command:   <vagent:run>command</vagent:run>
Search:        <vagent:search pattern="text" path="."/>

## RULES
- Apply changes directly with tools — never just describe them
- After each tool use, explain what you did in 1-2 sentences
- Write production-quality code with error handling
- Keep explanations concise — show, don't tell
"""

# ── Safe commands ──────────────────────────────────────────────────────────────
_SAFE_CMDS = [
    "ls","dir","pwd","echo","cat","type","python","python3","node","npm",
    "pip","pip3","git","mkdir","touch","cp","copy","mv","move",
    "grep","find","which","where","uname","ver","date","ruff","pytest",
]

def is_safe_command(cmd: str) -> bool:
    return any(cmd.strip().lower().startswith(s) for s in _SAFE_CMDS)

# ── Syntax highlighting ────────────────────────────────────────────────────────
SYNTAX_RULES = {
    "python":[
        ("kw","#C586C0",r'\b(False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)\b'),
        ("bi","#9CDCFE",r'\b(print|len|range|type|int|str|float|list|dict|set|tuple|bool|open|super|self|cls|input|enumerate|zip|map|filter|sorted|reversed|any|all|min|max|sum|abs|round|isinstance|hasattr|getattr|setattr)\b'),
        ("st","#CE9178",r"('''[\s\S]*?'''|\"\"\"[\s\S]*?\"\"\"|f'(?:[^'\\]|\\.)*'|f\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")"),
        ("cm","#6A9955",r'#[^\n]*'),
        ("nm","#B5CEA8",r'\b\d+\.?\d*\b'),
        ("dc","#C6A0F6",r'@[\w.]+'),
        ("fn","#DCDCAA",r'(?<=def )\w+'),
        ("cl","#4EC9B0",r'(?<=class )\w+'),
    ],
    "javascript":[
        ("kw","#C586C0",r'\b(async|await|break|case|catch|class|const|continue|default|delete|do|else|export|extends|finally|for|from|function|if|import|in|instanceof|let|new|of|return|static|super|switch|this|throw|try|typeof|var|void|while|yield)\b'),
        ("bi","#9CDCFE",r'\b(console|window|document|Array|Object|String|Number|Boolean|Promise|Math|JSON|Date|undefined|null|true|false|NaN|require|module|exports)\b'),
        ("st","#CE9178",r'(`[^`]*`|\'(?:[^\'\\]|\\.)*\'|"(?:[^"\\]|\\.)*")'),
        ("cm","#6A9955",r'(//[^\n]*|/\*[\s\S]*?\*/)'),
        ("nm","#B5CEA8",r'\b\d+\.?\d*\b'),
        ("fn","#DCDCAA",r'\b\w+(?=\s*\()'),
    ],
    "html":[
        ("tg","#4EC9B0",r'</?[a-zA-Z][a-zA-Z0-9-]*'),
        ("at","#9CDCFE",r'\b[a-zA-Z][a-zA-Z0-9-]*(?=\s*=)'),
        ("st","#CE9178",r'"[^"]*"'),
        ("cm","#6A9955",r'<!--[\s\S]*?-->'),
    ],
    "json":[
        ("ky","#9CDCFE",r'"(?:[^"\\]|\\.)*"(?=\s*:)'),
        ("st","#CE9178",r'(?<=:\s*)"(?:[^"\\]|\\.)*"'),
        ("kw","#569CD6",r'\b(true|false|null)\b'),
        ("nm","#B5CEA8",r'-?\b\d+\.?\d*\b'),
    ],
    "bash":[
        ("kw","#C586C0",r'\b(if|then|else|elif|fi|for|while|until|do|done|case|esac|function|return|local|export|echo|exit|source|cd|ls|rm|mv|cp|mkdir|grep|sed|awk|curl|git)\b'),
        ("st","#CE9178",r"'[^']*'|\"(?:[^\"\\]|\\.)*\""),
        ("cm","#6A9955",r'#[^\n]*'),
        ("vr","#9CDCFE",r'\$\{?[\w@#?$!*-]+\}?'),
    ],
    "css":[
        ("sl","#D7BA7D",r'[.#][a-zA-Z][a-zA-Z0-9_-]*'),
        ("pr","#9CDCFE",r'\b[a-z][a-z-]+(?=\s*:)'),
        ("st","#CE9178",r'"[^"]*"|\'[^\']*\''),
        ("cm","#6A9955",r'/\*[\s\S]*?\*/'),
        ("nm","#B5CEA8",r'\b\d+\.?\d*(?:px|em|rem|%|vh|vw|pt)?\b'),
    ],
}

class SyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, document, lang="python"):
        super().__init__(document)
        self._rules = []
        self.set_lang(lang)

    def set_lang(self, lang):
        self._rules = []
        for _, color, pattern in SYNTAX_RULES.get(lang, []):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            self._rules.append((re.compile(pattern), fmt))

    def highlightBlock(self, text):
        for regex, fmt in self._rules:
            for m in regex.finditer(text):
                self.setFormat(m.start(), m.end()-m.start(), fmt)

# ── LLM Worker ─────────────────────────────────────────────────────────────────
class LLMWorker(QThread):
    token_received = Signal(str)
    finished       = Signal(str)
    error          = Signal(str)

    def __init__(self, cfg, history, message):
        super().__init__()
        self._cfg      = cfg
        self._history  = history
        self._message  = message
        self._cancel   = False

    def cancel(self):
        self._cancel = True

    def run(self):
        provider = build_provider(self._cfg, AGENT_SYSTEM)
        full = []
        try:
            for tok in provider.stream(
                self._history,
                cancel_flag=lambda: self._cancel
            ):
                if self._cancel: return
                full.append(tok)
                self.token_received.emit(tok)
            self.finished.emit("".join(full))
        except LLMError as e:
            if not self._cancel:
                self.error.emit(str(e))
        except Exception as e:
            if not self._cancel:
                log.exception("LLM unexpected error")
                self.error.emit("Unexpected error. See logs.")

# ── Stylesheet ─────────────────────────────────────────────────────────────────
def make_stylesheet(C):
    return f"""
    QMainWindow,QWidget{{background:{C['bg']};color:{C['text']};}}
    QFrame{{background:transparent;}}
    QScrollBar:vertical{{background:transparent;width:8px;margin:0;}}
    QScrollBar::handle:vertical{{background:{C['scrollbar']};border-radius:4px;min-height:30px;}}
    QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}
    QScrollBar:horizontal{{background:transparent;height:8px;margin:0;}}
    QScrollBar::handle:horizontal{{background:{C['scrollbar']};border-radius:4px;min-width:30px;}}
    QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{{width:0;}}
    QLineEdit,QSpinBox{{background:{C['input_bg']};color:{C['text']};border:1px solid {C['border']};border-radius:6px;padding:6px 10px;font-size:13px;selection-background-color:{C['selection']};}}
    QLineEdit:focus,QSpinBox:focus{{border-color:{C['accent']};}}
    QPushButton{{background:{C['btn_bg']};color:{C['text']};border:1px solid {C['border']};border-radius:6px;padding:6px 14px;font-size:13px;}}
    QPushButton:hover{{background:{C['btn_hover']};border-color:{C['accent']};}}
    QPushButton:pressed{{background:{C['selection']};}}
    QPushButton#accent{{background:{C['accent']};color:#FFF;border-color:{C['accent2']};}}
    QPushButton#accent:hover{{background:{C['accent2']};}}
    QPushButton#danger{{background:transparent;color:{C['red']};border-color:{C['red']};}}
    QPushButton#danger:hover{{background:{C['red']};color:#FFF;}}
    QComboBox{{background:{C['input_bg']};color:{C['text']};border:1px solid {C['border']};border-radius:6px;padding:6px 10px;font-size:13px;}}
    QComboBox:focus{{border-color:{C['accent']};}}
    QComboBox::drop-down{{border:none;width:20px;}}
    QComboBox QAbstractItemView{{background:{C['panel']};color:{C['text']};border:1px solid {C['border']};selection-background-color:{C['selection']};}}
    QTextEdit,QPlainTextEdit{{background:{C['bg']};color:{C['text']};border:none;font-size:13px;selection-background-color:{C['selection']};}}
    QTreeWidget{{background:{C['sidebar']};color:{C['text']};border:none;font-size:12px;}}
    QTreeWidget::item:hover{{background:{C['hover']};}}
    QTreeWidget::item:selected{{background:{C['selection']};color:{C['text']};}}
    QTabBar{{background:transparent;}}
    QTabBar::tab{{background:{C['panel']};color:{C['dim']};border:none;border-right:1px solid {C['border']};padding:8px 16px;font-size:12px;}}
    QTabBar::tab:selected{{background:{C['bg']};color:{C['text']};border-bottom:2px solid {C['accent']};}}
    QTabBar::tab:hover{{background:{C['hover']};color:{C['text']};}}
    QCheckBox{{color:{C['text']};spacing:8px;}}
    QCheckBox::indicator{{width:16px;height:16px;border-radius:4px;border:1px solid {C['border']};background:{C['input_bg']};}}
    QCheckBox::indicator:checked{{background:{C['accent']};border-color:{C['accent']};}}
    QStatusBar{{background:{C['panel']};color:{C['dim']};border-top:1px solid {C['border']};font-size:11px;}}
    QLabel{{color:{C['text']};background:transparent;}}
    QLabel#dim{{color:{C['dim']};}}
    """

# ── Chat message ───────────────────────────────────────────────────────────────
class ChatMessage(QFrame):
    def __init__(self, role, content, C, parent=None):
        super().__init__(parent)
        self._C = C
        is_user = role == "user"
        bg  = C["user_bg"] if is_user else C["ai_bg"]
        bdr = C["accent"]  if is_user else C["border"]
        self.setStyleSheet(f"ChatMessage{{background:{bg};border-left:3px solid {bdr};margin:1px 0;}}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16,10,16,10)
        lay.setSpacing(4)

        hdr = QHBoxLayout()
        role_lbl = QLabel("You" if is_user else "V-Agent")
        role_lbl.setStyleSheet(f"font-weight:700;font-size:12px;color:{'#79C0FF' if is_user else '#3FB950'};")
        hdr.addWidget(role_lbl)
        hdr.addStretch()
        ts = QLabel(datetime.datetime.now().strftime("%H:%M"))
        ts.setStyleSheet(f"color:{C['dim']};font-size:11px;")
        hdr.addWidget(ts)
        lay.addLayout(hdr)

        self._lbl = QLabel(content)
        self._lbl.setWordWrap(True)
        self._lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse |
            Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self._lbl.setStyleSheet(f"color:{C['text']};font-size:13px;line-height:1.6;")
        self._lbl.setOpenExternalLinks(True)
        lay.addWidget(self._lbl)

    def append_text(self, t): self._lbl.setText(self._lbl.text() + t)
    def set_text(self, t):    self._lbl.setText(t)

# ── AI Chat panel ──────────────────────────────────────────────────────────────
class AIChatPanel(QWidget):
    def __init__(self, cfg, C, parent=None):
        super().__init__(parent)
        self._cfg     = cfg
        self._C       = C
        self._history = []
        self._worker  = None
        self._cur_msg = None
        self._build()

    def _build(self):
        C = self._C
        lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        # Header
        hdr = QFrame(); hdr.setFixedHeight(48)
        hdr.setStyleSheet(f"background:{C['panel']};border-bottom:1px solid {C['border']};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(16,0,16,0)
        t = QLabel("✦  AI Chat"); t.setStyleSheet(f"font-weight:700;font-size:14px;color:{C['text']};")
        hl.addWidget(t); hl.addStretch()
        self._badge = QLabel()
        self._badge.setStyleSheet(f"background:{C['tag_bg']};color:{C['dim']};border-radius:4px;padding:2px 8px;font-size:11px;")
        self._refresh_badge(); hl.addWidget(self._badge)
        lay.addWidget(hdr)

        # Quick actions
        qa = QFrame(); qa.setStyleSheet(f"background:{C['panel']};border-bottom:1px solid {C['border']};")
        ql = QHBoxLayout(qa); ql.setContentsMargins(12,6,12,6); ql.setSpacing(4)
        for label, prompt in [
            ("Explain","Explain what this code does step by step:"),
            ("Fix","Find and fix all bugs and edge cases:"),
            ("Comment","Add clear docstrings and inline comments:"),
            ("Refactor","Refactor for clarity and best practices:"),
            ("Tests","Write comprehensive unit tests:"),
        ]:
            b = QPushButton(label)
            b.setStyleSheet(f"QPushButton{{background:{C['tag_bg']};color:{C['dim']};border:1px solid {C['border']};border-radius:4px;padding:3px 10px;font-size:11px;}}QPushButton:hover{{color:{C['text']};border-color:{C['accent']};}}")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _,p=prompt: self._quick(p))
            ql.addWidget(b)
        ql.addStretch(); lay.addWidget(qa)

        # Messages
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(f"background:{C['bg']};border:none;")
        self._msg_cont = QWidget(); self._msg_cont.setStyleSheet(f"background:{C['bg']};")
        self._msg_lay  = QVBoxLayout(self._msg_cont)
        self._msg_lay.setContentsMargins(0,8,0,8); self._msg_lay.setSpacing(0)
        self._msg_lay.addStretch()
        self._scroll.setWidget(self._msg_cont); lay.addWidget(self._scroll,1)

        # Status
        sb = QFrame(); sb.setFixedHeight(28)
        sb.setStyleSheet(f"background:{C['panel']};border-top:1px solid {C['border']};")
        sl = QHBoxLayout(sb); sl.setContentsMargins(12,0,12,0)
        self._status = QLabel(""); self._status.setStyleSheet(f"color:{C['dim']};font-size:11px;")
        sl.addWidget(self._status); sl.addStretch(); lay.addWidget(sb)

        # Input
        inp = QFrame(); inp.setStyleSheet(f"background:{C['panel']};border-top:1px solid {C['border']};")
        il = QVBoxLayout(inp); il.setContentsMargins(12,8,12,8); il.setSpacing(6)
        self._input = QPlainTextEdit()
        self._input.setPlaceholderText("Ask V-Agent anything... (Enter to send, Shift+Enter for newline)")
        self._input.setFixedHeight(72)
        self._input.setStyleSheet(f"background:{C['input_bg']};color:{C['text']};border:1px solid {C['border']};border-radius:8px;padding:8px 12px;font-size:13px;selection-background-color:{C['selection']};")
        self._input.installEventFilter(self)
        il.addWidget(self._input)

        br = QHBoxLayout(); br.setSpacing(8)
        self._send_btn = QPushButton("Send  ↵"); self._send_btn.setObjectName("accent")
        self._send_btn.setFixedHeight(34); self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.clicked.connect(self._send); br.addWidget(self._send_btn)
        self._cancel_btn = QPushButton("✕  Cancel"); self._cancel_btn.setObjectName("danger")
        self._cancel_btn.setFixedHeight(34); self._cancel_btn.setVisible(False)
        self._cancel_btn.clicked.connect(self._cancel); br.addWidget(self._cancel_btn)
        br.addStretch()
        clr = QPushButton("Clear"); clr.setFixedHeight(34)
        clr.setCursor(Qt.CursorShape.PointingHandCursor); clr.clicked.connect(self._clear)
        br.addWidget(clr); il.addLayout(br); lay.addWidget(inp)

    def _refresh_badge(self):
        labels = {"backend":"☁  Groq Cloud","local":"⬡  Ollama","groq":"⚡  Groq Direct","openrouter":"◈  OpenRouter"}
        self._badge.setText(labels.get(self._cfg.get("ai_provider","backend"), "AI"))

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self._send(); return True
        return super().eventFilter(obj, event)

    def _quick(self, p): self._input.setPlainText(p); self._send()

    def _send(self):
        text = self._input.toPlainText().strip()
        if not text or self._worker: return
        self._input.clear()
        self._add_msg("user", text)
        self._history.append({"role":"user","content":text})
        self._cur_msg = ChatMessage("assistant","",self._C)
        self._msg_lay.insertWidget(self._msg_lay.count()-1, self._cur_msg)
        self._scroll_bot(); self._set_loading(True)
        self._worker = LLMWorker(self._cfg, list(self._history), text)
        self._worker.token_received.connect(self._on_tok)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_err)
        self._worker.start()

    def _on_tok(self, t):
        if self._cur_msg: self._cur_msg.append_text(t); self._scroll_bot()

    def _on_done(self, full):
        self._history.append({"role":"assistant","content":full})
        self._worker = None; self._cur_msg = None; self._set_loading(False)

    def _on_err(self, err):
        C = self._C
        if self._cur_msg:
            self._cur_msg.set_text(f"⚠  {err}")
            self._cur_msg.setStyleSheet(f"ChatMessage{{background:#2D1B1B;border-left:3px solid {C['red']};margin:1px 0;}}")
        self._worker = None; self._cur_msg = None; self._set_loading(False)
        log.warning("LLM error shown to user: %s", err)

    def _cancel(self):
        if self._worker: self._worker.cancel(); self._worker.quit(); self._worker = None
        self._set_loading(False)

    def _clear(self):
        while self._msg_lay.count() > 1:
            item = self._msg_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self._history.clear()

    def _add_msg(self, role, content):
        msg = ChatMessage(role, content, self._C)
        self._msg_lay.insertWidget(self._msg_lay.count()-1, msg)
        self._scroll_bot()

    def _scroll_bot(self):
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()))

    def _set_loading(self, v):
        self._send_btn.setVisible(not v); self._cancel_btn.setVisible(v)
        self._status.setText("⟳  Thinking..." if v else "")

    def reload_config(self, cfg):
        self._cfg = cfg; self._refresh_badge()

# ── Code Editor ────────────────────────────────────────────────────────────────
def _best_mono():
    fams = QFontDatabase.families()
    for f in ("Cascadia Code","JetBrains Mono","Fira Code","Source Code Pro","Consolas","Courier New"):
        if f in fams: return f
    return "Courier New"

class CodeEditor(QPlainTextEdit):
    def __init__(self, C, parent=None):
        super().__init__(parent)
        self._C = C; self._path = None; self._hl = None
        self.setFont(QFont(_best_mono(), 13))
        self.setStyleSheet(f"QPlainTextEdit{{background:{C['bg']};color:{C['text']};border:none;padding:12px;selection-background-color:{C['selection']};}}")
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

    def load_file(self, path):
        from pathlib import Path
        self._path = Path(path)
        try:
            self.setPlainText(self._path.read_text(encoding="utf-8", errors="replace"))
        except Exception as e:
            self.setPlainText(f"Error reading file: {e}")
            return
        lang = LANG_EXT.get(self._path.suffix.lower(), "text")
        self._hl = SyntaxHighlighter(self.document(), lang)

    def save_file(self, path=None):
        from pathlib import Path
        p = Path(path) if path else self._path
        if not p: return False
        try:
            atomic_write(p, self.toPlainText())
            self._path = p; return True
        except Exception as e:
            QMessageBox.warning(self, "Save Error", str(e)); return False

# ── IDE panel ──────────────────────────────────────────────────────────────────
class IDEPanel(QWidget):
    def __init__(self, C, parent=None):
        super().__init__(parent)
        self._C = C; self._tabs = {}; self._build()

    def _build(self):
        C = self._C; lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)
        self._tab_bar = QTabBar(); self._tab_bar.setTabsClosable(True); self._tab_bar.setMovable(True)
        self._tab_bar.tabCloseRequested.connect(self._close_tab)
        self._tab_bar.currentChanged.connect(self._switch_tab)
        lay.addWidget(self._tab_bar)
        self._stack = QStackedWidget(); self._stack.setStyleSheet(f"background:{C['bg']};")
        lay.addWidget(self._stack,1)
        empty = QLabel("Open a file from the Explorer\nor drag & drop here")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setStyleSheet(f"color:{C['dim']};font-size:14px;")
        self._empty = empty; self._stack.addWidget(empty)

    def open_file(self, path):
        from pathlib import Path
        p = str(path)
        if p in self._tabs:
            idx = list(self._tabs.keys()).index(p)
            self._tab_bar.setCurrentIndex(idx); return
        editor = CodeEditor(self._C); editor.load_file(path)
        self._tabs[p] = editor; self._stack.addWidget(editor)
        ext  = Path(path).suffix
        icon = FILE_ICONS.get(ext, "📄")
        idx  = self._tab_bar.addTab(f"{icon}  {Path(path).name}")
        self._tab_bar.setCurrentIndex(idx); self._stack.setCurrentWidget(editor)

    def _close_tab(self, idx):
        paths = list(self._tabs.keys())
        if idx < len(paths):
            p = paths[idx]; ed = self._tabs.pop(p)
            self._stack.removeWidget(ed); ed.deleteLater()
        self._tab_bar.removeTab(idx)

    def _switch_tab(self, idx):
        paths = list(self._tabs.keys())
        if idx < len(paths): self._stack.setCurrentWidget(self._tabs[paths[idx]])
        else: self._stack.setCurrentWidget(self._empty)

    def save_current(self):
        w = self._stack.currentWidget()
        if isinstance(w, CodeEditor): w.save_file()

    def current_content(self):
        w = self._stack.currentWidget()
        return w.toPlainText() if isinstance(w, CodeEditor) else ""

# ── File Explorer ──────────────────────────────────────────────────────────────
class FileExplorer(QTreeWidget):
    file_opened = Signal(str)

    def __init__(self, C, parent=None):
        super().__init__(parent)
        self._C = C; self._root = None
        self.setHeaderHidden(True); self.setIndentation(16)
        self.itemDoubleClicked.connect(self._on_item)
        self.setStyleSheet(f"QTreeWidget{{background:{C['sidebar']};color:{C['text']};border:none;font-size:12px;padding-top:4px;}}QTreeWidget::item{{padding:3px 4px;}}QTreeWidget::item:hover{{background:{C['hover']};border-radius:4px;}}QTreeWidget::item:selected{{background:{C['selection']};color:{C['text']};border-radius:4px;}}")

    def set_root(self, path):
        from pathlib import Path
        self._root = Path(path); self.clear()
        self._populate(self, self._root)

    def _populate(self, parent, path):
        from pathlib import Path
        try: entries = sorted(Path(path).iterdir(), key=lambda e:(not e.is_dir(), e.name.lower()))
        except PermissionError: return
        for e in entries:
            if e.name.startswith(".") or e.name == "__pycache__": continue
            item = QTreeWidgetItem(parent)
            if e.is_dir():
                item.setText(0, f"  {e.name}"); item.setData(0, Qt.ItemDataRole.UserRole, str(e))
                item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
                self._populate(item, e)
            else:
                icon = FILE_ICONS.get(e.suffix.lower(), "📄")
                item.setText(0, f"{icon}  {e.name}"); item.setData(0, Qt.ItemDataRole.UserRole, str(e))

    def _on_item(self, item, _):
        p = item.data(0, Qt.ItemDataRole.UserRole)
        if p and os.path.isfile(p): self.file_opened.emit(p)

# ── Terminal panel ─────────────────────────────────────────────────────────────
class TerminalPanel(QWidget):
    def __init__(self, C, parent=None):
        super().__init__(parent)
        self._C = C; self._hist = []; self._hist_idx = -1; self._build()

    def _build(self):
        C = self._C; lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)
        hdr = QFrame(); hdr.setFixedHeight(38)
        hdr.setStyleSheet(f"background:{C['panel']};border-bottom:1px solid {C['border']};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(16,0,16,0)
        hl.addWidget(QLabel("⬛  Terminal"))
        hl.addStretch()
        clr = QPushButton("Clear"); clr.setFixedHeight(26); clr.clicked.connect(self._clear)
        hl.addWidget(clr); lay.addWidget(hdr)
        self._out = QTextEdit(); self._out.setReadOnly(True)
        self._out.setFont(QFont(_best_mono(), 12))
        self._out.setStyleSheet(f"QTextEdit{{background:{C['bg']};color:{C['text']};border:none;padding:12px 16px;}}")
        lay.addWidget(self._out,1)
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{C['border']};"); lay.addWidget(sep)
        inp_f = QFrame(); inp_f.setStyleSheet(f"background:{C['panel']};")
        il = QHBoxLayout(inp_f); il.setContentsMargins(12,6,12,6); il.setSpacing(8)
        self._prompt = QLabel(f"$ "); self._prompt.setStyleSheet(f"color:{C['green']};font-family:monospace;font-size:12px;")
        il.addWidget(self._prompt)
        self._inp = QLineEdit(); self._inp.setPlaceholderText("Enter command...")
        self._inp.setStyleSheet(f"QLineEdit{{background:transparent;color:{C['text']};border:none;font-family:monospace;font-size:12px;}}")
        self._inp.returnPressed.connect(self._run); il.addWidget(self._inp,1); lay.addWidget(inp_f)
        self._write(f"V-Agent {VERSION} — Terminal\nPlatform: {os_label()}\n\n", C["dim"])

    def _write(self, text, color=None):
        cur = self._out.textCursor(); cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat(); fmt.setForeground(QColor(color or self._C["text"]))
        cur.insertText(text, fmt); self._out.setTextCursor(cur); self._out.ensureCursorVisible()

    def _run(self):
        cmd = self._inp.text().strip()
        if not cmd: return
        self._hist.insert(0, cmd); self._hist_idx = -1; self._inp.clear()
        C = self._C; self._write(f"$ {cmd}\n", C["green"])
        if not is_safe_command(cmd):
            self._write(f"⚠  Command not in allowlist: {cmd}\n", C["red"]); return
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=str(BASE_DIR))
            if r.stdout: self._write(r.stdout, C["text"])
            if r.stderr: self._write(r.stderr, C["red"])
        except subprocess.TimeoutExpired: self._write("Timeout (30s)\n", C["red"])
        except Exception as e: self._write(f"Error: {e}\n", C["red"])

    def _clear(self): self._out.clear()

# ── Settings panel ─────────────────────────────────────────────────────────────
class SettingsPanel(QWidget):
    settings_saved = Signal(dict)

    def __init__(self, cfg, C, parent=None):
        super().__init__(parent)
        self._cfg = cfg; self._C = C; self._build()

    def _build(self):
        C = self._C; lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)
        hdr = QFrame(); hdr.setFixedHeight(48)
        hdr.setStyleSheet(f"background:{C['panel']};border-bottom:1px solid {C['border']};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(16,0,16,0)
        t = QLabel("⚙  Settings"); t.setStyleSheet(f"font-weight:700;font-size:14px;color:{C['text']};")
        hl.addWidget(t); lay.addWidget(hdr)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"background:{C['bg']};border:none;")
        cont = QWidget(); cont.setStyleSheet(f"background:{C['bg']};")
        form = QVBoxLayout(cont); form.setContentsMargins(32,24,32,32); form.setSpacing(16)

        def section(title):
            l = QLabel(title)
            l.setStyleSheet(f"font-weight:700;font-size:15px;color:{C['text']};padding:8px 0 4px;border-bottom:1px solid {C['border']};")
            form.addWidget(l)

        def row(lbl_txt, widget, hint=None):
            r = QHBoxLayout()
            lb = QLabel(lbl_txt); lb.setFixedWidth(200)
            lb.setStyleSheet(f"color:{C['text']};font-size:13px;")
            r.addWidget(lb); r.addWidget(widget,1); form.addLayout(r)
            if hint:
                h = QLabel(hint); h.setStyleSheet(f"color:{C['dim']};font-size:11px;padding-left:204px;")
                form.addWidget(h)

        cfg = self._cfg

        section("General")
        self._sv_theme = QComboBox(); self._sv_theme.addItems(list(THEMES.keys()))
        self._sv_theme.setCurrentText(cfg.get("theme","dark"))
        row("Theme", self._sv_theme)
        self._sv_font = QSpinBox(); self._sv_font.setRange(8,28); self._sv_font.setValue(cfg.get("font_size",13))
        row("Font Size", self._sv_font)
        self._sv_stream = QCheckBox("Enable streaming"); self._sv_stream.setChecked(cfg.get("streaming",True))
        form.addWidget(self._sv_stream)

        section("AI Provider")
        note = QLabel("☁ backend = no setup, keys secured on server\n⬡ local = Ollama running on this machine\n⚡ groq / ◈ openrouter = your own API key")
        note.setStyleSheet(f"color:{C['dim']};font-size:12px;background:{C['tag_bg']};border-radius:6px;padding:8px;")
        form.addWidget(note)
        self._sv_provider = QComboBox(); self._sv_provider.addItems(["backend","local","groq","openrouter"])
        self._sv_provider.setCurrentText(cfg.get("ai_provider","backend"))
        row("AI Provider", self._sv_provider)
        self._sv_server = QLineEdit(cfg.get("vagent_server_url","https://vt-inference-relay.vercel.app"))
        row("Backend URL", self._sv_server, "Only change if self-hosting")
        self._sv_ollama = QLineEdit(cfg.get("ollama_base_url","http://localhost:11434"))
        row("Ollama URL", self._sv_ollama)
        self._sv_model = QComboBox(); self._sv_model.setEditable(True)
        self._sv_model.addItems(["qwen2.5-coder:14b","qwen2.5-coder:7b","llama3.1:8b","codellama:13b"])
        self._sv_model.setCurrentText(cfg.get("model","qwen2.5-coder:14b"))
        row("Local Model", self._sv_model)

        section("Cloud API Keys (Optional)")
        warn = QLabel("⚠  Keys saved to .env only — never to config.json or GitHub")
        warn.setStyleSheet(f"color:{C['yellow']};font-size:12px;")
        warn.setWordWrap(True); form.addWidget(warn)
        self._sv_groq_key = QLineEdit(); self._sv_groq_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._sv_groq_key.setPlaceholderText("gsk_... (leave blank to use backend)")
        row("Groq API Key", self._sv_groq_key, "console.groq.com (free)")
        self._sv_groq_model = QComboBox(); self._sv_groq_model.addItems(ALLOWED_GROQ_MODELS)
        self._sv_groq_model.setCurrentText(cfg.get("groq_model","llama-3.3-70b-versatile"))
        row("Groq Model", self._sv_groq_model)
        self._sv_or_key = QLineEdit(); self._sv_or_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._sv_or_key.setPlaceholderText("sk-or-... (only :free models used)")
        row("OpenRouter Key", self._sv_or_key)
        self._sv_or_model = QComboBox(); self._sv_or_model.addItems(ALLOWED_OPENROUTER_FREE_MODELS)
        self._sv_or_model.setCurrentText(cfg.get("openrouter_model","meta-llama/llama-3.2-3b-instruct:free"))
        row("OpenRouter Model", self._sv_or_model)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine); sep.setStyleSheet(f"color:{C['border']};")
        form.addWidget(sep)
        br = QHBoxLayout()
        sv = QPushButton("  Save Settings  "); sv.setObjectName("accent"); sv.setFixedHeight(38)
        sv.clicked.connect(self._save); br.addWidget(sv); br.addStretch()
        form.addLayout(br); form.addStretch(); scroll.setWidget(cont); lay.addWidget(scroll,1)

    def _save(self):
        cfg = self._cfg
        cfg["theme"]             = self._sv_theme.currentText()
        cfg["font_size"]         = self._sv_font.value()
        cfg["streaming"]         = self._sv_stream.isChecked()
        cfg["ai_provider"]       = self._sv_provider.currentText()
        cfg["vagent_server_url"] = self._sv_server.text().strip()
        cfg["ollama_base_url"]   = self._sv_ollama.text().strip()
        cfg["model"]             = self._sv_model.currentText()
        cfg["groq_model"]        = self._sv_groq_model.currentText()
        cfg["openrouter_model"]  = self._sv_or_model.currentText()
        gk = self._sv_groq_key.text().strip()
        ok = self._sv_or_key.text().strip()
        if gk: cfg["groq_api_key"] = gk; write_env_key("GROQ_API_KEY", gk)
        if ok: cfg["openrouter_api_key"] = ok; write_env_key("OPENROUTER_API_KEY", ok)
        save_cfg(cfg); self.settings_saved.emit(cfg)
        QMessageBox.information(self,"Saved","Settings saved.")

# ── Automator panel ────────────────────────────────────────────────────────────
class AutomatorPanel(QWidget):
    def __init__(self, C, parent=None):
        super().__init__(parent)
        self._C = C; self._proc = None; self._build()

    def _build(self):
        C = self._C; lay = QVBoxLayout(self); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)
        hdr = QFrame(); hdr.setFixedHeight(48)
        hdr.setStyleSheet(f"background:{C['panel']};border-bottom:1px solid {C['border']};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(16,0,16,0)
        hl.addWidget(QLabel("🤖  Automator")); lay.addWidget(hdr)
        info = QLabel("Watches Input/ for scripts. AI fixes bugs and saves corrected versions to Output/.\nSupported: .py  .js  .ts  .bat  .ps1  .sh")
        info.setStyleSheet(f"color:{C['dim']};font-size:13px;padding:12px 24px;background:{C['panel']};border-bottom:1px solid {C['border']};")
        lay.addWidget(info)
        ctrl = QFrame(); ctrl.setStyleSheet(f"background:{C['bg']};")
        cl = QHBoxLayout(ctrl); cl.setContentsMargins(24,12,24,12); cl.setSpacing(8)
        self._start_btn = QPushButton("▶  Start"); self._start_btn.setObjectName("accent")
        self._start_btn.setFixedHeight(36); self._start_btn.clicked.connect(self._start)
        cl.addWidget(self._start_btn)
        self._stop_btn = QPushButton("■  Stop"); self._stop_btn.setObjectName("danger")
        self._stop_btn.setFixedHeight(36); self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop); cl.addWidget(self._stop_btn); cl.addStretch()
        lay.addWidget(ctrl)
        self._log = QTextEdit(); self._log.setReadOnly(True)
        self._log.setFont(QFont(_best_mono(),11))
        self._log.setStyleSheet(f"QTextEdit{{background:{C['bg']};color:{C['green']};border:none;padding:12px 16px;}}")
        lay.addWidget(self._log,1)
        self._log_write("Automator ready — press ▶ to watch Input/")

    def _log_write(self, msg):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._log.append(f"[{ts}]  {msg}")

    def _start(self):
        a = BASE_DIR / "automator.py"
        if not a.exists():
            QMessageBox.critical(self,"Error",f"automator.py not found:\n{a}"); return
        ensure_dir(INPUT_DIR); ensure_dir(OUT_DIR)
        try:
            self._proc = subprocess.Popen([sys.executable, str(a)], cwd=str(BASE_DIR),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            self._start_btn.setEnabled(False); self._stop_btn.setEnabled(True)
            self._log_write(f"Started (PID {self._proc.pid})")
            threading.Thread(target=self._read, daemon=True).start()
        except Exception as e:
            QMessageBox.critical(self,"Error",str(e))

    def _stop(self):
        if self._proc and self._proc.poll() is None: self._proc.terminate()
        self._start_btn.setEnabled(True); self._stop_btn.setEnabled(False)
        self._log_write("Stopped.")

    def _read(self):
        for line in self._proc.stdout:
            line = line.rstrip()
            if line: QTimer.singleShot(0, lambda l=line: self._log_write(l))
        QTimer.singleShot(0, self._stop)

# ── Ollama status checker ──────────────────────────────────────────────────────
class OllamaChecker(QThread):
    status_changed = Signal(bool)
    def __init__(self, url):
        super().__init__(); self._url = url; self._running = True
    def run(self):
        while self._running:
            try:
                r = _req.get(f"{self._url}/api/tags", timeout=3)
                self.status_changed.emit(r.status_code == 200)
            except Exception:
                self.status_changed.emit(False)
            for _ in range(30):
                if not self._running: return
                time.sleep(1)
    def stop(self): self._running = False

# ── Main Window ────────────────────────────────────────────────────────────────
class VAgentWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_cfg()
        self.C   = THEMES.get(self.cfg.get("theme","dark"), THEMES["dark"])
        self.setWindowTitle(f"V-Agent v{VERSION}  ·  Voidtune")
        self.resize(1440, 880); self._center()
        self._apply_stylesheet(); self._build()
        self._start_ollama_checker()
        # Auto-open project folder in explorer
        if BASE_DIR.exists():
            QTimer.singleShot(300, lambda: self._explorer.set_root(BASE_DIR))

    def _center(self):
        s = QApplication.primaryScreen().geometry()
        self.move(max(0,(s.width()-1440)//2), max(0,(s.height()-880)//2))

    def _apply_stylesheet(self):
        self.setStyleSheet(make_stylesheet(self.C))

    def _build(self):
        C = self.C
        central = QWidget(); self.setCentralWidget(central)
        root_lay = QVBoxLayout(central); root_lay.setContentsMargins(0,0,0,0); root_lay.setSpacing(0)

        # ── Top bar ───────────────────────────────────────────────────────────
        topbar = QFrame(); topbar.setFixedHeight(42)
        topbar.setStyleSheet(f"QFrame{{background:{C['panel']};border-bottom:1px solid {C['border']};}}")
        tl = QHBoxLayout(topbar); tl.setContentsMargins(12,0,12,0); tl.setSpacing(0)

        badge = QLabel("  VA  ")
        badge.setStyleSheet(f"background:{C['accent']};color:#FFF;font-weight:800;font-size:11px;border-radius:4px;padding:2px 6px;letter-spacing:1px;")
        tl.addWidget(badge)
        tl.addWidget(QLabel("  V-Agent"))
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine); sep.setStyleSheet(f"color:{C['border']};"); sep.setFixedHeight(20)
        tl.addWidget(sep)

        self._mode_btns = {}
        for mode, label in [("chat","Chat"), ("ide","</>  IDE")]:
            btn = QPushButton(label); btn.setFixedHeight(42)
            btn.setStyleSheet(f"QPushButton{{background:transparent;color:{C['dim']};border:none;border-bottom:2px solid transparent;padding:0 16px;font-size:13px;}}QPushButton:hover{{color:{C['text']};}}")
            btn.clicked.connect(lambda _,m=mode: self._set_mode(m))
            tl.addWidget(btn); self._mode_btns[mode] = btn
        tl.addStretch()
        ver = QLabel(f"v{VERSION}"); ver.setStyleSheet(f"color:{C['dim']};font-size:11px;padding-right:8px;"); tl.addWidget(ver)
        self._dot = QLabel("○"); self._dot.setStyleSheet(f"color:{C['dim']};font-size:14px;padding-right:4px;"); tl.addWidget(self._dot)
        th_btn = QPushButton("◑"); th_btn.setFixedSize(34,34)
        th_btn.setStyleSheet(f"QPushButton{{background:transparent;color:{C['dim']};border:none;font-size:16px;border-radius:4px;}}QPushButton:hover{{background:{C['hover']};color:{C['text']};}}")
        th_btn.clicked.connect(self._toggle_theme); tl.addWidget(th_btn)
        root_lay.addWidget(topbar)

        # ── Body ──────────────────────────────────────────────────────────────
        body = QFrame(); bl = QHBoxLayout(body); bl.setContentsMargins(0,0,0,0); bl.setSpacing(0)

        # Sidebar nav
        nav = QFrame(); nav.setFixedWidth(48)
        nav.setStyleSheet(f"background:{C['sidebar']};border-right:1px solid {C['border']};")
        nl = QVBoxLayout(nav); nl.setContentsMargins(0,8,0,8); nl.setSpacing(2)
        self._nav_btns = {}; self._nav_inds = {}
        for name, icon in [("terminal","⬛"),("settings","⚙"),("automator","🤖")]:
            row = QFrame(); row.setStyleSheet("background:transparent;")
            rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0); rl.setSpacing(0)
            ind = QFrame(); ind.setFixedWidth(3); ind.setStyleSheet("background:transparent;border-radius:1px;")
            rl.addWidget(ind)
            btn = QPushButton(icon); btn.setFixedSize(45,42)
            btn.setStyleSheet(f"QPushButton{{background:transparent;color:{C['dim']};border:none;font-size:18px;border-radius:4px;}}QPushButton:hover{{background:{C['hover']};color:{C['text']};}}")
            btn.clicked.connect(lambda _,v=name: self._show_view(v))
            rl.addWidget(btn); nl.addWidget(row)
            self._nav_btns[name]=btn; self._nav_inds[name]=ind
        nl.addStretch(); bl.addWidget(nav)

        # Content stack
        self._stack = QStackedWidget(); bl.addWidget(self._stack,1)

        # Chat view
        chat_w = QWidget(); chat_w.setStyleSheet(f"background:{C['bg']};")
        cwl = QHBoxLayout(chat_w); cwl.setContentsMargins(0,0,0,0)
        self._chat_main = AIChatPanel(self.cfg, C); cwl.addWidget(self._chat_main)

        # IDE view
        ide_w = QWidget(); ide_w.setStyleSheet(f"background:{C['bg']};")
        idl = QHBoxLayout(ide_w); idl.setContentsMargins(0,0,0,0)
        ide_split = QSplitter(Qt.Orientation.Horizontal)
        ide_split.setHandleWidth(1)
        ide_split.setStyleSheet(f"QSplitter::handle{{background:{C['border']};}}")
        self._explorer = FileExplorer(C); self._explorer.setMinimumWidth(160); self._explorer.setMaximumWidth(320)
        self._explorer.file_opened.connect(self._on_file_open)
        ide_split.addWidget(self._explorer)
        self._editor = IDEPanel(C); ide_split.addWidget(self._editor)
        self._chat_ide = AIChatPanel(self.cfg, C); self._chat_ide.setMinimumWidth(280)
        ide_split.addWidget(self._chat_ide)
        ide_split.setSizes([220,700,340]); idl.addWidget(ide_split)

        # Panel views
        self._terminal  = TerminalPanel(C)
        self._settings  = SettingsPanel(self.cfg, C)
        self._automator = AutomatorPanel(C)
        self._settings.settings_saved.connect(self._on_settings_saved)

        for w in [chat_w, self._terminal, self._settings, self._automator, ide_w]:
            self._stack.addWidget(w)

        self._view_map = {"terminal":self._terminal,"settings":self._settings,"automator":self._automator}
        root_lay.addWidget(body,1)

        status = QStatusBar()
        status.setStyleSheet(f"background:{C['panel']};border-top:1px solid {C['border']};")
        self.setStatusBar(status)
        self._status_lbl = QLabel(f"Ready  ·  {os_label()}")
        self._status_lbl.setStyleSheet(f"color:{C['dim']};font-size:11px;padding:0 8px;")
        status.addWidget(self._status_lbl)

        self._set_mode("chat")

    def _set_mode(self, mode):
        idx = {"chat":0,"ide":4}.get(mode,0)
        self._stack.setCurrentIndex(idx)
        for m, btn in self._mode_btns.items():
            active = m == mode
            btn.setStyleSheet(f"QPushButton{{background:transparent;color:{'#E6EDF3' if active else self.C['dim']};border:none;border-bottom:2px solid {'#2F81F7' if active else 'transparent'};padding:0 16px;font-size:13px;}}QPushButton:hover{{color:{self.C['text']};}}")

    def _show_view(self, name):
        w = self._view_map.get(name)
        if w:
            self._stack.setCurrentIndex(list(self._view_map.values()).index(w)+1)
        C = self.C
        for n, btn in self._nav_btns.items():
            active = n == name
            btn.setStyleSheet(f"QPushButton{{background:transparent;color:{C['text'] if active else C['dim']};border:none;font-size:18px;border-radius:4px;}}QPushButton:hover{{background:{C['hover']};color:{C['text']};}}")
            self._nav_inds[n].setStyleSheet(f"background:{C['accent'] if active else 'transparent'};border-radius:1px;")

    def _on_file_open(self, path): self._editor.open_file(path)

    def _on_settings_saved(self, cfg):
        self.cfg = cfg
        if cfg.get("theme","dark") != list(THEMES.keys())[0]:
            self.C = THEMES.get(cfg.get("theme","dark"), THEMES["dark"])
            self._apply_stylesheet()
        self._chat_main.reload_config(cfg); self._chat_ide.reload_config(cfg)

    def _toggle_theme(self):
        keys = list(THEMES.keys()); cur = self.cfg.get("theme","dark")
        nxt = keys[(keys.index(cur)+1) % len(keys)]
        self.cfg["theme"] = nxt; self.C = THEMES[nxt]; save_cfg(self.cfg); self._apply_stylesheet()

    def _start_ollama_checker(self):
        url = self.cfg.get("ollama_base_url","http://localhost:11434")
        self._ollama = OllamaChecker(url)
        self._ollama.status_changed.connect(self._on_ollama_status)
        self._ollama.start()

    def _on_ollama_status(self, ok):
        self._dot.setText("●" if ok else "○")
        self._dot.setStyleSheet(f"color:{self.C['green'] if ok else self.C['dim']};font-size:14px;padding-right:4px;")

    def closeEvent(self, event):
        if hasattr(self,"_ollama"): self._ollama.stop()
        event.accept()

# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    if hasattr(Qt.ApplicationAttribute,"AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute,"AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("V-Agent"); app.setApplicationVersion(VERSION)
    w = VAgentWindow(); w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
