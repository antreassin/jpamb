# Group 15 reachability experiments

Group 15 evaluates four dynamic strategies on eight paired-target Java methods and
a supported subset of the team’s 140 categorised queries. A witness is an input
that reaches the instruction entry for Target 1 and then Target 2 in one invocation.
A search with no witness returns `unknown`. Unsupported queries have a reason and
zero executions. The original 30 single-line queries have a separate label validator.

| Strategy | Input policy |
|---|---|
| A · basic | Our local implementation of the team’s documented policy starts with fixed inputs, then samples signed Java integers uniformly. |
| B · dictionary | After the fixed inputs, try method-local integer constants and their in-range neighbours, then sample uniformly. The dictionary reads integer pushes and `iinc` increments. Switch case keys are outside this policy. |
| C · coverage | Keep inputs that add instruction coverage. Pick a retained input uniformly and mutate one argument by adding or subtracting one, or by flipping one bit, with Java 32-bit wraparound. |
| D · dictionary + coverage | Feed B’s fixed and dictionary inputs into C’s corpus, then use C’s mutations. Both phases use the same coverage history. |

All strategies start with the same nine fixed values and their Cartesian products
for two arguments. Every attempted invocation, including a duplicate, counts
toward one total cap per method and strategy. Each trial starts with fresh search
state and a seeded RNG. Ground-truth labels and examples are used only for
validation and scoring. Every distinct discovered witness is replayed on the
original JVM class and on a diagnostic copy that records the target order.

## Setup

Run the commands from the repository root. Use Python 3.13+ and a JDK 17+ with
`java`, `javac` and `javap` on `PATH`. The recorded runs used CPython 3.13.5
and OpenJDK 23.0.2 on macOS arm64, compiling with `-g --release 17`.
The runners use the Python standard library. In an activated virtual environment,
install the locked test dependencies.

```sh
python -m pip install pytest==9.1.1 hypothesis==6.165.5
```

The category pilot and its integration tests also need four files from Simone’s
pinned revision. The runner works offline and verifies all four SHA-256 digests
before loading Python code or compiling Java. To provision the default directory
once, use the GitHub CLI (`gh`) with read access to `antreassin/jpamb`.

```sh
python -m group15.run_category_pairs --list-dependencies
python - <<'PYTHON'
from base64 import b64decode
from hashlib import sha256
from subprocess import check_output
from group15.category_backend import DEFAULT_DEPS, PINNED_FILES, REVISION

for name, expected in PINNED_FILES.items():
    endpoint = f"repos/antreassin/jpamb/contents/{name}?ref={REVISION}"
    data = b64decode(check_output(["gh", "api", "--method", "GET", endpoint, "--jq", ".content"]))
    if sha256(data).hexdigest() != expected:
        raise SystemExit(f"SHA-256 mismatch for {name}")
    dest = DEFAULT_DEPS / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
PYTHON
```

The default root is
`group15/build/category-deps/595c81fa1707dc6e99563580626415e8e42e00c8/`.
A teammate can also supply those exact bytes under the listed relative paths.
The pilot accepts an alternate root with `--deps`. Provision the default root
for the contribution test command below, and check for zero skips.

## Reproduce

```sh
python group15/validate.py
python -m pytest -q -rs tests/test_dictionary.py group15/tests
python -m group15.evaluate_pairs
python -m group15.run_category_pairs --strategies A B C D --seed 15 --total-executions 256 --max-steps 10000
```

**Rerunning an evaluation replaces its generated reports.** Both commands write
`trials.jsonl` and `summary.json` under `group15/build/`, in `pair-evaluation/`
and `category-evaluation/` respectively. The category command defaults to B/C/D.
Select all four strategies as shown to reproduce the 560-row pilot.

### Eight paired benchmarks

The grid covers `p01`–`p08`, seeds 0–19 and five budgets, giving 3,200 trials.
Each invocation of these loop-free methods is bounded by its method’s instruction
count. Each table cell counts verified discoveries out of 80 feasible trials
(four feasible methods × 20 seeds).

| Total execution budget | A | B | C | D |
|---:|---:|---:|---:|---:|
| 16 | 20 | 60 | 22 | 60 |
| 64 | 20 | 60 | 23 | 60 |
| 128 | 20 | 60 | 30 | 60 |
| 256 | 20 | 80 | 38 | 80 |
| 1,024 | 20 | 80 | 40 | 80 |

B and D matched on verdict, witness and execution count in all 800 matched
trials. Both first found `p08(100003, 100003)` at execution 131. Repeated
deterministic discoveries across seeds and budgets concern the same four methods.

