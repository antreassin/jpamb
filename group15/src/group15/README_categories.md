# LineReachabilityCategories: a categorised two-line reachability benchmark for Java

`LineReachabilityCategories.java` (package `group15`) holds **140 Java test methods** for evaluating a
*two-line reachability* analysis. Each test is a small method with two marked assignments,
`// Target 1` and `// Target 2`. The question is whether **both can execute in the same run**.

The tests form **7 categories of 20 tests**. Every category has exactly **10 reachable and 10 unreachable**
tests, so always answering the same way scores 50%.

---

## 1. Conventions

- Each target sets a flag to 1 (`a = 1; // Target 1`). The method returns the sum of the flags, so a run that
  executes both targets returns **2**.
- Whenever both targets execute, **Target 1 executes first**.
- **Each target is reachable on its own** in every test. Only the *pair* is in question, so a tool cannot
  score by spotting dead code. It has to reason about the two conditions *together*.
- Both targets are inside the entry method, except in category 4, where targets may sit in helper methods
  (marked `Helper for methods_NN`, placed right after the test that uses them).
- A `null` argument throws before any target, so witnesses are never `null`. Exceptions are part of the
  semantics (see category 1).
- Many tests are wrapped in bounds such as `-1000 <= x <= 1000`. They keep arithmetic from wrapping and
  loops and recursion small (see the ideal-semantics rule below). Verdicts are for the code as written.

Every test has a comment block above it:

```java
// loops_07: REACHABLE pair                      <- label: REACHABLE or UNREACHABLE
// Type: early-exit search loop. k is the ...    <- construct that decides the verdict, then the tricky part
// ...
// Example: n = 20 reaches both targets (returns 2).   <- reachable tests only: a verified witness
public static int loops_07(int n) { ... }
```

---

## 2. Overview

| # | Category | Prefix | The verdict depends on |
|---|---|---|---|
| 1 | Branching and control flow | `branch_` | combining path conditions; which paths exclude each other |
| 2 | Ideal arithmetic | `arith_` | number-theoretic facts: relations, divisibility, products, bits |
| 3 | Loops | `loops_` | how often a loop runs and what it leaves behind |
| 4 | Methods and recursion | `methods_` | summarising code across calls; recursion |
| 5 | Arrays and strings | `arrstr_` | indexed data with a symbolic length |
| 6 | Objects and types | `objs_` | fields, constructors, types, dispatch, aliasing, static state |
| 7 | Java edge cases | `edge_` | Java rules that differ from ideal mathematics |

---

## 3. Design principles

**Categories are features, not difficulty levels.** A category names *which construct decides the answer*.
Difficulty is a separate axis and is deliberately not encoded in this file; within a category the tests
still range from simple to hard. Each category matches a capability an analysis needs:

| Category | Capability needed |
|---|---|
| Branching | path-sensitive reasoning: conjoin and compare path conditions |
| Ideal arithmetic | integer constraint solving: linear, modular, non-linear, bitwise |
| Loops | loop summaries (counts, closed forms, invariants), not just bounded unrolling |
| Methods and recursion | interprocedural reasoning: summaries and recursion fixpoints |
| Arrays and strings | array and string theories with a symbolic length |
| Objects and types | heap reasoning: aliasing, type constraints, dispatch |
| Java edge cases | bit-precise Java semantics |

**The ideal-semantics rule.** In categories 1-6 the verdict stays the same if Java `int` were the
mathematical integers and no floating point were involved. Category 7 deliberately violates this: with
mathematical integers or real numbers the verdict would flip. A failure in 1-6 is therefore a *reasoning*
failure, and a failure in 7 is a *semantics-modelling* failure. Category 7 comes last because every earlier
category can be solved with an idealised model of Java; this one cannot.

**One deciding construct per test.** A test may *use* other constructs, but it is filed under the one whose
removal would make the verdict trivial. For example `arrstr_06` is an array scan, not a loop test.

**Why 10/10, and why both targets are individually reachable.** Half reachable removes the constant-answer
shortcut. Individual reachability removes the "this line is dead code" shortcut.

The categories also follow the structure of established work: the SV-COMP reachability categories (Arrays,
BitVectors, ControlFlow, Floats, Heap, Loops, Recursive) and the infeasible-path literature, which lists
branch correlation, conflicting predicates, loop-related causes, data dependences, and non-linear and
floating-point operations as causes of infeasible paths.

---

## 4. The categories

### 4.1 Branching and control flow (`branch_`)

Loop-free code that calls no user-written method.

- **Predicate combinations** (01-04). `branch_01` and `branch_03` are decided by *integrality*: the open
  interval (10, 12) holds exactly one integer, so treating variables as reals gives the wrong answer.
  `branch_02` needs a relation between three variables. `branch_04` uses a large constant (100003), which
  defeats random testing.
- **Derived values** (05-07): a score built from two branches, boolean flags, a clamp.
- **Structural exclusion** (08-10): else-if arms, a state flag, early `return`.
- **Compound conditions** (11-13): De Morgan, and `?:` as maximum and minimum.
- **Switch** (14-16): stacked labels, `default` first with fallthrough, a switch on a `String`.
- **Exceptions** (17-20): `finally` running on both paths, an implicit
  `ArrayIndexOutOfBoundsException` as control flow (18), a swallowed exception, and an exception propagating
  through `finally`.

