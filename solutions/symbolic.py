"""Two-line reachability by bounded symbolic execution.

Question: can two locations of a method be executed in the SAME run (in either
order)? The analysis follows the lecture notes (Concolic Execution, "Symbolic
Execution / In Practice"): a depth-first search over the bytecode that keeps a
symbolic state and a path constraint, and asks z3 whether each branch is
satisfiable. Method arguments are symbolic 32-bit bit-vectors, so Java's
overflow semantics are respected.

Usage, from the JPAMB folder:

    uv run --project solutions/symbolic symbolic-reach info
    uv run --project solutions/symbolic symbolic-reach \
        "group15.LineReachability.q19:(II)I" line:150 line:151

A location is `line:N` (a source line, mapped through the `lines` table of the
decompiled method) or `pc:N` (a zero-based index into the method's bytecode
list, the same PCs jpamb uses elsewhere). Reaching a location means entering
the instruction at that index; for a line, any instruction where the line table
starts that line. Giving the same location twice asks the single-location
question.

Output: the first line is the verdict.

    Yes      both locations run on one path; the next line is a witness input
    No       the search finished with no cut-off, and no path runs both
    Unknown  the search was cut off (depth or state bound, an opcode this
             analysis does not model, or a solver timeout) and found no witness

Modelled: int-like arguments and locals, push, load, store, incr, negate, dup,
cast, binary add/sub/mul/div/rem, if, ifz, goto, return. Division by zero ends
the path. Anything else (arrays, objects, calls, throw, ...) makes the answer
Unknown unless a witness was found before it mattered.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field, replace
from typing import Iterable, Optional

import z3

import jvm

NAME = "symbolic"
VERSION = "1.0"
GROUP = "Group 15"
TAGS = ["symbolic", "python"]

BITS = 32
INT_LIKE = (jvm.Int, jvm.Boolean, jvm.Byte, jvm.Short, jvm.Char)


class Unsupported(Exception):
    """A path hit something this analysis does not model."""


@dataclass
class Result:
    verdict: str  # "Yes", "No" or "Unknown"
    witness: Optional[list] = None  # one value per argument, when verdict is Yes
    notes: list[str] = field(default_factory=list)  # why the search is incomplete


@dataclass(frozen=True)
class State:
    pc: int
    stack: tuple
    locals: tuple  # sorted ((index, value), ...) so states stay hashable-ish
    path: tuple  # z3 constraints accumulated along this path
    hit_a: bool = False
    hit_b: bool = False
    depth: int = 0

    def loc(self) -> dict:
        return dict(self.locals)


def bv(value: int):
    return z3.BitVecVal(value, BITS)


def _int_like(t) -> bool:
    return isinstance(t, INT_LIKE)


def _want_bv(value):
    if not z3.is_bv(value):
        raise Unsupported(f"expected an int value but found {value!r}")
    return value


COMPARE = {
    jvm.CmpOpr.Eq: lambda a, b: a == b,
    jvm.CmpOpr.Ne: lambda a, b: a != b,
    # z3 BitVec comparison operators are signed, as in Java.
    jvm.CmpOpr.Lt: lambda a, b: a < b,
    jvm.CmpOpr.Le: lambda a, b: a <= b,
    jvm.CmpOpr.Gt: lambda a, b: a > b,
    jvm.CmpOpr.Ge: lambda a, b: a >= b,
}


class Analysis:
    def __init__(
        self,
        opcodes: list,
        params: Iterable,
        locs_a: Iterable[int],
        locs_b: Iterable[int],
        max_depth: int = 500,
        max_states: int = 100_000,
        timeout_ms: int = 5_000,
    ):
        self.ops = list(opcodes)
        self.params = list(params)
        self.a, self.b = set(locs_a), set(locs_b)
        self.max_depth = max_depth
        self.max_states = max_states
        self.timeout_ms = timeout_ms
        self.notes: set[str] = set()

    # ------------------------------------------------------------------ z3

    def model(self, constraints) -> Optional[z3.ModelRef]:
        s = z3.Solver()
        s.set("timeout", self.timeout_ms)
        s.add(*constraints)
        r = s.check()
        if r == z3.sat:
            return s.model()
        if r == z3.unknown:
            self.notes.add("z3 returned unknown or timed out")
        return None

    def fork(self, st: State, cond, taken_pc: int, fall_pc: int, stack, loc):
        """Both sides of a branch on `cond`, keeping the satisfiable ones."""
        out = []
        for c, pc in ((cond, taken_pc), (z3.Not(cond), fall_pc)):
            c = z3.simplify(c)
            if z3.is_false(c):
                continue
            path = st.path
            if not z3.is_true(c):
                path = path + (c,)
                if self.model(path) is None:
                    continue
            out.append(self._next(st, pc, stack, loc, path))
        return out

    @staticmethod
    def _next(st: State, pc, stack, loc: dict, path) -> State:
        return replace(
            st,
            pc=pc,
            stack=tuple(stack),
            locals=tuple(sorted(loc.items())),
            path=path,
            depth=st.depth + 1,
        )

    # ---------------------------------------------------------------- step

    def step(self, st: State) -> list[State]:
        op = self.ops[st.pc]
        stack, loc = list(st.stack), st.loc()
        nxt = st.pc + 1

        def go(pc=nxt, path=None):
            return [self._next(st, pc, stack, loc, st.path if path is None else path)]

        match op:
            case jvm.Push(type=t, value=v):
                if not _int_like(t) or not isinstance(v, int):
                    raise Unsupported(f"push of {op}")
                stack.append(bv(int(v)))
                return go()

            case jvm.Load(type=t, index=i):
                if not _int_like(t):
                    raise Unsupported(f"load of {t}")
                if i not in loc:
                    raise Unsupported(f"read of unset local {i}")
                stack.append(loc[i])
                return go()

            case jvm.Store(type=t, index=i):
                if not _int_like(t):
                    raise Unsupported(f"store of {t}")
                loc[i] = _want_bv(stack.pop())
                return go()

            case jvm.Incr(index=i, amount=n):
                loc[i] = z3.simplify(_want_bv(loc[i]) + bv(n))
                return go()

            case jvm.Negate(type=t):
                if not _int_like(t):
                    raise Unsupported(f"negate of {t}")
                stack.append(z3.simplify(-_want_bv(stack.pop())))
                return go()

            case jvm.Dup(words=1):
                stack.append(stack[-1])
                return go()

            case jvm.Cast(from_=jvm.Int(), to_=to):
                v = _want_bv(stack.pop())
                if isinstance(to, jvm.Short):
                    v = z3.SignExt(16, z3.Extract(15, 0, v))
                elif isinstance(to, jvm.Char):
                    v = z3.ZeroExt(16, z3.Extract(15, 0, v))
                elif isinstance(to, jvm.Byte):
                    v = z3.SignExt(24, z3.Extract(7, 0, v))
                elif not isinstance(to, jvm.Int):
                    raise Unsupported(f"cast to {to}")
                stack.append(z3.simplify(v))
                return go()

            case jvm.Binary(type=t, operant=opr):
                if not isinstance(t, jvm.Int):
                    raise Unsupported(f"binary on {t}")
                b, a = _want_bv(stack.pop()), _want_bv(stack.pop())
                path = st.path
                if opr in (jvm.BinaryOpr.Div, jvm.BinaryOpr.Rem):
                    # Dividing by zero raises, which ends this path.
                    nonzero = z3.simplify(b != 0)
                    if z3.is_false(nonzero):
                        return []
                    if not z3.is_true(nonzero):
                        path = path + (nonzero,)
                        if self.model(path) is None:
                            return []
                    # On z3 bit-vectors, "/" is signed division and SRem takes the
                    # sign of the dividend, both as in Java.
                    res = a / b if opr == jvm.BinaryOpr.Div else z3.SRem(a, b)
                elif opr == jvm.BinaryOpr.Add:
                    res = a + b
                elif opr == jvm.BinaryOpr.Sub:
                    res = a - b
                elif opr == jvm.BinaryOpr.Mul:
                    res = a * b
                else:
                    raise Unsupported(f"binary operation {opr}")
                stack.append(z3.simplify(res))
                return go(path=path)

            case jvm.Goto(target=target):
                return go(pc=target)

            case jvm.If(condition=c, target=target):
                b, a = _want_bv(stack.pop()), _want_bv(stack.pop())
                return self.fork(st, COMPARE[c](a, b), target, nxt, stack, loc)

            case jvm.Ifz(condition=c, target=target):
                a = _want_bv(stack.pop())
                return self.fork(st, COMPARE[c](a, bv(0)), target, nxt, stack, loc)

            case jvm.Return():
                return []

            case _:
                raise Unsupported(f"opcode {op}")

    # -------------------------------------------------------------- search

    def initial(self):
        args, path = [], []
        for i, t in enumerate(self.params):
            a = z3.BitVec(f"arg{i}", BITS)
            if isinstance(t, jvm.Boolean):
                path.append(z3.Or(a == 0, a == 1))
            elif isinstance(t, jvm.Byte):
                path += [a >= -128, a <= 127]
            elif isinstance(t, jvm.Short):
                path += [a >= -32768, a <= 32767]
            elif isinstance(t, jvm.Char):
                path += [a >= 0, a <= 65535]
            elif not isinstance(t, jvm.Int):
                raise Unsupported(f"argument of type {t}")
            args.append(a)
        locals_ = tuple(enumerate(args))
        return args, State(0, (), locals_, tuple(path))

    def run(self) -> Result:
        try:
            args, start = self.initial()
        except Unsupported as e:
            return Result("Unknown", None, [f"unsupported: {e}"])

        todo, seen = [start], 0
        while todo:
            st = todo.pop()
            seen += 1
            if seen > self.max_states:
                self.notes.add(f"state limit {self.max_states} reached")
                break
            st = replace(
                st,
                hit_a=st.hit_a or st.pc in self.a,
                hit_b=st.hit_b or st.pc in self.b,
            )
            if st.hit_a and st.hit_b:
                m = self.model(st.path)
                if m is not None:
                    return Result("Yes", self._witness(m, args), sorted(self.notes))
                continue
            if st.depth >= self.max_depth:
                self.notes.add(f"depth bound {self.max_depth} reached")
                continue
            try:
                succ = self.step(st)
            except Unsupported as e:
                self.notes.add(f"unsupported: {e}")
                continue
            except IndexError:
                self.notes.add("stack underflow (unexpected bytecode shape)")
                continue
            todo.extend(reversed(succ))

        verdict = "Unknown" if self.notes else "No"
        return Result(verdict, None, sorted(self.notes))

    def _witness(self, model, args) -> list:
        out = []
        for a, t in zip(args, self.params):
            v = model.eval(a, model_completion=True).as_signed_long()
            out.append(bool(v) if isinstance(t, jvm.Boolean) else v)
        return out


def reach_together(opcodes, params, locs_a, locs_b, **limits) -> Result:
    """Can one run execute a location in `locs_a` and one in `locs_b`?"""
    return Analysis(opcodes, params, locs_a, locs_b, **limits).run()


# ---------------------------------------------------------------------- CLI


def resolve_location(text: str, n_opcodes: int, lines: list[dict]) -> set[int]:
    kind, _, value = text.partition(":")
    if not value:
        kind, value = "pc", text
    try:
        n = int(value)
    except ValueError:
        raise SystemExit(f"bad location {text!r}: use line:N or pc:N")
    if kind == "pc":
        if not 0 <= n < n_opcodes:
            raise SystemExit(f"pc {n} is outside the method (0..{n_opcodes - 1})")
        return {n}
    if kind == "line":
        pcs = {e["offset"] for e in lines if e["line"] == n}
        if not pcs:
            raise SystemExit(f"line {n} has no entry in the method's line table")
        return pcs
    raise SystemExit(f"bad location kind {kind!r}: use line:N or pc:N")


def main(argv: Optional[list[str]] = None) -> int:
    import jpamb

    argv = sys.argv[1:] if argv is None else argv
    if argv == ["info"]:
        jpamb.printinfo(NAME, VERSION, GROUP, TAGS, for_science=False)
    if len(argv) != 3:
        print(
            "usage: symbolic-reach info\n"
            "       symbolic-reach <method-id> <loc> <loc>   (loc = line:N or pc:N)",
            file=sys.stderr,
        )
        return 2

    methodid = jpamb.parse_methodid(argv[0])
    suite, eff = jpamb.setup()
    bc = jpamb.Bytecode(suite, eff, {})
    method = bc.getmethod(methodid)
    lines = suite.findmethod(methodid, eff=eff)["code"].get("lines", [])

    a = resolve_location(argv[1], len(method.opcodes), lines)
    b = resolve_location(argv[2], len(method.opcodes), lines)
    res = reach_together(method.opcodes, methodid.extension.params, a, b)

    print(res.verdict)
    if res.witness is not None:
        vals = ", ".join(str(v).lower() if isinstance(v, bool) else str(v) for v in res.witness)
        print(f"witness: ({vals})")
    for note in res.notes:
        print(f"note: {note}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
