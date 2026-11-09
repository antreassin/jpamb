# S1 milestone: bytecode constants and input search B

`dictionary.py` is a dependency-free module for the current Group 15 fragment:
static methods with one or two Java `int` arguments. It extracts method-local
integer literals and implements B as a concrete target search. It adds no new
interpreter, coverage engine, corpus, or claims of unreachability.

## Policy

1. Try the same fixed tuples as A on the team's `Simone` branch: the Cartesian
   product of `0, 1, -1, 2, -2, INT_MIN, INT_MIN+1, INT_MAX-1, INT_MAX`.
2. Build a dictionary from the method's executable integer literals and their
   `c-1`/`c+1` neighbors, dropping neighbors outside signed 32-bit range. Keep
   fixed values first, then sorted unique additional values. Try up to 1,000
   Cartesian tuples, skipping tuples already in the fixed phase. Mixed tuples
   and equal pairs are included. The product is lazy and the order is stable.
3. Try up to 1,000 uniform random tuples using a caller-supplied `random.Random`.
   Both endpoints of the signed Java `int` range are valid; `2**31` is not.

These are explicit initial defaults, not tuned experiment results. The maximum
number of executions is `9**arity + dictionary_trials + random_trials`; the
dictionary phase can end earlier if its unique tuples run out. A small budget
uses a deterministic prefix and may miss useful combinations. B's extra phase
means its default total budget is larger than A's; compare with matched total
executions/time in the experiment runner and report all three phase counters.

`SearchResult` contains `verdict`, `witness`, `fixed_trials`, `dictionary_trials`
and `random_trials`. A witnessed target entry yields `reachable`; exhausting
the search yields `unknown`. The callback must check entry into the designated
instruction during **one run**, not just a method outcome. It must bound that
run's execution. Callback failures propagate instead of becoming verdicts.

## Bytecode adapters

`extract_jvm_constants(method["code"]["bytecode"])` consumes JPAMB's native
jvm2json instruction list. It reads integer `push` values and `incr.amount`.
`iconst`, `bipush`, `sipush`, and integer `ldc` are represented as `push` in that
format. Noninteger/null pushes are ignored. A `push` without its literal value
is an error, including the stripped pushes in the current structural CFG adapter.

`extract_javap_constants(method["instructions"])` consumes the raw
`(byte_offset, opcode, operand)` tuples produced by the existing validator. It
supports `iconst_m1` through `iconst_5`, `bipush`, `sipush`, integer `ldc`/`ldc_w`,
and `iinc`/`iinc_w`. It reads the resolved `// int` value of `ldc`, not its pool
index. This lets B use the current compiled benchmarks without jvm2json/Docker.

Both adapters return sorted, deduplicated integer tuples. They do not infer
values through arithmetic, fields, calls or switches. Implicit comparison-zero
is already covered by the fixed seeds. They retain irrelevant executable
literals (including `noise` and `hit` constants); offsets, source lines,
parameter/local indices, jump targets, annotations, labels and supplied
witnesses are not dictionary data. Select a single method before extraction.

## Use and integration boundary

From the repository root, this standalone example finds an input without
reading any benchmark answers:

```python
import random
from group15.dictionary import extract_jvm_constants, search

instructions = [
    {"opr": "push", "offset": 0, "value": {"type": "integer", "value": 100003}},
]
constants = extract_jvm_constants(instructions)
result = search(1, constants, lambda args: args[0] == 100003, random.Random(0))
assert result.verdict == "reachable" and result.witness == (100003,)
```

For the future Group 15 runner, after the shared loader is merged:

```python
# query and method come from the shared, artifact-verified loader.
from group15.dictionary import extract_javap_constants, search

constants = extract_javap_constants(method["instructions"])
result = search(
    len(query["parameters"]),
    constants,
    hits_target,
    rng,
    dictionary_trials=1000,
    random_trials=1000,
)
```

`hits_target(tuple[int, ...]) -> bool` matches A's callback convention. Use the
raw `method["instructions"]`, not `normalize_instructions()` output, which on
the inspected `Simone` branch omits literal values. A future JPAMB interpreter
adapter can wrap a tuple as
`jpamb.case.Input([jpamb.case.Int(value) for value in arguments])`.

For D, reuse `dictionary_values(constants)` to obtain the value pool or
`dictionary_inputs(arity, constants, max_trials=...)` for the extra tuples.
The latter excludes A's fixed tuples; the shared runner supplies that prefix.
The shared C engine should own coverage, corpus retention and mutation. A
later D change will schedule dictionary candidates in that same engine; this
milestone does not implement a second fuzzer or take over that shared work.

The benchmark PR #1 is merged at `b7bcba0`. At implementation time, `Simone`
contains S, A and shared loader changes at `40e927d`. This addition is based on
`main` and leaves those paths, the benchmark, and the proposal unchanged. After
the loader merges, add `run_b.py` using its artifact checks and report format,
then connect the dictionary iterator to the agreed C/D scheduler.

## Verification

From the repository root, in the normal JPAMB development environment:

```bash
uv run pytest tests/test_group15_dictionary.py
python3 group15/validate.py
uv run pytest
```

The focused tests cover both adapters, metadata exclusion, neighbors and Java
integer endpoints, input ordering, tuple budgets, deterministic randomness,
early stopping and unknown results. They also exercise tracked jvm2json data
and compile the real Group 15 methods with debug information, search their
bytecode, and replay generated witnesses on the JVM. The compiled integration
test needs JDK 17+; it is skipped when JDK tools are absent. The production
module never reads `targets.json` or imports the validator. Test-only evaluation
may use the validator and ground truth after input generation.