Exceptions belong here because they are control flow. `branch_16` is the only test in this category with a
`String` argument, so `null` is meaningful there.

### 4.2 Ideal arithmetic (`arith_`)

Integer reasoning where ordinary mathematics is exact.

- **Linear relations** (01-04). `arith_02` (`x + y == 10`, `x - y == 5`) forces `x = 7.5`: no integer
  solution although each equation alone has many. `arith_03` hides `x + y == 11` in a scaled equation.
- **Division and modulo** (05-08): Java's truncating division (`x / 5 == 2` means 10..14), parity, and quotient
  and remainder tied to one variable.
- **Bounded products** (09-12): `x * y == 30` plus a sum or difference condition needs a search over factor
  pairs; `arith_12` asks for a perfect square.
- **Congruences** (13-16): different moduli, a Chinese-remainder case (16), one modulus implying another (15).
- **Bitwise operations** (17-20): masks, shifts, the low-bit parity test, the power-of-two trick
  `x & (x - 1) == 0`.

An interval domain cannot decide `arith_02`, `arith_14` or `arith_15`: the contradictions are parity or
congruence facts, not range facts. Products and sums that could wrap sit inside bounds; parity and low-bit
facts hold under wraparound too, so `arith_06` and `arith_19` are unguarded.

### 4.3 Loops (`loops_`)

The verdict depends on the iteration count or on what the loop leaves behind.

- **Counting** (01-03) and **accumulation** (04-06): `3n`, a doubling step, sums of even numbers, iterative
  factorial, the sum of the first `n` odd numbers (`n * n`).
- **Early exit** (07-10): a search loop, `break`, `continue`, `while (true)`.
- **Loop entry and step** (11-13): a `do-while` (the body runs once even if the condition is false), a
  compound loop condition, a step of 4 (iterations = ceiling of `n / 4`).
- **Nested loops** (14-16): a dependent inner bound (`n * (n - 1) / 2`), an inner `break`, a labeled `continue`.
- **Invariants** (17-20): lockstep variables, a congruence preserved by the loop, a conserved sum, two pointers
  meeting.

The iteration count depends on the input, so **bounded unrolling** misses witnesses with a large `n` and can
never prove unreachability (`loops_07` needs `n` between 17 and 25, `loops_14` needs `n = 5`). Where a
product could wrap (`loops_03`, `05`, `07`), `n` is bounded.

### 4.4 Methods and recursion (`methods_`)

The analysis must reason across method boundaries; recursion is the hard end.

- **Helper summaries** (01-04): a call whose result is a *range* (`clampTo(x, 0, 10) == 10` holds for every
  `x >= 10`), and helpers with three return values.
- **Call chains** (05-07): `inc(twice(x))`, `add(twice(x), inc(y))`, and `sub(add(x, y), y)` where `y` cancels.
- **Targets in callees** (08-11): the only tests where a target is in a helper. The callee runs its target
  depending on its argument, and the entry method passes a *transformed* argument (`x + 1`, `x - 3`,
  `clampTo(x, 0, 20)`).
- **Several return values** (12-13): the entry method branches on which value came back.
- **Direct recursion** (14-16): `sumTo` (returns 0 for every negative input), Euclid's `gcd`, `pow2`.
- **Targets inside recursion** (17-18): in `walk17` the base case holds Target 1 and a multiple of 7 stops
  the recursion at Target 2, so the two exits are exclusive. In `rec18`, Target 1 fires on the way down and
  Target 2 at the base case.
- **Mutual recursion** (19-20): `ping`/`pong` and `evenRec`/`oddRec`.

Calls and recursion share a category because both are about summarising across methods; recursion adds a
fixpoint. Recursion depth is bounded by guards in the entry method (for example `0 <= x <= 100`); without
them a negative argument would recurse until a `StackOverflowError`. In `methods_17` the helper returns 1
for either exit, since the targets are mutually exclusive; in `methods_18` the flags are summed along the
recursion.

### 4.5 Arrays and strings (`arrstr_`)

Sequences indexed by position, usually with a symbolic length.

- **Fixed arrays and lengths** (01-03): a constant array indexed by the input (bounds check first), an array
  whose length depends on the input.
- **Writes and reads** (04-05): a write at a symbolic index and a read at a fixed one.
- **Array scans** (06-10): a maximum with a `MIN_VALUE` sentinel, a count, adjacent equality (implies
  first-equals-last by transitivity), a reverse copy.
- **String inspection** (11-16, 19): `length`, `charAt`, `equals`, `startsWith`/`endsWith`, `indexOf`,
  `substring`.
- **String construction** (17, 18, 20): concatenation in a loop and `s + s`.

Array and string arguments have a symbolic length, so the scans involve loops over an unknown number of
iterations; string tests need a string theory or an explicit length bound. Comparisons are case sensitive.

### 4.6 Objects and types (`objs_`)

