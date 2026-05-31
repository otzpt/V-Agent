#!/usr/bin/env python3
"""V-Agent v1.0 — Professional Agentic IDE · Voidtune Ecosystem"""

import os, sys, json, threading, subprocess, datetime, random, re, platform

# ── Tkinter check ──────────────────────────────────────────────────────────────
try:
    import tkinter as tk
    from tkinter import font as tkfont, ttk, messagebox, filedialog, simpledialog
except ImportError:
    print("ERROR: tkinter not found.")
    print("Install Python from https://python.org (NOT the Microsoft Store version).")
    input("Press Enter to exit...")
    sys.exit(1)

# ── Dependency check ───────────────────────────────────────────────────────────
try:
    import requests
except ImportError:
    root = tk.Tk(); root.withdraw()
    answer = messagebox.askyesno(
        "Missing dependency",
        "The 'requests' library is not installed.\n\n"
        "Install it now?\n\n"
        "  pip install requests",
        parent=root)
    if answer:
        import subprocess as _sp
        _sp.run([sys.executable, "-m", "pip", "install", "requests"], check=True)
        messagebox.showinfo("Done", "Installed! Please restart V-Agent.", parent=root)
    root.destroy()
    sys.exit(0)

VERSION   = "1.0"
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
CFG_PATH  = os.path.join(BASE_DIR, "config.json")
INPUT_DIR = os.path.join(BASE_DIR, "Input")
OUT_DIR   = os.path.join(BASE_DIR, "Output")

DEFAULT_CFG = {
    "model":              "qwen2.5-coder:14b",
    "theme":              "dark",
    "ollama_base_url":    "http://localhost:11434",
    "streaming":          True,
    "font_size":          12,
    # Cloud AI
    "ai_provider":        "local",   # local | groq | openrouter
    "groq_api_key":       "",
    "groq_model":         "llama-3.3-70b-versatile",
    "openrouter_api_key": "",
    "openrouter_model":   "meta-llama/llama-3.2-3b-instruct:free",
}

FALLBACK_MODELS = [
    "qwen2.5-coder:14b","qwen2.5-coder:7b","deepseek-coder-v2:16b",
    "codellama:13b","granite-code:8b","llama3.1:8b",
]

# ── Themes ─────────────────────────────────────────────────────────────────────
THEMES = {
    # ── VS Code Dark Modern ────────────────────────────────────────────────
    "dark": {
        "bg":          "#1F1F1F",   # editor.background
        "panel":       "#181818",   # sideBar / activityBar / statusBar
        "sidebar":     "#181818",
        "border":      "#2B2B2B",   # tab.border
        "text":        "#CCCCCC",   # editor.foreground
        "dim":         "#6E7681",   # editorLineNumber.foreground
        "text_active": "#FFFFFF",   # tab.activeForeground
        "text_dim":    "#9D9D9D",   # tab.inactiveForeground
        "accent":      "#0078D4",   # focusBorder / activeBorder
        "blue":        "#9CDCFE",
        "cyan":        "#4FC1FF",
        "green":       "#4EC994",
        "yellow":      "#DCDCAA",
        "red":         "#F44747",
        "orange":      "#CE9178",
        "purple":      "#C586C0",
        "selection":   "#264F78",
        "line_hl":     "#282828",
        "hover":       "#2A2D2E",
        "code_bg":     "#1F1F1F",
        "ln_fg":       "#6E7681",
        "ln_active":   "#CCCCCC",
        "tabbg":       "#181818",
        "tabactive":   "#1F1F1F",
        "tabline":     "#0078D4",
        "statusbar":   "#181818",
        "statusfg":    "#CCCCCC",
        "actbar":      "#181818",
        "actbar_fg":   "#D7D7D7",
        "actbar_dim":  "#868686",
        "actborder":   "#0078D4",
        "find_bg":     "#313131",
        "input_bg":    "#313131",
        "button_bg":   "#0078D4",
        "button_fg":   "#FFFFFF",
        "list_sel":    "#04395E",
        "list_hover":  "#2A2D2E",
        "chat_bg":     "#252526",
        "apply_bg":    "#1B3A1B",
        "apply_fg":    "#4EC994",
        "copy_fg":     "#9CDCFE",
        "user":        "#9CDCFE",
        "assistant":   "#B5CEA8",
        "prompt":      "#CCCCCC",
        "separator":   "#3C3C3C",
    },
    # ── VS Code Light Modern ───────────────────────────────────────────────
    "light": {
        "bg":          "#FFFFFF",   # editor.background
        "panel":       "#F8F8F8",   # sideBar
        "sidebar":     "#F8F8F8",
        "border":      "#E5E5E5",
        "text":        "#3B3B3B",
        "dim":         "#8A8A8A",
        "text_active": "#3B3B3B",
        "text_dim":    "#868686",
        "accent":      "#005FB8",
        "blue":        "#0070C1",
        "cyan":        "#0070C1",
        "green":       "#008000",
        "yellow":      "#795E26",
        "red":         "#D32F2F",
        "orange":      "#A31515",
        "purple":      "#AF00DB",
        "selection":   "#ADD6FF",
        "line_hl":     "#F5F5F5",
        "hover":       "#F2F2F2",
        "code_bg":     "#F5F5F5",
        "ln_fg":       "#999999",
        "ln_active":   "#3B3B3B",
        "tabbg":       "#F8F8F8",
        "tabactive":   "#FFFFFF",
        "tabline":     "#005FB8",
        "statusbar":   "#F8F8F8",
        "statusfg":    "#3B3B3B",
        "actbar":      "#F8F8F8",
        "actbar_fg":   "#1F1F1F",
        "actbar_dim":  "#616161",
        "actborder":   "#005FB8",
        "find_bg":     "#FFFFFF",
        "input_bg":    "#FFFFFF",
        "button_bg":   "#005FB8",
        "button_fg":   "#FFFFFF",
        "list_sel":    "#E8E8E8",
        "list_hover":  "#F2F2F2",
        "chat_bg":     "#F3F3F3",
        "apply_bg":    "#E6F3E6",
        "apply_fg":    "#1E8A1E",
        "copy_fg":     "#005FB8",
        "user":        "#005FB8",
        "assistant":   "#1E8A1E",
        "prompt":      "#3B3B3B",
        "separator":   "#E0E0E0",
    },
}
# ── Language maps ──────────────────────────────────────────────────────────────
LANG_EXT = {
    ".py":"python",".pyw":"python",
    ".js":"javascript",".jsx":"javascript",".mjs":"javascript",
    ".ts":"typescript",".tsx":"typescript",
    ".html":"html",".htm":"html",".jinja":"html",".j2":"html",
    ".xml":"xml",
    ".css":"css",".scss":"css",".less":"css",
    ".json":"json",".jsonc":"json",
    ".sh":"bash",".bash":"bash",".zsh":"bash",
    ".bat":"batch",".cmd":"batch",".ps1":"powershell",
    ".md":"markdown",".mdx":"markdown",
    ".c":"c",".h":"c",
    ".cpp":"cpp",".cxx":"cpp",".cc":"cpp",".hpp":"cpp",
    ".rs":"rust",".go":"go",".rb":"ruby",".php":"php",
    ".java":"java",".kt":"kotlin",".swift":"swift",
    ".sql":"sql",".yaml":"yaml",".yml":"yaml",".toml":"toml",
    ".txt":"text",".env":"text",".gitignore":"text",
}

FILE_ICONS = {
    ".py":"🐍",".pyw":"🐍",
    ".js":"🟨",".jsx":"⚛",".mjs":"🟨",".ts":"🔷",".tsx":"⚛",
    ".html":"🌐",".htm":"🌐",".xml":"📋",
    ".css":"🎨",".scss":"🎨",".less":"🎨",
    ".json":"{}",".jsonc":"{}",
    ".md":"📝",".mdx":"📝",".txt":"📄",
    ".sh":"⚙",".bash":"⚙",".zsh":"⚙",".bat":"⚙",".cmd":"⚙",".ps1":"⚙",
    ".c":"⚡",".h":"⚡",".cpp":"⚡",".cxx":"⚡",".hpp":"⚡",
    ".rs":"🦀",".go":"🐹",".rb":"💎",".php":"🐘",".java":"☕",
    ".kt":"🟣",".swift":"🦅",".sql":"🗄",".yaml":"📐",".yml":"📐",
    ".toml":"⚙",".env":"🔑",".gitignore":"🔍",
}

LANG_DISPLAY = {
    "python":"Python","javascript":"JavaScript","typescript":"TypeScript",
    "html":"HTML","xml":"XML","css":"CSS","json":"JSON","bash":"Shell",
    "batch":"Batch","powershell":"PowerShell","markdown":"Markdown",
    "c":"C","cpp":"C++","rust":"Rust","go":"Go","ruby":"Ruby","php":"PHP",
    "java":"Java","kotlin":"Kotlin","swift":"Swift","sql":"SQL",
    "yaml":"YAML","toml":"TOML","text":"Plain Text",
}

