# Group 15: first 30 line-reachability queries

This is a standalone, reviewable starting dataset for **Climbing the Analysis
Ladder**. It contains 30 independently labeled single-line queries: five
reachable/unreachable template pairs, each instantiated at three fixed constant
settings. There are 15 reachable and 15 unreachable targets. These are 30
queries, not 30 statistically independent program designs.

## Use it

From the JPAMB repository root, with Python 3.10+ and a JDK 17+ on `PATH`:

```bash
python3 group15/validate.py
```

The validator compiles with debug line information, validates the labels over
the full supported input domain, checks that all target instructions survive
compilation, and cross-checks concrete execution on the JVM. It writes generated
files under ignored `group15/build/`. No third-party Python packages are needed.

A successful run writes `build/validation.json` with the proof evidence and
compiler-specific mappings, `build/analysis-inputs.json` with target inputs but
no answer fields, and `build/LineReachability.javap.txt` with the disassembly.
Failed reruns remove earlier successful reports and input mappings.

### Run the structural analysis (S)

The S runner is now implemented in [run_s.py](run_s.py), reusing the existing
`parse_disassembly` bytecode loader in [validate.py](validate.py). Its small
adapter converts raw JVM jump offsets to instruction-list indices, then calls
the shared [structural analysis](../solutions/syntactic/src/structural.py).
It does not write a new Java or bytecode parser.

Run these commands from the repository root in PowerShell (Python 3.10+ and
JDK 17+ must be on `PATH`):

```powershell
python group15\validate.py
if ($LASTEXITCODE -eq 0) { python group15\run_s.py }
```

If the JDK is not on `PATH`, set it for your current terminal first, using your
actual installation directory:

```powershell
$env:JAVA_HOME = 'C:\path\to\your\jdk-17'
$env:Path = "$env:JAVA_HOME\bin;$env:Path"
javac -version
```

This standalone route needs neither Docker nor a JPAMB package installation.
It uses the same S core and instruction-index convention, but **is not a
verified integration with jvm2json or the team's concrete interpreter**.

The runner reads only `build/analysis-inputs.json`, the source hash and the
compiled class. It never reads `targets.json` or the validator's answer labels.
It invokes `javap` on the current class and checks the method descriptors,
source lines, statement-entry offsets and instruction indices against the
manifest. Each target must still start with the assignment's `iconst_1` followed
by its store on the same source line. Unsupported instructions, backward edges,
exception handlers, stale hashes and missing/ambiguous mappings are errors,
not `unreachable` verdicts.

The output is one `query-id;verdict` line per query and a persisted report at
`build/s-results.json`, including artifact hashes. Failed S reruns remove this
report; rerunning the validator also invalidates it.

The verified result on JDK 17.0.21 is **30 unknown, 0 unreachable**. This includes
all 15 actually unreachable targets: their contradictions require reasoning
about guards, which S deliberately omits. No S result is `reachable`.

Tests, including a fresh compilation of the real 30-method dataset:

```powershell
python -m pytest -c solutions\syntactic\pyproject.toml solutions\syntactic\tests -q
```

The tests require `pytest`; only the real-JVM integration tests are skipped
when the JDK tools are absent. The integration tests explicitly cover Q01
(equality), Q02 (contradictory nested guards) and Q13 (early returns), as well as
the complete dataset. All three examples return `unknown`.

To test a genuine `unreachable` result, the unit tests use synthetic bytecode
with a `goto` over an instruction, or an instruction after a `return`, with no
other incoming path. Do not use an invalid target index or a source line removed
by compilation: neither is an unreachability proof. Java rejects some dead
statements and compilers can remove others, so synthetic instruction lists are
the simplest direct test of this rule.

An English S-only report fragment is provided in [syntactic-s.tex](syntactic-s.tex).
It uses the team's `\Owner` and `\MemberFour` macros and is intended for inclusion
in the report, not as a standalone LaTeX document. It makes no claims about A.

To inspect the compiled code yourself after validation:

```bash
javap -classpath group15/build/classes -c -l -s group15.LineReachability
```

## Files and target meaning

- `src/group15/LineReachability.java`: the 30 benchmark methods, `q01`–`q30`.
- `targets.json`: authoritative identities, exact source lines, stable markers,
  expected labels, witnesses and proof explanations.
- `validate.py`: an independent restricted-source checker and validation driver.
- `validation/RuntimeCheck.java`: concrete JVM validation harness; it is not part
  of the benchmark methods or their supported language subset.