Ordinary object-oriented reasoning with no Java quirks.

- **Field mutation** (01-06): a counter incremented under conditions, an account whose `withdraw` may do
  nothing, a pair that swaps its fields.
- **Constructors** (07-10): a constructor that clamps its argument, a rectangle with a derived `area()`.
- **Type checks** (11-14): `instanceof` with a cast, unrelated classes (nothing is both a `String` and an
  `Integer`), `null` versus `instanceof Object`.
- **Dynamic dispatch** (15-16): the receiver's concrete class depends on the input.
- **Aliasing** (17-18): two references that are the same object only for some inputs.
- **Static state** (19-20): a static field accumulated across calls; it is reset at the start of each test.

A tool needs a heap model plus type reasoning. Java's identity quirks (`Integer` cache, `String ==`) are
not here; they belong to category 7.

### 4.7 Java edge cases (`edge_`)

The verdict comes out right only if a Java rule is modelled; with mathematical integers or reals it would be
wrong.

| Sub-type | Tests | The rule |
|---|---|---|
| Numeric representation | 01-08, 11, 13, 14, 17 | int overflow (`x * x < 0`, `Math.abs(MIN_VALUE)`), narrowing (`byte`, `char`, `(int)` of a double, `short +=`), float and double rounding and absorption, NaN, negative zero |
| Operator semantics | 09, 12, 18, 20 | shift distance modulo 32, sign of `%`, unsigned shift `>>>`, `i = i++` |
| Reference identity | 10, 16 | `String ==` versus `equals`, the `Integer` cache |
| Library rules | 15, 19 | `String.hashCode` collisions, `Math.round` (rounds half up) |

Reachable tests use a special value as witness (`Integer.MIN_VALUE`, `NaN`, `-0.0f`, `x = 33`, a fresh
string object). Unreachable tests are those where a Java rule removes a witness an idealised model would
accept; for example `0.1 + 0.2` is not the double nearest to `0.3` (`edge_11`).

Results were obtained on OpenJDK 21. Floating-point arithmetic is strict since JDK 17, which `edge_06` and
`edge_13` rely on, and `edge_16` assumes the default `Integer` cache range of -128 to 127.

---

## 5. How the verdicts were checked

A script confirmed the structure: label, `Type:` line and explanation on every test, names `<prefix>_01` to
`_20`, 10 reachable and 10 unreachable per category, and targets in helpers only in category 4.

For the behaviour, a copy of the file was instrumented so that each target records when it fires, and every
test was run on a large input set on OpenJDK 21. For every test it checked that:

1. both targets are individually reachable;
2. a run fires both targets exactly in the tests labelled reachable;
3. Target 1 fires before Target 2 whenever both fire;
4. the return value equals the number of targets hit.

Inputs: ints from -3000 to 3000 (smaller ranges for loop and length arguments) plus extreme values such as
`MIN_VALUE` and `MAX_VALUE`; grids for two and three arguments; arrays of length 0-4; all strings up to
length 3 over a small alphabet plus selected longer ones; a set of objects; and selected `float` and
`double` values (NaN, infinities, signed zeros, rounding boundaries). Each `Example:` line is the simplest
input found that fires both targets.

For eight tests the whole input space was enumerated (all 2^32 values; for the float test all 2^32 bit
patterns): `edge_12`, `13`, `14`, `17`, `18`, `20` (unreachable) and `edge_01`, `02` (reachable).

---

## 6. Using the benchmark

1. Take the ground truth from the label line above each test.
2. Analyse each method for the two marked lines.
3. Report per category, and separately for reachable and unreachable tests. For an over-approximating
   analysis, a wrong "reachable" answer is *imprecision* and a wrong "unreachable" answer is *unsoundness*.
4. Compare categories 1-6 with category 7. A tool good on 1-6 but weak on 7 models Java as mathematics; a
   tool weak on 3 or 4 lacks loop or interprocedural reasoning.
5. Use the `Example:` inputs as dynamic oracles: running the method on them must return 2.

---

## 7. Limitations

- **Verdict proofs.** Only the eight tests above are proved exhaustively. Every other *reachable* verdict is
  certain (the example was executed), but the other *unreachable* verdicts rest on the written argument plus
  a bounded search.
- **Near-twin pairs.** Reachable and unreachable tests were meant to be independent, but a few pairs share a
  skeleton and differ in one condition: `arith_09`/`10`, `arrstr_01`/`02`, `arrstr_09`/`10`,
  `arrstr_17`/`18`, `objs_05`/`06`, `objs_07`/`08`, `objs_09`/`10`, `objs_17`/`18` (16 of 140 tests).
- **No difficulty or reason tags.** The reason an unreachable pair is unreachable (contradictory predicates,
  control-flow exclusion, arithmetic impossibility, Java rule) is given only in prose.
- **Coverage gaps.** Not covered: `long`/`short`/`char` parameters, collections, generics, lambdas,
  exceptions thrown from a callee, targets in different classes, concurrency and I/O. Aliasing, static state
  and dynamic dispatch have only two tests each.
- **Platform.** Edge cases assume OpenJDK 21 defaults.