# ── Syntax highlighting rules (VS Code Dark+ palette) ──────────────────────────
SYNTAX = {
    "python": [
        ("kw",    "#c586c0", r'\b(False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)\b'),
        ("bi",    "#9cdcfe", r'\b(print|len|range|type|int|str|float|list|dict|set|tuple|bool|open|super|self|cls|input|enumerate|zip|map|filter|sorted|reversed|any|all|min|max|sum|abs|round|isinstance|hasattr|getattr|setattr|property|staticmethod|classmethod|vars|dir|id|hash|repr|chr|ord|hex|bin|oct)\b'),
        ("st",    "#ce9178", r'(\'\'\'[\s\S]*?\'\'\'|"""[\s\S]*?"""|f\'(?:[^\'\\]|\\.)*\'|f"(?:[^"\\]|\\.)*"|r\'[^\']*\'|r"[^"]*"|b\'[^\']*\'|b"[^"]*"|\'(?:[^\'\\]|\\.)*\'|"(?:[^"\\]|\\.)*")'),
        ("cm",    "#6a9955", r'#[^\n]*'),
        ("nm",    "#b5cea8", r'\b(?:0x[0-9a-fA-F]+|0o[0-7]+|0b[01]+|\d+\.?\d*(?:[eE][+-]?\d+)?j?)\b'),
        ("dc",    "#c6a0f6", r'@[\w.]+'),
        ("fn",    "#dcdcaa", r'(?<=def )\w+'),
        ("cl",    "#4ec9b0", r'(?<=class )\w+'),
        ("mg",    "#569cd6", r'\b(__\w+__)\b'),
    ],
    "javascript": [
        ("kw",    "#c586c0", r'\b(async|await|break|case|catch|class|const|continue|debugger|default|delete|do|else|export|extends|finally|for|from|function|if|import|in|instanceof|let|new|of|return|static|super|switch|this|throw|try|typeof|var|void|while|with|yield)\b'),
        ("bi",    "#9cdcfe", r'\b(console|window|document|Array|Object|String|Number|Boolean|Symbol|Promise|Math|JSON|Date|RegExp|Error|Map|Set|WeakMap|WeakSet|Proxy|Reflect|undefined|null|true|false|NaN|Infinity|require|module|exports|__dirname|__filename)\b'),
        ("st",    "#ce9178", r'(`[^`]*`|\'(?:[^\'\\]|\\.)*\'|"(?:[^"\\]|\\.)*")'),
        ("cm",    "#6a9955", r'(//[^\n]*|/\*[\s\S]*?\*/)'),
        ("nm",    "#b5cea8", r'\b(?:0x[0-9a-fA-F]+|\d+\.?\d*(?:[eE][+-]?\d+)?n?)\b'),
        ("fn",    "#dcdcaa", r'\b\w+(?=\s*\()'),
        ("kw2",   "#569cd6", r'\b(get|set|from|of|as|abstract|declare|enum|implements|interface|namespace|override|private|protected|public|readonly|type)\b'),
    ],
    "typescript": [
        ("kw",    "#c586c0", r'\b(async|await|break|case|catch|class|const|continue|do|else|export|extends|finally|for|from|function|if|implements|import|in|instanceof|interface|let|namespace|new|of|return|static|super|switch|this|throw|try|type|typeof|var|void|while|yield)\b'),
        ("ty",    "#4ec9b0", r'\b(any|boolean|never|number|object|string|symbol|undefined|unknown|void|null|true|false|Array|Record|Partial|Required|Readonly|Pick|Omit|Exclude|Extract|NonNullable|ReturnType|InstanceType|Parameters|ConstructorParameters)\b'),
        ("st",    "#ce9178", r'(`[^`]*`|\'(?:[^\'\\]|\\.)*\'|"(?:[^"\\]|\\.)*")'),
        ("cm",    "#6a9955", r'(//[^\n]*|/\*[\s\S]*?\*/)'),
        ("nm",    "#b5cea8", r'\b\d+\.?\d*\b'),
        ("fn",    "#dcdcaa", r'\b\w+(?=\s*[<(])'),
        ("dc",    "#c6a0f6", r'@[\w.]+'),
    ],
    "html": [
        ("tg",    "#4ec9b0", r'</?\b[a-zA-Z][a-zA-Z0-9-]*\b'),
        ("at",    "#9cdcfe", r'\b[a-zA-Z][a-zA-Z0-9-]*(?=\s*=)'),
        ("st",    "#ce9178", r'"[^"]*"'),
        ("cm",    "#6a9955", r'<!--[\s\S]*?-->'),
        ("dt",    "#808080", r'<!DOCTYPE[^>]*>'),
        ("ev",    "#c586c0", r'\bon\w+(?=\s*=)'),
    ],
    "css": [
        ("sl",    "#d7ba7d", r'[.#:*>+~]?[a-zA-Z][a-zA-Z0-9_-]*(?:\s*[.#:[\]>+~,])?'),
        ("pr",    "#9cdcfe", r'(?<=:?\s)\b[a-z][a-z-]+(?=\s*:)|\b[a-z-]+(?=\s*:)'),
        ("st",    "#ce9178", r'"[^"]*"|\'[^\']*\''),
        ("cm",    "#6a9955", r'/\*[\s\S]*?\*/'),
        ("nm",    "#b5cea8", r'\b\d+\.?\d*(?:px|em|rem|%|vh|vw|vmin|vmax|pt|cm|mm|in|ex|ch|fr|deg|rad|turn|s|ms)?\b'),
        ("co",    "#ce9178", r'(?:#[0-9a-fA-F]{3,8}|rgba?\([^)]+\)|hsla?\([^)]+\))\b'),
        ("var",   "#c6a0f6", r'--[\w-]+|var\(--[\w-]+\)'),
    ],
    "json": [
        ("ky",    "#9cdcfe", r'"(?:[^"\\]|\\.)*"(?=\s*:)'),
        ("st",    "#ce9178", r'(?<=:\s*)"(?:[^"\\]|\\.)*"|(?<=\[)"(?:[^"\\]|\\.)*"'),
        ("kw",    "#569cd6", r'\b(true|false|null)\b'),
        ("nm",    "#b5cea8", r'-?\b\d+\.?\d*(?:[eE][+-]?\d+)?\b'),
    ],
    "bash": [
        ("kw",    "#c586c0", r'\b(if|then|else|elif|fi|for|while|until|do|done|case|esac|in|function|return|local|export|readonly|declare|typeset|unset|shift|source|alias|echo|printf|read|exit|trap|wait|exec|eval|set|unset|true|false|test|cd|ls|rm|mv|cp|mkdir|rmdir|chmod|chown|find|grep|sed|awk|sort|uniq|head|tail|cat|less|more|curl|wget|ssh|scp|git)\b'),
        ("st",    "#ce9178", r'\'[^\']*\'|"(?:[^"\\]|\\.)*"'),
        ("cm",    "#6a9955", r'#[^\n]*'),
        ("vr",    "#9cdcfe", r'\$\{?[\w@#?$!*-]+\}?|\$\([^)]+\)'),
        ("nm",    "#b5cea8", r'\b\d+\b'),
        ("sh",    "#4ec9b0", r'^\s*[\w/.-]+(?=\s)'),
    ],
    "batch": [
        ("kw",    "#c586c0", r'(?i)\b(echo|set|if|else|for|call|goto|exit|rem|pause|mkdir|rmdir|del|copy|move|cd|dir|start|cls|endlocal|setlocal|defined|not|equ|neq|lss|leq|gtr|geq|exist|errorlevel)\b'),
        ("st",    "#ce9178", r'"[^"]*"'),
        ("cm",    "#6a9955", r'(?i)(^rem\b[^\n]*|::[^\n]*)'),
        ("vr",    "#9cdcfe", r'%\w+%|!\w+!|%~[fdpnxsatz]+\d?'),
        ("lb",    "#dcdcaa", r'^:[^\s:][^\n]*'),
    ],
    "c": [
        ("kw",    "#c586c0", r'\b(auto|break|case|char|const|continue|default|do|double|else|enum|extern|float|for|goto|if|inline|int|long|register|restrict|return|short|signed|sizeof|static|struct|switch|typedef|union|unsigned|void|volatile|while)\b'),
        ("pp",    "#9b9b9b", r'#\s*(?:include|define|undef|ifdef|ifndef|endif|if|elif|else|pragma|error|warning)\b[^\n]*'),
        ("st",    "#ce9178", r'"[^"]*"|\'[^\']*\''),
        ("cm",    "#6a9955", r'(//[^\n]*|/\*[\s\S]*?\*/)'),
        ("nm",    "#b5cea8", r'\b(?:0x[0-9a-fA-F]+[uUlL]*|0[0-7]+[uUlL]*|\d+\.?\d*(?:[eE][+-]?\d+)?[fFlLuU]*)\b'),
        ("ty",    "#4ec9b0", r'\b(int|char|float|double|long|short|unsigned|signed|void|bool|size_t|uint8_t|uint16_t|uint32_t|uint64_t|int8_t|int16_t|int32_t|int64_t)\b'),
    ],
    "cpp": [
        ("kw",    "#c586c0", r'\b(alignas|alignof|and|and_eq|asm|auto|bitand|bitor|bool|break|case|catch|char|char8_t|char16_t|char32_t|class|compl|concept|const|consteval|constexpr|constinit|const_cast|continue|co_await|co_return|co_yield|decltype|default|delete|do|double|dynamic_cast|else|enum|explicit|export|extern|false|float|for|friend|goto|if|inline|int|long|mutable|namespace|new|noexcept|not|not_eq|nullptr|operator|or|or_eq|private|protected|public|register|reinterpret_cast|requires|return|short|signed|sizeof|static|static_assert|static_cast|struct|switch|template|this|thread_local|throw|true|try|typedef|typeid|typename|union|unsigned|using|virtual|void|volatile|wchar_t|while|xor|xor_eq|override|final)\b'),
        ("pp",    "#9b9b9b", r'#\s*(?:include|define|undef|ifdef|ifndef|endif|if|elif|else|pragma|error|warning)\b[^\n]*'),
        ("st",    "#ce9178", r'"[^"]*"|\'[^\']*\'|R"[^(]*\([\s\S]*?\)[^"]*"'),
        ("cm",    "#6a9955", r'(//[^\n]*|/\*[\s\S]*?\*/)'),
        ("nm",    "#b5cea8", r'\b(?:0x[0-9a-fA-F]+[uUlL]*|\d+\.?\d*(?:[eE][+-]?\d+)?[fFlLuU]*)\b'),
        ("ty",    "#4ec9b0", r'\b(int|char|float|double|long|short|unsigned|signed|void|bool|auto|string|vector|map|set|pair|tuple|array|deque|list|queue|stack|size_t|nullptr_t)\b'),
    ],
    "rust": [
        ("kw",    "#c586c0", r'\b(as|async|await|break|const|continue|crate|dyn|else|enum|extern|false|fn|for|if|impl|in|let|loop|match|mod|move|mut|pub|ref|return|self|Self|static|struct|super|trait|true|type|unsafe|use|where|while|abstract|become|box|do|final|macro|override|priv|try|typeof|unsized|virtual|yield)\b'),
        ("ty",    "#4ec9b0", r'\b(bool|char|f32|f64|i8|i16|i32|i64|i128|isize|str|u8|u16|u32|u64|u128|usize|String|Vec|Option|Result|Box|Rc|Arc|Cell|RefCell|Mutex|RwLock|HashMap|HashSet|BTreeMap|BTreeSet)\b'),
        ("st",    "#ce9178", r'"(?:[^"\\]|\\.)*"|b"(?:[^"\\]|\\.)*"|r#*"[^"]*"#*|\'(?:[^\'\\]|\\.)*\''),
        ("cm",    "#6a9955", r'(//[^\n]*|/\*[\s\S]*?\*/)'),
        ("nm",    "#b5cea8", r'\b(?:0x[0-9a-fA-F_]+|0o[0-7_]+|0b[01_]+|\d[\d_]*\.?[\d_]*(?:[eE][+-]?[\d_]+)?(?:f32|f64|u8|u16|u32|u64|i8|i16|i32|i64|usize|isize)?)\b'),
        ("dc",    "#c6a0f6", r'#\[[\s\S]*?\]'),
        ("lf",    "#dcdcaa", r"'[a-zA-Z_]\w*"),
    ],
    "go": [
        ("kw",    "#c586c0", r'\b(break|case|chan|const|continue|default|defer|else|fallthrough|for|func|go|goto|if|import|interface|map|package|range|return|select|struct|switch|type|var)\b'),
        ("bi",    "#9cdcfe", r'\b(append|cap|close|complex|copy|delete|imag|len|make|new|panic|print|println|real|recover)\b'),
        ("ty",    "#4ec9b0", r'\b(bool|byte|complex64|complex128|error|float32|float64|int|int8|int16|int32|int64|rune|string|uint|uint8|uint16|uint32|uint64|uintptr)\b'),
        ("st",    "#ce9178", r'`[^`]*`|"(?:[^"\\]|\\.)*"'),
        ("cm",    "#6a9955", r'(//[^\n]*|/\*[\s\S]*?\*/)'),
        ("nm",    "#b5cea8", r'\b(?:0x[0-9a-fA-F]+|\d+\.?\d*)\b'),
    ],
    "sql": [
        ("kw",    "#c586c0", r'(?i)\b(SELECT|FROM|WHERE|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|DROP|ALTER|TABLE|INDEX|VIEW|DATABASE|SCHEMA|JOIN|LEFT|RIGHT|INNER|OUTER|FULL|CROSS|ON|AS|AND|OR|NOT|NULL|IS|IN|LIKE|BETWEEN|EXISTS|HAVING|GROUP|BY|ORDER|LIMIT|OFFSET|UNION|ALL|DISTINCT|CASE|WHEN|THEN|ELSE|END|IF|BEGIN|COMMIT|ROLLBACK|TRANSACTION|CONSTRAINT|PRIMARY|KEY|FOREIGN|REFERENCES|UNIQUE|CHECK|DEFAULT|AUTO_INCREMENT|SERIAL|CASCADE|RESTRICT|WITH|RETURNS|FUNCTION|PROCEDURE|TRIGGER|DECLARE)\b'),
        ("ty",    "#4ec9b0", r'(?i)\b(INT|INTEGER|BIGINT|SMALLINT|TINYINT|FLOAT|DOUBLE|DECIMAL|NUMERIC|CHAR|VARCHAR|TEXT|BLOB|BOOLEAN|BOOL|DATE|TIME|DATETIME|TIMESTAMP|UUID|JSON|JSONB|ARRAY)\b'),
        ("st",    "#ce9178", r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\""),
        ("cm",    "#6a9955", r'(--[^\n]*|/\*[\s\S]*?\*/)'),
        ("nm",    "#b5cea8", r'\b\d+\.?\d*\b'),
    ],
    "markdown": [
        ("h1",    "#dcdcaa", r'^# .+$'),
        ("h2",    "#dcdcaa", r'^## .+$'),
        ("h3",    "#4ec9b0", r'^### .+$'),
        ("bd",    "#d4d4d4", r'\*\*[^*]+\*\*|__[^_]+__'),
        ("it",    "#ce9178", r'\*[^*]+\*|_[^_]+_'),
        ("cd",    "#ce9178", r'`[^`]+`'),
        ("lk",    "#73d0ff", r'\[([^\]]+)\]\(([^)]+)\)'),
        ("bl",    "#9cdcfe", r'^\s*[-*+] .+$'),
        ("fc",    "#6a9955", r'^```[\s\S]*?```'),
        ("qt",    "#6a9955", r'^> .+$'),
    ],
    "yaml": [
        ("ky",    "#9cdcfe", r'^[\s-]*[\w.-]+(?=\s*:)'),
        ("st",    "#ce9178", r'"(?:[^"\\]|\\.)*"|\'[^\']*\''),
        ("cm",    "#6a9955", r'#[^\n]*'),
        ("nm",    "#b5cea8", r'\b\d+\.?\d*\b'),
        ("kw",    "#c586c0", r'\b(true|false|null|yes|no|on|off)\b'),
        ("an",    "#c6a0f6", r'&\w+|\*\w+|!!\w+'),
    ],
    "toml": [
        ("sc",    "#4ec9b0", r'^\s*\[+[^\]]*\]+'),
        ("ky",    "#9cdcfe", r'^\s*[\w.-]+(?=\s*=)'),
        ("st",    "#ce9178", r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:[^"\\]|\\.)*"|\'[^\']*\''),
        ("cm",    "#6a9955", r'#[^\n]*'),
        ("nm",    "#b5cea8", r'\b\d+\.?\d*\b'),
        ("kw",    "#c586c0", r'\b(true|false)\b'),
    ],
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

# ── Config ─────────────────────────────────────────────────────────────────────
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
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, val)
    except Exception:
        pass

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
    """Save settings — API keys are never written to config.json (stay in .env)."""
    safe = {k: v for k, v in cfg.items() if "api_key" not in k}
    try:
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(safe, f, indent=2)
    except Exception as e:
        print(f"[cfg] {e}")

# ── Agent tools ────────────────────────────────────────────────────────────────
def parse_tools(text):
    tools = []
    pat = r'<vagent:(\w+)([^>/]*)(?:>([\s\S]*?)</vagent:\1>|/>)'
    for m in re.finditer(pat, text, re.DOTALL):
        verb    = m.group(1)
        attrs_s = m.group(2).strip()
        content = (m.group(3) or "").strip()
        attrs   = dict(re.findall(r'(\w+)="([^"]*)"', attrs_s))
        tools.append({"verb": verb, "attrs": attrs, "content": content, "full": m.group(0)})
    return tools

def strip_tools(text):
    t = re.sub(r'<vagent:\w+[^>]*>[\s\S]*?</vagent:\w+>', '', text, flags=re.DOTALL)
    t = re.sub(r'<vagent:\w+[^/]*/>', '', t)
    return t.strip()

def exec_tool(tool, cwd=None):
    verb    = tool["verb"]
    attrs   = tool["attrs"]
    content = tool["content"]
    cwd     = cwd or os.getcwd()

    def resolve(p):
        if not p: return cwd
        return p if os.path.isabs(p) else os.path.join(cwd, p)

    try:
        if verb == "read":
            path = resolve(attrs.get("path", ""))
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                data = f.read()
            ext  = os.path.splitext(path)[1].lower()
            lang = LANG_EXT.get(ext, "text")
            rel  = os.path.relpath(path, cwd) if cwd else path
            return (f"read: {rel}\n```{lang}\n{data[:4000]}\n```", None)

        elif verb == "write":
            path = resolve(attrs.get("path", ""))
            parent = os.path.dirname(path)
            if parent and not os.path.exists(parent):
                os.makedirs(parent, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            rel = os.path.relpath(path, cwd) if cwd else path
            return (f"created: {rel} ({len(content):,} chars)", None)

        elif verb == "edit":
            return ("edit: applying to open file…", content)

        elif verb == "ls":
            path  = resolve(attrs.get("path", "."))
            items = sorted(os.listdir(path),
                           key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower()))
            lines = []
            for name in items[:60]:
                full  = os.path.join(path, name)
                isdir = os.path.isdir(full)
                ext   = os.path.splitext(name)[1].lower()
                icon  = "📁" if isdir else FILE_ICONS.get(ext, "📄")
                size  = ""
                if not isdir:
                    try:
                        sz = os.path.getsize(full)
                        for u in ("B","KB","MB"):
                            if sz < 1024: size = f"  {sz:.0f}{u}"; break
                            sz //= 1024
                    except Exception: pass
                lines.append(f"  {icon} {name}{size}")
            if len(items) > 60:
                lines.append(f"  … +{len(items)-60} more")
            rel = os.path.relpath(path, cwd) if cwd else path
            return (f"ls: {rel}/\n" + "\n".join(lines), None)

        elif verb == "run":
            cmd = content.strip()
            # Security: block / warn on dangerous patterns
            if is_dangerous_command(cmd):
                return (f"⛔ Blocked: `{cmd[:80]}` matches a potentially destructive pattern.\n"
                        f"Run manually if intentional.", None)
            import shlex
            try:
                args   = shlex.split(cmd)
                r      = subprocess.run(args, capture_output=True, text=True,
                                        timeout=30, cwd=cwd)
            except Exception:
                # Fallback: if shlex split fails, run with shell but warn
                r = subprocess.run(cmd, shell=True, capture_output=True,
                                   text=True, timeout=30, cwd=cwd)
            out = (r.stdout + r.stderr).strip()
            ok  = r.returncode == 0
            return (f"{'✅' if ok else '❌'} run: `{cmd}`\n```\n{out[:3000] or '(no output)'}\n```", None)

        elif verb == "search":
            pattern = attrs.get("pattern", content)
            path    = resolve(attrs.get("path", "."))
            results = []
            exts    = {".py",".js",".ts",".jsx",".tsx",".html",".css",".json",
                       ".sh",".bat",".md",".txt",".c",".cpp",".h",".rs",".go"}
            count   = 0
            for root_d, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__" and d != "node_modules"]
                for fname in files:
                    if os.path.splitext(fname)[1].lower() not in exts: continue
                    fpath = os.path.join(root_d, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                            for lineno, line in enumerate(f, 1):
                                if pattern.lower() in line.lower():
                                    rel = os.path.relpath(fpath, cwd)
                                    results.append(f"  {rel}:{lineno}  {line.rstrip()}")
                                    count += 1
                                    if count >= 30: break
                        if count >= 30: break
                    except Exception: pass
                if count >= 30: break
            header = f"search: \"{pattern}\" — {count} result{'s' if count!=1 else ''}"
            return (header + ("\n"+"\n".join(results) if results else "\n  (no results)"), None)

        else:
            return (f"unknown tool: {verb}", None)

    except Exception as e:
        return (f"error ({verb}): {e}", None)


# ══════════════════════════════════════════════════════════════════════════
#  CLOUD AI CLIENT  (Groq · OpenRouter — OpenAI-compatible streaming)
# ══════════════════════════════════════════════════════════════════════════
# Commands that are always allowed without confirmation
_SAFE_CMDS = {
    "ls","dir","cat","type","echo","pwd","whoami","python --version",
    "pip list","pip show","git status","git log","git diff","git branch",
    "ollama list","ollama ps","node --version","npm --version",
}
_DANGER_PATTERNS = (
    "rm -rf","del /f","del /s","format ","mkfs","dd if=",
    "curl","wget","invoke-webrequest","powershell","cmd /c",
    "shutdown","reboot","reg delete","reg add",
)

def is_dangerous_command(cmd: str) -> bool:
    low = cmd.strip().lower()
    for p in _DANGER_PATTERNS:
        if p in low:
            return True
    return False

def is_safe_command(cmd: str) -> bool:
    low = cmd.strip().lower()
    return any(low.startswith(s) for s in _SAFE_CMDS)


class CloudAIClient:
    """OpenAI-compatible client for Groq and OpenRouter."""

    BASE_URLS = {
        "groq":        "https://api.groq.com/openai/v1",
        "openrouter":  "https://openrouter.ai/api/v1",
    }

    def __init__(self, provider: str, api_key: str, model: str):
        self.provider = provider
        self.model    = model
        self.base_url = self.BASE_URLS.get(provider, "")
        import requests as _req
        self._s = _req.Session()
        self._s.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
        })
        if provider == "openrouter":
            self._s.headers.update({
                "HTTP-Referer": "https://github.com/vagent",
                "X-Title":      "V-Agent",
            })

    def stream(self, messages: list, temperature: float = 0.15, cancel_flag=None):
        """Yields text tokens. Raises on HTTP error."""
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
            if cancel_flag and cancel_flag():
                break
            if not raw:
                continue
            line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data == "[DONE]":
                break
            try:
                import json as _j
                delta = _j.loads(data)["choices"][0].get("delta", {})
                tok   = delta.get("content", "")
                if tok:
                    yield tok
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════════════════════
#  TOAST NOTIFICATION
# ══════════════════════════════════════════════════════════════════════════════
class Toast:
    def __init__(self, root, message, color="#4ec994", duration=2500):
        try:
            self.win = tk.Toplevel(root)
            self.win.overrideredirect(True)
            self.win.attributes("-topmost", True)
            w, h = max(300, len(message) * 7 + 40), 36
            sw   = root.winfo_screenwidth()
            sh   = root.winfo_screenheight()
            x    = sw - w - 24
            y    = sh - h - 60
            self.win.geometry(f"{w}x{h}+{x}+{y}")
            tk.Label(self.win, text=f"  {message}  ",
                     bg="#1a1a2e", fg=color,
                     font=("Segoe UI", 10), pady=8).pack(fill=tk.BOTH, expand=True)
            root.after(duration, self._destroy)
        except Exception:
            pass

    def _destroy(self):
        try: self.win.destroy()
        except Exception: pass

# ══════════════════════════════════════════════════════════════════════════════
#  COMMAND PALETTE
# ══════════════════════════════════════════════════════════════════════════════
class CommandPalette(tk.Toplevel):
    def __init__(self, root, C, commands):
        super().__init__(root)
        self.overrideredirect(True)
        self.C        = C
        self.commands = commands   # List of {"label": str, "key": str, "action": callable}
        self._all     = list(commands)
        w, h = 560, 360
        rx   = root.winfo_x() + (root.winfo_width()  - w) // 2
        ry   = root.winfo_y() + 44
        self.geometry(f"{w}x{h}+{rx}+{ry}")
        self.configure(bg=C["border"])
        self.grab_set()
        self._build()

    def _build(self):
        C = self.C
        # Outer border
        frame = tk.Frame(self, bg=C["panel"], bd=1, relief=tk.FLAT)
        frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Search bar
        top = tk.Frame(frame, bg=C["panel"])
        top.pack(fill=tk.X)
        tk.Label(top, text="  ›  ", font=("Segoe UI", 12),
                 fg=C["accent"], bg=C["panel"]).pack(side=tk.LEFT)
        self._var = tk.StringVar()
        self._var.trace("w", lambda *_: self._filter())
        entry = tk.Entry(top, textvariable=self._var, font=("Segoe UI", 12),
                         bg=C["panel"], fg=C["text"], insertbackground=C["text"],
                         relief=tk.FLAT, bd=0)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=10, padx=(0, 10))
        entry.focus_set()

        tk.Frame(frame, bg=C["border"], height=1).pack(fill=tk.X)

        # Results list
        list_frame = tk.Frame(frame, bg=C["panel"])
        list_frame.pack(fill=tk.BOTH, expand=True)
        self._lb = tk.Listbox(list_frame, bg=C["panel"], fg=C["text"],
                              font=("Segoe UI", 10), relief=tk.FLAT,
                              selectbackground=C["selection"],
                              selectforeground=C["text"],
                              activestyle="none", bd=0, pady=2)
        self._lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self._lb.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._lb.configure(yscrollcommand=sb.set)

        # Hint
        tk.Label(frame, text="  ↑↓ navigate   ↵ run   Esc dismiss",
                 font=("Segoe UI", 8), fg=C["dim"], bg=C["panel"],
                 anchor=tk.W, pady=4).pack(fill=tk.X)

        # Bindings
        entry.bind("<Return>",   lambda e: self._select())
        entry.bind("<Down>",     lambda e: self._move(1))
        entry.bind("<Up>",       lambda e: self._move(-1))
        entry.bind("<Escape>",   lambda e: self.destroy())
        self._lb.bind("<Return>", lambda e: self._select())
        self._lb.bind("<Escape>", lambda e: self.destroy())
        self._lb.bind("<Double-1>", lambda e: self._select())
        self.bind("<FocusOut>",  lambda e: self.destroy())

        self._filter()

    def _filter(self):
        q = self._var.get().lower()
        self._lb.delete(0, tk.END)
        self._filtered = []
        for cmd in self._all:
            label = cmd["label"]
            key   = cmd.get("key", "")
            if not q or q in label.lower():
                display = f"  {label}"
                if key: display += f"  ({key})"
                self._lb.insert(tk.END, display)
                self._filtered.append(cmd)
        if self._filtered:
            self._lb.selection_set(0)
            self._lb.activate(0)

    def _move(self, delta):
        sel = self._lb.curselection()
        idx = (sel[0] if sel else -1) + delta
        idx = max(0, min(idx, self._lb.size() - 1))
        self._lb.selection_clear(0, tk.END)
        self._lb.selection_set(idx)
        self._lb.activate(idx)
        self._lb.see(idx)

    def _select(self):
        sel = self._lb.curselection()
        if sel and sel[0] < len(self._filtered):
            cmd = self._filtered[sel[0]]
            self.destroy()
            cmd["action"]()

