// VS Code-style token enhancement for Monaco's stock Monarch grammars.
//
// VS Code colors function calls, class names, and constants distinctly because
// its TextMate grammars emit scopes like entity.name.function; Monaco's Monarch
// grammars only emit keyword/identifier/string/number. This module re-registers
// C/C++ and Python with a few rules prepended (first match wins in Monarch), so
// the theme's "function", "type.identifier" and "constant" colors apply:
//
//   foo(...)      → function        (yellow-gold, like VS Code)
//   CONST_NAME    → constant
//   ClassName     → type.identifier (Python — CapWords per PEP 8)
//
// Everything else falls through to the original vendored grammar untouched.

import { cppLanguage, pythonLanguage } from "./monacoGrammars.js";

const cppEnhanced = {
  ...cppLanguage,
  tokenizer: {
    ...cppLanguage.tokenizer,
    root: [
      // call position: identifier immediately before "(" — keywords keep their
      // token (if/while/sizeof are calls syntactically but not semantically)
      [/[a-zA-Z_]\w*(?=\s*\()/, { cases: { "@keywords": { token: "keyword.$0" }, "@default": "function" } }],
      // SCREAMING_CASE identifiers read as macros/constants
      [/\b[A-Z][A-Z0-9_]{2,}\b/, "constant"],
      ...cppLanguage.tokenizer.root,
    ],
  },
};

const pythonEnhanced = {
  ...pythonLanguage,
  tokenizer: {
    ...pythonLanguage.tokenizer,
    root: [
      [/\b[A-Z][A-Z0-9_]{2,}\b/, { cases: { "@keywords": "keyword", "@default": "constant" } }],
      // CapWords = class reference; True/False/None are keywords, not classes
      [/\b[A-Z]\w*\b/, { cases: { "@keywords": "keyword", "@default": "type.identifier" } }],
      [/[a-zA-Z_]\w*(?=\s*\()/, { cases: { "@keywords": "keyword", "@default": "function" } }],
      ...pythonLanguage.tokenizer.root,
    ],
  },
};

// Re-register over the built-ins. Later registrations win in Monaco's
// tokenization registry, and this runs in the Editor's beforeMount — after
// monaco (and its built-in grammar factories) loaded, before any model renders.
export function defineEnhancedLanguages(monaco) {
  monaco.languages.setMonarchTokensProvider("c", cppEnhanced);
  monaco.languages.setMonarchTokensProvider("cpp", cppEnhanced);
  monaco.languages.setMonarchTokensProvider("python", pythonEnhanced);
}
