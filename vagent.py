#!/usr/bin/env python3
"""V-Agent 0.7.1 — Professional Agentic IDE · Voidtune Ecosystem
PySide6 redesign — modern, cross-platform (Windows & Linux)
"""

import os, sys, json, threading, subprocess, datetime, re, platform, time
from collections import defaultdict

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
        print(f"Run:  pip install {' '.join(missing)}")
        ans = input("Install now? [y/N]: ").strip().lower()
        if ans == "y":
            subprocess.run([sys.executable, "-m", "pip", "install"] + missing, check=True)
            print("Installed! Restarting...")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        sys.exit(1)

_bootstrap()

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTextEdit, QPlainTextEdit, QLineEdit, QLabel,
    QPushButton, QFrame, QScrollArea, QComboBox, QCheckBox,
    QSpinBox, QFileDialog, QMessageBox, QTabBar, QStackedWidget,
    QTreeWidget, QTreeWidgetItem, QSizePolicy, QToolButton,
    QStatusBar, QDialog, QDialogButtonBox, QProgressBar
)
from PySide6.QtCore import (
    Qt, QThread, Signal, QTimer, QSize, QPropertyAnimation,
    QEasingCurve, QPoint, QRect, QObject, Slot
)
from PySide6.QtGui import (
    QFont, QFontMetrics, QColor, QPalette, QTextCharFormat,
    QSyntaxHighlighter, QKeySequence, QShortcut, QIcon,
    QPainter, QPen, QBrush, QLinearGradient, QTextCursor,
    QAction, QPixmap
)
import requests as _req

# ── Env loader ─────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CFG_PATH  = os.path.join(BASE_DIR, "config.json")
INPUT_DIR = os.path.join(BASE_DIR, "Input")
OUT_DIR   = os.path.join(BASE_DIR, "Output")
VERSION   = "0.7.1"

def _load_env():
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip(); val = val.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, val)
    except Exception:
        pass

_load_env()

DEFAULT_CFG = {
    "model":             "qwen2.5-coder:14b",
    "theme":             "dark",
    "ollama_base_url":   "http://localhost:11434",
    "streaming":         True,
    "font_size":         13,
    "ai_provider":       "backend",
    "vagent_server_url": "https://v-agent.vercel.app",
    "groq_api_key":      "",
    "groq_model":        "llama-3.3-70b-versatile",
    "openrouter_api_key":"",
    "openrouter_model":  "meta-llama/llama-3.2-3b-instruct:free",
}

FALLBACK_MODELS = [
    "qwen2.5-coder:14b","qwen2.5-coder:7b","deepseek-coder-v2:16b",
    "codellama:13b","granite-code:8b","llama3.1:8b",
]

# ── Config ─────────────────────────────────────────────────────────────────────
def load_cfg():
    _load_env()
    cfg = dict(DEFAULT_CFG)
    if os.path.exists(CFG_PATH):
        try:
            with open(CFG_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
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

def save_cfg(cfg):
    """Save settings — API keys are NEVER written to config.json (stay in .env only)."""
    safe = {k: v for k, v in cfg.items() if "api_key" not in k}
    try:
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(safe, f, indent=2)
    except Exception as e:
        print(f"[cfg] {e}")

# ── Design tokens ──────────────────────────────────────────────────────────────
THEMES = {
    "dark": {
        "bg":         "#0D1117",
        "panel":      "#161B22",
        "sidebar":    "#0D1117",
        "border":     "#21262D",
        "text":       "#E6EDF3",
        "dim":        "#7D8590",
        "accent":     "#2F81F7",
        "accent2":    "#1F6FEB",
        "green":      "#3FB950",
        "red":        "#F85149",
        "yellow":     "#D29922",
        "orange":     "#E3B341",
        "purple":     "#BC8CFF",
        "cyan":       "#79C0FF",
        "selection":  "#1F3358",
        "hover":      "#21262D",
        "input_bg":   "#161B22",
        "btn_bg":     "#21262D",
        "btn_hover":  "#30363D",
        "tag_bg":     "#1C2128",
        "code_bg":    "#161B22",
        "user_bg":    "#1C2128",
        "ai_bg":      "#161B22",
        "scrollbar":  "#30363D",
    },
    "light": {
        "bg":         "#FFFFFF",
        "panel":      "#F6F8FA",
        "sidebar":    "#F6F8FA",
        "border":     "#D0D7DE",
        "text":       "#1F2328",
        "dim":        "#636C76",
        "accent":     "#0969DA",
        "accent2":    "#0550AE",
        "green":      "#1A7F37",
        "red":        "#CF222E",
        "yellow":     "#9A6700",
        "orange":     "#BC4C00",
        "purple":     "#8250DF",
        "cyan":       "#0550AE",
        "selection":  "#DDF4FF",
        "hover":      "#F3F4F6",
        "input_bg":   "#FFFFFF",
        "btn_bg":     "#F6F8FA",
        "btn_hover":  "#EAEEF2",
        "tag_bg":     "#EFF1F3",
        "code_bg":    "#F6F8FA",
        "user_bg":    "#EFF1F3",
        "ai_bg":      "#FFFFFF",
        "scrollbar":  "#D0D7DE",
    },
}

# ── Language / syntax maps ─────────────────────────────────────────────────────
LANG_EXT = {
    ".py":"python",".pyw":"python",
    ".js":"javascript",".jsx":"javascript",".mjs":"javascript",
    ".ts":"typescript",".tsx":"typescript",
    ".html":"html",".htm":"html",".jinja":"html",".j2":"html",
    ".xml":"xml",".css":"css",".scss":"css",".less":"css",
    ".json":"json",".sh":"bash",".bash":"bash",".zsh":"bash",
    ".bat":"batch",".cmd":"batch",".ps1":"powershell",
    ".md":"markdown",".c":"c",".h":"c",
    ".cpp":"cpp",".cxx":"cpp",".cc":"cpp",".hpp":"cpp",
    ".rs":"rust",".go":"go",".rb":"ruby",".php":"php",
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
AGENT_SYSTEM = """You are V-Agent, an expert agentic AI coding assistant embedded in a professional IDE.
You think carefully before acting and produce clean, correct, idiomatic code.

## TOOLS

You can use tools by including XML tags in your response.
Always prefer tools over just describing code changes — apply them directly.

Read a file:
<vagent:read path="relative/or/absolute/path"/>

Write or create a file:
<vagent:write path="relative/path">
complete file content here
</vagent:write>

Edit the currently open file (replaces entire content):
<vagent:edit>
complete new file content here
</vagent:edit>

List a directory:
<vagent:ls path="."/>

Run a shell command:
<vagent:run>command here</vagent:run>

Search for text in files:
<vagent:search pattern="search_text" path="."/>

## GUIDELINES
- When asked to fix/edit/refactor: use <vagent:edit> to apply changes directly to the open file
- When creating a new file: use <vagent:write path="filename">content</vagent:write>
- When you need to inspect a file: use <vagent:read path="..."/>
- After every tool use, briefly explain what you did (1-2 sentences)
- Produce production-quality code: handle errors, add types where appropriate
- Keep explanations short — prefer showing over telling
- When fixing bugs, explain the root cause briefly
"""

# ── Syntax Highlighter ─────────────────────────────────────────────────────────
SYNTAX_RULES = {
    "python": [
        ("kw",   "#C586C0", r'\b(False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)\b'),
        ("bi",   "#9CDCFE", r'\b(print|len|range|type|int|str|float|list|dict|set|tuple|bool|open|super|self|cls|input|enumerate|zip|map|filter|sorted|reversed|any|all|min|max|sum|abs|round|isinstance|hasattr|getattr|setattr)\b'),
        ("st",   "#CE9178", r"('''[\s\S]*?'''|\"\"\"[\s\S]*?\"\"\"|f'(?:[^'\\]|\\.)*'|f\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")"),
        ("cm",   "#6A9955", r'#[^\n]*'),
        ("nm",   "#B5CEA8", r'\b\d+\.?\d*\b'),
        ("dc",   "#C6A0F6", r'@[\w.]+'),
        ("fn",   "#DCDCAA", r'(?<=def )\w+'),
        ("cl",   "#4EC9B0", r'(?<=class )\w+'),
    ],
    "javascript": [
        ("kw",   "#C586C0", r'\b(async|await|break|case|catch|class|const|continue|default|delete|do|else|export|extends|finally|for|from|function|if|import|in|instanceof|let|new|of|return|static|super|switch|this|throw|try|typeof|var|void|while|with|yield)\b'),
        ("bi",   "#9CDCFE", r'\b(console|window|document|Array|Object|String|Number|Boolean|Promise|Math|JSON|Date|undefined|null|true|false|NaN|require|module|exports)\b'),
        ("st",   "#CE9178", r'(`[^`]*`|\'(?:[^\'\\]|\\.)*\'|"(?:[^"\\]|\\.)*")'),
        ("cm",   "#6A9955", r'(//[^\n]*|/\*[\s\S]*?\*/)'),
        ("nm",   "#B5CEA8", r'\b\d+\.?\d*\b'),
        ("fn",   "#DCDCAA", r'\b\w+(?=\s*\()'),
    ],
    "html": [
        ("tg",   "#4EC9B0", r'</?[a-zA-Z][a-zA-Z0-9-]*'),
        ("at",   "#9CDCFE", r'\b[a-zA-Z][a-zA-Z0-9-]*(?=\s*=)'),
        ("st",   "#CE9178", r'"[^"]*"'),
        ("cm",   "#6A9955", r'<!--[\s\S]*?-->'),
    ],
    "css": [
        ("sl",   "#D7BA7D", r'[.#][a-zA-Z][a-zA-Z0-9_-]*'),
        ("pr",   "#9CDCFE", r'\b[a-z][a-z-]+(?=\s*:)'),
        ("st",   "#CE9178", r'"[^"]*"|\'[^\']*\''),
        ("cm",   "#6A9955", r'/\*[\s\S]*?\*/'),
        ("nm",   "#B5CEA8", r'\b\d+\.?\d*(?:px|em|rem|%|vh|vw|pt)?\b'),
    ],
    "json": [
        ("ky",   "#9CDCFE", r'"(?:[^"\\]|\\.)*"(?=\s*:)'),
        ("st",   "#CE9178", r'(?<=:\s*)"(?:[^"\\]|\\.)*"'),
        ("kw",   "#569CD6", r'\b(true|false|null)\b'),
        ("nm",   "#B5CEA8", r'-?\b\d+\.?\d*\b'),
    ],
    "bash": [
        ("kw",   "#C586C0", r'\b(if|then|else|elif|fi|for|while|until|do|done|case|esac|function|return|local|export|echo|exit|source|cd|ls|rm|mv|cp|mkdir|grep|sed|awk|curl|git)\b'),
        ("st",   "#CE9178", r"'[^']*'|\"(?:[^\"\\]|\\.)*\""),
        ("cm",   "#6A9955", r'#[^\n]*'),
        ("vr",   "#9CDCFE", r'\$\{?[\w@#?$!*-]+\}?'),
    ],
}

class SyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, document, lang="python", theme="dark"):
        super().__init__(document)
        self._rules = []
        self._theme = theme
        self.set_lang(lang)

    def set_lang(self, lang):
        self._rules = []
        rules = SYNTAX_RULES.get(lang, [])
        for _, color, pattern in rules:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            self._rules.append((re.compile(pattern), fmt))

    def highlightBlock(self, text):
        for regex, fmt in self._rules:
            for m in regex.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)