# ══════════════════════════════════════════════════════════════════════════════
#  FIND / REPLACE BAR
# ══════════════════════════════════════════════════════════════════════════════
class FindBar(tk.Frame):
    def __init__(self, parent, editor_ref, C):
        super().__init__(parent, bg=C["find_bg"])
        self._ed       = editor_ref
        self.C         = C
        self._visible  = False
        self._matches  = []
        self._midx     = -1
        self._replace_open = False
        self._build()

    def _build(self):
        C = self.C
        # Find row
        fr = tk.Frame(self, bg=C["find_bg"])
        fr.pack(fill=tk.X, padx=8, pady=(6, 2))

        tk.Label(fr, text="Find", font=("Segoe UI", 9), fg=C["dim"],
                 bg=C["find_bg"], width=7, anchor=tk.W).pack(side=tk.LEFT)
        self._fv = tk.StringVar()
        self._fv.trace("w", lambda *_: self._find_all())
        self._fe = tk.Entry(fr, textvariable=self._fv, font=("Segoe UI", 10),
                            bg=C["bg"], fg=C["text"], insertbackground=C["text"],
                            relief=tk.FLAT, bd=3, width=32,
                            selectbackground=C["selection"])
        self._fe.pack(side=tk.LEFT, ipady=3)

        self._ml = tk.Label(fr, text="", font=("Segoe UI", 8), fg=C["dim"],
                            bg=C["find_bg"], padx=8, width=12)
        self._ml.pack(side=tk.LEFT)

        for txt, cmd in [("▲", self._prev), ("▼", self._next)]:
            tk.Button(fr, text=txt, font=("Segoe UI", 9), fg=C["text"],
                      bg=C["find_bg"], relief=tk.FLAT, bd=0, cursor="hand2",
                      activebackground=C["border"], padx=8, pady=2,
                      command=cmd).pack(side=tk.LEFT, padx=1)

        tk.Button(fr, text="⇌", font=("Segoe UI", 9), fg=C["dim"],
                  bg=C["find_bg"], relief=tk.FLAT, bd=0, cursor="hand2",
                  activebackground=C["border"], padx=6, pady=2,
                  command=self._toggle_replace).pack(side=tk.LEFT, padx=2)

        tk.Button(fr, text="✕", font=("Segoe UI", 9), fg=C["dim"],
                  bg=C["find_bg"], relief=tk.FLAT, bd=0, cursor="hand2",
                  activebackground=C["border"], padx=8, pady=2,
                  command=self.hide).pack(side=tk.RIGHT)

        # Replace row (hidden by default)
        self._rr = tk.Frame(self, bg=C["find_bg"])
        tk.Label(self._rr, text="Replace", font=("Segoe UI", 9), fg=C["dim"],
                 bg=C["find_bg"], width=7, anchor=tk.W).pack(side=tk.LEFT, padx=(8, 0))
        self._rv = tk.StringVar()
        tk.Entry(self._rr, textvariable=self._rv, font=("Segoe UI", 10),
                 bg=C["bg"], fg=C["text"], insertbackground=C["text"],
                 relief=tk.FLAT, bd=3, width=32,
                 selectbackground=C["selection"]).pack(side=tk.LEFT, ipady=3)
        for txt, cmd in [("Replace", self._replace_one), ("All", self._replace_all)]:
            tk.Button(self._rr, text=txt, font=("Segoe UI", 8), fg=C["text"],
                      bg=C["border"], relief=tk.FLAT, bd=0, cursor="hand2",
                      activebackground=C["selection"], padx=10, pady=3,
                      command=cmd).pack(side=tk.LEFT, padx=4)

        # Key bindings
        self._fe.bind("<Return>",       lambda e: self._next())
        self._fe.bind("<Shift-Return>", lambda e: self._prev())
        self._fe.bind("<Escape>",       lambda e: self.hide())

    def show(self, with_replace=False):
        if not self._visible:
            self.pack(fill=tk.X)
            self._visible = True
        if with_replace and not self._replace_open:
            self._rr.pack(fill=tk.X, padx=0, pady=(0, 4))
            self._replace_open = True
        self._fe.focus_set()
        self._fe.select_range(0, tk.END)
        self._find_all()

    def hide(self):
        self.pack_forget()
        self._rr.pack_forget()
        self._visible       = False
        self._replace_open  = False
        try:
            self._ed.tag_remove("found",         "1.0", tk.END)
            self._ed.tag_remove("found_current", "1.0", tk.END)
        except Exception: pass
        self._ed.focus_set()

    def _toggle_replace(self):
        if self._replace_open:
            self._rr.pack_forget()
            self._replace_open = False
        else:
            self._rr.pack(fill=tk.X, padx=0, pady=(0, 4))
            self._replace_open = True

    def _find_all(self):
        C   = self.C
        term = self._fv.get()
        try:
            self._ed.tag_remove("found",         "1.0", tk.END)
            self._ed.tag_remove("found_current", "1.0", tk.END)
        except Exception: return
        self._matches = []
        if not term:
            self._ml.config(text="")
            return
        self._ed.tag_config("found",         background="#3a3d41", foreground=C["text"])
        self._ed.tag_config("found_current", background=C["yellow"], foreground="#1a1a1a")
        start = "1.0"
        while True:
            pos = self._ed.search(term, start, stopindex=tk.END, nocase=True)
            if not pos: break
            end = f"{pos} + {len(term)} chars"
            self._ed.tag_add("found", pos, end)
            self._matches.append((pos, end))
            start = end
        n = len(self._matches)
        self._ml.config(text=f"{n} match{'es' if n!=1 else ''}")
        self._midx = -1
        if self._matches:
            self._next()

    def _highlight_current(self, idx):
        if 0 <= idx < len(self._matches):
            p, e = self._matches[idx]
            self._ed.tag_remove("found",         p, e)
            self._ed.tag_add   ("found_current", p, e)
            self._ed.see(p)
            total = len(self._matches)
            self._ml.config(text=f"{idx+1}/{total}")

    def _unhighlight_current(self):
        if 0 <= self._midx < len(self._matches):
            p, e = self._matches[self._midx]
            self._ed.tag_remove("found_current", p, e)
            self._ed.tag_add   ("found",         p, e)

    def _next(self):
        if not self._matches: return
        self._unhighlight_current()
        self._midx = (self._midx + 1) % len(self._matches)
        self._highlight_current(self._midx)

    def _prev(self):
        if not self._matches: return
        self._unhighlight_current()
        self._midx = (self._midx - 1) % len(self._matches)
        self._highlight_current(self._midx)

    def _replace_one(self):
        if not (0 <= self._midx < len(self._matches)): return
        p, e   = self._matches[self._midx]
        newval = self._rv.get()
        self._ed.delete(p, e)
        self._ed.insert(p, newval)
        self._find_all()

    def _replace_all(self):
        term   = self._fv.get()
        newval = self._rv.get()
        if not term: return
        content = self._ed.get("1.0", "end-1c")
        count   = content.count(term)
        if count == 0: return
        new_content = content.replace(term, newval)
        self._ed.delete("1.0", tk.END)
        self._ed.insert("1.0", new_content)
        self._find_all()
        return count


