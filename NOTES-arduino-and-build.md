# Notes: slow builds, CI idea, Arduino branch review, ROADMAP suggestions

Documentation only. No code changes. Written from a read-through of the
README and ROADMAP on `main` and the README of `feat/arduino-upload`; nothing
here has been tested on Windows yet.

## 1. Slow compile

Observed: a full build takes close to 2 hours on an Intel i5 6th gen.

- The first build is always the slowest. Later builds reuse the incremental
  cache, so keep the `target/` directory between builds and do not run
  `cargo clean` unless needed.
- For quick checks while editing, use `cargo check` (no codegen) or a debug
  build instead of a release build.
- Release builds are for producing the distributable only.

## 2. CI idea: build the Windows .zip on GitHub Actions

Instead of compiling the release locally, add a manually triggered workflow
(`workflow_dispatch`) that builds the Windows release and uploads the `.zip`
as an artifact. The weak local machine then only needs to download and test
the result.

Open points to decide before implementing:

- Which runner and toolchain versions to pin.
- Whether to cache `target/` and the cargo registry between runs.
- Whether the artifact is only for testing or also feeds a release.

## 3. Review notes for `feat/arduino-upload`

The branch adds an Arduino toolbar and Tools menu using `arduino-cli`,
`arduino-language-server` with `clangd`, Arduino syntax highlights, a
Build & Run button replacing F9, and a plain C/C++ upload option.

To check or improve:

- Downloads of `arduino-language-server` and `clangd`: confirm a checksum or
  signature is verified after download.
- A leftover bullet still mentions `.pde` files. Decide if legacy `.pde`
  is supported and fix the text either way.
- Opening a sketch should open the sketch folder, not only the single file.
- Do a real test on Windows with an actual board (a servo sketch is a good
  smoke test: compile, upload, serial output).
- Arduino IDE 2 only reloads external changes when the sketch is saved.
  Worth remembering when testing the editor and the IDE side by side.

## 4. ROADMAP suggestions

- Split the changelog out of `ROADMAP.md` so the roadmap only lists future
  work.
- Note that F9 Build & Run did not work before; the README should not claim
  it does until the new button replaces it.
- Add an Arduino section to the roadmap.
- Strip the release binary to reduce download size.
- Reduce the number of target platforms if they are not all maintained.
- The README and docs disagree on the minimum glibc (2.31 vs 2.35). Pick the
  real one and make them consistent.