# ── Safe command check ─────────────────────────────────────────────────────────
_SAFE_CMDS = [
    "ls","dir","pwd","echo","cat","type","python","node","npm","pip",
    "git","code","mkdir","touch","cp","copy","mv","move","rm","del",
    "grep","find","which","where","uname","ver","date","time",
]

def is_safe_command(cmd: str) -> bool:
    low = cmd.strip().lower()
    return any(low.startswith(s) for s in _SAFE_CMDS)

# ── Cloud AI Client (direct, for groq/openrouter fallback) ────────────────────
class CloudAIClient:
    BASE_URLS = {
        "groq":       "https://api.groq.com/openai/v1",
        "openrouter": "https://openrouter.ai/api/v1",
    }
    def __init__(self, provider, api_key, model):
        self.provider = provider
        self.model    = model
        self.base_url = self.BASE_URLS.get(provider, "")
        self._s = _req.Session()
        self._s.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        })
        if provider == "openrouter":
            self._s.headers.update({
                "HTTP-Referer": "https://github.com/otzpt/V-Agent",
                "X-Title":      "V-Agent",
            })

    def stream(self, messages, temperature=0.15, cancel_flag=None):
        url  = f"{self.base_url}/chat/completions"
        body = {
            "model":       self.model,
            "messages":    messages,
            "stream":      True,
            "temperature": temperature,
            "max_tokens":  4096,
        }
        resp = self._s.post(url, json=body, stream=True, timeout=180)
        resp.raise_for_status()
        for raw in resp.iter_lines():
            if cancel_flag and cancel_flag(): break
            if not raw: continue
            line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            if not line.startswith("data: "): continue
            data = line[6:]
            if data == "[DONE]": break
            try:
                delta = json.loads(data)["choices"][0].get("delta", {})
                tok   = delta.get("content", "")
                if tok: yield tok
            except Exception: pass

# ── Worker thread for LLM requests ────────────────────────────────────────────
class LLMWorker(QThread):
    token_received = Signal(str)
    finished       = Signal(str)
    error          = Signal(str)

    def __init__(self, cfg, history, message):
        super().__init__()
        self._cfg      = cfg
        self._history  = history
        self._message  = message
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        provider = self._cfg.get("ai_provider", "backend")
        try:
            if provider == "backend":
                self._run_backend()
            elif provider == "local":
                self._run_local()
            else:
                self._run_cloud(provider)
        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))

    def _run_backend(self):
        server_url = self._cfg.get("vagent_server_url", "https://v-agent.vercel.app").rstrip("/")
        model      = self._cfg.get("groq_model", "llama-3.3-70b-versatile")
        history    = [m for m in self._history[-10:] if m["role"] in ("user", "assistant")]
        # Remove last user message (sent separately)
        history    = [m for m in history if not (m["role"] == "user" and m["content"] == self._message)]

        try:
            resp = _req.post(
                f"{server_url}/chat",
                json={"message": self._message, "model": model, "history": history},
                timeout=60,
            )
            if self._cancelled: return
            if resp.status_code == 429:
                self.error.emit("Rate limit reached (30/min). Try again shortly.")
                return
            if resp.status_code != 200:
                self.error.emit(f"Server error ({resp.status_code}). Try again.")
                return
            content = resp.json().get("content", "")
            # Stream character by character for a nice effect
            for char in content:
                if self._cancelled: return
                self.token_received.emit(char)
            self.finished.emit(content)
        except _req.exceptions.ConnectionError:
            self.error.emit("Cannot reach server. Check internet connection.")
        except _req.exceptions.Timeout:
            self.error.emit("Request timed out (60s).")

    def _run_local(self):
        base  = self._cfg.get("ollama_base_url", "http://localhost:11434")
        model = self._cfg.get("model", FALLBACK_MODELS[0])
        msgs  = [{"role": "system", "content": AGENT_SYSTEM}] + self._history[-20:]
        full  = []
        resp  = _req.post(
            f"{base}/api/chat",
            json={"model": model, "messages": msgs, "stream": True,
                  "options": {"temperature": 0.15, "num_ctx": 32768}},
            stream=True, timeout=180)
        resp.raise_for_status()
        for line in resp.iter_lines():
            if self._cancelled: return
            if not line: continue
            try:
                tok = json.loads(line).get("message", {}).get("content", "")
                if tok:
                    full.append(tok)
                    self.token_received.emit(tok)
            except Exception: pass
        self.finished.emit("".join(full))

    def _run_cloud(self, provider):
        api_key = self._cfg.get(f"{provider}_api_key", "").strip()
        model   = self._cfg.get(f"{provider}_model",   "").strip()
        if not api_key:
            self.error.emit(f"No {provider} API key. Add it in Settings.")
            return
        msgs   = [{"role": "system", "content": AGENT_SYSTEM}] + self._history[-20:]
        client = CloudAIClient(provider, api_key, model)
        full   = []
        for tok in client.stream(msgs, cancel_flag=lambda: self._cancelled):
            if self._cancelled: return
            full.append(tok)
            self.token_received.emit(tok)
        self.finished.emit("".join(full))