### Categorised pilot

The pilot supports **59 of 140** queries with the pinned team interpreter.
These include 14 branching, 19 arithmetic, 19 loops and 7 Java edge cases. Supported entries
take one or two signed integers and have two unambiguous targets in the entry
method. The other 81 queries require unsupported signatures, calls, heap or
reference operations, floating-point operations, exception handlers or other
excluded bytecode. Per-query reasons appear in the generated results.

The pilot used **one seed (15)**, 256 candidate executions per query and strategy,
and 10,000 instructions per invocation. Of the 59 supported queries, 30 had a
reachable ground-truth label. The JVM independently confirmed all 34 distinct
method-and-witness combinations. There were zero label disagreements.

| Strategy | Discoveries among 30 feasible | Unknown | Unsupported |
|---|---:|---:|---:|
| A | 9 | 50 | 81 |
| B | 23 | 36 | 81 |
| C | 15 | 44 | 81 |
| D | 27 | 32 | 81 |

The trace counts only dispatched instructions and distinguishes normal returns,
instruction cutoffs and exceptional termination. Results depend on the supported
fragment, seed and budgets. Search times exclude preparation, constant extraction
and JVM replay, and depend on the machine. The legacy `run_pairs` and
`compare_pairs` commands use a return-value smoke oracle and start a JVM per
candidate. JVM startup dominates those timings, so report them separately from
the tracer experiments. JPAMB’s `@Case` score measures method outcomes.

## Original single-line benchmark validation

`src/group15/LineReachability.java` contains `q01`–`q30`.
`targets.json` records the expected labels, source lines, witnesses and proof
explanations. The validator compiles with debug information, maps each marked
assignment to its first bytecode instruction and checks each mapping against the
compiled method and descriptor. It rejects missing or ambiguous mappings.
JVM byte offsets and instruction-list indices are recorded separately.

Each method is static, loop-free and intraprocedural, with one or two unchanged
signed 32-bit integer arguments. Guards compare arguments to integer constants
or to each other. Each method sets a local flag to one at its target and returns
that flag or an early zero. This lets `validation/RuntimeCheck.java` cross-check
the recorded traces on the JVM.

Each template has one reachable and one unreachable member at each of three
constant settings (`c = -7, 0, 100003`). This gives 15 reachable and 15 unreachable
queries. Within each row, each setting’s reachable member precedes its
unreachable member.

| Queries | Template | Reachable condition | Unreachable condition |
|---|---|---|---|
| Q01–Q06 | Exact match | `x == c` | `x == c && x > c` |
| Q07–Q12 | Integer gap | `x > c-1 && x < c+1` | `x > c && x < c+1` |
| Q13–Q18 | Early-return filtering | `x >= c && x <= c` | `x >= c && x < c` |
| Q19–Q24 | Argument order | `x < y && y > x` | `x < y && y <= x` |
| Q25–Q30 | Shared equality | `x == y && x <= y` | `x == y && x < y` |

The integer-gap methods store the computed literals for `c-1` and `c+1` in
source. The argument-order and shared-equality templates vary an unused local
literal while keeping their guards fixed. These settings measure the effect
of irrelevant constants. They repeat the same reachability conditions.

### Why the labels cover the entire domain

The validator parses the actual Java methods using a deliberately narrow
grammar. It rejects unsupported syntax and parameter mutation. It does not use
the metadata's explanation or expected label to decide which path executes.

For each method, collect its guard constants and the Java `int` endpoints.
These divide the integers into singleton constants and nonempty open intervals.
Use every singleton and up to two distinct representatives from each interval.
Then enumerate all tuples for the method's one or two arguments.

For any concrete tuple, its comparisons to constants depend only on its cells.
Within an interval the representatives realize every possible ordering of two
arguments. Between different cells their order is fixed. Thus every
possible truth pattern of the permitted comparisons has a representative tuple.
Unchanged arguments make every subsequent branch decision identical. Exhaustive
execution of these tuples is therefore a complete decision procedure for these
methods. Unused local literals cannot influence a guard and therefore need
no additional partition.

The source checker independently records whether the target assignment executes.
Every declared witness is checked directly, and every reachable query must also
have a rejecting input. A separate concrete bytecode interpreter traces entry
into the actual mapped target instruction for every checked input. Those traces
must agree with source execution, and JVM results must agree with both.
The partition argument above supplies the proof of unreachability.

The validator checks 333 inputs against source, bytecode and JVM execution.
It writes proof evidence to `group15/build/validation.json`, answer-free target
mappings to `analysis-inputs.json` in the same directory, and disassembly to
`LineReachability.javap.txt`.
