# OptimizeAnything

Optimize an existing application's **behavior, output quality, and performance**
together. Language changes are one possible experiment, not the objective.

**v0 is executable:** a standard-library Python runner, one pinned JavaScript
reference, a complete small Rust library port, deterministic differential tests,
resource gates, receipts, and a Hermes handoff. No model calls, search backend,
REA, dashboard, or mandatory dependencies on other zer0 repositories.

## First rewrite: `leven` (JavaScript -> Rust)

Sindre Sorhus's `leven` computes edit distance between two strings: `kitten` ->
`sitting` is 3. The reference is v4.0.0 at commit
`447058af4df87e45724ad608c8892eb263aa1276`.

The candidate preserves **UTF-16 code-unit semantics**, including unpaired
surrogates. The distance from an emoji encoded as a surrogate pair to an empty
string is 2, not 1. This is a behavioral library port, **not** an npm replacement.
The library uses safe Rust and no dependencies. All 14 upstream test examples
are included, alongside edge cases, exhaustive small pairs, and seeded cases.

## Run

Requirements: Python 3.10+, Node.js 18+, Cargo/Rust 1.70+ and rustfmt. CI pins
Rust 1.85.1. The numeric command-line protocol is supported on Linux/macOS;
Windows packaging and subprocess-tree isolation are not validated.

```sh
python3 -m unittest discover -s tests -v
python3 optimizeanything.py check
python3 optimizeanything.py bench --rounds 7
```

`check` runs formatting, debug/release Rust tests, the release build, and **6,698
exact reference comparisons** by default. `bench` first repeats those checks,
then compares a separate 72-case batch with warmups and alternating order.
Every timed output must match too. The unchanged JavaScript implementation is
always the baseline; a faster but wrong candidate fails.

Benchmarks measure **process startup + protocol parsing + batch computation**,
not just the library, and not a downstream application's speedup. Raw timing
samples and toolchain versions are recorded. Memory, energy, and model spending
are `null` when unmeasured. Shared CI timing is not production evidence.

Each invocation writes a new JSON file under `runs/`, including failures.
Exit codes: 0 = `PILOT_PASS`, 1 = `FAIL`, 2 = `BLOCKED`.

```sh
python3 optimizeanything.py check --seed 872349 --random-cases 10000
python3 optimizeanything.py check --candidate-dir work/my-candidate
python3 optimizeanything.py check --max-seconds 180 --command-timeout 60
```

A missing compiler is a recorded `BLOCKED`, never a simulated Rust pass.
Model-token budgets must be enforced by the external agent/provider; this
runner bounds subprocess wall time and output, not billing or resident memory.

## One-shot Hermes experiment

Paste `prompts/hermes-leven.md` into a fresh, externally budgeted Hermes session.
Give that session the pinned reference and contract, **not the included Rust
candidate or prior attempts**. It writes a separate candidate, then the trusted
runner grades it. The included candidate is the initial seeded implementation,
not evidence of an independently graded Hermes one-shot.

The public development corpus and same-author harness make this a **pilot**.
Fresh hidden grading workloads and a separately trusted runner are required for
an independent benchmark. Changed reference/test files are detected during a
run, but hashing inside a writable checkout is NOT a security boundary. Do not
run untrusted manifests or generated code on a host with sensitive files; use
an OS sandbox with restricted mounts, networking, and memory limits.

## Small extension surface

`targets/leven/experiment.json` declares build commands, workload generation,
reference and candidate commands, source pin, and integrity hashes. Commands
are argument arrays, never shell strings. They support `{root}`, `{candidate}`,
`{python}`, `{seed}`, `{random_cases}`, and `{suite}` substitutions; escape
literal braces in embedded commands. The v0 output contract is exactly one
unsigned integer per case, not a universal application evaluator.

Application-specific workloads and quality evaluators are the next extension.
Keep reusable engine code here; sustained target development belongs in its own
fork. This tiny vendored specimen makes the first experiment reproducible offline.

Next milestones, in order:
1. Independently grade fresh Hermes attempts and record cost per successful port.
2. Add a parser/stateful library and generalize only the interfaces it needs.
3. Optimize one runnable application's measured bottleneck; compare keeping the
   original, optimizing in the original language, and a justified alternative.
4. Add sourced technique research and optional search backends after the basic
   loop has a measured baseline. Do not rewrite the search engine first.

## Attribution and license

Kevin Rajan defined the product direction and experiment requirements. ChatGPT
implemented this initial harness and candidate; it did not run Hermes to produce
them. Sindre Sorhus and the `leven` contributors own the upstream implementation
and tests. Original source bytes are preserved in `targets/leven/vendor/index.mjs`
(renamed from `index.js` only); the MIT notice is adjacent. Port optimizations
such as common-prefix/suffix trimming are derived from that reference, not new
algorithmic claims. The repository's existing root `LICENSE` is unchanged.

Sources:
- https://github.com/sindresorhus/leven/tree/447058af4df87e45724ad608c8892eb263aa1276
- https://github.com/sindresorhus/leven/blob/447058af4df87e45724ad608c8892eb263aa1276/test.js