# ── Styled widgets ─────────────────────────────────────────────────────────────
def make_stylesheet(C):
    return f"""
    QMainWindow, QWidget {{ background: {C['bg']}; color: {C['text']}; }}
    QFrame {{ background: transparent; }}

    /* Scrollbars */
    QScrollBar:vertical {{
        background: transparent; width: 8px; margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {C['scrollbar']}; border-radius: 4px; min-height: 30px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{
        background: transparent; height: 8px; margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: {C['scrollbar']}; border-radius: 4px; min-width: 30px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

    /* Inputs */
    QLineEdit, QSpinBox {{
        background: {C['input_bg']}; color: {C['text']};
        border: 1px solid {C['border']}; border-radius: 6px;
        padding: 6px 10px; font-size: 13px;
        selection-background-color: {C['selection']};
    }}
    QLineEdit:focus, QSpinBox:focus {{
        border-color: {C['accent']};
    }}

    /* Buttons */
    QPushButton {{
        background: {C['btn_bg']}; color: {C['text']};
        border: 1px solid {C['border']}; border-radius: 6px;
        padding: 6px 14px; font-size: 13px;
    }}
    QPushButton:hover {{ background: {C['btn_hover']}; border-color: {C['accent']}; }}
    QPushButton:pressed {{ background: {C['selection']}; }}
    QPushButton#accent {{
        background: {C['accent']}; color: #FFFFFF; border-color: {C['accent2']};
    }}
    QPushButton#accent:hover {{ background: {C['accent2']}; }}
    QPushButton#danger {{
        background: transparent; color: {C['red']}; border-color: {C['red']};
    }}
    QPushButton#danger:hover {{ background: {C['red']}; color: #FFFFFF; }}

    /* Combobox */
    QComboBox {{
        background: {C['input_bg']}; color: {C['text']};
        border: 1px solid {C['border']}; border-radius: 6px;
        padding: 6px 10px; font-size: 13px;
    }}
    QComboBox:focus {{ border-color: {C['accent']}; }}
    QComboBox::drop-down {{ border: none; width: 20px; }}
    QComboBox QAbstractItemView {{
        background: {C['panel']}; color: {C['text']};
        border: 1px solid {C['border']}; selection-background-color: {C['selection']};
    }}

    /* TextEdit */
    QTextEdit, QPlainTextEdit {{
        background: {C['bg']}; color: {C['text']};
        border: none; font-size: 13px;
        selection-background-color: {C['selection']};
    }}

    /* TreeWidget */
    QTreeWidget {{
        background: {C['sidebar']}; color: {C['text']};
        border: none; font-size: 12px;
    }}
    QTreeWidget::item:hover {{ background: {C['hover']}; }}
    QTreeWidget::item:selected {{ background: {C['selection']}; color: {C['text']}; }}
    QTreeWidget::branch {{ background: transparent; }}

    /* TabBar */
    QTabBar {{ background: transparent; }}
    QTabBar::tab {{
        background: {C['panel']}; color: {C['dim']};
        border: none; border-right: 1px solid {C['border']};
        padding: 8px 16px; font-size: 12px;
    }}
    QTabBar::tab:selected {{ background: {C['bg']}; color: {C['text']}; border-bottom: 2px solid {C['accent']}; }}
    QTabBar::tab:hover {{ background: {C['hover']}; color: {C['text']}; }}
    QTabBar::close-button {{ image: none; }}

    /* Checkbox */
    QCheckBox {{ color: {C['text']}; spacing: 8px; }}
    QCheckBox::indicator {{
        width: 16px; height: 16px; border-radius: 4px;
        border: 1px solid {C['border']}; background: {C['input_bg']};
    }}
    QCheckBox::indicator:checked {{
        background: {C['accent']}; border-color: {C['accent']};
    }}

    /* StatusBar */
    QStatusBar {{ background: {C['panel']}; color: {C['dim']}; border-top: 1px solid {C['border']}; font-size: 11px; }}

    /* Labels */
    QLabel {{ color: {C['text']}; background: transparent; }}
    QLabel#dim {{ color: {C['dim']}; }}
    QLabel#accent {{ color: {C['accent']}; }}
    QLabel#green {{ color: {C['green']}; }}
    QLabel#red {{ color: {C['red']}; }}

    /* Separator */
    QFrame[frameShape="4"], QFrame[frameShape="5"] {{
        color: {C['border']};
    }}
    """

# ── Chat message widget ────────────────────────────────────────────────────────
class ChatMessage(QFrame):
    def __init__(self, role, content, C, parent=None):
        super().__init__(parent)
        self._C    = C
        self._role = role
        self._build(role, content)

    def _build(self, role, content):
        C   = self._C
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(4)

        is_user = role == "user"
        bg_color = C["user_bg"] if is_user else C["ai_bg"]
        border   = C["accent"] if is_user else C["border"]

        self.setStyleSheet(f"""
            ChatMessage {{
                background: {bg_color};
                border-left: 3px solid {border};
                border-radius: 0px;
                margin: 1px 0;
            }}
        """)

        # Header row
        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        role_label = QLabel("You" if is_user else "V-Agent")
        role_label.setStyleSheet(f"""
            font-weight: 700; font-size: 12px;
            color: {'#79C0FF' if is_user else '#3FB950'};
            letter-spacing: 0.5px;
        """)
        hdr.addWidget(role_label)
        hdr.addStretch()

        ts = QLabel(datetime.datetime.now().strftime("%H:%M"))
        ts.setStyleSheet(f"color: {C['dim']}; font-size: 11px;")
        hdr.addWidget(ts)
        lay.addLayout(hdr)

        # Content
        self._content_lbl = QLabel(content)
        self._content_lbl.setWordWrap(True)
        self._content_lbl.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse |
            Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self._content_lbl.setStyleSheet(f"""
            color: {C['text']}; font-size: 13px;
            line-height: 1.6; padding: 2px 0;
        """)
        self._content_lbl.setOpenExternalLinks(True)
        lay.addWidget(self._content_lbl)

    def append_text(self, text):
        current = self._content_lbl.text()
        self._content_lbl.setText(current + text)

    def set_text(self, text):
        self._content_lbl.setText(text)