For example, `G15-Q01` names the assignment on the line containing
`// TARGET: G15-Q01` in method `q01`. The target is **entry into that assignment**,
not entry into the method, evaluation of its guard, or its final return.

Every benchmark starts with `hit = 0`, assigns `hit = 1` only at its target, and
returns `hit` (or returns zero along an early exit). This makes return values a
convenient validation oracle without calls, fields, arrays, exceptions or
assertions inside the benchmark. Neither a comment nor a return is used as the
target. The validator checks that the assignment has executable bytecode even
when its path is logically impossible. An absent or ambiguous source mapping
is a validation failure, **never an unreachable label**.

All methods are static, loop-free and intraprocedural, with one or two unchanged
`int` arguments. Guards compare an argument with a literal or the other
argument. There is no arithmetic on arguments and therefore no arithmetic
overflow assumption hidden in the proofs. The input domain is every Java
signed 32-bit integer, including both endpoints.

## Dataset design

The proposal specifies the dataset shape, not these particular templates or
constant values. The choices below are new implementation choices for this
first set. Each row contains a reachable and unreachable member at `c = -7`,
`c = 0`, and `c = 100003` (settings C1, C2, C3).

| Queries | Template | Reachable condition | Unreachable condition |
|---|---|---|---|
| Q01–Q06 | T1: exact match | `x == c` | `x == c && x > c` |
| Q07–Q12 | T2: integer gap | `x > c-1 && x < c+1` | `x > c && x < c+1` |
| Q13–Q18 | T3: early-return filtering | `x >= c && x <= c` | `x >= c && x < c` |
| Q19–Q24 | T4: argument order | `x < y && y > x` | `x < y && y <= x` |
| Q25–Q30 | T5: shared equality | `x == y && x <= y` | `x == y && x < y` |

Within each row the order is C1 reachable, C1 unreachable, C2 reachable,
C2 unreachable, C3 reachable, C3 unreachable. T1 supplies three single-guard
baselines; the other targets require two comparisons. The `c-1`/`c+1` notation
above is explanatory: the Java source contains the already-computed literals.

T2's unreachable gap is empty over **integers**, even though it is nonempty over
reals. T3 requires following the false edges of both early exits. T4 and T5 need
relationships between arguments to prove the impossible cases.

For T4 and T5, `c` appears only in an unused local `noise` assignment: their three
settings intentionally vary an **irrelevant executable literal**, not the path
condition. This keeps the two-argument contradictions within two simple guards
and supplies a controlled distraction for dictionary input generation. These
are repeated semantic instances; do not describe them as six distinct
reachability challenges per template. Adding threshold-dependent relational
families later would require revisiting the two-guard restriction.

The `hit` literals 0 and 1 are also executable constants. A faithful dictionary
extractor should include them; comments, source line numbers, bytecode offsets,
metadata labels and IDs are not dictionary constants. The large equality
setting provides a deliberately narrow target that uniform random input is
unlikely to find. This small constructed suite favors some techniques by
design; it is not representative evidence about arbitrary Java programs.

## Why the labels cover the entire domain

The validator parses the actual Java methods using a deliberately narrow
grammar. It rejects unsupported syntax and parameter mutation. It does not use
the metadata's explanation or expected label to decide which path executes.

For each method, collect its guard constants and the Java `int` endpoints.
These divide the integers into singleton constants and nonempty open intervals.
Use every singleton and up to two distinct representatives from each interval.
Then enumerate all tuples for the method's one or two arguments.

For any concrete tuple, its comparisons to constants depend only on its cells.
If two arguments occupy the same interval, two representatives realize `<`,
`=`, and `>`; if they occupy different cells, their order is fixed. Thus every
possible truth pattern of the permitted comparisons has a representative tuple.
Unchanged arguments make every subsequent branch decision identical. Exhaustive
execution of these tuples is therefore a complete decision procedure for these
methods, not an arbitrary small-number test range. Unused local literals do not
need to split the domain because they cannot influence any guard.

The source checker independently records whether the target assignment executes.
Every declared witness is checked directly, and every reachable query must also
have a rejecting input. A separate concrete bytecode interpreter traces entry
into the actual mapped target instruction for every checked input. Those traces
must agree with source execution, and JVM results must agree with both.
Compilation and target-line mapping provide additional artifact checks. No finite collection
of JVM tests alone is presented as a proof of unreachability.

## How this fits the actual team fork

