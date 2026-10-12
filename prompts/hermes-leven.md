Execute a bounded one-shot library rewrite experiment, not a plan.

Read the trusted OptimizeAnything README and targets/leven/CONTRACT.md. Source:
https://github.com/sindresorhus/leven at
447058af4df87e45724ad608c8892eb263aa1276 (v4.0.0).
Use the byte-pinned source and MIT notice under targets/leven/vendor/.

Create a NEW Rust crate under work/hermes-leven. Do not inspect the included
Rust candidate, earlier attempts, or grader implementation. The trusted
launcher should withhold those paths rather than rely on this instruction.
Provide lib function `pub fn leven(a: &[u16], b: &[u16]) -> usize`, package and
binary name `oa-leven`, and the contract's hex-u16 tab-separated stdin adapter.
Preserve UTF-16 behavior, including lone surrogates. No dependencies, unsafe,
original-runtime delegation, hard-coded answers, or corpus-specific behavior.
Preserve upstream author/license credit. Commit a Cargo.lock so --locked works.

Use one implementation agent. Build, exercise reference comparisons, minimize
counterexamples, repair, and stop when the contract passes or the external
budget expires. Run cheap checks first; do not repeatedly compile expensive
profiles. Stop an approach after three attempts without progress or new evidence.
Do not edit the trusted engine, oracle, contract, workloads, or integrity pins.

The trusted runner can check the candidate with:
python3 optimizeanything.py check --candidate-dir work/hermes-leven
It can time it with:
python3 optimizeanything.py bench --candidate-dir work/hermes-leven
Final independent grading uses fresh withheld workloads and no repairs.

Suggested externally enforced envelope: $5 inference and 30 minutes. These
are ceilings, not predictions; a prompt cannot enforce a billing limit. The
runner's per-invocation timeout is separate from the whole-session budget.
Report actual/API-equivalent spend separately; unknown means null, never zero.
Retain failures. Do not push, publish, mutate unrelated files, or install global
tools. Missing prerequisites are BLOCKED, not permission to change the host.

Return candidate path, immutable revision/hash, actual checks, receipts, costs,
limitations, and PILOT_PASS/FAIL/BLOCKED. Do not claim an application speedup
from a process-startup-plus-batch benchmark. Do not claim independent one-shot
success unless the external verifier actually ran.
