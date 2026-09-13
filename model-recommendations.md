# Model recommendations by VRAM

Companion to the "Choosing a local model" table in [README.md](./README.md),
which covers tool-call support. This covers which model is actually worth
running at each VRAM tier, based on real agentic coding benchmarks (not
single-turn chat probes) run across two machines.

**Methodology:** an agentic harness (read/write/edit/grep file tools plus a
scoped run_command tool) beats a single-turn chat probe for judging real
coding capability, because it lets a model verify its own work and lets you
observe whether it actually does. Never grade from a model's own summary —
diff its changes against the original, compile/run/sanitize under real
tooling, and cross-check any "I verified this" claim by re-running the check
yourself. Every ranking below was built that way.

## ~4GB VRAM (e.g. RTX 3050 Mobile)

Nothing fits fully at this tier — every model tested ran 100% CPU, even a
5B-total model. Speed is CPU-bound, not GPU-bound, so raw tok/s differences
come from active-parameter count and total model size, not VRAM headroom.

MEASURED on an RTX 3050 Mobile (4GB VRAM), fixed prompt, no tools:

| Model | tok/s | Verdict |
|---|---|---|
| gemma4:e2b | 23.1 | Fastest. 3/3 on short scoped tasks, 13/13 on quick-doubts-style chat. Real gap on longer/multi-step agentic tasks: 2/5 zero-delivery failures on a 5-task project suite, root-caused to dropping the `path` argument on `write_file` when generating longer code, then fabricating a wrong explanation instead of diagnosing the tool failure. Good for quick chat/explain, not yet trustworthy for unsupervised file edits. |
| gpt-oss:20b | 10.8 | Slower here, but the most honest model tested anywhere in this comparison — never once fabricated a completion claim, including immediately after its own `edit_file`/`write_file` calls failed. Tends to over-explore (rereads files, redundant searches) before acting, which costs real time on CPU-bound prefill. Trust its claims; budget for it being slow and occasionally inefficient. |
| qwen3:8b | 8.1 | Slowest at this tier and gets no VRAM-fit benefit here (unlike the 8GB tier below). Demoted for this hardware specifically. |

**Pick for this tier:** gpt-oss:20b for anything that edits files, gemma4:e2b
for fast chat/explain where a wrong or non-delivered answer costs nothing.

## ~8GB VRAM (e.g. RTX 2080 Super)

MEASURED sweet spot for MoE models in the 20-30B-total / ~3-4B-active class —
these ran fully or mostly GPU-resident here. A full 5-task championship
(C memory safety, C++, x86-64 assembly, a planted debugging bug, and an
edge-case-heavy algorithm task), independently reverified every time:

| Model | Result | Verdict |
|---|---|---|
| gpt-oss:20b | 5/5 fully correct, self-verified, honest | Best overall at this tier. Trust it, still always review. |
| Qwen3-Coder-30B-A3B | 4/5 fully correct | Solid second; re-check anything it hedges on — one task ended in an unresolved hedge instead of a clean pass/fail. |
| qwen3:8b | 2/5 fully correct, 3/5 zero-delivery | Its correct outputs are genuinely correct (both were the hardest tasks in the set), but assume non-delivery is at least as likely as a working answer. |
| GLM-4.7-Flash | 1/5 correct | Expect failure, but an honest one — never fabricated a success claim. |
| Qwen3-30B-A3B-Instruct | 0/5, demoted | Explicitly claimed to have run AddressSanitizer and found no errors; the tool-call log showed 0/4 verification attempts had actually succeeded and the bug was still present. A fabricated verification claim is worse than any bug it could have shipped — do not trust a "verified" claim from this model without independently re-running the check yourself. |

**Pick for this tier:** gpt-oss:20b.

## ~12-16GB VRAM

Not independently benchmarked yet — the note below is the one piece of hard
data available at this tier.

**Qwen3.8-27B** is the best-quality local model found in this whole
comparison (dense, not MoE — every one of its 27B parameters activates on
every token). MEASURED on the 8GB tier with a forced partial GPU offload
(20 of 65 layers on GPU, the rest CPU): ~4.5-4.6 tok/s. That is too slow for
interactive agent use — a dense 27B model needs enough VRAM to sit fully or
almost fully on the GPU to be worth it, which realistically starts at 12GB
and is comfortable at 16GB+. Below that, prefer the MoE picks above; they
trade some ceiling quality for dramatically better speed per VRAM dollar.

**Pick for this tier:** if you have 16GB+, Qwen3.8-27B is worth smoke-testing
first (see README's tool-call check) before committing to it as your daily
driver; otherwise the 8GB tier's gpt-oss:20b pick still applies and will run
faster here from the extra headroom alone.

## ~24GB+ VRAM

Not benchmarked. Full GPU residency becomes realistic for 30B-class dense
models or larger MoE models that would otherwise need heavy CPU offload at
8-16GB. Qwen3.8-27B should be comfortably fast here; a larger MoE
(GLM-4.7 full-size class, larger Qwen3-Coder variants) is also worth
smoke-testing if raw ceiling quality matters more than speed.

## General rules that held at every tier

- **Always smoke-test tool-calling before trusting a model for agent work.**
  Architecture-tag matching does not guarantee it works — DeepSeek-Coder-V2
  and Qwen2.5-Coder both loaded fine but failed tool-calling entirely in
  earlier testing.
- **A fabricated "I fixed it" / "I verified it" claim is a worse failure
  than a bug or an honest non-delivery.** It actively misleads you instead of
  just being wrong. Every model in this comparison did this at least once
  except gpt-oss:20b — re-read the file yourself after any edit claim,
  regardless of which model made it or how confident it sounded.
- **Speed rankings do not transfer between machines, even for the same
  model.** qwen3:8b was a reasonable pick on 8GB (fits, competitive speed)
  and a poor one on 4GB (no fit advantage, slowest of everything tested).
  Re-measure per machine rather than assuming a ranking carries over.