Inspected on 2026-11-02 at
[`antreassin/jpamb@273ec51`](https://github.com/antreassin/jpamb/tree/273ec51a807f2780bafe820d2463d3f2e12ed57d).

- The actual Java source root is `cases/`, and `Suite.sourcefiles()` scans
  `cases/**/*.java`: [build code](https://github.com/antreassin/jpamb/blob/273ec51a807f2780bafe820d2463d3f2e12ed57d/src/jpamb/__init__.py).
- `cases/jpamb/Runtime.java` enumerates a hard-coded class list and reads
  `@Case` annotations: [runtime](https://github.com/antreassin/jpamb/blob/273ec51a807f2780bafe820d2463d3f2e12ed57d/cases/jpamb/Runtime.java).
- Original `@Case` values specify possible **method outcomes** such as `ok`,
  assertion error or divide by zero. They do not specify single-line
  reachability: [JPAMB description](https://github.com/antreassin/jpamb/blob/273ec51a807f2780bafe820d2463d3f2e12ed57d/README.md).
  Its runtime discards method return values, so `ok` does not mean a target ran.
- `docs/extending-jpamb.md` mentions `src/main/java`; that path is stale relative
  to the inspected implementation. The fork also tracks compiled artifacts in
  `target/`, which this addition leaves untouched.

This isolated folder is intentional. It adds no `@Case` annotations, does not
modify `Runtime.caseclasses`, and does not add the custom labels to upstream
outcome scoring. The standard `jpamb` case list will therefore not discover
these 30 queries automatically. A Group 15 runner should consume the custom
query identities and observe execution at each designated instruction entry.
The standalone S runner described above implements this query interface using
the existing `javap` loader. The remaining ladder analyses and integration with
the team's concrete interpreter are separate work.

Method identifiers follow JPAMB's syntax, for example
`group15.LineReachability.q01:(I)I` and
`group15.LineReachability.q19:(II)I`.

**Byte offsets and instruction indices are different.** `javap` displays JVM
byte offsets. JPAMB coverage PCs use zero-based indices into jvm2json's
`method["code"]["bytecode"]` list. In that JSON, an instruction's `offset` is its
raw byte offset, while `code.lines[*].offset` and branch targets are instruction
indices. For a compiled artifact, map the validated statement-entry offset:

```python
target_index = next(
    i for i, instruction in enumerate(method["code"]["bytecode"])
    if instruction["offset"] == target_byte_offset
)
```

Use the matching method and descriptor, and verify the JSON source-line mapping.
Do not hard-code a `javap` byte offset as a JPAMB PC. Rebuild mappings after any
source or compiler change; the JSON manifest pins the source hash and exact
source lines, while build reports describe the particular compiled artifact.
The checked-in metadata's source hash is computed after normalizing CRLF to LF,
so a Windows Git checkout does not change its meaning. Generated manifests
and reports still hash the exact source and class bytes used in that run.

If `jvm2json` is installed in your existing JPAMB environment, a later runner
can convert the independently compiled class without changing upstream sources:

```bash
jvm2json -s group15/build/classes/group15/LineReachability.class > group15/build/LineReachability.json
```

This command requires the converter; it is not part of the dependency-free
validation command. Conversion through Docker and the team's JPAMB interpreter
were not run for this delivery because the local Docker daemon was unavailable.

## Evaluation and later extension

Keep `expected`, `witness`, `path_condition` and `rationale` out of analyzer inputs.
Give each analysis only the program, method identity and target location; the
evaluation harness reads the answer fields afterward. Witnesses in this file
are ground truth, not seed inputs for B/D. A dynamic search that misses a target
reports **unknown/not found**, not unreachable.

The generated `build/analysis-inputs.json` provides those answer-free records.
Its mappings are bound to the compiled class hash; verify that hash before
using them. Its disassembled instruction indices still require confirmation
against the exact jvm2json output used by the team.

Before final experiments, ask a teammate to review the labels and replay the
reachable witnesses through the team's interpreter. The independent checker and
JVM checks here are a strong first validation, not a claim that the as-yet
unintegrated team interpreter has been tested. Pin the dataset version and
compiler, publish mapping exclusions and keep upstream JPAMB outcome results
separate.

The optional eight ordered checkpoint-pair queries are deferred. If added, put
them in a separate source/manifest and report their results separately: four
feasible, four infeasible, with both endpoints individually reachable and
feasibility requiring P then Q in the **same execution**. Observe existing
instruction entries rather than inserting helper calls, assertions or returns.

## Commit this contribution

Use `feature/group15-benchmark-cases` and a PR into **antreassin/jpamb:main**.
Commit only `group15/`; generated `group15/build/` is ignored. The accompanying
commit guide gives safe clone, branch and review commands. No push or PR has
been made on your behalf.