# ── AI Chat panel ──────────────────────────────────────────────────────────────
class AIChatPanel(QWidget):
    def __init__(self, cfg, C, parent=None):
        super().__init__(parent)
        self._cfg     = cfg
        self._C       = C
        self._history = []
        self._worker  = None
        self._current_msg = None
        self._build()

    def _build(self):
        C   = self._C
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QFrame()
        hdr.setFixedHeight(48)
        hdr.setStyleSheet(f"background: {C['panel']}; border-bottom: 1px solid {C['border']};")
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(16, 0, 16, 0)

        title = QLabel("✦  AI Chat")
        title.setStyleSheet(f"font-weight: 700; font-size: 14px; color: {C['text']}; letter-spacing: -0.3px;")
        hdr_lay.addWidget(title)
        hdr_lay.addStretch()

        # Provider badge
        self._provider_badge = QLabel()
        self._provider_badge.setStyleSheet(f"""
            background: {C['tag_bg']}; color: {C['dim']};
            border-radius: 4px; padding: 2px 8px; font-size: 11px;
        """)
        self._update_provider_badge()
        hdr_lay.addWidget(self._provider_badge)

        lay.addWidget(hdr)

        # ── Quick actions ──────────────────────────────────────────────────────
        qa_frame = QFrame()
        qa_frame.setStyleSheet(f"background: {C['panel']}; border-bottom: 1px solid {C['border']};")
        qa_lay = QHBoxLayout(qa_frame)
        qa_lay.setContentsMargins(12, 6, 12, 6)
        qa_lay.setSpacing(4)

        for label, prompt in [
            ("Explain",  "Explain what this code does, step by step:"),
            ("Fix",      "Find and fix all bugs, edge cases, and issues:"),
            ("Comment",  "Add clear, helpful docstrings and inline comments:"),
            ("Refactor", "Refactor for clarity, best practices, and performance:"),
            ("Tests",    "Write comprehensive unit tests:"),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {C['tag_bg']}; color: {C['dim']};
                    border: 1px solid {C['border']}; border-radius: 4px;
                    padding: 3px 10px; font-size: 11px;
                }}
                QPushButton:hover {{ color: {C['text']}; border-color: {C['accent']}; }}
            """)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, p=prompt: self._quick(p))
            qa_lay.addWidget(btn)
        qa_lay.addStretch()
        lay.addWidget(qa_frame)

        # ── Messages scroll area ───────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(f"background: {C['bg']}; border: none;")

        self._msg_container = QWidget()
        self._msg_container.setStyleSheet(f"background: {C['bg']};")
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(0, 8, 0, 8)
        self._msg_layout.setSpacing(0)
        self._msg_layout.addStretch()

        self._scroll.setWidget(self._msg_container)
        lay.addWidget(self._scroll, 1)

        # ── Status bar ─────────────────────────────────────────────────────────
        self._status_bar = QFrame()
        self._status_bar.setFixedHeight(28)
        self._status_bar.setStyleSheet(f"background: {C['panel']}; border-top: 1px solid {C['border']};")
        sb_lay = QHBoxLayout(self._status_bar)
        sb_lay.setContentsMargins(12, 0, 12, 0)
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color: {C['dim']}; font-size: 11px;")
        sb_lay.addWidget(self._status_lbl)
        sb_lay.addStretch()
        lay.addWidget(self._status_bar)

        # ── Input area ─────────────────────────────────────────────────────────
        inp_frame = QFrame()
        inp_frame.setStyleSheet(f"background: {C['panel']}; border-top: 1px solid {C['border']};")
        inp_lay = QVBoxLayout(inp_frame)
        inp_lay.setContentsMargins(12, 8, 12, 8)
        inp_lay.setSpacing(6)

        self._input = QPlainTextEdit()
        self._input.setPlaceholderText("Ask V-Agent anything... (Enter to send, Shift+Enter for newline)")
        self._input.setFixedHeight(72)
        self._input.setStyleSheet(f"""
            background: {C['input_bg']}; color: {C['text']};
            border: 1px solid {C['border']}; border-radius: 8px;
            padding: 8px 12px; font-size: 13px;
            selection-background-color: {C['selection']};
        """)
        self._input.installEventFilter(self)
        inp_lay.addWidget(self._input)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._send_btn = QPushButton("Send  ↵")
        self._send_btn.setObjectName("accent")
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setFixedHeight(34)
        self._send_btn.clicked.connect(self._send)
        btn_row.addWidget(self._send_btn)

        self._cancel_btn = QPushButton("✕  Cancel")
        self._cancel_btn.setObjectName("danger")
        self._cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_btn.setFixedHeight(34)
        self._cancel_btn.setVisible(False)
        self._cancel_btn.clicked.connect(self._cancel)
        btn_row.addWidget(self._cancel_btn)

        btn_row.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(34)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear)
        btn_row.addWidget(clear_btn)

        inp_lay.addLayout(btn_row)
        lay.addWidget(inp_frame)

    def _update_provider_badge(self):
        p = self._cfg.get("ai_provider", "backend")
        labels = {
            "backend":    "☁  Groq Cloud",
            "local":      "⬡  Local Ollama",
            "groq":       "⚡  Groq Direct",
            "openrouter": "◈  OpenRouter",
        }
        self._provider_badge.setText(labels.get(p, p))

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            from PySide6.QtGui import QKeyEvent
            key = event.key()
            mods = event.modifiers()
            if key == Qt.Key.Key_Return and not (mods & Qt.KeyboardModifier.ShiftModifier):
                self._send()
                return True
        return super().eventFilter(obj, event)

    def _quick(self, prompt):
        self._input.setPlainText(prompt)
        self._send()

    def _send(self):
        text = self._input.toPlainText().strip()
        if not text or self._worker is not None:
            return
        self._input.clear()

        # Add user message
        self._add_message("user", text)
        self._history.append({"role": "user", "content": text})

        # Placeholder AI message
        self._current_msg = ChatMessage("assistant", "", self._C)
        self._msg_layout.insertWidget(self._msg_layout.count() - 1, self._current_msg)
        self._scroll_to_bottom()

        self._set_loading(True)

        self._worker = LLMWorker(self._cfg, list(self._history), text)
        self._worker.token_received.connect(self._on_token)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_token(self, tok):
        if self._current_msg:
            self._current_msg.append_text(tok)
            self._scroll_to_bottom()

    def _on_done(self, full_text):
        self._history.append({"role": "assistant", "content": full_text})
        self._worker = None
        self._current_msg = None
        self._set_loading(False)

    def _on_error(self, err):
        if self._current_msg:
            self._current_msg.set_text(f"⚠  {err}")
            self._current_msg.setStyleSheet(f"""
                ChatMessage {{
                    background: #2D1B1B;
                    border-left: 3px solid {self._C['red']};
                    border-radius: 0px;
                    margin: 1px 0;
                }}
            """)
        self._worker = None
        self._current_msg = None
        self._set_loading(False)

    def _cancel(self):
        if self._worker:
            self._worker.cancel()
            self._worker.quit()
            self._worker = None
        self._set_loading(False)

    def _clear(self):
        # Remove all message widgets
        while self._msg_layout.count() > 1:
            item = self._msg_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._history.clear()

    def _add_message(self, role, content):
        msg = ChatMessage(role, content, self._C)
        self._msg_layout.insertWidget(self._msg_layout.count() - 1, msg)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()))

    def _set_loading(self, loading):
        self._send_btn.setVisible(not loading)
        self._cancel_btn.setVisible(loading)
        txt = "⟳  Thinking..." if loading else ""
        self._status_lbl.setText(txt)

    def reload_config(self, cfg):
        self._cfg = cfg
        self._update_provider_badge()

# ── Code editor ───────────────────────────────────────────────────────────────
class CodeEditor(QPlainTextEdit):
    def __init__(self, C, parent=None):
        super().__init__(parent)
        self._C = C
        self._highlighter = None
        self._path = None

        mono = self._best_mono()
        self.setFont(QFont(mono, 13))
        self.setStyleSheet(f"""
            QPlainTextEdit {{
                background: {C['bg']}; color: {C['text']};
                border: none; padding: 12px;
                selection-background-color: {C['selection']};
            }}
        """)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

    def _best_mono(self):
        from PySide6.QtGui import QFontDatabase
        available = QFontDatabase.families()
        for f in ("Cascadia Code", "JetBrains Mono", "Fira Code",
                  "Source Code Pro", "Consolas", "Courier New"):
            if f in available:
                return f
        return "Courier New"

    def load_file(self, path):
        self._path = path
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                self.setPlainText(f.read())
            ext  = os.path.splitext(path)[1].lower()
            lang = LANG_EXT.get(ext, "text")
            self._highlighter = SyntaxHighlighter(self.document(), lang)
        except Exception as e:
            self.setPlainText(f"Error reading file: {e}")

    def save_file(self, path=None):
        p = path or self._path
        if not p: return False
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write(self.toPlainText())
            self._path = p
            return True
        except Exception as e:
            QMessageBox.warning(None, "Save Error", str(e))
            return False

# ── IDE panel ─────────────────────────────────────────────────────────────────
class IDEPanel(QWidget):
    def __init__(self, cfg, C, parent=None):
        super().__init__(parent)
        self._cfg   = cfg
        self._C     = C
        self._tabs  = {}  # path -> CodeEditor
        self._build()

    def _build(self):
        C   = self._C
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Tab bar
        self._tab_bar = QTabBar()
        self._tab_bar.setTabsClosable(True)
        self._tab_bar.setMovable(True)
        self._tab_bar.tabCloseRequested.connect(self._close_tab)
        self._tab_bar.currentChanged.connect(self._switch_tab)
        lay.addWidget(self._tab_bar)

        # Editor stack
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background: {C['bg']};")
        lay.addWidget(self._stack, 1)

        # Empty state
        empty = QLabel("Open a file from the Explorer\nor drag & drop here")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setStyleSheet(f"color: {C['dim']}; font-size: 14px;")
        self._empty = empty
        self._stack.addWidget(empty)

    def open_file(self, path):
        if path in self._tabs:
            idx = list(self._tabs.keys()).index(path)
            self._tab_bar.setCurrentIndex(idx + 1)  # +1 for empty
            return
        editor = CodeEditor(self._C)
        editor.load_file(path)
        self._tabs[path] = editor
        self._stack.addWidget(editor)
        ext  = os.path.splitext(path)[1]
        icon = FILE_ICONS.get(ext, "📄")
        idx  = self._tab_bar.addTab(f"{icon}  {os.path.basename(path)}")
        self._tab_bar.setCurrentIndex(idx)
        self._stack.setCurrentWidget(editor)

    def _close_tab(self, idx):
        # idx is tab bar index; tab 0 is empty placeholder correction
        tab_idx = idx
        paths   = list(self._tabs.keys())
        if tab_idx < len(paths):
            path = paths[tab_idx]
            editor = self._tabs.pop(path)
            self._stack.removeWidget(editor)
            editor.deleteLater()
        self._tab_bar.removeTab(idx)

    def _switch_tab(self, idx):
        paths = list(self._tabs.keys())
        if idx < len(paths):
            self._stack.setCurrentWidget(self._tabs[paths[idx]])
        else:
            self._stack.setCurrentWidget(self._empty)

    def save_current(self):
        w = self._stack.currentWidget()
        if isinstance(w, CodeEditor):
            w.save_file()

    def current_content(self):
        w = self._stack.currentWidget()
        if isinstance(w, CodeEditor):
            return w.toPlainText()
        return ""

# ── File explorer ─────────────────────────────────────────────────────────────
class FileExplorer(QTreeWidget):
    file_opened = Signal(str)

    def __init__(self, C, parent=None):
        super().__init__(parent)
        self._C    = C
        self._root = None
        self.setHeaderHidden(True)
        self.setIndentation(16)
        self.itemDoubleClicked.connect(self._on_item)
        self.setStyleSheet(f"""
            QTreeWidget {{
                background: {C['sidebar']}; color: {C['text']};
                border: none; font-size: 12px;
                padding-top: 4px;
            }}
            QTreeWidget::item {{ padding: 3px 4px; }}
            QTreeWidget::item:hover {{ background: {C['hover']}; border-radius: 4px; }}
            QTreeWidget::item:selected {{
                background: {C['selection']}; color: {C['text']}; border-radius: 4px;
            }}
        """)

    def set_root(self, path):
        self._root = path
        self.clear()
        self._populate(self, path)

    def _populate(self, parent, path):
        try:
            entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return
        for entry in entries:
            if entry.name.startswith(".") or entry.name == "__pycache__":
                continue
            item = QTreeWidgetItem(parent)
            if entry.is_dir():
                item.setText(0, f"  {entry.name}")
                item.setData(0, Qt.ItemDataRole.UserRole, entry.path)
                item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
                self._populate(item, entry.path)
            else:
                ext  = os.path.splitext(entry.name)[1].lower()
                icon = FILE_ICONS.get(ext, "📄")
                item.setText(0, f"{icon}  {entry.name}")
                item.setData(0, Qt.ItemDataRole.UserRole, entry.path)

    def _on_item(self, item, col):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path and os.path.isfile(path):
            self.file_opened.emit(path)

# ── Terminal panel ─────────────────────────────────────────────────────────────
class TerminalPanel(QWidget):
    def __init__(self, cfg, C, parent=None):
        super().__init__(parent)
        self._cfg  = cfg
        self._C    = C
        self._hist = []
        self._hist_idx = -1
        self._build()

    def _build(self):
        C   = self._C
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setFixedHeight(38)
        hdr.setStyleSheet(f"background: {C['panel']}; border-bottom: 1px solid {C['border']};")
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(16, 0, 16, 0)
        title = QLabel("⬛  Terminal")
        title.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {C['text']};")
        hdr_lay.addWidget(title)
        hdr_lay.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(26)
        clear_btn.clicked.connect(self._clear)
        hdr_lay.addWidget(clear_btn)
        lay.addWidget(hdr)

        # Output
        self._out = QTextEdit()
        self._out.setReadOnly(True)
        mono = QFont("Cascadia Code", 12)
        self._out.setFont(mono)
        self._out.setStyleSheet(f"""
            QTextEdit {{
                background: {C['bg']}; color: {C['text']};
                border: none; padding: 12px 16px;
            }}
        """)
        lay.addWidget(self._out, 1)

        # Input
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C['border']};")
        lay.addWidget(sep)

        inp_frame = QFrame()
        inp_frame.setStyleSheet(f"background: {C['panel']};")
        inp_lay = QHBoxLayout(inp_frame)
        inp_lay.setContentsMargins(12, 6, 12, 6)
        inp_lay.setSpacing(8)

        self._prompt_lbl = QLabel(f"{os.getcwd()} $")
        self._prompt_lbl.setStyleSheet(f"color: {C['green']}; font-family: 'Cascadia Code', monospace; font-size: 12px;")
        inp_lay.addWidget(self._prompt_lbl)

        self._inp = QLineEdit()
        self._inp.setPlaceholderText("Enter command...")
        self._inp.setStyleSheet(f"""
            QLineEdit {{
                background: transparent; color: {C['text']};
                border: none; font-family: 'Cascadia Code', monospace; font-size: 12px;
            }}
        """)
        self._inp.returnPressed.connect(self._run_cmd)
        inp_lay.addWidget(self._inp, 1)

        lay.addWidget(inp_frame)

        # Welcome
        self._write(f"V-Agent {VERSION} — Terminal\n", C["accent"])
        self._write(f"Platform: {platform.system()} {platform.machine()}\n", C["dim"])
        self._write("Type commands below. Use Ctrl+C to copy output.\n\n", C["dim"])

    def _write(self, text, color=None):
        C   = self._C
        cur = self._out.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color or C["text"]))
        cur.insertText(text, fmt)
        self._out.setTextCursor(cur)
        self._out.ensureCursorVisible()

    def _run_cmd(self):
        cmd = self._inp.text().strip()
        if not cmd: return
        self._hist.insert(0, cmd)
        self._hist_idx = -1
        self._inp.clear()

        C = self._C
        self._write(f"$ {cmd}\n", C["green"])

        if not is_safe_command(cmd):
            self._write(f"⚠  Command not allowed: {cmd}\n", C["red"])
            return

        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=30, cwd=BASE_DIR)
            if result.stdout:
                self._write(result.stdout, C["text"])
            if result.stderr:
                self._write(result.stderr, C["red"])
            if result.returncode != 0 and not result.stderr:
                self._write(f"Exit code: {result.returncode}\n", C["yellow"])
        except subprocess.TimeoutExpired:
            self._write("Timeout (30s)\n", C["red"])
        except Exception as e:
            self._write(f"Error: {e}\n", C["red"])

    def _clear(self):
        self._out.clear()

# ── Settings panel ─────────────────────────────────────────────────────────────
class SettingsPanel(QWidget):
    settings_saved = Signal(dict)

    def __init__(self, cfg, C, parent=None):
        super().__init__(parent)
        self._cfg = cfg
        self._C   = C
        self._build()

    def _build(self):
        C   = self._C
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setFixedHeight(48)
        hdr.setStyleSheet(f"background: {C['panel']}; border-bottom: 1px solid {C['border']};")
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(16, 0, 16, 0)
        title = QLabel("⚙  Settings")
        title.setStyleSheet(f"font-weight: 700; font-size: 14px; color: {C['text']};")
        hdr_lay.addWidget(title)
        lay.addWidget(hdr)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"background: {C['bg']}; border: none;")

        container = QWidget()
        container.setStyleSheet(f"background: {C['bg']};")
        form = QVBoxLayout(container)
        form.setContentsMargins(32, 24, 32, 32)
        form.setSpacing(24)

        def section(title):
            lbl = QLabel(title)
            lbl.setStyleSheet(f"""
                font-weight: 700; font-size: 16px; color: {C['text']};
                padding-bottom: 4px; border-bottom: 1px solid {C['border']};
            """)
            form.addWidget(lbl)

        def row(label_text, widget, hint=None):
            r = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFixedWidth(200)
            lbl.setStyleSheet(f"color: {C['text']}; font-size: 13px;")
            r.addWidget(lbl)
            r.addWidget(widget, 1)
            form.addLayout(r)
            if hint:
                h = QLabel(hint)
                h.setStyleSheet(f"color: {C['dim']}; font-size: 11px; padding-left: 204px;")
                form.addWidget(h)

        cfg = self._cfg

        # ── General ───────────────────────────────────────────────────────────
        section("General")

        self._sv_theme = QComboBox()
        self._sv_theme.addItems(list(THEMES.keys()))
        self._sv_theme.setCurrentText(cfg.get("theme", "dark"))
        row("Theme", self._sv_theme)

        self._sv_font = QSpinBox()
        self._sv_font.setRange(8, 28)
        self._sv_font.setValue(cfg.get("font_size", 13))
        row("Font Size", self._sv_font)

        self._sv_stream = QCheckBox("Enable streaming responses")
        self._sv_stream.setChecked(cfg.get("streaming", True))
        form.addWidget(self._sv_stream)

        # ── AI Provider ───────────────────────────────────────────────────────
        section("AI Provider")

        info = QFrame()
        info.setStyleSheet(f"background: {C['tag_bg']}; border-radius: 8px; padding: 4px;")
        info_lay = QVBoxLayout(info)
        info_lay.setContentsMargins(12, 8, 12, 8)
        for line in [
            "☁  Backend (default)  — Groq via Vercel server, no key needed",
            "⬡  Local Ollama       — privacy, offline, requires Ollama running",
            "⚡  Groq Direct        — requires your own Groq API key",
            "◈  OpenRouter         — requires your own OpenRouter API key",
        ]:
            lbl = QLabel(line)
            lbl.setStyleSheet(f"color: {C['dim']}; font-size: 12px; font-family: monospace;")
            info_lay.addWidget(lbl)
        form.addWidget(info)

        self._sv_provider = QComboBox()
        self._sv_provider.addItems(["backend", "local", "groq", "openrouter"])
        self._sv_provider.setCurrentText(cfg.get("ai_provider", "backend"))
        row("AI Provider", self._sv_provider, "backend = no setup needed, keys secured on server")

        self._sv_server_url = QLineEdit(cfg.get("vagent_server_url", "https://v-agent.vercel.app"))
        row("Backend URL", self._sv_server_url, "Only change if self-hosting the backend")

        self._sv_ollama_url = QLineEdit(cfg.get("ollama_base_url", "http://localhost:11434"))
        row("Ollama URL", self._sv_ollama_url)

        self._sv_model = QComboBox()
        self._sv_model.addItems(FALLBACK_MODELS)
        self._sv_model.setCurrentText(cfg.get("model", FALLBACK_MODELS[0]))
        self._sv_model.setEditable(True)
        row("Local Model", self._sv_model)

        # ── Cloud keys (optional) ─────────────────────────────────────────────
        section("Cloud API Keys (Optional)")

        key_note = QLabel(
            "⚠  These keys are stored ONLY in your local .env file, never in config.json or GitHub.\n"
            "   Leave blank to use the default backend (no key required).")
        key_note.setStyleSheet(f"color: {C['yellow']}; font-size: 12px; line-height: 1.5;")
        key_note.setWordWrap(True)
        form.addWidget(key_note)

        self._sv_groq_key = QLineEdit()
        self._sv_groq_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._sv_groq_key.setPlaceholderText("gsk_... (leave blank to use backend)")
        row("Groq API Key", self._sv_groq_key, "Get at console.groq.com (free)")

        self._sv_groq_model = QComboBox()
        self._sv_groq_model.addItems([
            "llama-3.3-70b-versatile", "llama-3.1-8b-instant",
            "mixtral-8x7b-32768", "gemma2-9b-it"])
        self._sv_groq_model.setCurrentText(cfg.get("groq_model", "llama-3.3-70b-versatile"))
        row("Groq Model", self._sv_groq_model)

        self._sv_or_key = QLineEdit()
        self._sv_or_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._sv_or_key.setPlaceholderText("sk-or-... (optional)")
        row("OpenRouter API Key", self._sv_or_key, "Only :free models will be used")

        self._sv_or_model = QComboBox()
        self._sv_or_model.addItems([
            "meta-llama/llama-3.2-3b-instruct:free",
            "google/gemini-2.0-flash-exp:free",
            "deepseek/deepseek-r1:free"])
        self._sv_or_model.setCurrentText(cfg.get("openrouter_model", "meta-llama/llama-3.2-3b-instruct:free"))
        row("OpenRouter Model", self._sv_or_model)

        # ── Save ──────────────────────────────────────────────────────────────
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C['border']};")
        form.addWidget(sep)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("  Save Settings  ")
        save_btn.setObjectName("accent")
        save_btn.setFixedHeight(38)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)
        btn_row.addStretch()
        form.addLayout(btn_row)

        form.addStretch()
        scroll.setWidget(container)
        lay.addWidget(scroll, 1)

    def _save(self):
        cfg = self._cfg
        cfg["theme"]             = self._sv_theme.currentText()
        cfg["font_size"]         = self._sv_font.value()
        cfg["streaming"]         = self._sv_stream.isChecked()
        cfg["ai_provider"]       = self._sv_provider.currentText()
        cfg["vagent_server_url"] = self._sv_server_url.text().strip()
        cfg["ollama_base_url"]   = self._sv_ollama_url.text().strip()
        cfg["model"]             = self._sv_model.currentText()
        cfg["groq_model"]        = self._sv_groq_model.currentText()
        cfg["openrouter_model"]  = self._sv_or_model.currentText()

        # Save keys to .env ONLY — never to config.json
        groq_key = self._sv_groq_key.text().strip()
        or_key   = self._sv_or_key.text().strip()
        if groq_key: cfg["groq_api_key"] = groq_key
        if or_key:   cfg["openrouter_api_key"] = or_key
        self._write_env(groq_key, or_key)

        save_cfg(cfg)
        self.settings_saved.emit(cfg)
        QMessageBox.information(self, "Saved", "Settings saved successfully.")

    def _write_env(self, groq_key, or_key):
        """Write API keys to .env ONLY. Never to config.json or committed files."""
        env_path = os.path.join(BASE_DIR, ".env")
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                lines = f.readlines()

        def set_key(lines, key, value):
            for i, line in enumerate(lines):
                if line.strip().startswith(f"{key}="):
                    lines[i] = f"{key}={value}\n"
                    return lines
            lines.append(f"{key}={value}\n")
            return lines

        if groq_key:
            lines = set_key(lines, "GROQ_API_KEY", groq_key)
        if or_key:
            lines = set_key(lines, "OPENROUTER_API_KEY", or_key)

        try:
            with open(env_path, "w") as f:
                f.writelines(lines)
        except Exception as e:
            print(f"[env] {e}")

# ── Automator panel ────────────────────────────────────────────────────────────
class AutomatorPanel(QWidget):
    def __init__(self, cfg, C, parent=None):
        super().__init__(parent)
        self._cfg  = cfg
        self._C    = C
        self._proc = None
        self._build()

    def _build(self):
        C   = self._C
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setFixedHeight(48)
        hdr.setStyleSheet(f"background: {C['panel']}; border-bottom: 1px solid {C['border']};")
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(16, 0, 16, 0)
        title = QLabel("🤖  Automator")
        title.setStyleSheet(f"font-weight: 700; font-size: 14px; color: {C['text']};")
        hdr_lay.addWidget(title)
        lay.addWidget(hdr)

        # Info
        info = QFrame()
        info.setStyleSheet(f"background: {C['panel']}; border-bottom: 1px solid {C['border']};")
        info_lay = QVBoxLayout(info)
        info_lay.setContentsMargins(24, 16, 24, 16)
        for line in [
            "Watches Input/ for scripts. AI fixes bugs and saves corrected versions to Output/.",
            "Supported: .py  .js  .ts  .bat  .ps1  .sh  .cmd",
        ]:
            lbl = QLabel(line)
            lbl.setStyleSheet(f"color: {C['dim']}; font-size: 13px;")
            info_lay.addWidget(lbl)
        lay.addWidget(info)

        # Controls
        ctrl = QFrame()
        ctrl.setStyleSheet(f"background: {C['bg']};")
        ctrl_lay = QHBoxLayout(ctrl)
        ctrl_lay.setContentsMargins(24, 12, 24, 12)
        ctrl_lay.setSpacing(8)

        self._start_btn = QPushButton("▶  Start Watching")
        self._start_btn.setObjectName("accent")
        self._start_btn.setFixedHeight(36)
        self._start_btn.clicked.connect(self._start)
        ctrl_lay.addWidget(self._start_btn)

        self._stop_btn = QPushButton("■  Stop")
        self._stop_btn.setObjectName("danger")
        self._stop_btn.setFixedHeight(36)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop)
        ctrl_lay.addWidget(self._stop_btn)
        ctrl_lay.addStretch()
        lay.addWidget(ctrl)

        # Log
        log_hdr = QLabel("  Log")
        log_hdr.setFixedHeight(28)
        log_hdr.setStyleSheet(f"background: {C['panel']}; color: {C['dim']}; font-size: 12px; border-top: 1px solid {C['border']};")
        lay.addWidget(log_hdr)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Cascadia Code", 11))
        self._log.setStyleSheet(f"""
            QTextEdit {{
                background: {C['bg']}; color: {C['green']};
                border: none; padding: 12px 16px;
            }}
        """)
        lay.addWidget(self._log, 1)
        self._log_write("Automator ready — press ▶ to begin watching Input/")

    def _log_write(self, msg):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._log.append(f"[{ts}]  {msg}")

    def _start(self):
        a = os.path.join(BASE_DIR, "automator.py")
        if not os.path.exists(a):
            QMessageBox.critical(self, "Error", f"automator.py not found:\n{a}")
            return
        os.makedirs(INPUT_DIR, exist_ok=True)
        os.makedirs(OUT_DIR, exist_ok=True)
        try:
            self._proc = subprocess.Popen(
                [sys.executable, a], cwd=BASE_DIR,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1)
            self._start_btn.setEnabled(False)
            self._stop_btn.setEnabled(True)
            self._log_write(f"Started (PID {self._proc.pid}) — watching: {INPUT_DIR}")
            threading.Thread(target=self._read, daemon=True).start()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _stop(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._log_write("Stopped.")

    def _read(self):
        for line in self._proc.stdout:
            line = line.rstrip()
            if line:
                # Thread-safe GUI update
                QTimer.singleShot(0, lambda l=line: self._log_write(l))
        QTimer.singleShot(0, self._stop)

# ── Ollama status checker ──────────────────────────────────────────────────────
class OllamaChecker(QThread):
    status_changed = Signal(bool)

    def __init__(self, url):
        super().__init__()
        self._url = url
        self._running = True

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

    def stop(self):
        self._running = False

# ── Main window ───────────────────────────────────────────────────────────────
class VAgentWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg    = load_cfg()
        self.C      = THEMES.get(self.cfg.get("theme", "dark"), THEMES["dark"])
        self._mode  = "chat"

        self.setWindowTitle(f"V-Agent v{VERSION}  ·  Voidtune")
        self.resize(1440, 880)
        self._center()

        self._apply_stylesheet()
        self._build()
        self._start_ollama_checker()

    def _center(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width()  - 1440) // 2
        y = (screen.height() -  880) // 2
        self.move(max(0, x), max(0, y))

    def _apply_stylesheet(self):
        self.setStyleSheet(make_stylesheet(self.C))

    def _build(self):
        C = self.C

        # ── Central widget ────────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        root_lay = QVBoxLayout(central)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # ── Top bar ───────────────────────────────────────────────────────────
        topbar = QFrame()
        topbar.setFixedHeight(42)
        topbar.setStyleSheet(f"""
            QFrame {{
                background: {C['panel']};
                border-bottom: 1px solid {C['border']};
            }}
        """)
        tb_lay = QHBoxLayout(topbar)
        tb_lay.setContentsMargins(12, 0, 12, 0)
        tb_lay.setSpacing(0)

        # App badge
        badge = QLabel("  VA  ")
        badge.setStyleSheet(f"""
            background: {C['accent']}; color: #FFFFFF;
            font-weight: 800; font-size: 11px;
            border-radius: 4px; padding: 2px 6px;
            letter-spacing: 1px;
        """)
        tb_lay.addWidget(badge)

        app_name = QLabel("  V-Agent")
        app_name.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {C['text']}; padding-right: 16px;")
        tb_lay.addWidget(app_name)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {C['border']};")
        sep.setFixedHeight(20)
        tb_lay.addWidget(sep)

        # Mode buttons
        self._mode_btns = {}
        for mode, label in [("chat", "Chat"), ("ide", "</>  IDE")]:
            btn = QPushButton(label)
            btn.setFixedHeight(42)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C['dim']};
                    border: none; border-bottom: 2px solid transparent;
                    padding: 0 16px; font-size: 13px;
                }}
                QPushButton:hover {{ color: {C['text']}; }}
            """)
            btn.clicked.connect(lambda _, m=mode: self._set_mode(m))
            tb_lay.addWidget(btn)
            self._mode_btns[mode] = btn

        tb_lay.addStretch()

        # Version
        ver = QLabel(f"v{VERSION}")
        ver.setStyleSheet(f"color: {C['dim']}; font-size: 11px; padding-right: 8px;")
        tb_lay.addWidget(ver)

        # Ollama status dot
        self._status_dot = QLabel("○")
        self._status_dot.setStyleSheet(f"color: {C['dim']}; font-size: 14px; padding-right: 4px;")
        tb_lay.addWidget(self._status_dot)

        # Theme toggle
        theme_btn = QPushButton("◑")
        theme_btn.setFixedSize(34, 34)
        theme_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C['dim']};
                border: none; font-size: 16px; border-radius: 4px;
            }}
            QPushButton:hover {{ background: {C['hover']}; color: {C['text']}; }}
        """)
        theme_btn.clicked.connect(self._toggle_theme)
        tb_lay.addWidget(theme_btn)

        root_lay.addWidget(topbar)

        # ── Body ──────────────────────────────────────────────────────────────
        body = QFrame()
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        # ── Sidebar nav ───────────────────────────────────────────────────────
        nav = QFrame()
        nav.setFixedWidth(48)
        nav.setStyleSheet(f"background: {C['sidebar']}; border-right: 1px solid {C['border']};")
        nav_lay = QVBoxLayout(nav)
        nav_lay.setContentsMargins(0, 8, 0, 8)
        nav_lay.setSpacing(2)

        self._nav_btns = {}
        self._nav_inds = {}
        for name, icon in [
            ("terminal", "⬛"),
            ("settings", "⚙"),
            ("automator", "🤖"),
        ]:
            row = QFrame()
            row.setStyleSheet("background: transparent;")
            row_lay = QHBoxLayout(row)
            row_lay.setContentsMargins(0, 0, 0, 0)
            row_lay.setSpacing(0)

            ind = QFrame()
            ind.setFixedWidth(3)
            ind.setStyleSheet(f"background: transparent; border-radius: 1px;")
            row_lay.addWidget(ind)

            btn = QPushButton(icon)
            btn.setFixedSize(45, 42)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C['dim']};
                    border: none; font-size: 18px; border-radius: 4px;
                }}
                QPushButton:hover {{ background: {C['hover']}; color: {C['text']}; }}
            """)
            btn.clicked.connect(lambda _, v=name: self._show_view(v))
            row_lay.addWidget(btn)

            nav_lay.addWidget(row)
            self._nav_btns[name] = btn
            self._nav_inds[name] = ind

        nav_lay.addStretch()
        body_lay.addWidget(nav)

        # ── Content stack ─────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        body_lay.addWidget(self._stack, 1)

        # Build views
        self._terminal  = TerminalPanel(self.cfg, C)
        self._settings  = SettingsPanel(self.cfg, C)
        self._automator = AutomatorPanel(self.cfg, C)
        self._settings.settings_saved.connect(self._on_settings_saved)

        # IDE with splitter (explorer + editor + chat)
        ide_widget = QWidget()
        ide_widget.setStyleSheet(f"background: {C['bg']};")
        ide_lay = QHBoxLayout(ide_widget)
        ide_lay.setContentsMargins(0, 0, 0, 0)
        ide_lay.setSpacing(0)

        ide_splitter = QSplitter(Qt.Orientation.Horizontal)
        ide_splitter.setHandleWidth(1)
        ide_splitter.setStyleSheet(f"QSplitter::handle {{ background: {C['border']}; }}")

        self._explorer = FileExplorer(C)
        self._explorer.setMinimumWidth(160)
        self._explorer.setMaximumWidth(320)
        self._explorer.file_opened.connect(self._on_file_open)
        ide_splitter.addWidget(self._explorer)

        self._editor = IDEPanel(self.cfg, C)
        ide_splitter.addWidget(self._editor)

        self._chat_panel = AIChatPanel(self.cfg, C)
        self._chat_panel.setMinimumWidth(280)
        ide_splitter.addWidget(self._chat_panel)

        ide_splitter.setSizes([220, 700, 340])
        ide_lay.addWidget(ide_splitter)

        # Chat-only view (terminal mode)
        chat_widget = QWidget()
        chat_widget.setStyleSheet(f"background: {C['bg']};")
        chat_lay = QHBoxLayout(chat_widget)
        chat_lay.setContentsMargins(0, 0, 0, 0)
        chat_lay.setSpacing(0)
        self._chat_main = AIChatPanel(self.cfg, C)
        chat_lay.addWidget(self._chat_main)

        # Add to stack
        self._stack.addWidget(chat_widget)   # 0 = chat
        self._stack.addWidget(self._terminal) # via nav
        self._stack.addWidget(self._settings) # via nav
        self._stack.addWidget(self._automator)# via nav
        self._stack.addWidget(ide_widget)     # via IDE mode btn

        self._view_map = {
            "terminal":  self._terminal,
            "settings":  self._settings,
            "automator": self._automator,
        }

        root_lay.addWidget(body, 1)

        # ── Status bar ────────────────────────────────────────────────────────
        status = QStatusBar()
        status.setStyleSheet(f"background: {C['panel']}; border-top: 1px solid {C['border']};")
        self.setStatusBar(status)
        self._status_msg = QLabel(f"Ready  ·  {platform.system()}")
        self._status_msg.setStyleSheet(f"color: {C['dim']}; font-size: 11px; padding: 0 8px;")
        status.addWidget(self._status_msg)

        # Init mode
        self._set_mode("chat")
        self._update_nav("terminal")

    def _set_mode(self, mode):
        self._mode = mode
        for m, btn in self._mode_btns.items():
            active = m == mode
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {'#' + 'E6EDF3' if active else self.C['dim'][1:]};
                    border: none;
                    border-bottom: 2px solid {'#2F81F7' if active else 'transparent'};
                    padding: 0 16px; font-size: 13px;
                }}
                QPushButton:hover {{ color: {self.C['text']}; }}
            """)
        if mode == "ide":
            self._stack.setCurrentIndex(4)
        else:
            self._stack.setCurrentIndex(0)

    def _show_view(self, name):
        widget = self._view_map.get(name)
        if widget:
            idx = self._stack.indexOf(widget)
            if idx >= 0:
                self._stack.setCurrentIndex(idx)
        self._update_nav(name)
        if self._mode != "chat":
            self._set_mode("chat")

    def _update_nav(self, active_name):
        C = self.C
        for name, btn in self._nav_btns.items():
            active = name == active_name
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {C['text'] if active else C['dim']};
                    border: none; font-size: 18px; border-radius: 4px;
                }}
                QPushButton:hover {{ background: {C['hover']}; color: {C['text']}; }}
            """)
            ind = self._nav_inds.get(name)
            if ind:
                ind.setStyleSheet(f"background: {C['accent'] if active else 'transparent'}; border-radius: 1px;")

    def _on_file_open(self, path):
        self._editor.open_file(path)

    def _on_settings_saved(self, cfg):
        self.cfg = cfg
        new_theme = cfg.get("theme", "dark")
        if new_theme != self.cfg.get("theme", "dark"):
            self.C = THEMES.get(new_theme, THEMES["dark"])
            self._apply_stylesheet()
        self._chat_main.reload_config(cfg)
        self._chat_panel.reload_config(cfg)

    def _toggle_theme(self):
        keys  = list(THEMES.keys())
        cur   = self.cfg.get("theme", "dark")
        nxt   = keys[(keys.index(cur) + 1) % len(keys)]
        self.cfg["theme"] = nxt
        self.C = THEMES[nxt]
        save_cfg(self.cfg)
        self._apply_stylesheet()

    def _start_ollama_checker(self):
        url = self.cfg.get("ollama_base_url", "http://localhost:11434")
        self._ollama = OllamaChecker(url)
        self._ollama.status_changed.connect(self._on_ollama_status)
        self._ollama.start()

    def _on_ollama_status(self, ok):
        self._status_dot.setText("●" if ok else "○")
        self._status_dot.setStyleSheet(
            f"color: {self.C['green'] if ok else self.C['dim']}; font-size: 14px; padding-right: 4px;")

    def closeEvent(self, event):
        if hasattr(self, "_ollama"):
            self._ollama.stop()
        event.accept()

# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    # Hi-DPI support
    if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("V-Agent")
    app.setApplicationVersion(VERSION)

    window = VAgentWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