# ══════════════════════════════════════════════════════════════════════════════
#  EDITOR WIDGET
# ══════════════════════════════════════════════════════════════════════════════
class EditorWidget(tk.Frame):
    """Single-file editor: line numbers, syntax highlight, find bar, smart indent."""

    def __init__(self, parent, app, path, content, lang):
        super().__init__(parent, bg=app.C["bg"])
        self.app      = app
        self.path     = path
        self.lang     = lang
        self.modified = False
        self._hl_job  = None
        self.on_modified = None
        self.on_cursor   = None
        self.on_save     = None
        self.on_new      = None
        self.on_open     = None
        self.on_close    = None
        self.on_palette  = None
        self._build(content)

    def _build(self, content):
        C = self.app.C
        self._hsb = ttk.Scrollbar(self, orient=tk.HORIZONTAL)
        self._hsb.pack(side=tk.BOTTOM, fill=tk.X)
        row = tk.Frame(self, bg=C["bg"])
        row.pack(fill=tk.BOTH, expand=True)
        self.linenums = tk.Text(
            row, bg=C["code_bg"], fg=C.get("ln_fg",C["dim"]), font=self.app.tf,
            width=4, relief=tk.FLAT, padx=6, pady=6,
            state="disabled", bd=0, selectbackground=C["code_bg"],
            cursor="arrow", takefocus=False)
        self.linenums.pack(side=tk.LEFT, fill=tk.Y)
        tk.Frame(row, bg=C["border"], width=1).pack(side=tk.LEFT, fill=tk.Y)
        self._vsb = ttk.Scrollbar(row, orient=tk.VERTICAL)
        self._vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.editor = tk.Text(
            row, bg=C["bg"], fg=C["text"], font=self.app.tf,
            wrap=tk.NONE, relief=tk.FLAT, bd=0,
            insertbackground=C["purple"],
            selectbackground=C["selection"], selectforeground=C["text"],
            padx=12, pady=6, undo=True, maxundo=-1,
            spacing1=2, spacing2=1, spacing3=2)
        self.editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.editor.configure(
            yscrollcommand=lambda *a: (self._vsb.set(*a), self._sync_ln()),
            xscrollcommand=self._hsb.set)
        self._vsb.configure(command=lambda *a: (self.editor.yview(*a), self._sync_ln()))
        self._hsb.configure(command=self.editor.xview)
        self.editor.tag_config("line_hl",      background=C["line_hl"])
        self.editor.tag_config("found",         background="#3a3d41", foreground=C["text"])
        self.editor.tag_config("found_current", background=C["yellow"], foreground="#1a1a1a")
        self.editor.insert("1.0", content)
        self.editor.edit_reset()
        self.find_bar = FindBar(self, self.editor, C)
        self._bind()
        self.app.root.after(50,  self._upd_linenums)
        self.app.root.after(100, self._do_highlight)
        self.app.root.after(30,  self._upd_line_hl)

    def _bind(self):
        ed = self.editor
        ed.bind("<Key>",            self._on_key)
        ed.bind("<ButtonRelease>",  self._upd_cursor_evt)
        ed.bind("<KeyRelease>",     self._upd_cursor_evt)
        ed.bind("<ButtonPress>",    lambda e: self.app.root.after(5, self._upd_line_hl))
        ed.bind("<KeyPress>",       lambda e: self.app.root.after(5, self._upd_line_hl))
        def _cb(fn, *a): return (fn(*a) if fn else None, "break")[1]
        ed.bind("<Control-s>",      lambda e: _cb(self.on_save, self.path))
        ed.bind("<Control-S>",      lambda e: _cb(self.on_save, self.path))
        ed.bind("<Control-n>",      lambda e: _cb(self.on_new))
        ed.bind("<Control-o>",      lambda e: _cb(self.on_open))
        ed.bind("<Control-w>",      lambda e: _cb(self.on_close, self.path))
        ed.bind("<Control-z>",      lambda e: (ed.edit_undo(), "break")[1])
        ed.bind("<Control-y>",      lambda e: (ed.edit_redo(), "break")[1])
        ed.bind("<Control-Z>",      lambda e: (ed.edit_redo(), "break")[1])
        ed.bind("<Control-f>",      lambda e: (self.find_bar.show(), "break")[1])
        ed.bind("<Control-h>",      lambda e: (self.find_bar.show(with_replace=True), "break")[1])
        ed.bind("<Control-g>",      lambda e: (self._goto_line(), "break")[1])
        ed.bind("<Control-plus>",   lambda e: self._zoom(1))
        ed.bind("<Control-equal>",  lambda e: self._zoom(1))
        ed.bind("<Control-minus>",  lambda e: self._zoom(-1))
        ed.bind("<Control-0>",      lambda e: self._zoom(0))
        ed.bind("<Tab>",            lambda e: (ed.insert(tk.INSERT, "    "), "break")[1])
        ed.bind("<Shift-Tab>",      lambda e: (self._unindent(), "break")[1])
        ed.bind("<Return>",         self._on_return)
        ed.bind("<parenleft>",      lambda e: self._auto_close("(", ")"))
        ed.bind("<bracketleft>",    lambda e: self._auto_close("[", "]"))
        ed.bind("<braceleft>",      lambda e: self._auto_close("{", "}"))
        ed.bind("<quotedbl>",       lambda e: self._auto_close('"', '"'))
        ed.bind("<Control-d>",      lambda e: (self._dup_line(), "break")[1])
        ed.bind("<Control-slash>",  lambda e: (self._toggle_comment(), "break")[1])
        ed.bind("<Control-Shift-P>", lambda e: _cb(self.on_palette))

    def _on_key(self, event):
        mods = {"Control_L","Control_R","Alt_L","Alt_R",
                "Shift_L","Shift_R","Meta_L","Meta_R","Caps_Lock"}
        if event.keysym in mods: return
        if event.state & 0x4: return
        if not self.modified:
            self.modified = True
            if self.on_modified: self.on_modified(self.path)
        if self._hl_job: self.app.root.after_cancel(self._hl_job)
        self._hl_job = self.app.root.after(400, self._do_highlight)
        self.app.root.after(10, self._upd_linenums)

    def _on_return(self, event):
        ed     = self.editor
        line   = ed.get("insert linestart", "insert")
        indent = len(line) - len(line.lstrip(" \t"))
        extra  = "    " if line.rstrip().endswith(":") else ""
        ed.insert(tk.INSERT, "\n" + " " * indent + extra)
        self.app.root.after(10, self._upd_linenums)
        return "break"

    def _auto_close(self, open_c, close_c):
        ed = self.editor
        try:
            sel = ed.get(tk.SEL_FIRST, tk.SEL_LAST)
            ed.delete(tk.SEL_FIRST, tk.SEL_LAST)
            ed.insert(tk.INSERT, open_c + sel + close_c)
        except tk.TclError:
            ed.insert(tk.INSERT, open_c + close_c)
            ed.mark_set(tk.INSERT, f"{tk.INSERT} - 1 chars")
        return "break"

    def _unindent(self):
        ed   = self.editor
        line = ed.get("insert linestart", "insert lineend")
        if line.startswith("    "):
            ed.delete("insert linestart", "insert linestart + 4 chars")
        elif line.startswith("\t"):
            ed.delete("insert linestart", "insert linestart + 1 chars")

    def _dup_line(self):
        ed   = self.editor
        line = ed.get("insert linestart", "insert lineend")
        ed.insert("insert lineend", "\n" + line)

    def _toggle_comment(self):
        ed       = self.editor
        line     = ed.get("insert linestart", "insert lineend")
        stripped = line.lstrip()
        pfx = "#" if self.lang in ("python","bash","yaml","toml","ruby") else "//"
        if stripped.startswith(pfx + " "):
            new = line.replace(pfx + " ", "", 1)
        elif stripped.startswith(pfx):
            new = line.replace(pfx, "", 1)
        else:
            spaces = len(line) - len(stripped)
            new    = line[:spaces] + pfx + " " + stripped
        ed.delete("insert linestart", "insert lineend")
        ed.insert("insert linestart", new)

    def _upd_line_hl(self):
        self.editor.tag_remove("line_hl", "1.0", tk.END)
        self.editor.tag_add("line_hl", "insert linestart", "insert lineend+1c")

    def _do_highlight(self):
        ed    = self.editor
        rules = SYNTAX.get(self.lang, [])
        for tag in [t for t in ed.tag_names() if t.startswith("hl_")]:
            ed.tag_remove(tag, "1.0", tk.END)
        content = ed.get("1.0", tk.END)
        for name, color, pat in rules:
            tag = "hl_" + name
            ed.tag_config(tag, foreground=color)
            for m in re.finditer(pat, content, re.MULTILINE | re.DOTALL):
                ed.tag_add(tag, f"1.0+{m.start()}c", f"1.0+{m.end()}c")
        self._upd_line_hl()

    def _upd_linenums(self):
        ed    = self.editor
        ln    = self.linenums
        total = int(ed.index("end-1c").split(".")[0])
        width = max(3, len(str(total))) + 1
        ln.config(state="normal", width=width)
        ln.delete("1.0", tk.END)
        ln.insert("1.0", "\n".join(str(i) for i in range(1, total + 1)))
        ln.config(state="disabled")

    def _sync_ln(self):
        try: self.linenums.yview_moveto(self.editor.yview()[0])
        except Exception: pass

    def _upd_cursor_evt(self, _=None):
        if self.on_cursor:
            idx = self.editor.index(tk.INSERT)
            ln, col = idx.split(".")
            self.on_cursor(int(ln), int(col) + 1)

    def _goto_line(self):
        n = simpledialog.askinteger("Go to Line", "Line number:",
                                    parent=self.app.root, minvalue=1)
        if n:
            self.editor.see(f"{n}.0")
            self.editor.mark_set(tk.INSERT, f"{n}.0")
            self.editor.focus_set()
            self._upd_line_hl()

    def _zoom(self, delta):
        try:
            fs = self.app.tf.actual("size")
            fs = self.app.cfg.get("font_size", 12) if delta == 0 else max(8, min(28, fs + delta))
            self.app.tf.config(size=fs)
            self.app.tfb.config(size=fs)
            self.app.tfi.config(size=fs)
        except Exception: pass

    def set_content(self, content):
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", content)
        self.modified = True
        if self.on_modified: self.on_modified(self.path)
        self.app.root.after(50, self._upd_linenums)
        self.app.root.after(100, self._do_highlight)

    def get_content(self):
        return self.editor.get("1.0", "end-1c")

    def get_selection(self):
        try: return self.editor.get(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError: return ""

    def focus(self):
        self.editor.focus_set()
        self._upd_line_hl()


# ══════════════════════════════════════════════════════════════════════════════
#  AI PANEL
# ══════════════════════════════════════════════════════════════════════════════
class AIPanel:
    """Agentic AI assistant: streaming tokens, tool loop, apply-to-editor."""

    def __init__(self, parent, app, ide):
        self.app   = app
        self._ide  = ide
        self.frame = tk.Frame(parent, bg=app.C["panel"])
        self._hist = []
        self._running      = False
        self._cancel       = False
        self._stream_start = None
        self._build()

    def _build(self):
        C = self.app.C
        # Header
        hdr = tk.Frame(self.frame, bg=C["panel"])
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="  V\u00b7AGENT",
                 font=("Cascadia Code", 11, "bold"),
                 fg=C["accent"], bg=C["panel"], pady=10).pack(side=tk.LEFT)
        self._status_lbl = tk.Label(hdr, text="",
                 font=("Segoe UI", 8), fg=C["green"], bg=C["panel"], padx=6)
        self._status_lbl.pack(side=tk.RIGHT)
        tk.Frame(self.frame, bg=C["border"], height=1).pack(fill=tk.X)
        # Provider + model row
        mrow = tk.Frame(self.frame, bg=C["panel"])
        mrow.pack(fill=tk.X, padx=10, pady=(8, 2))
        tk.Label(mrow, text="Provider", font=("Segoe UI", 8),
                 fg=C["dim"], bg=C["panel"]).pack(side=tk.LEFT)
        self._sv_provider = tk.StringVar(value=self.app.cfg.get("ai_provider","local"))
        ttk.Combobox(mrow, textvariable=self._sv_provider,
                     values=["local","groq","openrouter"],
                     font=("Segoe UI", 9), state="readonly", width=12
                     ).pack(side=tk.LEFT, padx=(6,0))
        self._sv_provider.trace("w", lambda *_: self._on_provider_change())

        mrow2 = tk.Frame(self.frame, bg=C["panel"])
        mrow2.pack(fill=tk.X, padx=10, pady=(2, 4))
        tk.Label(mrow2, text="Model", font=("Segoe UI", 8),
                 fg=C["dim"], bg=C["panel"]).pack(side=tk.LEFT)
        self._sv_model = tk.StringVar(value=self.app.cfg.get("model", FALLBACK_MODELS[0]))
        self._model_cb = ttk.Combobox(mrow2, textvariable=self._sv_model,
                     values=FALLBACK_MODELS, font=("Segoe UI", 9),
                     state="readonly")
        self._model_cb.pack(side=tk.LEFT, padx=(8,0), fill=tk.X, expand=True)
        # Quick actions
        qa = tk.Frame(self.frame, bg=C["panel"])
        qa.pack(fill=tk.X, padx=10, pady=(0, 6))
        for label, prompt in [
            ("Explain",  "Explain what this code does, step by step:"),
            ("Fix",      "Find and fix all bugs, edge cases, and issues:"),
            ("Comment",  "Add clear, helpful docstrings and inline comments:"),
            ("Refactor", "Refactor for clarity, best practices, and performance:"),
            ("Tests",    "Write comprehensive unit tests:"),
            ("Optimize", "Optimize for performance, explain trade-offs:"),
        ]:
            tk.Button(qa, text=label, font=("Segoe UI", 8),
                      fg=C["text"], bg=C["border"],
                      activebackground=C["selection"],
                      relief=tk.FLAT, bd=0, cursor="hand2", padx=7, pady=3,
                      command=lambda p=prompt: self._quick(p)
                      ).pack(side=tk.LEFT, padx=1, pady=2)
        tk.Frame(self.frame, bg=C["border"], height=1).pack(fill=tk.X)
        # Chat
        cw = tk.Frame(self.frame, bg=C["panel"])
        cw.pack(fill=tk.BOTH, expand=True)
        self._chat = tk.Text(
            cw, bg=C["panel"], fg=C["text"],
            font=("Cascadia Code", 9), wrap=tk.WORD,
            relief=tk.FLAT, padx=10, pady=8,
            state="disabled", bd=0, cursor="arrow",
            spacing1=1, spacing2=0, spacing3=2)
        self._chat.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        csb = ttk.Scrollbar(cw, orient=tk.VERTICAL, command=self._chat.yview)
        csb.pack(side=tk.RIGHT, fill=tk.Y)
        self._chat.configure(yscrollcommand=csb.set)
        self._setup_tags()
        # Input
        tk.Frame(self.frame, bg=C["border"], height=1).pack(fill=tk.X)
        inp = tk.Frame(self.frame, bg=C["bg"])
        inp.pack(fill=tk.X)
        self._ai_in = tk.Text(
            inp, bg=C["bg"], fg=C["text"],
            font=("Cascadia Code", 9), wrap=tk.WORD,
            relief=tk.FLAT, height=3, padx=10, pady=8,
            insertbackground=C["purple"], bd=0)
        self._ai_in.pack(fill=tk.X)
        self._ai_in.bind("<Return>",       self._on_enter)
        self._ai_in.bind("<Shift-Return>", lambda e: None)
        brow = tk.Frame(self.frame, bg=C["bg"])
        brow.pack(fill=tk.X, padx=10, pady=(0, 10))
        tk.Button(brow, text="  Send  \u21b5  ",
                  font=("Segoe UI", 9, "bold"),
                  fg=C.get("button_fg","#FFFFFF"), bg=C.get("button_bg",C["accent"]),
                  activebackground=C["accent"],
                  relief=tk.FLAT, bd=0, cursor="hand2", padx=12, pady=6,
                  command=self._send).pack(side=tk.RIGHT)
        tk.Button(brow, text="\u2297",
                  font=("Segoe UI", 10), fg=C["red"], bg=C["bg"],
                  relief=tk.FLAT, bd=0, cursor="hand2", padx=8, pady=6,
                  activebackground=C["panel"],
                  command=lambda: setattr(self, "_cancel", True)
                  ).pack(side=tk.RIGHT, padx=(0, 4))
        tk.Button(brow, text="\U0001f5d1  Clear",
                  font=("Segoe UI", 8), fg=C["dim"], bg=C["bg"],
                  relief=tk.FLAT, bd=0, cursor="hand2", padx=8, pady=6,
                  activebackground=C["panel"],
                  command=self._clear_chat).pack(side=tk.LEFT)
        self._chat_sys("V\u00b7AGENT ready \u2014 I can read, edit, and run files in your project.")

    def _setup_tags(self):
        C = self.app.C
        mono = ("Cascadia Code", 9)
        ui_b = ("Segoe UI", 9, "bold")
        ui_s = ("Segoe UI", 8)
        self._chat.tag_config("user_lbl",    foreground=C["blue"],      font=ui_b)
        self._chat.tag_config("user_text",   foreground=C["text"],      font=mono)
        self._chat.tag_config("ai_lbl",      foreground=C["accent"],    font=ui_b)
        self._chat.tag_config("ai_text",     foreground=C["text"],      font=mono)
        self._chat.tag_config("ai_h1",       foreground=C["purple"],    font=("Segoe UI",11,"bold"))
        self._chat.tag_config("ai_h2",       foreground=C["purple"],    font=("Segoe UI",10,"bold"))
        self._chat.tag_config("ai_h3",       foreground=C["blue"],      font=("Segoe UI", 9,"bold"))
        self._chat.tag_config("ai_quote",    foreground=C["dim"],       font=mono)
        self._chat.tag_config("inline_code", foreground=C["cyan"],      background=C["code_bg"], font=mono)
        self._chat.tag_config("code_lang",   foreground=C["dim"],       font=ui_s)
        self._chat.tag_config("code_text",   foreground=C["text"],      background=C["code_bg"], font=mono)
        self._chat.tag_config("tool_lbl",    foreground=C["green"],     font=ui_b)
        self._chat.tag_config("tool_text",   foreground=C["assistant"], font=mono)
        self._chat.tag_config("sys_text",    foreground=C["dim"],       font=ui_s)
        self._chat.tag_config("timestamp",   foreground=C["dim"],       font=ui_s)
        self._chat.tag_config("stream_raw",  foreground=C["assistant"], font=mono)
        self._chat.tag_config("err_text",    foreground=C["red"],       font=("Segoe UI",9))
        self._chat.tag_config("sep",         foreground=C["border"],    font=ui_s)

    def _cw(self, text, tag="ai_text", nl=True):
        self._chat.config(state="normal")
        self._chat.insert(tk.END, text, tag)
        if nl: self._chat.insert(tk.END, "\n")
        self._chat.see(tk.END)
        self._chat.config(state="disabled")

    def _chat_sys(self, msg):
        self._cw(f"\n  {msg}", "sys_text")

    def _chat_sep(self):
        self._chat.config(state="normal")
        self._chat.insert(tk.END, "\n  " + "\u2500"*38 + "\n", "sep")
        self._chat.config(state="disabled")

    def _clear_chat(self):
        self._chat.config(state="normal")
        self._chat.delete("1.0", tk.END)
        self._chat.config(state="disabled")
        self._hist.clear()
        self._chat_sys("Chat cleared.")

    def _set_status(self, msg):
        self._status_lbl.config(text=msg)
        if self._ide and hasattr(self._ide, "_st_agent"):
            self._ide._st_agent.config(text=msg)

    def _msg_user(self, text):
        ts = datetime.datetime.now().strftime("%H:%M")
        self._chat_sep()
        self._chat.config(state="normal")
        self._chat.insert(tk.END, "  YOU", "user_lbl")
        self._chat.insert(tk.END, f"   {ts}\n", "timestamp")
        self._chat.insert(tk.END, f"  {text}\n", "user_text")
        self._chat.config(state="disabled")
        self._chat.see(tk.END)

    def _begin_ai_bubble(self):
        ts = datetime.datetime.now().strftime("%H:%M")
        self._chat.config(state="normal")
        self._chat.insert(tk.END, "\n  V\u00b7AGENT", "ai_lbl")
        self._chat.insert(tk.END, f"   {ts}\n", "timestamp")
        self._stream_start = self._chat.index(tk.END)
        self._chat.config(state="disabled")
        self._chat.see(tk.END)

    def _stream_tok(self, tok):
        self._chat.config(state="normal")
        self._chat.insert(tk.END, tok, "stream_raw")
        self._chat.see(tk.END)
        self._chat.config(state="disabled")

    def _end_ai_bubble(self, full_text):
        clean = strip_tools(full_text)
        self._chat.config(state="normal")
        try:
            self._chat.delete(self._stream_start, tk.END)
        except Exception:
            pass
        self._render_ai_content(clean)
        self._chat.config(state="disabled")
        self._chat.see(tk.END)

    def _render_ai_content(self, text):
        if not text.strip(): return
        parts = re.split(r'(```(?:[a-zA-Z0-9_+#-]*)?\n?[\s\S]*?```)', text, flags=re.DOTALL)
        for part in parts:
            fm = re.match(r'```([a-zA-Z0-9_+#-]*)\n?([\s\S]*?)```', part, re.DOTALL)
            if fm:
                lang = fm.group(1).strip() or "code"
                code = fm.group(2)
                self._insert_code_block(lang, code)
            else:
                stripped = part.strip()
                if stripped:
                    self._insert_md_text(stripped)
        self._chat.insert(tk.END, "\n")

    def _insert_md_text(self, text):
        for line in text.split("\n"):
            s = line.strip()
            if not s:
                self._chat.insert(tk.END, "\n"); continue
            if s.startswith("### "):
                self._chat.insert(tk.END, f"\n  {s[4:]}\n", "ai_h3")
            elif s.startswith("## "):
                self._chat.insert(tk.END, f"\n  {s[3:]}\n", "ai_h2")
            elif s.startswith("# "):
                self._chat.insert(tk.END, f"\n  {s[2:]}\n", "ai_h1")
            elif s.startswith("> "):
                self._chat.insert(tk.END, f"\n  \u258c {s[2:]}", "ai_quote")
            elif re.match(r'^[-*+] ', s):
                self._chat.insert(tk.END, "\n  \u2022 ")
                self._insert_inline(s[2:])
            elif re.match(r'^\d+\. ', s):
                self._chat.insert(tk.END, "\n  ")
                self._insert_inline(s)
            elif s.startswith("---"):
                self._chat.insert(tk.END, "\n  " + "\u2500"*34 + "\n", "sep")
            else:
                self._chat.insert(tk.END, "\n  ")
                self._insert_inline(s)

    def _insert_inline(self, text):
        parts = re.split(r'(`[^`]+`|\*\*[^*]+\*\*)', text)
        for p in parts:
            if p.startswith("`") and p.endswith("`"):
                self._chat.insert(tk.END, p[1:-1], "inline_code")
            elif p.startswith("**") and p.endswith("**"):
                self._chat.insert(tk.END, p[2:-2], "ai_h3")
            else:
                self._chat.insert(tk.END, p, "ai_text")

    def _insert_code_block(self, lang, code):
        C = self.app.C
        lang_name = LANG_DISPLAY.get(lang, lang.capitalize() if lang else "Code")
        self._chat.insert(tk.END, f"\n  \u2500\u2500\u2500 {lang_name} ", "code_lang")
        self._chat.insert(tk.END, "\n")
        if code.strip():
            self._chat.insert(tk.END, code.rstrip(), "code_text")
            self._chat.insert(tk.END, "\n")
        self._chat.insert(tk.END, "  ")
        code_c = code.strip()
        if code_c:
            apply_btn = tk.Button(self._chat,
                text=" \u2197 Apply to file ",
                font=("Segoe UI", 8, "bold"),
                fg=C["apply_fg"], bg=C["apply_bg"],
                activebackground=C["border"],
                relief=tk.FLAT, bd=0, cursor="hand2", pady=4,
                command=lambda c=code_c: self._apply_to_editor(c))
            self._chat.window_create(tk.END, window=apply_btn)
            self._chat.insert(tk.END, "  ")
            copy_btn = tk.Button(self._chat,
                text=" \U0001f4cb Copy ",
                font=("Segoe UI", 8),
                fg=C["copy_fg"], bg=C["chat_ai"],
                activebackground=C["border"],
                relief=tk.FLAT, bd=0, cursor="hand2", pady=4,
                command=lambda c=code_c: self._copy_code(c))
            self._chat.window_create(tk.END, window=copy_btn)
        self._chat.insert(tk.END, "\n\n")

    def _show_tool_msg(self, result_str, apply_c=None):
        C = self.app.C
        self._chat.config(state="normal")
        self._chat.insert(tk.END, "\n  TOOL  ", "tool_lbl")
        self._chat.insert(tk.END, "\n")
        lines = result_str.split("\n")
        for line in lines[:20]:
            self._chat.insert(tk.END, f"  {line}\n", "tool_text")
        if len(lines) > 20:
            self._chat.insert(tk.END, f"  \u2026 +{len(lines)-20} lines\n", "sys_text")
        if apply_c:
            self._chat.insert(tk.END, "  ")
            ac = apply_c
            btn = tk.Button(self._chat, text=" \u2197 Apply to file ",
                font=("Segoe UI", 8, "bold"),
                fg=C["apply_fg"], bg=C["apply_bg"],
                activebackground=C["border"],
                relief=tk.FLAT, bd=0, cursor="hand2", pady=4,
                command=lambda c=ac: self._apply_to_editor(c))
            self._chat.window_create(tk.END, window=btn)
            self._chat.insert(tk.END, "\n")
        self._chat.insert(tk.END, "\n")
        self._chat.config(state="disabled")
        self._chat.see(tk.END)

    def _chat_err(self, msg):
        self._cw(f"\n  Error: {msg}", "err_text")

    def _apply_to_editor(self, code):
        if self._ide and self._ide.active:
            ew = self._ide._tabs.get(self._ide.active)
            if ew:
                ew.set_content(code)
                Toast(self.app.root, "Applied to editor", color=self.app.C["green"])

    def _copy_code(self, code):
        try:
            self.app.root.clipboard_clear()
            self.app.root.clipboard_append(code)
            Toast(self.app.root, "Copied to clipboard")
        except Exception: pass

    def _on_provider_change(self):
        """Update model combobox options when provider changes."""
        p = self._sv_provider.get()
        if p == "local":
            self._model_cb.configure(values=FALLBACK_MODELS)
            self._sv_model.set(self.app.cfg.get("model", FALLBACK_MODELS[0]))
        elif p == "groq":
            models = ["llama-3.3-70b-versatile","llama-3.1-8b-instant",
                      "mixtral-8x7b-32768","gemma2-9b-it"]
            self._model_cb.configure(values=models)
            self._sv_model.set(self.app.cfg.get("groq_model", models[0]))
        elif p == "openrouter":
            models = ["meta-llama/llama-3.2-3b-instruct:free",
                      "google/gemini-2.0-flash-exp:free",
                      "microsoft/phi-3-mini-128k:free",
                      "deepseek/deepseek-r1:free"]
            self._model_cb.configure(values=models)
            self._sv_model.set(self.app.cfg.get("openrouter_model", models[0]))
        # Persist
        self.app.cfg["ai_provider"] = p

    def _build_context(self):
        cwd = os.getcwd()
        ctx = f"Working directory: {cwd}\n"
        if self._ide and self._ide.active:
            ew = self._ide._tabs.get(self._ide.active)
            if ew:
                name = os.path.basename(self._ide.active)
                lang = ew.lang
                code = ew.get_content()
                ctx += f"Open file: {name} ({LANG_DISPLAY.get(lang, lang)})\n"
                ctx += f"```{lang}\n{code[:8000]}\n```\n"
        try:
            items = [x for x in os.listdir(cwd)
                     if not x.startswith(".") and x not in ("__pycache__","node_modules")]
            ctx += "Directory: " + ", ".join(sorted(items)[:20])
        except Exception: pass
        return ctx

    def _quick(self, prefix):
        if not (self._ide and self._ide.active): return
        ew  = self._ide._tabs.get(self._ide.active)
        if not ew: return
        sel  = ew.get_selection()
        code = sel if sel.strip() else ew.get_content()
        if not code.strip(): return
        lang = ew.lang
        msg  = f"{prefix}\n\n```{lang}\n{code[:4000]}\n```"
        self._run_agent(msg, display=prefix.rstrip(":"))

    def _on_enter(self, event):
        if event.state & 0x1: return
        self._send()
        return "break"

    def _send(self):
        msg = self._ai_in.get("1.0", "end-1c").strip()
        if not msg: return
        self._ai_in.delete("1.0", tk.END)
        if self._ide and self._ide.active:
            ew = self._ide._tabs.get(self._ide.active)
            if ew:
                sel = ew.get_selection()
                if sel.strip():
                    msg += f"\n\n(Selected):\n```{ew.lang}\n{sel[:2000]}\n```"
        self._run_agent(msg, display=msg.split("\n")[0][:70])

    def _run_agent(self, message, display=""):
        if self._running: return
        self._running = True; self._cancel = False
        ctx      = self._build_context()
        full_msg = f"{ctx}\n\n{message}"
        self._hist.append({"role": "user", "content": full_msg})
        self._msg_user(display or message[:80])
        self._set_status("\u26a1 Thinking\u2026")
        threading.Thread(target=self._agent_thread, daemon=True).start()

    def _agent_thread(self):
        import time
        for iteration in range(6):
            if self._cancel: break
            self.app.root.after(0, self._begin_ai_bubble)
            time.sleep(0.04)
            full_response = self._llm_stream_sync()
            if full_response is None: break
            self.app.root.after(0, lambda r=full_response: self._end_ai_bubble(r))
            tools = parse_tools(full_response)
            if not tools:
                self._hist.append({"role": "assistant", "content": full_response})
                break
            self._hist.append({"role": "assistant", "content": full_response})
            tool_results = []
            for tool in tools:
                if self._cancel: break
                v = tool["verb"]
                self.app.root.after(0, lambda v=v: self._set_status(f"\u26a1 Running {v}\u2026"))
                result_str, apply_c = exec_tool(tool, os.getcwd())
                rs = result_str; ac = apply_c
                self.app.root.after(0, lambda r=rs, c=ac: self._show_tool_msg(r, apply_c=c))
                if apply_c is None:
                    tool_results.append(result_str)
                time.sleep(0.05)
            if tool_results:
                self._hist.append({
                    "role":    "user",
                    "content": "[Tool results]\n" + "\n\n---\n\n".join(tool_results)
                })
                time.sleep(0.1)
            else:
                break
        self.app.root.after(0, self._on_done)

    def _llm_stream_sync(self):
        """Route to local Ollama or cloud provider based on config."""
        provider = self.app.cfg.get("ai_provider", "local")
        if provider == "local":
            return self._llm_local()
        else:
            return self._llm_cloud(provider)

    def _llm_local(self):
        base  = self.app.cfg.get("ollama_base_url", "http://localhost:11434")
        model = self._sv_model.get()
        full  = []
        try:
            msgs = [{"role": "system", "content": AGENT_SYSTEM}] + self._hist[-20:]
            resp = requests.post(
                f"{base}/api/chat",
                json={"model": model, "messages": msgs, "stream": True,
                      "options": {"temperature": 0.15, "num_ctx": 32768}},
                stream=True, timeout=180)
            if resp.status_code != 200:
                self.app.root.after(0, lambda: self._chat_err(f"Ollama HTTP {resp.status_code}"))
                return None
            for line in resp.iter_lines():
                if self._cancel: break
                if not line: continue
                try:
                    tok = json.loads(line).get("message", {}).get("content", "")
                    if tok:
                        full.append(tok); t = tok
                        self.app.root.after(0, lambda t=t: self._stream_tok(t))
                except Exception: pass
        except Exception as e:
            self.app.root.after(0, lambda: self._chat_err(str(e)))
            return None
        return "".join(full)

    def _llm_cloud(self, provider):
        api_key = self.app.cfg.get(f"{provider}_api_key", "").strip()
        model   = self.app.cfg.get(f"{provider}_model",   "").strip()
        if not api_key:
            self.app.root.after(0, lambda: self._chat_err(
                f"No {provider} API key — add it in Settings."))
            return None
        full = []
        try:
            client = CloudAIClient(provider, api_key, model)
            msgs   = [{"role": "system", "content": AGENT_SYSTEM}] + self._hist[-20:]
            for tok in client.stream(msgs, cancel_flag=lambda: self._cancel):
                if self._cancel: break
                full.append(tok); t = tok
                self.app.root.after(0, lambda t=t: self._stream_tok(t))
        except Exception as e:
            self.app.root.after(0, lambda: self._chat_err(f"{provider}: {e}"))
            return None
        return "".join(full)

    def _on_done(self):
        self._running = False; self._cancel = False
        self._set_status("")


