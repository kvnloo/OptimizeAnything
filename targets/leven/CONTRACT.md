# leven v4 -> Rust: frozen pilot contract

Reference: sindresorhus/leven, v4.0.0,
commit 447058af4df87e45724ad608c8892eb263aa1276.
Original index.js Git blob: 9eaec1f5531441e4141312e038a8b1be9d4fd7e5.

## Required behavior

Provide `pub fn leven(a: &[u16], b: &[u16]) -> usize`: unit-cost Levenshtein
insertion, deletion, and substitution distance on UTF-16 **code units**.
Empty inputs, NULs, equal strings, arbitrary u16 values, unpaired surrogates,
and repeated independent calls are in scope. No normalization, scalar decoding,
case folding, approximate matching, or grapheme segmentation.

The library is not restricted to the generated corpus. Finite tests cannot
prove all-input equivalence. JavaScript non-string inputs, npm packaging, ABI
compatibility, and matching resource-exhaustion exceptions are not in scope.

## Adapter protocol (pilot boundary)

Each UTF-8 input line has exactly two fields separated by one tab. Each field
contains comma-separated four-digit ASCII hexadecimal UTF-16 units; an empty
field is an empty sequence. A tab by itself denotes two empty sequences.
Adapters accept up to 4096 units per field, preserve order, and emit one
nonnegative decimal integer per line. Examples:

```text
0061,0062<TAB>0061   => 1
d83d,de00<TAB>      => 2
<TAB>              => 0
```

`<TAB>` above means a literal tab; input has no comments, spaces, or arrows.
Protocol input bounds do not change the Rust library's semantic contract.
Malformed adapter inputs must exit nonzero rather than fabricate a distance.

## Acceptance and anti-shortcut rules

No dependencies implementing distance, original-runtime delegation, unsafe
Rust, hard-coded corpus lookup, changed fixtures, or weakened graders. Preserve
upstream credit. Require Cargo fmt, debug tests, release tests, and exact
reference equality for every development and timed case. Benchmarking must
not proceed after failed correctness. Keep build flags constant across timing.

The current harness is same-author/public-corpus verification. Final grading
uses a trusted checkout, a separate verifier, and fresh workloads not exposed
for candidate repair. More samples on public fixtures do not make it independent.
