// Vendored Monarch grammars from monaco-editor v0.55.1 (MIT License,
// Copyright (c) Microsoft Corporation) — basic-languages/cpp and /python.
// Vendored because importing them from the package would bundle a second
// copy of the whole editor next to the CDN-loaded one. Enhanced by
// defineEnhancedLanguages() in monacoLangs.js.

export const cppLanguage =  {
  defaultToken: "",
  tokenPostfix: ".cpp",
  brackets: [
    { token: "delimiter.curly", open: "{", close: "}" },
    { token: "delimiter.parenthesis", open: "(", close: ")" },
    { token: "delimiter.square", open: "[", close: "]" },
    { token: "delimiter.angle", open: "<", close: ">" }
  ],
  keywords: [
    "abstract",
    "amp",
    "array",
    "auto",
    "bool",
    "break",
    "case",
    "catch",
    "char",
    "class",
    "const",
    "constexpr",
    "const_cast",
    "continue",
    "cpu",
    "decltype",
    "default",
    "delegate",
    "delete",
    "do",
    "double",
    "dynamic_cast",
    "each",
    "else",
    "enum",
    "event",
    "explicit",
    "export",
    "extern",
    "false",
    "final",
    "finally",
    "float",
    "for",
    "friend",
    "gcnew",
    "generic",
    "goto",
    "if",
    "in",
    "initonly",
    "inline",
    "int",
    "interface",
    "interior_ptr",
    "internal",
    "literal",
    "long",
    "mutable",
    "namespace",
    "new",
    "noexcept",
    "nullptr",
    "__nullptr",
    "operator",
    "override",
    "partial",
    "pascal",
    "pin_ptr",
    "private",
    "property",
    "protected",
    "public",
    "ref",
    "register",
    "reinterpret_cast",
    "restrict",
    "return",
    "safe_cast",
    "sealed",
    "short",
    "signed",
    "sizeof",
    "static",
    "static_assert",
    "static_cast",
    "struct",
    "switch",
    "template",
    "this",
    "thread_local",
    "throw",
    "tile_static",
    "true",
    "try",
    "typedef",
    "typeid",
    "typename",
    "union",
    "unsigned",
    "using",
    "virtual",
    "void",
    "volatile",
    "wchar_t",
    "where",
    "while",
    "_asm",
    // reserved word with one underscores
    "_based",
    "_cdecl",
    "_declspec",
    "_fastcall",
    "_if_exists",
    "_if_not_exists",
    "_inline",
    "_multiple_inheritance",
    "_pascal",
    "_single_inheritance",
    "_stdcall",
    "_virtual_inheritance",
    "_w64",
    "__abstract",
    // reserved word with two underscores
    "__alignof",
    "__asm",
    "__assume",
    "__based",
    "__box",
    "__builtin_alignof",
    "__cdecl",
    "__clrcall",
    "__declspec",
    "__delegate",
    "__event",
    "__except",
    "__fastcall",
    "__finally",
    "__forceinline",
    "__gc",
    "__hook",
    "__identifier",
    "__if_exists",
    "__if_not_exists",
    "__inline",
    "__int128",
    "__int16",
    "__int32",
    "__int64",
    "__int8",
    "__interface",
    "__leave",
    "__m128",
    "__m128d",
    "__m128i",
    "__m256",
    "__m256d",
    "__m256i",
    "__m512",
    "__m512d",
    "__m512i",
    "__m64",
    "__multiple_inheritance",
    "__newslot",
    "__nogc",
    "__noop",
    "__nounwind",
    "__novtordisp",
    "__pascal",
    "__pin",
    "__pragma",
    "__property",
    "__ptr32",
    "__ptr64",
    "__raise",
    "__restrict",
    "__resume",
    "__sealed",
    "__single_inheritance",
    "__stdcall",
    "__super",
    "__thiscall",
    "__try",
    "__try_cast",
    "__typeof",
    "__unaligned",
    "__unhook",
    "__uuidof",
    "__value",
    "__virtual_inheritance",
    "__w64",
    "__wchar_t"
  ],
  operators: [
    "=",
    ">",
    "<",
    "!",
    "~",
    "?",
    ":",
    "==",
    "<=",
    ">=",
    "!=",
    "&&",
    "||",
    "++",
    "--",
    "+",
    "-",
    "*",
    "/",
    "&",
    "|",
    "^",
    "%",
    "<<",
    ">>",
    "+=",
    "-=",
    "*=",
    "/=",
    "&=",
    "|=",
    "^=",
    "%=",
    "<<=",
    ">>="
  ],
  // we include these common regular expressions
  symbols: /[=><!~?:&|+\-*\/\^%]+/,
  escapes: /\\(?:[0abfnrtv\\"']|x[0-9A-Fa-f]{1,4}|u[0-9A-Fa-f]{4}|U[0-9A-Fa-f]{8})/,
  integersuffix: /([uU](ll|LL|l|L)|(ll|LL|l|L)?[uU]?)/,
  floatsuffix: /[fFlL]?/,
  encoding: /u|u8|U|L/,
  // The main tokenizer for our languages
  tokenizer: {
    root: [
      // C++ 11 Raw String
      [/@encoding?R\"(?:([^ ()\\\t]*))\(/, { token: "string.raw.begin", next: "@raw.$1" }],
      // identifiers and keywords
      [
        /[a-zA-Z_]\w*/,
        {
          cases: {
            "@keywords": { token: "keyword.$0" },
            "@default": "identifier"
          }
        }
      ],
      // The preprocessor checks must be before whitespace as they check /^\s*#/ which
      // otherwise fails to match later after other whitespace has been removed.
      // Inclusion
      [/^\s*#\s*include/, { token: "keyword.directive.include", next: "@include" }],
      // Preprocessor directive
      [/^\s*#\s*\w+/, "keyword.directive"],
      // whitespace
      { include: "@whitespace" },
      // [[ attributes ]].
      [/\[\s*\[/, { token: "annotation", next: "@annotation" }],
      // delimiters and operators
      [/[{}()<>\[\]]/, "@brackets"],
      [
        /@symbols/,
        {
          cases: {
            "@operators": "delimiter",
            "@default": ""
          }
        }
      ],
      // numbers
      [/\d*\d+[eE]([\-+]?\d+)?(@floatsuffix)/, "number.float"],
      [/\d*\.\d+([eE][\-+]?\d+)?(@floatsuffix)/, "number.float"],
      [/0[xX][0-9a-fA-F']*[0-9a-fA-F](@integersuffix)/, "number.hex"],
      [/0[0-7']*[0-7](@integersuffix)/, "number.octal"],
      [/0[bB][0-1']*[0-1](@integersuffix)/, "number.binary"],
      [/\d[\d']*\d(@integersuffix)/, "number"],
      [/\d(@integersuffix)/, "number"],
      // delimiter: after number because of .\d floats
      [/[;,.]/, "delimiter"],
      // strings
      [/"([^"\\]|\\.)*$/, "string.invalid"],
      // non-teminated string
      [/"/, "string", "@string"],
      // characters
      [/'[^\\']'/, "string"],
      [/(')(@escapes)(')/, ["string", "string.escape", "string"]],
      [/'/, "string.invalid"]
    ],
    whitespace: [
      [/[ \t\r\n]+/, ""],
      [/\/\*\*(?!\/)/, "comment.doc", "@doccomment"],
      [/\/\*/, "comment", "@comment"],
      [/\/\/.*\\$/, "comment", "@linecomment"],
      [/\/\/.*$/, "comment"]
    ],
    comment: [
      [/[^\/*]+/, "comment"],
      [/\*\//, "comment", "@pop"],
      [/[\/*]/, "comment"]
    ],
    //For use with continuous line comments
    linecomment: [
      [/.*[^\\]$/, "comment", "@pop"],
      [/[^]+/, "comment"]
    ],
    //Identical copy of comment above, except for the addition of .doc
    doccomment: [
      [/[^\/*]+/, "comment.doc"],
      [/\*\//, "comment.doc", "@pop"],
      [/[\/*]/, "comment.doc"]
    ],
    string: [
      [/[^\\"]+/, "string"],
      [/@escapes/, "string.escape"],
      [/\\./, "string.escape.invalid"],
      [/"/, "string", "@pop"]
    ],
    raw: [
      [/[^)]+/, "string.raw"],
      [/\)$S2\"/, { token: "string.raw.end", next: "@pop" }],
      [/\)/, "string.raw"]
    ],
    annotation: [
      { include: "@whitespace" },
      [/using|alignas/, "keyword"],
      [/[a-zA-Z0-9_]+/, "annotation"],
      [/[,:]/, "delimiter"],
      [/[()]/, "@brackets"],
      [/\]\s*\]/, { token: "annotation", next: "@pop" }]
    ],
    include: [
      [
        /(\s*)(<)([^<>]*)(>)/,
        [
          "",
          "keyword.directive.include.begin",
          "string.include.identifier",
          { token: "keyword.directive.include.end", next: "@pop" }
        ]
      ],
      [
        /(\s*)(")([^"]*)(")/,
        [
          "",
          "keyword.directive.include.begin",
          "string.include.identifier",
          { token: "keyword.directive.include.end", next: "@pop" }
        ]
      ]
    ]
  }
};

export const pythonLanguage =  {
  defaultToken: "",
  tokenPostfix: ".python",
  keywords: [
    // This section is the result of running
    // `import keyword; for k in sorted(keyword.kwlist + keyword.softkwlist): print("  '" + k + "',")`
    // in a Python REPL,
    // though note that the output from Python 3 is not a strict superset of the
    // output from Python 2.
    "False",
    // promoted to keyword.kwlist in Python 3
    "None",
    // promoted to keyword.kwlist in Python 3
    "True",
    // promoted to keyword.kwlist in Python 3
    "_",
    // new in Python 3.10
    "and",
    "as",
    "assert",
    "async",
    // new in Python 3
    "await",
    // new in Python 3
    "break",
    "case",
    // new in Python 3.10
    "class",
    "continue",
    "def",
    "del",
    "elif",
    "else",
    "except",
    "exec",
    // Python 2, but not 3.
    "finally",
    "for",
    "from",
    "global",
    "if",
    "import",
    "in",
    "is",
    "lambda",
    "match",
    // new in Python 3.10
    "nonlocal",
    // new in Python 3
    "not",
    "or",
    "pass",
    "print",
    // Python 2, but not 3.
    "raise",
    "return",
    "try",
    "type",
    // new in Python 3.12
    "while",
    "with",
    "yield",
    "int",
    "float",
    "long",
    "complex",
    "hex",
    "abs",
    "all",
    "any",
    "apply",
    "basestring",
    "bin",
    "bool",
    "buffer",
    "bytearray",
    "callable",
    "chr",
    "classmethod",
    "cmp",
    "coerce",
    "compile",
    "complex",
    "delattr",
    "dict",
    "dir",
    "divmod",
    "enumerate",
    "eval",
    "execfile",
    "file",
    "filter",
    "format",
    "frozenset",
    "getattr",
    "globals",
    "hasattr",
    "hash",
    "help",
    "id",
    "input",
    "intern",
    "isinstance",
    "issubclass",
    "iter",
    "len",
    "locals",
    "list",
    "map",
    "max",
    "memoryview",
    "min",
    "next",
    "object",
    "oct",
    "open",
    "ord",
    "pow",
    "print",
    "property",
    "reversed",
    "range",
    "raw_input",
    "reduce",
    "reload",
    "repr",
    "reversed",
    "round",
    "self",
    "set",
    "setattr",
    "slice",
    "sorted",
    "staticmethod",
    "str",
    "sum",
    "super",
    "tuple",
    "type",
    "unichr",
    "unicode",
    "vars",
    "xrange",
    "zip",
    "__dict__",
    "__methods__",
    "__members__",
    "__class__",
    "__bases__",
    "__name__",
    "__mro__",
    "__subclasses__",
    "__init__",
    "__import__"
  ],
  brackets: [
    { open: "{", close: "}", token: "delimiter.curly" },
    { open: "[", close: "]", token: "delimiter.bracket" },
    { open: "(", close: ")", token: "delimiter.parenthesis" }
  ],
  tokenizer: {
    root: [
      { include: "@whitespace" },
      { include: "@numbers" },
      { include: "@strings" },
      [/[,:;]/, "delimiter"],
      [/[{}\[\]()]/, "@brackets"],
      [/@[a-zA-Z_]\w*/, "tag"],
      [
        /[a-zA-Z_]\w*/,
        {
          cases: {
            "@keywords": "keyword",
            "@default": "identifier"
          }
        }
      ]
    ],
    // Deal with white space, including single and multi-line comments
    whitespace: [
      [/\s+/, "white"],
      [/(^#.*$)/, "comment"],
      [/'''/, "string", "@endDocString"],
      [/"""/, "string", "@endDblDocString"]
    ],
    endDocString: [
      [/[^']+/, "string"],
      [/\\'/, "string"],
      [/'''/, "string", "@popall"],
      [/'/, "string"]
    ],
    endDblDocString: [
      [/[^"]+/, "string"],
      [/\\"/, "string"],
      [/"""/, "string", "@popall"],
      [/"/, "string"]
    ],
    // Recognize hex, negatives, decimals, imaginaries, longs, and scientific notation
    numbers: [
      [/-?0x([abcdef]|[ABCDEF]|\d)+[lL]?/, "number.hex"],
      [/-?(\d*\.)?\d+([eE][+\-]?\d+)?[jJ]?[lL]?/, "number"]
    ],
    // Recognize strings, including those broken across lines with \ (but not without)
    strings: [
      [/'$/, "string.escape", "@popall"],
      [/f'{1,3}/, "string.escape", "@fStringBody"],
      [/'/, "string.escape", "@stringBody"],
      [/"$/, "string.escape", "@popall"],
      [/f"{1,3}/, "string.escape", "@fDblStringBody"],
      [/"/, "string.escape", "@dblStringBody"]
    ],
    fStringBody: [
      [/[^\\'\{\}]+$/, "string", "@popall"],
      [/[^\\'\{\}]+/, "string"],
      [/\{[^\}':!=]+/, "identifier", "@fStringDetail"],
      [/\\./, "string"],
      [/'/, "string.escape", "@popall"],
      [/\\$/, "string"]
    ],
    stringBody: [
      [/[^\\']+$/, "string", "@popall"],
      [/[^\\']+/, "string"],
      [/\\./, "string"],
      [/'/, "string.escape", "@popall"],
      [/\\$/, "string"]
    ],
    fDblStringBody: [
      [/[^\\"\{\}]+$/, "string", "@popall"],
      [/[^\\"\{\}]+/, "string"],
      [/\{[^\}':!=]+/, "identifier", "@fStringDetail"],
      [/\\./, "string"],
      [/"/, "string.escape", "@popall"],
      [/\\$/, "string"]
    ],
    dblStringBody: [
      [/[^\\"]+$/, "string", "@popall"],
      [/[^\\"]+/, "string"],
      [/\\./, "string"],
      [/"/, "string.escape", "@popall"],
      [/\\$/, "string"]
    ],
    fStringDetail: [
      [/[:][^}]+/, "string"],
      [/[!][ars]/, "string"],
      // only !a, !r, !s are supported by f-strings: https://docs.python.org/3/tutorial/inputoutput.html#formatted-string-literals
      [/=/, "string"],
      [/\}/, "identifier", "@pop"]
    ]
  }
};