# ══════════════════════════════════════════════════════════════════════════════
#  IDE PANEL
# ══════════════════════════════════════════════════════════════════════════════
class IDEPanel:
    """Full IDE: activity bar, file explorer, tabbed editor, AI panel, status bar."""

    def __init__(self, parent, app):
        self.app   = app
        self.frame = tk.Frame(parent, bg=app.C["bg"])
        self._tabs = {}
        self.active = None
        self._tab_widgets = {}
        self._tree_visible = True
        self._build()

    def _build(self):
        C = self.app.C
        # Status bar (bottom, VS Code style)
        self._sb = tk.Frame(self.frame, bg=C["statusbar"], height=24)
        self._sb.pack(side=tk.BOTTOM, fill=tk.X)
        self._sb.pack_propagate(False)
        self._st_branch = tk.Label(self._sb, text="",
            font=("Segoe UI",8), fg=C["statusfg"], bg=C["statusbar"], padx=10)
        self._st_branch.pack(side=tk.LEFT)
        self._st_file = tk.Label(self._sb, text="  No file open",
            font=("Segoe UI",8), fg=C["statusfg"], bg=C["statusbar"])
        self._st_file.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._st_agent = tk.Label(self._sb, text="",
            font=("Segoe UI",8), fg=C["green"], bg=C["statusbar"], padx=10)
        self._st_agent.pack(side=tk.RIGHT)
        self._st_lang = tk.Label(self._sb, text="Plain Text",
            font=("Segoe UI",8), fg=C["statusfg"], bg=C["statusbar"], padx=12)
        self._st_lang.pack(side=tk.RIGHT)
        self._st_pos = tk.Label(self._sb, text="Ln 1, Col 1",
            font=("Segoe UI",8), fg=C["statusfg"], bg=C["statusbar"], padx=12)
        self._st_pos.pack(side=tk.RIGHT)
        self._update_git_branch()

        # Body = activity bar + paned window
        body = tk.Frame(self.frame, bg=C["bg"])
        body.pack(fill=tk.BOTH, expand=True)

        # Activity bar (46px, leftmost)
        self._actbar = tk.Frame(body, bg=C["actbar"], width=46)
        self._actbar.pack(side=tk.LEFT, fill=tk.Y)
        self._actbar.pack_propagate(False)
        self._build_actbar()

        # Paned window
        self._pw = tk.PanedWindow(body, orient=tk.HORIZONTAL,
            sashwidth=4, bg=C["border"], bd=0, sashrelief=tk.FLAT)
        self._pw.pack(fill=tk.BOTH, expand=True)

        # Explorer panel
        self._exp_frame = tk.Frame(self._pw, bg=C["panel"])
        self._pw.add(self._exp_frame, minsize=140, width=210)
        self._build_explorer(self._exp_frame)

        # Editor area
        self._ed_frame = tk.Frame(self._pw, bg=C["bg"])
        self._pw.add(self._ed_frame, minsize=300)
        self._build_editor_area(self._ed_frame)

        # AI panel
        self._ai_frame = tk.Frame(self._pw, bg=C["panel"])
        self._pw.add(self._ai_frame, minsize=260, width=350)
        self._ai = AIPanel(self._ai_frame, self.app, self)
        self._ai.frame.pack(fill=tk.BOTH, expand=True)

        self.new_file()

    # ── Activity bar ───────────────────────────────────────────────────────────
    def _build_actbar(self):
        C = self.app.C
        tk.Frame(self._actbar, bg=C["border"], height=1).pack(fill=tk.X, pady=(6,4))
        self._act_btns = {}
        for key, icon in [("explorer","\U0001f5c2"),("search","\U0001f50d")]:
            b = tk.Button(self._actbar, text=icon, font=("Segoe UI",15),
                fg=C["accent"] if key=="explorer" else C["dim"],
                bg=C["actbar"], activebackground=C["sidebar"],
                relief=tk.FLAT, bd=0, cursor="hand2", width=3, pady=10,
                command=lambda k=key: self._act_toggle(k))
            b.pack(fill=tk.X, pady=1)
            self._act_btns[key] = b
        tk.Button(self._actbar, text="\u2699", font=("Segoe UI",13),
            fg=C["dim"], bg=C["actbar"], activebackground=C["sidebar"],
            relief=tk.FLAT, bd=0, cursor="hand2", width=3, pady=10,
            command=lambda: self.app.show_view("settings")
        ).pack(side=tk.BOTTOM, fill=tk.X)

    def _act_toggle(self, key):
        C = self.app.C
        if key == "explorer":
            if self._tree_visible:
                self._pw.forget(self._exp_frame); self._tree_visible = False
                self._act_btns[key].config(fg=C["dim"])
            else:
                self._pw.add(self._exp_frame, before=self._ed_frame, minsize=140, width=210)
                self._tree_visible = True
                self._act_btns[key].config(fg=C["accent"])
        elif key == "search":
            if self.active and self.active in self._tabs:
                self._tabs[self.active].find_bar.show()

    # ── Explorer ───────────────────────────────────────────────────────────────
    def _build_explorer(self, parent):
        C = self.app.C
        hdr = tk.Frame(parent, bg=C["panel"]); hdr.pack(fill=tk.X)
        tk.Label(hdr, text="  EXPLORER", font=("Segoe UI",8,"bold"),
            fg=C["dim"], bg=C["panel"], anchor=tk.W, pady=8
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(hdr, text="\U0001f4c2", font=("Segoe UI",10), fg=C["dim"], bg=C["panel"],
            relief=tk.FLAT, bd=0, cursor="hand2", activebackground=C["border"],
            command=self._open_folder).pack(side=tk.RIGHT, padx=6)
        tk.Frame(parent, bg=C["border"], height=1).pack(fill=tk.X)
        self._cwd_lbl = tk.Label(parent, text="  "+os.path.basename(os.getcwd()),
            font=("Segoe UI",9,"bold"), fg=C["text"], bg=C["panel"],
            anchor=tk.W, pady=5, cursor="hand2")
        self._cwd_lbl.pack(fill=tk.X)
        self._cwd_lbl.bind("<Button-1>", lambda e: self._open_folder())
        style = ttk.Style()
        style.configure("FT.Treeview",
            background=C["panel"], foreground=C["text"],
            fieldbackground=C["panel"], borderwidth=0,
            font=("Segoe UI", 9), rowheight=22, indent=14)
        style.configure("FT.Treeview.Heading",
            background=C["panel"], foreground=C["dim"], relief="flat")
        style.map("FT.Treeview",
            background=[("selected", C.get("list_sel", C["selection"])),
                        ("!selected", C["panel"])],
            foreground=[("selected", C["text"]), ("!selected", C["text"])])
        wrap = tk.Frame(parent, bg=C["panel"]); wrap.pack(fill=tk.BOTH, expand=True)
        self._tree = ttk.Treeview(wrap, style="FT.Treeview", show="tree", selectmode="browse")
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=self._tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree_paths = {}
        self._tree.bind("<Double-1>", self._on_tree)
        self._tree.bind("<Return>",   self._on_tree)
        self._tree.bind("<Button-3>", self._on_tree_ctx)
        self._populate_tree(os.getcwd())
        brow = tk.Frame(parent, bg=C["panel"]); brow.pack(fill=tk.X, pady=4, padx=6)
        for txt, cmd in [("+ File", self.new_file), ("+ Folder", self._new_folder)]:
            tk.Button(brow, text=txt, font=("Segoe UI",8), fg=C["dim"], bg=C["panel"],
                relief=tk.FLAT, bd=0, cursor="hand2", activebackground=C["border"],
                padx=8, pady=3, command=cmd).pack(side=tk.LEFT, padx=2)

    def _populate_tree(self, path):
        """Async directory scan — won't freeze UI on large directories."""
        self._tree.delete(*self._tree.get_children())
        self._tree_paths.clear()
        def _scan():
            try:
                git_st = self._get_git_status(path)
                items  = sorted(os.listdir(path),
                    key=lambda x: (not os.path.isdir(os.path.join(path,x)), x.lower()))
                rows = []
                for name in items[:500]:
                    if name.startswith(".") and name not in (".env",".gitignore"): continue
                    full  = os.path.join(path, name)
                    isdir = os.path.isdir(full)
                    ext   = os.path.splitext(name)[1].lower()
                    icon  = "\U0001f4c1 " if isdir else (FILE_ICONS.get(ext,"\U0001f4c4")+" ")
                    rel   = os.path.relpath(full, path)
                    gst   = git_st.get(name, git_st.get(rel, ""))
                    gmark = f" {gst}" if gst else ""
                    rows.append((f"  {icon}{name}{gmark}", full, gst))
                self.app.root.after(0, lambda r=rows, g=git_st: self._insert_tree_rows(r))
            except Exception: pass
        threading.Thread(target=_scan, daemon=True).start()

    def _insert_tree_rows(self, rows):
        for text, full, gst in rows:
            iid = self._tree.insert("","end", text=text)
            self._tree_paths[iid] = full
            if gst == "M":
                self._tree.tag_configure("M", foreground=self.app.C["yellow"])
                self._tree.item(iid, tags=("M",))
            elif gst == "?":
                self._tree.tag_configure("U", foreground=self.app.C["green"])
                self._tree.item(iid, tags=("U",))

    def _get_git_status(self, path):
        try:
            r = subprocess.run(["git","status","--porcelain"],
                               cwd=path, capture_output=True, text=True, timeout=3)
            if r.returncode != 0: return {}
            st = {}
            for line in r.stdout.splitlines():
                if len(line) < 4: continue
                xy = line[:2]
                fname = line[3:].strip().split("->")[-1].strip()
                fname = os.path.basename(fname)
                if "M" in xy: st[fname] = "M"
                elif "?" in xy: st[fname] = "?"
                elif "A" in xy: st[fname] = "A"
            return st
        except Exception: return {}

    def _update_git_branch(self):
        try:
            r = subprocess.run(["git","branch","--show-current"],
                               cwd=os.getcwd(), capture_output=True, text=True, timeout=2)
            branch = r.stdout.strip()
            self._st_branch.config(text=f"  \u2387  {branch}" if branch else "")
        except Exception:
            self._st_branch.config(text="")

    def _on_tree(self, _=None):
        sel = self._tree.selection()
        if not sel: return
        path = self._tree_paths.get(sel[0])
        if not path: return
        if os.path.isdir(path):
            os.chdir(path)
            self._cwd_lbl.config(text="  "+os.path.basename(path))
            self._populate_tree(path); self._update_git_branch()
        else:
            self.open_file(path)

    def _on_tree_ctx(self, event):
        item = self._tree.identify_row(event.y)
        if not item: return
        path = self._tree_paths.get(item, "")
        C    = self.app.C
        menu = tk.Menu(self.app.root, tearoff=0,
                       bg=C["panel"], fg=C["text"], activebackground=C["selection"])
        if path and os.path.isfile(path):
            menu.add_command(label="Open", command=lambda: self.open_file(path))
            menu.add_separator()
        menu.add_command(label="Rename", command=lambda: self._rename(path))
        menu.add_command(label="Delete", command=lambda: self._delete(path))
        menu.add_separator()
        menu.add_command(label="Reveal in Explorer", command=lambda: self._reveal(path))
        menu.tk_popup(event.x_root, event.y_root)

    def _rename(self, path):
        old = os.path.basename(path)
        new = simpledialog.askstring("Rename","New name:",initialvalue=old,parent=self.app.root)
        if new and new != old:
            try:
                new_path = os.path.join(os.path.dirname(path), new)
                os.rename(path, new_path)
                self._populate_tree(os.getcwd())
                if path in self._tabs:
                    ew = self._tabs.pop(path)
                    ew.path = new_path
                    self._tabs[new_path] = ew
                    if self.active == path: self.active = new_path
                    if path in self._tab_widgets:
                        self._tab_widgets[new_path] = self._tab_widgets.pop(path)
                    self._refresh_tab_labels()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self.app.root)

    def _delete(self, path):
        name = os.path.basename(path)
        if not messagebox.askyesno("Delete",f"Delete '{name}'?",parent=self.app.root): return
        try:
            if os.path.isdir(path):
                import shutil; shutil.rmtree(path)
            else:
                os.remove(path)
            self._populate_tree(os.getcwd())
            if path in self._tabs: self.close_tab(path, force=True)
        except Exception as e:
            messagebox.showerror("Error",str(e),parent=self.app.root)

    def _reveal(self, path):
        try:
            if platform.system()=="Windows": subprocess.Popen(["explorer","/select,",path])
            elif platform.system()=="Darwin": subprocess.Popen(["open","-R",path])
            else: subprocess.Popen(["xdg-open",os.path.dirname(path)])
        except Exception: pass

    def _open_folder(self):
        p = filedialog.askdirectory(title="Open Folder", parent=self.app.root)
        if p:
            os.chdir(p)
            self._cwd_lbl.config(text="  "+os.path.basename(p))
            self._populate_tree(p); self._update_git_branch()

    def _new_folder(self):
        n = simpledialog.askstring("New Folder","Name:",parent=self.app.root)
        if n:
            try:
                os.makedirs(os.path.join(os.getcwd(),n), exist_ok=True)
                self._populate_tree(os.getcwd())
            except Exception as e:
                messagebox.showerror("Error",str(e),parent=self.app.root)

    # ── Editor area ────────────────────────────────────────────────────────────
    def _build_editor_area(self, parent):
        C = self.app.C
        self._tabbar = tk.Frame(parent, bg=C["tabbg"], height=34)
        self._tabbar.pack(fill=tk.X); self._tabbar.pack_propagate(False)
        tk.Button(self._tabbar, text=" \uff0b ", font=("Segoe UI",11),
            fg=C["dim"], bg=C["tabbg"], relief=tk.FLAT, bd=0, cursor="hand2",
            activebackground=C["border"], command=self.new_file
            ).pack(side=tk.RIGHT, padx=4)
        tk.Frame(parent, bg=C["border"], height=1).pack(fill=tk.X)
        self._eswap = tk.Frame(parent, bg=C["bg"])
        self._eswap.pack(fill=tk.BOTH, expand=True)
        self._empty_lbl = tk.Label(self._eswap,
            text="Open a file \u00b7  Ctrl+N new  \u00b7  Ctrl+O open  \u00b7  Ctrl+Shift+P commands",
            font=("Segoe UI",11), fg=C["dim"], bg=C["bg"])
        self._empty_lbl.place(relx=.5, rely=.5, anchor="center")

    # ── Tab management ─────────────────────────────────────────────────────────
    def new_file(self):
        n = sum(1 for p in self._tabs if p.startswith("untitled"))+1
        self._create_tab(f"untitled-{n}","","text")

    def open_file(self, path):
        if path in self._tabs: self._activate(path); return
        try:
            size = os.path.getsize(path)
            if size > 5_000_000:   # 5 MB
                mb = size / 1_048_576
                if not messagebox.askyesno(
                        "Large File",
                        f"'{os.path.basename(path)}' is {mb:.1f} MB — may be slow.\nOpen anyway?",
                        parent=self.app.root):
                    return
            with open(path,"r",encoding="utf-8",errors="replace") as f: content=f.read()
            lang = LANG_EXT.get(os.path.splitext(path)[1].lower(),"text")
            self._create_tab(path, content, lang)
        except Exception as e:
            messagebox.showerror("Open",str(e),parent=self.app.root)

    def save_file(self, path=None):
        target = path or self.active
        if not target or target not in self._tabs: return
        ew = self._tabs[target]
        if target.startswith("untitled"):
            new_path = filedialog.asksaveasfilename(parent=self.app.root,
                defaultextension=".py",
                filetypes=[("Python","*.py"),("JS","*.js"),("TS","*.ts"),
                           ("HTML","*.html"),("CSS","*.css"),("JSON","*.json"),
                           ("Markdown","*.md"),("Text","*.txt"),("All","*.*")])
            if not new_path: return
            self._tabs[new_path] = self._tabs.pop(target)
            self._tab_widgets[new_path] = self._tab_widgets.pop(target, {})
            ew.path = new_path
            if self.active == target: self.active = new_path
            target = new_path
        try:
            with open(target,"w",encoding="utf-8") as f: f.write(ew.get_content())
            ew.modified = False
            self._refresh_tab_labels(); self._upd_status()
            self._populate_tree(os.getcwd())
            Toast(self.app.root, f"Saved: {os.path.basename(target)}")
        except Exception as e:
            messagebox.showerror("Save",str(e),parent=self.app.root)

    def close_tab(self, path, force=False):
        if path not in self._tabs: return
        ew = self._tabs[path]
        if ew.modified and not force:
            if not messagebox.askyesno("Unsaved Changes",
                    f"'{os.path.basename(path)}' has unsaved changes. Close anyway?",
                    parent=self.app.root): return
        ew.destroy()
        td = self._tab_widgets.get(path, {})
        if "frame" in td: td["frame"].destroy()
        del self._tabs[path]
        if path in self._tab_widgets: del self._tab_widgets[path]
        self.active = None
        if self._tabs: self._activate(list(self._tabs)[-1])
        else: self.new_file()

    def _create_tab(self, path, content, lang):
        C    = self.app.C
        name = os.path.basename(path)
        ext  = os.path.splitext(path)[1].lower()
        icon = FILE_ICONS.get(ext,"") if not path.startswith("untitled") else ""
        # Tab button
        tbf  = tk.Frame(self._tabbar, bg=C["tabbg"]); tbf.pack(side=tk.LEFT)
        # Top border indicator (like VS Code active tab line)
        ind  = tk.Frame(tbf, bg=C["tabbg"], height=2)
        ind.pack(side=tk.TOP, fill=tk.X)
        lbl  = tk.Label(tbf,
            text=(f"  {icon} {name}  " if icon else f"  {name}  "),
            font=("Segoe UI", 9), fg=C["dim"], bg=C["tabbg"], cursor="hand2", pady=7)
        lbl.pack(side=tk.LEFT)
        xbtn = tk.Label(tbf, text="\u00d7", font=("Segoe UI", 9),
            fg=C["dim"], bg=C["tabbg"], cursor="hand2", padx=5)
        xbtn.pack(side=tk.LEFT)
        sep  = tk.Frame(self._tabbar, bg=C["border"], width=1)
        sep.pack(side=tk.LEFT, fill=tk.Y, pady=4)
        # Editor widget
        ew = EditorWidget(self._eswap, self.app, path, content, lang)
        ew.on_modified = self._on_ew_modified
        ew.on_cursor   = self._on_ew_cursor
        ew.on_save     = self.save_file
        ew.on_new      = self.new_file
        ew.on_open     = self._open_dialog
        ew.on_close    = self.close_tab
        ew.on_palette  = self._open_palette
        self._tabs[path]        = ew
        self._tab_widgets[path] = {"frame":tbf,"lbl":lbl,"xbtn":xbtn,"sep":sep,"indicator":ind}
        for w in (tbf, lbl):
            w.bind("<Button-1>", lambda e, p=path: self._activate(p))
        xbtn.bind("<Button-1>", lambda e, p=path: self.close_tab(p))
        xbtn.bind("<Enter>",    lambda e: xbtn.config(fg=C["red"]))
        xbtn.bind("<Leave>",    lambda e: xbtn.config(fg=C["dim"]))
        self._activate(path)

    def _activate(self, path):
        C = self.app.C
        for p, ew in self._tabs.items():
            ew.pack_forget()
            td = self._tab_widgets.get(p, {})
            for k in ("frame","lbl","xbtn"):
                w = td.get(k)
                if w: w.config(bg=C["tabbg"])
            if td.get("lbl"):  td["lbl"].config(fg=C["dim"])
            if td.get("indicator"): td["indicator"].config(bg=C["tabbg"])
        self.active = path; ew = self._tabs[path]; td = self._tab_widgets.get(path,{})
        ew.pack(fill=tk.BOTH, expand=True)
        for k in ("frame","lbl","xbtn"):
            w = td.get(k)
            if w: w.config(bg=C["tabactive"])
        if td.get("lbl"): td["lbl"].config(fg=C["text"])
        # VS Code-style active tab indicator (coloured top border)
        ind = td.get("indicator")
        if ind: ind.config(bg=C.get("tabline", C["accent"]))
        self._empty_lbl.place_forget()
        ew.focus(); self._upd_status()

    def _refresh_tab_labels(self):
        C = self.app.C
        for path, ew in self._tabs.items():
            td  = self._tab_widgets.get(path,{})
            lbl = td.get("lbl")
            if not lbl: continue
            name = os.path.basename(path)
            ext  = os.path.splitext(path)[1].lower()
            icon = FILE_ICONS.get(ext,"") if not path.startswith("untitled") else ""
            dot  = "\u25cf " if ew.modified else "  "
            txt  = (f"  {dot}{icon} {name}  " if icon else f"  {dot}{name}  ")
            lbl.config(text=txt)

    def _on_ew_modified(self, path): self._refresh_tab_labels()
    def _on_ew_cursor(self, line, col): self._st_pos.config(text=f"Ln {line}, Col {col}")

    def _upd_status(self):
        if not self.active: return
        ew   = self._tabs.get(self.active)
        if not ew: return
        name = os.path.basename(self.active)
        lang = LANG_DISPLAY.get(ew.lang, ew.lang.capitalize())
        self._st_file.config(
            text=f"  {self.active if not self.active.startswith('untitled') else name}")
        self._st_lang.config(text=lang)

    def _open_dialog(self):
        p = filedialog.askopenfilename(parent=self.app.root,
            filetypes=[("Code","*.py *.js *.ts *.jsx *.tsx *.html *.css *.json "
                               "*.sh *.bat *.md *.txt *.rs *.go *.c *.cpp *.h *.yaml *.yml *.toml"),
                       ("All","*.*")])
        if p: self.open_file(p)

    def _open_palette(self):
        C = self.app.C
        commands = [
            {"label":"New File",             "key":"Ctrl+N",       "action":self.new_file},
            {"label":"Open File",            "key":"Ctrl+O",       "action":self._open_dialog},
            {"label":"Save File",            "key":"Ctrl+S",       "action":lambda:self.save_file()},
            {"label":"Close Tab",            "key":"Ctrl+W",       "action":lambda:self.close_tab(self.active) if self.active else None},
            {"label":"Find in File",         "key":"Ctrl+F",       "action":lambda:self._tabs[self.active].find_bar.show() if self.active else None},
            {"label":"Find and Replace",     "key":"Ctrl+H",       "action":lambda:self._tabs[self.active].find_bar.show(with_replace=True) if self.active else None},
            {"label":"Go to Line",           "key":"Ctrl+G",       "action":lambda:self._tabs[self.active]._goto_line() if self.active else None},
            {"label":"Toggle Comment",       "key":"Ctrl+/",       "action":lambda:self._tabs[self.active]._toggle_comment() if self.active else None},
            {"label":"Duplicate Line",       "key":"Ctrl+D",       "action":lambda:self._tabs[self.active]._dup_line() if self.active else None},
            {"label":"Toggle Explorer",      "key":"",             "action":lambda:self._act_toggle("explorer")},
            {"label":"Open Folder",          "key":"",             "action":self._open_folder},
            {"label":"Zoom In",              "key":"Ctrl++",       "action":lambda:self._tabs[self.active]._zoom(1) if self.active else None},
            {"label":"Zoom Out",             "key":"Ctrl+-",       "action":lambda:self._tabs[self.active]._zoom(-1) if self.active else None},
            {"label":"Reset Zoom",           "key":"Ctrl+0",       "action":lambda:self._tabs[self.active]._zoom(0) if self.active else None},
            {"label":"Settings",             "key":"",             "action":lambda:self.app.show_view("settings")},
            {"label":"Switch to Terminal",   "key":"",             "action":lambda:self.app._set_mode("terminal")},
            {"label":"AI: Explain Code",     "key":"",             "action":lambda:self._ai._quick("Explain what this code does:")},
            {"label":"AI: Fix Bugs",         "key":"",             "action":lambda:self._ai._quick("Find and fix all bugs:")},
            {"label":"AI: Write Tests",      "key":"",             "action":lambda:self._ai._quick("Write comprehensive tests:")},
            {"label":"AI: Add Comments",     "key":"",             "action":lambda:self._ai._quick("Add helpful comments:")},
            {"label":"AI: Refactor",         "key":"",             "action":lambda:self._ai._quick("Refactor for best practices:")},
            {"label":"AI: Optimize",         "key":"",             "action":lambda:self._ai._quick("Optimize performance:")},
        ]
        CommandPalette(self.app.root, C, commands)

    def on_focus(self):
        self._act_btns["explorer"].config(fg=self.app.C["accent"])
        if self.active and self.active in self._tabs:
            self.app.root.after(50, self._tabs[self.active].focus)


# ══════════════════════════════════════════════════════════════════════════════
#  TERMINAL PANEL
# ══════════════════════════════════════════════════════════════════════════════
FORTUNES = [
    "A bug in the hand is worth two in production.",
    "All code is legacy code the moment you write it.",
    "It works on my machine \u2014 ship the machine.",
    "Real programmers count from 0.",
    "sudo make me a sandwich.",
    "There are only two hard things: cache invalidation and naming things.",
    "The best code is no code at all.",
    "git blame yourself.",
    "Premature optimisation is the root of all evil.",
    "Works? Ship it. Breaks? Revert.",
    "// TODO: write better comments",
    "It's not a bug, it's an undocumented feature.",
]

class TerminalPanel:
    def __init__(self, parent, app):
        self.app   = app
        self.frame = tk.Frame(parent, bg=app.C["bg"])
        self._init(); self._build(); self._bind()
        self._reg_cmds(); self._welcome(); self._chk_ollama()

    def _init(self):
        cfg = self.app.cfg
        self.model     = cfg.get("model",           DEFAULT_CFG["model"])
        self.streaming = cfg.get("streaming",        True)
        self.base      = cfg.get("ollama_base_url",  "http://localhost:11434")
        self.history   = []; self.last_ai = ""; self.ollama_ok = False
        self.is_stream = False; self._cancel = False
        self.hcmds = []; self.hidx = -1; self.hbuf = ""

    def _build(self):
        C = self.app.C
        self._sb = tk.Frame(self.frame, bg=C["statusbar"], height=24)
        self._sb.pack(fill=tk.X); self._sb.pack_propagate(False)
        self.slbl = tk.Label(self._sb,
            text=f"V-Agent v{VERSION} \u2502 {self.model} \u2502 \u25cb Checking\u2026",
            bg=C["statusbar"], fg=C["statusfg"], font=self.app.sf, anchor=tk.W, padx=10)
        self.slbl.pack(side=tk.LEFT)
        self.clbl = tk.Label(self._sb, text="ctx: 0",
            bg=C["statusbar"], fg=C["statusfg"], font=self.app.sf, padx=10)
        self.clbl.pack(side=tk.RIGHT)
        ow = tk.Frame(self.frame, bg=C["bg"]); ow.pack(fill=tk.BOTH, expand=True)
        self.out = tk.Text(ow, bg=C["bg"], fg=C["text"],
            insertbackground=C["purple"], font=self.app.tf,
            wrap=tk.WORD, relief=tk.FLAT, borderwidth=0,
            padx=14, pady=10, state="disabled",
            spacing1=2, spacing2=1, spacing3=2)
        self.out.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(ow, orient=tk.VERTICAL, command=self.out.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y); self.out.configure(yscrollcommand=sb.set)
        self._inp = tk.Frame(self.frame, bg=C.get("input_bg",C["panel"]), height=38)
        self._inp.pack(fill=tk.X); self._inp.pack_propagate(False)
        self._plbl = tk.Label(self._inp, text="\u279c ",
            bg=C.get("input_bg",C["panel"]), fg=C["accent"], font=self.app.tf)
        self._plbl.pack(side=tk.LEFT, padx=(12,2))
        self.ti = tk.Entry(self._inp, bg=C.get("input_bg",C["bg"]), fg=C["text"],
            insertbackground=C["accent"], font=self.app.tf,
            relief=tk.FLAT, bd=0,
            selectbackground=C["selection"], selectforeground=C["text"])
        self.ti.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,4))
        self._hl = tk.Label(self._inp, text="", bg=C["panel"],
            fg=C["dim"], font=self.app.sf)
        self._hl.pack(side=tk.LEFT, padx=(0,10))
        self._setup_tags()

    def _setup_tags(self):
        C = self.app.C; tf = self.app.tf; tfb = self.app.tfb
        for t, c in [("prompt",C["purple"]),("user",C["blue"]),
                     ("assistant",C["assistant"]),("system",C["cyan"]),
                     ("dim",C["dim"]),("error",C["red"]),("warning",C["yellow"]),
                     ("success",C["green"]),("header",C["accent"]),
                     ("cyan",C["cyan"]),("blue",C["blue"]),("stream",C["assistant"])]:
            self.out.tag_config(t, foreground=c, font=tf)
        self.out.tag_config("header", font=tfb)
        self.out.tag_config("bold",   font=tfb)

    def _bind(self):
        self.ti.bind("<Return>",    self._enter)
        self.ti.bind("<Up>",        self._hup)
        self.ti.bind("<Down>",      self._hdn)
        self.ti.bind("<Tab>",       self._ac)
        self.ti.bind("<Control-c>", lambda e: setattr(self,"_cancel",True) or "break")
        self.ti.bind("<Control-l>", lambda e: self._clr("") or "break")
        self.app.root.bind("<Control-l>",
            lambda e: self._clr("") if self.frame.winfo_ismapped() else None)

    def _w(self, text, tag=None, nl=True):
        self.out.config(state="normal")
        self.out.insert(tk.END, text, tag or "")
        if nl: self.out.insert(tk.END, "\n")
        self.out.see(tk.END); self.out.config(state="disabled")

    def _wp(self, text, tag="success"):
        user = os.environ.get("USERNAME") or os.environ.get("USER") or "user"
        cwd  = os.path.basename(os.getcwd()) or os.getcwd()
        self._w(f"\u250c\u2500({user}@vagent) [{cwd}]", "prompt")
        self._w(f"\u2514\u2500$ {text}", tag)

    def _welcome(self):
        self.out.config(state="normal"); self.out.delete(1.0,tk.END); self.out.config(state="disabled")
        banner = (
            "\n   ______     __  __     __     __   __     __  __\n"
            "  /\\  ___\\   /\\ \\/\\ \\   /\\ \\   /\\ \"-..\\ \\  /\\ \\/\\ \\\n"
            "  \\ \\ \\____  \\ \\ \\_\\ \\  \\ \\ \\  \\ \\ \\-. \\ \\ \\ \\ \\_\\ \\\n"
            "   \\ \\_____\\  \\ \\_____\\  \\ \\_\\  \\ \\_\\\\\\\"\\_\\ \\ \\_____\\\n"
            "    \\/_____/   \\/_____/   \\/_/   \\/_/ \\/_/  \\/_____/"
        )
        self._w(banner, "prompt")
        self._w(f"\n  V-Agent v{VERSION} \u2014 Professional Agentic IDE \u00b7 Voidtune", "header")
        self._w(f"  Model: {self.model}  \u00b7  Streaming: {'on' if self.streaming else 'off'}  \u00b7  100% local", "dim")
        self._w("  Type /help for all commands, or just chat with the AI.\n", "dim")
        self._wp("V-Agent ready", "success"); self._w("")

    def _enter(self, _=None):
        raw = self.ti.get().strip()
        if not raw:
            self._wp("","prompt"); self.app.root.after(10,self.ti.focus_set); return "break"
        self.hcmds.append(raw); self.hidx=len(self.hcmds); self.hbuf=""
        self.ti.delete(0,tk.END); self._wp(raw,"user")
        if raw.startswith("/"):
            parts=raw[1:].split(None,1); cmd=parts[0].lower(); args=parts[1] if len(parts)>1 else ""
            if cmd in self.cmds:
                try: self.cmds[cmd](args)
                except Exception as e: self._w(f"Error: {e}","error")
            else:
                self._w(f"Unknown command: /{cmd}","error")
                self._w("Type /help to see all commands.","dim")
        else: self._ai(raw)
        self.app.root.after(10,self.ti.focus_set); return "break"

    def _hup(self,_=None):
        if not self.hcmds: return "break"
        if self.hidx==len(self.hcmds): self.hbuf=self.ti.get()
        if self.hidx>0:
            self.hidx-=1; self.ti.delete(0,tk.END); self.ti.insert(0,self.hcmds[self.hidx])
        return "break"

    def _hdn(self,_=None):
        if self.hidx<len(self.hcmds)-1:
            self.hidx+=1; self.ti.delete(0,tk.END); self.ti.insert(0,self.hcmds[self.hidx])
        elif self.hidx==len(self.hcmds)-1:
            self.hidx+=1; self.ti.delete(0,tk.END); self.ti.insert(0,self.hbuf)
        return "break"

    def _ac(self,_=None):
        raw=self.ti.get().strip()
        if raw.startswith("/"):
            s=raw[1:].lower(); m=[c for c in self.cmds if c.startswith(s)]
            if len(m)==1: self.ti.delete(0,tk.END); self.ti.insert(0,f"/{m[0]} ")
            elif len(m)>1:
                self._hl.config(text="  ".join(f"/{c}" for c in m[:8]))
                self.app.root.after(2500,lambda:self._hl.config(text=""))
        return "break"

    def _chk_ollama(self):
        def _do():
            try: r=requests.get(f"{self.base}/api/tags",timeout=3); ok=r.status_code==200
            except Exception: ok=False
            self.ollama_ok=ok; self.app.root.after(0,self._rstatus)
        threading.Thread(target=_do,daemon=True).start()

    def _rstatus(self):
        C=self.app.C; ok=self.ollama_ok
        col=C["green"] if ok else C["red"]
        self.slbl.config(
            text=f"V-Agent v{VERSION} \u2502 {self.model} \u2502 {'\u25cf Online' if ok else '\u25cb Offline'}",
            fg=col)
        self.app.update_ollama(ok)

    def _uctx(self):
        c=sum(len(m["content"]) for m in self.history)
        self.clbl.config(text=f"ctx: ~{c//4}tok")

    def _ai(self,msg):
        if not self.ollama_ok: self._w("Ollama offline \u2014 run: ollama serve","error"); return
        if self.is_stream: self._w("Still streaming \u2014 Ctrl+C to cancel.","warning"); return
        self.history.append({"role":"user","content":msg})
        if len(self.history)>40: self.history=self.history[-40:]
        self._uctx(); self.is_stream=True; self._cancel=False
        self._w("\u2514\u2500 ","prompt",nl=False)
        self.out.config(state="normal"); self.out.insert(tk.END,"\n"); self.out.config(state="disabled")
        def _s():
            full=[]
            try:
                msgs=[{"role":"system","content":"You are V-Agent, an expert local AI coding assistant. Be concise, accurate, and prefer code examples. Format all code in markdown code blocks with the language name."}]+self.history
                resp=requests.post(f"{self.base}/api/chat",
                    json={"model":self.model,"messages":msgs,"stream":self.streaming,
                          "options":{"temperature":0.7,"num_ctx":32768}},
                    stream=self.streaming,timeout=180)
                if resp.status_code!=200:
                    self.app.root.after(0,lambda:self._w(f"Error {resp.status_code}","error")); return
                if self.streaming:
                    for line in resp.iter_lines():
                        if self._cancel: break
                        if not line: continue
                        try:
                            tok=json.loads(line).get("message",{}).get("content","")
                            if tok:
                                full.append(tok); t=tok
                                self.app.root.after(0,lambda t=t:(
                                    self.out.config(state="normal"),
                                    self.out.insert(tk.END,t,"stream"),
                                    self.out.see(tk.END),
                                    self.out.config(state="disabled")))
                        except Exception: pass
                else:
                    tok=resp.json().get("message",{}).get("content",""); full.append(tok)
                    self.app.root.after(0,lambda t=tok:(
                        self.out.config(state="normal"),
                        self.out.insert(tk.END,t,"stream"),
                        self.out.see(tk.END),
                        self.out.config(state="disabled")))
            except requests.RequestException as e:
                self.app.root.after(0,lambda:self._w(f"Connection error: {e}","error"))
            finally:
                combined="".join(full); self.last_ai=combined
                self.history.append({"role":"assistant","content":combined})
                def _d():
                    self.is_stream=False; self._cancel=False
                    self._w("\n","dim",nl=False); self._uctx()
                self.app.root.after(0,_d)
        threading.Thread(target=_s,daemon=True).start()

    def _reg_cmds(self):
        self.cmds={
            "help":self._help,"clear":self._clr,
            "clear-history":lambda _:(self.history.clear(),self._uctx(),self._w("History cleared.","success")),
            "about":lambda _:(
                self._w(f"\nV-Agent v{VERSION} \u2014 Professional Agentic IDE","header"),
                self._w("  Voidtune Ecosystem \u00b7 Powered by Ollama \u00b7 100% local","dim"),
                self._w("  Zero telemetry. Your code never leaves your machine.\n","dim")),
            "date":lambda _:(
                self._w(f"Date : {datetime.datetime.now().strftime('%Y-%m-%d')}","system"),
                self._w(f"Time : {datetime.datetime.now().strftime('%H:%M:%S')}","system")),
            "echo":lambda a:self._w(a,"cyan") if a else self._w("Usage: /echo <text>","dim"),
            "whoami":lambda _:(
                self._w(f"User : {os.environ.get('USERNAME') or os.environ.get('USER') or 'user'}","system"),
                self._w(f"CWD  : {os.getcwd()}","dim"),
                self._w(f"OS   : {platform.system()} {platform.release()}","dim"),
                self._w(f"Py   : {sys.version.split()[0]}","dim")),
            "files":self._files,"cd":self._cd,"run":self._run,
            "exit":lambda _:(self._w("Goodbye! \U0001f44b","prompt"),self.app.root.after(600,self.app.root.quit)),
            "model":self._model,
            "ask":lambda a:self._ai(a) if a else self._w("Usage: /ask <question>","dim"),
            "context":lambda _:(
                self._w(f"Messages : {len(self.history)}","system"),
                self._w(f"Tokens   : ~{sum(len(m['content']) for m in self.history)//4}","system"),
                self._w("Use /clear-history to reset.","dim")),
            "copy":lambda _:(
                self.app.root.clipboard_clear(),
                self.app.root.clipboard_append(self.last_ai),
                self._w("\u2713 Copied.","success")) if self.last_ai else self._w("No AI response yet.","warning"),
            "theme":lambda _:self.app.toggle_theme(),
            "streaming":self._streaming_toggle,
            "fortune":lambda _:self._w(f"\n  \U0001f960  {random.choice(FORTUNES)}\n","cyan"),
            "matrix":lambda _:[self._w(
                "  "+"".join(random.choice("\u30a2\u30a4\u30a6\u30a8\u30aa\u30ab\u30ad\u30af\u30b1\u30b30123456789ABCDEF@#$%") for _ in range(62)),
                "success") for _ in range(5)],
            "neofetch":self._neofetch,"cowsay":self._cowsay,
            "ide":lambda _:self.app._set_mode("ide"),
            "settings":lambda _:self.app.show_view("settings"),
            "automator":lambda _:self.app.show_view("automator"),
        }

    def _help(self,_):
        rows=[
            ("header",f"\n\u250c\u2500 V-Agent v{VERSION} \u2014 Commands \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"),
            ("prompt","│"),
            ("dim","│  AI"),
            ("dim","│    /ask <text>            Ask the AI"),
            ("dim","│    /model [name]          Show or switch model"),
            ("dim","│    /streaming             Toggle streaming on/off"),
            ("dim","│    /context               Token usage stats"),
            ("dim","│    /clear-history         Clear conversation"),
            ("dim","│    /copy                  Copy last AI response"),
            ("prompt","│"),
            ("dim","│  Shell"),
            ("dim","│    /files [path]          List directory"),
            ("dim","│    /cd <path>             Change directory"),
            ("dim","│    /run <cmd>             Run a shell command"),
            ("prompt","│"),
            ("dim","│  Navigation"),
            ("dim","│    /ide                   Switch to IDE mode"),
            ("dim","│    /settings              Open Settings panel"),
            ("dim","│    /automator             Open Automator panel"),
            ("prompt","│"),
            ("dim","│  Extras"),
            ("dim","│    /clear   (Ctrl+L)      Clear screen"),
            ("dim","│    /theme                 Toggle theme"),
            ("dim","│    /neofetch              System information"),
            ("dim","│    /fortune               Fortune cookie"),
            ("dim","│    /matrix                Matrix rain effect"),
            ("dim","│    /cowsay [text]         Cow says something"),
            ("dim","│    /date  /whoami  /echo  /about  /exit"),
            ("prompt","│"),
            ("prompt","\u2514\u2500 Type anything else to chat with the AI"),
        ]
        for tag, txt in rows: self._w(txt, tag)

    def _clr(self,_):
        self.out.config(state="normal"); self.out.delete(1.0,tk.END); self.out.config(state="disabled")

    def _files(self,args):
        path=args.strip() or "."
        try:
            items=sorted(os.listdir(path))
            self._w(f"\nDirectory: {os.path.abspath(path)}","yellow")
            for name in items[:80]:
                full=os.path.join(path,name); isdir=os.path.isdir(full)
                ext=os.path.splitext(name)[1].lower()
                icon="\U0001f4c1" if isdir else FILE_ICONS.get(ext,"\U0001f4c4")
                size=""
                if not isdir:
                    try:
                        s=os.path.getsize(full)
                        for u in ("B","KB","MB","GB"):
                            if s<1024: size=f"  {s:.0f}{u}"; break
                            s//=1024
                    except Exception: pass
                self._w(f"  {icon} {name:<42}{size}")
            if len(items)>80: self._w(f"  \u2026 and {len(items)-80} more","dim")
            self._w(f"  {len(items)} items total","dim")
        except Exception as e: self._w(f"Error: {e}","error")

    def _cd(self,args):
        if not args: self._w("Usage: /cd <path>","dim"); return
        try: os.chdir(os.path.expandvars(os.path.expanduser(args))); self._w(f"\u2192 {os.getcwd()}","success")
        except Exception as e: self._w(f"Error: {e}","error")

    def _run(self,args):
        if not args: self._w("Usage: /run <command>","dim"); return
        self._w(f"$ {args}","yellow")
        try:
            r=subprocess.run(args,shell=True,capture_output=True,text=True,timeout=30)
            for line in r.stdout.splitlines(): self._w(f"  {line}")
            for line in r.stderr.splitlines(): self._w(f"  {line}","error")
            self._w(f"Exit: {r.returncode}","success" if r.returncode==0 else "warning")
        except subprocess.TimeoutExpired: self._w("Timed out (30s)","error")
        except Exception as e: self._w(f"Error: {e}","error")

    def _model(self,args):
        if not args: self._w(f"Current model: {self.model}","cyan"); self._w("Usage: /model <name>","dim"); return
        try:
            resp=requests.get(f"{self.base}/api/tags",timeout=5)
            names=[m["name"] for m in resp.json().get("models",[])]
            if args in names:
                self.model=args; self.app.cfg["model"]=args; save_cfg(self.app.cfg)
                self._rstatus(); self._w(f"\u2713 Model: {self.model}","success")
            else:
                self._w(f"'{args}' not found locally.","error")
                self._w("Available: "+", ".join(names[:10]),"dim")
                self._w(f"Pull with:  ollama pull {args}","dim")
        except Exception as e: self._w(f"Error: {e}","error")

    def _streaming_toggle(self,_):
        self.streaming=not self.streaming
        self.app.cfg["streaming"]=self.streaming; save_cfg(self.app.cfg)
        self._w(f"Streaming: {'ON' if self.streaming else 'OFF'}","success")

    def _neofetch(self,_):
        self._w("\n\u250c\u2500 System Information","header")
        self._w(f"\u2502  OS      : {platform.system()} {platform.release()}","text")
        self._w(f"\u2502  Machine : {platform.machine()}","dim")
        self._w(f"\u2502  Python  : {sys.version.split()[0]}","text")
        self._w(f"\u2502  Model   : {self.model}","text")
        self._w(f"\u2502  Ollama  : {'\u25cf ONLINE' if self.ollama_ok else '\u25cb OFFLINE'}","success" if self.ollama_ok else "error")
        self._w(f"\u2502  Stream  : {'on' if self.streaming else 'off'}","dim")
        self._w(f"\u2502  Theme   : {self.app.theme_name}","dim")
        self._w("\u2514\u2500","prompt")

    def _cowsay(self,args):
        msg=args or "Moo! Type /ask to talk to the AI."
        bar="\u2500"*(len(msg)+2)
        self._w(f"\n  \u250c{bar}\u2510","yellow")
        self._w(f"  \u2502 {msg} \u2502","yellow")
        self._w(f"  \u2514{bar}\u2518","yellow")
        self._w("        \\   ^__^","yellow")
        self._w("         \\  (oo)\\_______","yellow")
        self._w("            (__)\\ )\\/\\","yellow")
        self._w("                ||----w |","yellow")
        self._w("                ||     ||\n","yellow")

    def reload_config(self):
        cfg=self.app.cfg
        self.model=cfg.get("model",self.model)
        self.streaming=cfg.get("streaming",True)
        self.base=cfg.get("ollama_base_url",self.base)
        fs=cfg.get("font_size",12)
        self.app.tf.config(size=fs); self.app.tfb.config(size=fs); self.app.tfi.config(size=fs)
        self._chk_ollama()

    def recolor(self,C):
        self.frame.config(bg=C["bg"]); self.out.config(bg=C["bg"],fg=C["text"])
        self._sb.config(bg=C["statusbar"])
        self.slbl.config(bg=C["statusbar"],fg=C["statusfg"])
        self.clbl.config(bg=C["statusbar"],fg=C["statusfg"])
        self._inp.config(bg=C.get("input_bg",C["panel"]))
        self._plbl.config(bg=C.get("input_bg",C["panel"]),fg=C["accent"])
        self._hl.config(bg=C.get("input_bg",C["panel"]),fg=C["dim"])
        self.ti.config(bg=C.get("input_bg",C["panel"]),fg=C["text"],
            insertbackground=C["prompt"],selectbackground=C["selection"])
        self._setup_tags()

    def on_focus(self): self.app.root.after(50,self.ti.focus_set)


# ══════════════════════════════════════════════════════════════════════════════
#  SETTINGS PANEL
# ══════════════════════════════════════════════════════════════════════════════
class SettingsPanel:
    def __init__(self,parent,app):
        self.app=app; self.frame=tk.Frame(parent,bg=app.C["bg"]); self._build()

    def _build(self):
        C=self.app.C
        canvas=tk.Canvas(self.frame,bg=C["bg"],highlightthickness=0)
        sb=ttk.Scrollbar(self.frame,orient="vertical",command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right",fill="y"); canvas.pack(side="left",fill="both",expand=True)
        inner=tk.Frame(canvas,bg=C["bg"])
        wid=canvas.create_window((0,0),window=inner,anchor="nw")
        inner.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",lambda e:canvas.itemconfig(wid,width=e.width))

        tk.Label(inner,text="\u2699  Settings",
            font=("Segoe UI",24,"bold"),fg=C["accent"],bg=C["bg"]
            ).pack(anchor="w",padx=40,pady=(32,2))
        tk.Label(inner,text=f"V-Agent v{VERSION} \u00b7 Voidtune Ecosystem",
            font=("Segoe UI",10),fg=C["dim"],bg=C["bg"]
            ).pack(anchor="w",padx=40,pady=(0,8))
        tk.Frame(inner,bg=C["border"],height=1).pack(fill="x",padx=40,pady=(0,8))

        def section(title):
            tk.Label(inner,text=title,font=("Segoe UI",13,"bold"),
                fg=C["accent"],bg=C["bg"]).pack(anchor="w",padx=40,pady=(24,4))
            tk.Frame(inner,bg=C["border"],height=1).pack(fill="x",padx=40,pady=(0,14))

        section("AI Configuration")
        frm=tk.Frame(inner,bg=C["bg"]); frm.pack(fill="x",padx=40)
        frm.grid_columnconfigure(1,weight=1)
        cfg=self.app.cfg

        def lbl(t,r):
            tk.Label(frm,text=t,font=("Segoe UI",11),fg=C["text"],
                bg=C["bg"],anchor="w").grid(row=r,column=0,sticky="w",pady=10)

        self._sv_model  = tk.StringVar(value=cfg.get("model",DEFAULT_CFG["model"]))
        self._sv_theme  = tk.StringVar(value=cfg.get("theme","voidtune_purple"))
        self._sv_url    = tk.StringVar(value=cfg.get("ollama_base_url","http://localhost:11434"))
        self._sv_font   = tk.IntVar(   value=cfg.get("font_size",12))
        self._sv_stream = tk.BooleanVar(value=cfg.get("streaming",True))

        lbl("AI Model:",0)
        self._mcb=ttk.Combobox(frm,textvariable=self._sv_model,values=FALLBACK_MODELS,
            font=("Segoe UI",11),state="readonly")
        self._mcb.grid(row=0,column=1,sticky="ew",pady=10,padx=(16,0))

        lbl("Theme:",1)
        ttk.Combobox(frm,textvariable=self._sv_theme,values=list(THEMES.keys()),
            font=("Segoe UI",11),state="readonly").grid(row=1,column=1,sticky="ew",pady=10,padx=(16,0))

        lbl("Ollama URL:",2)
        tk.Entry(frm,textvariable=self._sv_url,font=("Segoe UI",11),
            bg=C["panel"],fg=C["text"],insertbackground=C["text"],
            relief=tk.FLAT,bd=4).grid(row=2,column=1,sticky="ew",pady=10,padx=(16,0))

        lbl("Font Size:",3)
        tk.Spinbox(frm,from_=8,to=28,textvariable=self._sv_font,
            font=("Segoe UI",11),bg=C["panel"],fg=C["text"],
            relief=tk.FLAT,width=6).grid(row=3,column=1,sticky="w",pady=10,padx=(16,0))

        lbl("Streaming Responses:",4)
        tk.Checkbutton(frm,variable=self._sv_stream,bg=C["bg"],
            activebackground=C["bg"],fg=C["text"],
            selectcolor=C["panel"]).grid(row=4,column=1,sticky="w",pady=10,padx=(16,0))

        tk.Frame(inner,bg=C["border"],height=1).pack(fill="x",padx=40,pady=(20,0))
        brow=tk.Frame(inner,bg=C["bg"]); brow.pack(padx=40,pady=20,anchor="w")
        tk.Button(brow,text="  Save Settings  ",command=self._save,
            font=("Segoe UI",12,"bold"),fg=C["bg"],bg=C["green"],
            activebackground=C["green"],padx=20,pady=10,bd=0,cursor="hand2"
            ).pack(side=tk.LEFT,padx=(0,10))
        tk.Button(brow,text="\u27f3  Refresh Models",command=self._refresh,
            font=("Segoe UI",10),fg=C["text"],bg=C["panel"],
            activebackground=C["border"],padx=14,pady=10,bd=0,cursor="hand2"
            ).pack(side=tk.LEFT)

        section("Ollama Quick Setup")
        steps=tk.Frame(inner,bg=C["panel"],pady=14,padx=18)
        steps.pack(fill="x",padx=40,pady=(0,24))
        for s in [
            "1.  Download from  https://ollama.com/download/windows",
            "2.  Install and run \u2014 system tray icon appears",
            "3.  Open a terminal:  ollama serve",
            "4.  Pull a model:  ollama pull qwen2.5-coder:14b",
            "5.  V-Agent connects automatically and shows \u25cf Online",
        ]:
            tk.Label(steps,text=s,font=("Consolas",10),fg=C["dim"],
                bg=C["panel"],anchor="w",justify="left").pack(anchor="w",pady=2)

        section("Cloud AI  (optional — for complex tasks)")
        cloud_info = tk.Frame(inner, bg=C["panel"], pady=8, padx=14)
        cloud_info.pack(fill="x", padx=40, pady=(0,12))
        for line in [
            "Local Ollama:  privacy, offline, simple tasks",
            "Groq (free):   70B models, 1M tokens/day — https://console.groq.com",
            "OpenRouter:    many models, free tier — https://openrouter.ai",
        ]:
            tk.Label(cloud_info, text=line, font=("Consolas",9),
                fg=C["dim"], bg=C["panel"], anchor="w").pack(anchor="w", pady=1)

        cloud_frm = tk.Frame(inner, bg=C["bg"]); cloud_frm.pack(fill="x", padx=40)
        cloud_frm.grid_columnconfigure(1, weight=1)
        crow = [0]
        def clbl(t, r):
            tk.Label(cloud_frm, text=t, font=("Segoe UI",11), fg=C["text"],
                bg=C["bg"], anchor="w").grid(row=r, column=0, sticky="w", pady=8)
        def crow_next():
            n = crow[0]; crow[0] += 1; return n

        r = crow_next(); clbl("AI Provider:", r)
        self._sv_cloud_prov = tk.StringVar(value=cfg.get("ai_provider","local"))
        ttk.Combobox(cloud_frm, textvariable=self._sv_cloud_prov,
            values=["local","groq","openrouter"],
            font=("Segoe UI",11), state="readonly"
        ).grid(row=r, column=1, sticky="ew", pady=8, padx=(16,0))

        r = crow_next(); clbl("Groq API Key:", r)
        self._sv_groq_key = tk.StringVar(value=cfg.get("groq_api_key",""))
        tk.Entry(cloud_frm, textvariable=self._sv_groq_key, show="*",
            font=("Segoe UI",11), bg=C.get("input_bg",C["panel"]),
            fg=C["text"], insertbackground=C["text"],
            relief=tk.FLAT, bd=4
        ).grid(row=r, column=1, sticky="ew", pady=8, padx=(16,0))

        r = crow_next(); clbl("Groq Model:", r)
        self._sv_groq_model = tk.StringVar(value=cfg.get("groq_model","llama-3.3-70b-versatile"))
        ttk.Combobox(cloud_frm, textvariable=self._sv_groq_model,
            values=["llama-3.3-70b-versatile","llama-3.1-8b-instant",
                    "mixtral-8x7b-32768","gemma2-9b-it"],
            font=("Segoe UI",11), state="readonly"
        ).grid(row=r, column=1, sticky="ew", pady=8, padx=(16,0))

        r = crow_next(); clbl("OpenRouter API Key:", r)
        self._sv_or_key = tk.StringVar(value=cfg.get("openrouter_api_key",""))
        tk.Entry(cloud_frm, textvariable=self._sv_or_key, show="*",
            font=("Segoe UI",11), bg=C.get("input_bg",C["panel"]),
            fg=C["text"], insertbackground=C["text"],
            relief=tk.FLAT, bd=4
        ).grid(row=r, column=1, sticky="ew", pady=8, padx=(16,0))

        r = crow_next(); clbl("OpenRouter Model:", r)
        self._sv_or_model = tk.StringVar(value=cfg.get("openrouter_model","meta-llama/llama-3.2-3b-instruct:free"))
        ttk.Combobox(cloud_frm, textvariable=self._sv_or_model,
            values=["meta-llama/llama-3.2-3b-instruct:free",
                    "google/gemini-2.0-flash-exp:free",
                    "microsoft/phi-3-mini-128k:free",
                    "deepseek/deepseek-r1:free"],
            font=("Segoe UI",11), state="readonly"
        ).grid(row=r, column=1, sticky="ew", pady=8, padx=(16,0))

        tk.Frame(inner, bg=C["border"], height=1).pack(fill="x", padx=40, pady=(16,0))

        section("Keyboard Shortcuts")
        ks=tk.Frame(inner,bg=C["panel"],pady=14,padx=18)
        ks.pack(fill="x",padx=40,pady=(0,40))
        for k,v in [
            ("Ctrl+N","New file"),("Ctrl+O","Open file"),("Ctrl+S","Save file"),
            ("Ctrl+W","Close tab"),("Ctrl+F","Find in file"),("Ctrl+H","Find and replace"),
            ("Ctrl+G","Go to line"),("Ctrl+/","Toggle comment"),("Ctrl+D","Duplicate line"),
            ("Ctrl+Shift+P","Command palette"),("Ctrl++/-","Zoom in/out"),
            ("Tab","Indent 4 spaces"),("Shift+Tab","Unindent"),
            ("Return","Smart indent"),("( [ {","Auto-close brackets"),
        ]:
            r=tk.Frame(ks,bg=C["panel"]); r.pack(fill="x",pady=1)
            tk.Label(r,text=k,font=("Cascadia Code",9),fg=C["cyan"],
                bg=C["panel"],width=20,anchor="w").pack(side="left")
            tk.Label(r,text=v,font=("Segoe UI",9),fg=C["dim"],
                bg=C["panel"],anchor="w").pack(side="left")

    def _save(self):
        cfg=self.app.cfg
        cfg["model"]=self._sv_model.get(); cfg["theme"]=self._sv_theme.get()
        cfg["ollama_base_url"]=self._sv_url.get()
        cfg["font_size"]=int(self._sv_font.get()); cfg["streaming"]=self._sv_stream.get()
        # Cloud AI settings
        if hasattr(self,"_sv_cloud_prov"):
            cfg["ai_provider"]        = self._sv_cloud_prov.get()
            cfg["groq_api_key"]       = self._sv_groq_key.get()
            cfg["groq_model"]         = self._sv_groq_model.get()
            cfg["openrouter_api_key"] = self._sv_or_key.get()
            cfg["openrouter_model"]   = self._sv_or_model.get()
        save_cfg(cfg); self.app.apply_theme(cfg["theme"])
        term=self.app.views.get("terminal")
        if term: term.reload_config()
        Toast(self.app.root,"Settings saved!",color=self.app.C["green"])
        messagebox.showinfo("Saved","Settings saved successfully.",parent=self.app.root)

    def _refresh(self):
        base=self._sv_url.get() or "http://localhost:11434"
        try:
            resp=requests.get(f"{base}/api/tags",timeout=5)
            names=[m["name"] for m in resp.json().get("models",[])]
            if names:
                self._mcb.configure(values=names)
                Toast(self.app.root,f"Found {len(names)} models")
                return
        except Exception: pass
        messagebox.showwarning("Ollama Offline",
            "Could not reach Ollama.\nCheck the URL and run: ollama serve",
            parent=self.app.root)

    def on_focus(self): pass


# ══════════════════════════════════════════════════════════════════════════════
#  AUTOMATOR PANEL
# ══════════════════════════════════════════════════════════════════════════════
class AutomatorPanel:
    def __init__(self,parent,app):
        self.app=app; self.frame=tk.Frame(parent,bg=app.C["bg"])
        self._proc=None; self._running=False; self._build()

    def _build(self):
        C=self.app.C
        tk.Label(self.frame,text="\U0001f916  Automator",
            font=("Segoe UI",22,"bold"),fg=C["accent"],bg=C["bg"]
            ).pack(anchor="w",padx=32,pady=(28,4))
        tk.Label(self.frame,
            text="Watches Input/ for scripts. AI fixes bugs and saves corrected versions to Output/.",
            font=("Segoe UI",10),fg=C["dim"],bg=C["bg"]
            ).pack(anchor="w",padx=32,pady=(0,12))
        tk.Frame(self.frame,bg=C["border"],height=1).pack(fill="x",padx=32,pady=(0,16))
        info=tk.Frame(self.frame,bg=C["panel"],pady=12,padx=16)
        info.pack(fill="x",padx=32,pady=(0,14))
        for line in [
            "Supported: .py  .js  .ts  .bat  .ps1  .sh  .cmd",
            "Drop files into  Input/  \u2192  Fixed files appear in  Output/  with timestamp",
            "Requires: pip install watchdog",
        ]:
            tk.Label(info,text=line,font=("Consolas",10),fg=C["dim"],
                bg=C["panel"],anchor="w").pack(anchor="w",pady=2)
        brow=tk.Frame(self.frame,bg=C["bg"]); brow.pack(padx=32,pady=(0,12),anchor="w")
        self._sb_btn=tk.Button(brow,text="\u25b6  Start Watching",command=self._start,
            font=("Segoe UI",11,"bold"),fg=C["bg"],bg=C["green"],
            activebackground=C["green"],padx=18,pady=8,bd=0,cursor="hand2")
        self._sb_btn.pack(side="left",padx=(0,8))
        self._st_btn=tk.Button(brow,text="\u25a0  Stop",command=self._stop,
            font=("Segoe UI",11,"bold"),fg=C["bg"],bg=C["red"],
            activebackground=C["red"],padx=18,pady=8,bd=0,cursor="hand2",state="disabled")
        self._st_btn.pack(side="left")
        tk.Label(self.frame,text="Log:",font=("Segoe UI",9),
            fg=C["dim"],bg=C["bg"]).pack(anchor="w",padx=32,pady=(4,0))
        lw=tk.Frame(self.frame,bg=C["bg"]); lw.pack(fill="both",expand=True,padx=32,pady=(4,28))
        self.log=tk.Text(lw,bg=C["panel"],fg=C["green"],
            font=("Consolas",10),relief=tk.FLAT,padx=10,pady=8,state="disabled")
        self.log.pack(side="left",fill="both",expand=True)
        sb=ttk.Scrollbar(lw,orient="vertical",command=self.log.yview)
        sb.pack(side="right",fill="y"); self.log.configure(yscrollcommand=sb.set)
        self._log("Automator ready \u2014 press \u25b6 to begin watching Input/")

    def _log(self,msg):
        ts=datetime.datetime.now().strftime("%H:%M:%S")
        self.log.config(state="normal")
        self.log.insert(tk.END,f"[{ts}]  {msg}\n")
        self.log.see(tk.END); self.log.config(state="disabled")

    def _start(self):
        if self._running: return
        a=os.path.join(BASE_DIR,"automator.py")
        if not os.path.exists(a):
            messagebox.showerror("Error",f"automator.py not found:\n{a}",parent=self.app.root); return
        os.makedirs(INPUT_DIR,exist_ok=True); os.makedirs(OUT_DIR,exist_ok=True)
        try:
            self._proc=subprocess.Popen([sys.executable,a],cwd=BASE_DIR,
                stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
            self._running=True
            self._sb_btn.config(state="disabled"); self._st_btn.config(state="normal")
            self._log(f"Started (PID {self._proc.pid}) \u2014 watching: {INPUT_DIR}")
            threading.Thread(target=self._read,daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error",str(e),parent=self.app.root)

    def _stop(self):
        if self._proc and self._proc.poll() is None: self._proc.terminate()
        self._running=False
        self._sb_btn.config(state="normal"); self._st_btn.config(state="disabled")
        self._log("Stopped.")

    def _read(self):
        for line in self._proc.stdout:
            line=line.rstrip()
            if line: self.app.root.after(0,lambda l=line:self._log(l))
        self.app.root.after(0,self._stop)

    def on_focus(self): pass


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ══════════════════════════════════════════════════════════════════════════════
class VAgent:
    TERM_VIEWS = [("terminal","\U0001f5a5"), ("settings","\u2699"), ("automator","\U0001f916")]

    def __init__(self, root):
        self.root = root
        self.root.title(f"V-Agent v{VERSION} \u00b7 Voidtune")
        self.root.geometry("1360x860"); self.root.minsize(900,600)
        self._center()
        # Fix ttk Treeview white background on Windows
        try:
            s = ttk.Style(self.root)
            s.theme_use("clam")
        except Exception:
            pass
        self.cfg        = load_cfg()
        self.theme_name = self.cfg.get("theme","dark")
        self.C          = THEMES.get(self.theme_name, THEMES["dark"])
        self._mode      = "terminal"
        self._last_tv   = "terminal"
        fs = self.cfg.get("font_size",12)
        # Pick best available monospace font (VS Code preference order)
        _mono = "Courier New"
        for _fam in ("Cascadia Code","Cascadia Mono","Consolas","Menlo","Monaco"):
            _test = tkfont.Font(family=_fam, size=fs)
            if _fam.lower().replace(" ","") in _test.actual("family").lower().replace(" ",""):
                _mono = _fam; break
        self.tf  = tkfont.Font(family=_mono, size=fs)
        self.tfb = tkfont.Font(family=_mono, size=fs, weight="bold")
        self.tfi = tkfont.Font(family=_mono, size=fs, slant="italic")
        self.sf  = tkfont.Font(family="Segoe UI",  size=9)
        self.sf2 = tkfont.Font(family="Segoe UI",  size=9, weight="bold")
        self._build()
        self._build_views()
        self._set_mode("terminal", initial=True)

    def _center(self):
        self.root.update_idletasks()
        w, h = 1360, 860
        x = (self.root.winfo_screenwidth()  - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        C = self.C
        self.root.configure(bg=C["bg"])
        # Top bar
        self.topbar = tk.Frame(self.root, bg=C["sidebar"], height=38)
        self.topbar.pack(fill=tk.X); self.topbar.pack_propagate(False)
        # App icon badge (colored square like a real app)
        icon_badge = tk.Label(self.topbar,
            text="  VA  ",
            font=("Segoe UI", 10, "bold"),
            fg="#FFFFFF",
            bg=C["accent"],
            padx=2, pady=0)
        icon_badge.pack(side=tk.LEFT, padx=(8,4), pady=6)
        # App name
        tk.Label(self.topbar, text="V-Agent",
            font=("Segoe UI", 9, "bold"),
            fg=C["text"], bg=C["panel"],
            padx=4).pack(side=tk.LEFT)
        # Separator
        tk.Frame(self.topbar, bg=C["border"], width=1).pack(
            side=tk.LEFT, fill=tk.Y, pady=8, padx=6)
        # Mode toggle buttons (minimal, like VS Code menu items)
        self._btn_term = tk.Button(self.topbar,
            text="Terminal",
            font=("Segoe UI", 9),
            fg=C["text"], bg=C["panel"],
            activebackground=C["hover"],
            relief=tk.FLAT, bd=0, cursor="hand2",
            padx=12, pady=0,
            command=lambda: self._set_mode("terminal"))
        self._btn_term.pack(side=tk.LEFT, fill=tk.Y)
        self._btn_ide = tk.Button(self.topbar,
            text="</>  IDE",
            font=("Segoe UI", 9),
            fg=C["dim"], bg=C["panel"],
            activebackground=C["hover"],
            relief=tk.FLAT, bd=0, cursor="hand2",
            padx=12, pady=0,
            command=lambda: self._set_mode("ide"))
        self._btn_ide.pack(side=tk.LEFT, fill=tk.Y)
        # Right: theme toggle + Ollama status
        self._ollama_dot = tk.Label(self.topbar, text="○",
            font=("Segoe UI", 10), fg=C["dim"], bg=C["panel"], padx=10)
        self._ollama_dot.pack(side=tk.RIGHT)
        # Theme toggle button
        self._theme_btn = tk.Button(self.topbar,
            text="◑",   # half-circle = dark/light
            font=("Segoe UI", 11),
            fg=C["dim"], bg=C["panel"],
            activebackground=C["hover"],
            relief=tk.FLAT, bd=0, cursor="hand2",
            padx=10, pady=0,
            command=self.toggle_theme)
        self._theme_btn.pack(side=tk.RIGHT)
        tk.Label(self.topbar, text=f"v{VERSION}",
            font=("Segoe UI", 8),
            fg=C["dim"], bg=C["panel"], padx=8
            ).pack(side=tk.RIGHT)
        tk.Frame(self.topbar, bg=C["border"], height=1).pack(side=tk.BOTTOM, fill=tk.X)
        # Lower body
        self.lower = tk.Frame(self.root, bg=C["bg"])
        self.lower.pack(fill=tk.BOTH, expand=True)
        self.sidebar = tk.Frame(self.lower, bg=C["actbar"], width=48)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y); self.sidebar.pack_propagate(False)
        self._nav_btns  = {}
        self._nav_inds  = {}
        for name, icon in self.TERM_VIEWS:
            row = tk.Frame(self.sidebar, bg=C["actbar"]); row.pack(fill=tk.X)
            ind = tk.Frame(row, bg=C["actbar"], width=2)
            ind.pack(side=tk.LEFT, fill=tk.Y)
            b   = tk.Button(row, text=icon, font=("Segoe UI",16),
                fg=C["actbar_dim"], bg=C["actbar"],
                activebackground=C["hover"],
                relief=tk.FLAT, bd=0, cursor="hand2",
                padx=0, pady=12, width=3,
                command=lambda v=name: self.show_view(v))
            b.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self._nav_btns[name] = b
            self._nav_inds[name] = ind
        self.content = tk.Frame(self.lower, bg=C["bg"])
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _build_views(self):
        self.views = {}
        self.views["terminal"]  = TerminalPanel(self.content, self)
        self.views["settings"]  = SettingsPanel(self.content, self)
        self.views["automator"] = AutomatorPanel(self.content, self)
        self.views["ide"]       = IDEPanel(self.content, self)
        for v in self.views.values(): v.frame.pack_forget()

    def _set_mode(self, mode, initial=False):
        C = self.C; self._mode = mode
        if mode == "terminal":
            self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
            self._btn_term.config(fg=C["text"], bg=C["panel"])
            self._btn_ide.config(fg=C["dim"],   bg=C["sidebar"])
            self.show_view(self._last_tv if not initial else "terminal")
        else:
            self.sidebar.pack_forget()
            self._btn_ide.config(fg=C["text"],  bg=C["panel"])
            self._btn_term.config(fg=C["dim"],  bg=C["sidebar"])
            self.show_view("ide")

    def show_view(self, name):
        C = self.C
        for k, v in self.views.items():
            if k == name: v.frame.pack(fill=tk.BOTH, expand=True)
            else: v.frame.pack_forget()
        for k, b in self._nav_btns.items():
            active = (k == name)
            b.config(fg=C["actbar_fg"] if active else C["actbar_dim"],
                     bg=C["actbar"])
            if k in self._nav_inds:
                self._nav_inds[k].config(bg=C["actborder"] if active else C["actbar"])
        if name != "ide": self._last_tv = name
        self.views[name].on_focus()

    def update_ollama(self, ok):
        C = self.C
        self._ollama_dot.config(text="\u25cf" if ok else "\u25cb",
                                fg=C["green"] if ok else C["red"])

    def toggle_theme(self):
        keys = list(THEMES.keys())
        self.apply_theme(keys[(keys.index(self.theme_name)+1)%len(keys)])

    def apply_theme(self, name):
        if name not in THEMES: return
        self.theme_name = name; self.C = THEMES[name]; self.cfg["theme"] = name
        C = self.C
        self.root.configure(bg=C["bg"])
        self.topbar.config(bg=C["panel"])
        # Update topbar children bg
        for w in self.topbar.winfo_children():
            try: w.config(bg=C["panel"])
            except Exception: pass
        # Accent badge stays as accent color
        for w in self.topbar.winfo_children():
            if isinstance(w, tk.Label) and w.cget("text").strip() == "VA":
                try: w.config(bg=C["accent"]); break
                except Exception: pass
        self._btn_term.config(
            bg=C["panel"],
            fg=C["text"]  if self._mode=="terminal" else C["dim"])
        self._btn_ide.config(
            bg=C["panel"],
            fg=C["text"]  if self._mode=="ide" else C["dim"])
        self._ollama_dot.config(bg=C["panel"])
        self.lower.config(bg=C["bg"])
        self.sidebar.config(bg=C["actbar"])
        for k, b in self._nav_btns.items():
            b.config(bg=C["actbar"], fg=C["actbar_dim"],
                     activebackground=C["hover"])
            if k in self._nav_inds:
                self._nav_inds[k].config(bg=C["actbar"])
        # Re-apply active nav indicator
        for k, v in self.views.items():
            if v.frame.winfo_ismapped() and k in self._nav_inds:
                self._nav_btns[k].config(fg=C["actbar_fg"])
                self._nav_inds[k].config(bg=C["actborder"])
        self.content.config(bg=C["bg"])
        term = self.views.get("terminal")
        if isinstance(term, TerminalPanel): term.recolor(C)


def main():
    root = tk.Tk()
    VAgent(root)
    root.mainloop()


if __name__ == "__main__":
    main()
