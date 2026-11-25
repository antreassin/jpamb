package group15;

/**
 * Categorised two-line reachability benchmarks: 7 categories x 20 tests = 140 tests.
 *
 * Question for every test: can the two assignments marked "// Target 1" and "// Target 2"
 * both execute in the SAME run? Every entry method returns a + b (or an equivalent sum of
 * the two flags), so a run that reaches both targets returns 2. Where both targets execute,
 * Target 1 executes first. In every test each target is reachable on its own; only the pair
 * is in question.
 *
 * Every category has exactly 10 REACHABLE and 10 UNREACHABLE tests. The tests of a category
 * are independent programs: no reachable test is the twin of an unreachable one.
 * The label above each test (// name: REACHABLE pair / UNREACHABLE pair) gives the verdict;
 * the comment lines below it name the test type and explain the tricky part.
 *
 * Categories (test-name prefix):
 *   branch_   1  Branching and control flow: loop-free, call-free code. Predicate combinations,
 *                derived values, structural exclusion, compound conditions, switch, exceptions.
 *   arith_    2  Ideal arithmetic: linear relations, division and modulo, bounded products,
 *                congruences, bitwise operations. No wraparound or rounding decides a verdict.
 *   loops_    3  Loops: counting, accumulation, early exit, loop entry, nested loops, invariants.
 *   methods_  4  Methods and recursion: helper summaries, call chains, targets in different
 *                methods (only here), direct, mutual and target-carrying recursion.
 *   arrstr_   5  Arrays and strings: fixed arrays and bounds, scans, writes, string inspection
 *                and string construction.
 *   objs_     6  Objects and types: field mutation, constructors, null and type checks, dynamic
 *                dispatch, aliasing, static state.
 *   edge_     7  Java edge cases: the verdict only comes out right if a Java rule is modelled
 *                (overflow, conversions, floating point, operators, identity, library rules).
 *
 * Categories 1-6 keep the same verdict if Java int were a mathematical integer and no
 * floating point were involved (bounds or invariants keep arithmetic from wrapping).
 * Category 7 is where that stops being true.
 */
public final class LineReachabilityCategories {

    private LineReachabilityCategories() {}

    // =====================================================================================
    // Support code (contains no targets)
    // =====================================================================================

    static int sign(int v) {
        return v < 0 ? -1 : (v > 0 ? 1 : 0);
    }

    static int clampTo(int v, int lo, int hi) {
        return v < lo ? lo : (v > hi ? hi : v);
    }

    static boolean isEven(int v) {
        return v % 2 == 0;
    }

    static int twice(int v) {
        return 2 * v;
    }

    static int inc(int v) {
        return v + 1;
    }

    static int add(int p, int q) {
        return p + q;
    }

    static int sub(int p, int q) {
        return p - q;
    }

    static int classify(int v) {
        if (v < 0) {
            return 0;
        }
        if (v < 10) {
            return 1;
        }
        return 2;
    }

    static int sumTo(int n) {
        return n <= 0 ? 0 : n + sumTo(n - 1);
    }

    static int gcd(int p, int q) {
        return q == 0 ? p : gcd(q, p % q);
    }

    static int pow2(int n) {
        return n <= 0 ? 1 : 2 * pow2(n - 1);
    }

    static boolean evenRec(int n) {
        return n == 0 || oddRec(n - 1);
    }

    static boolean oddRec(int n) {
        return n != 0 && evenRec(n - 1);
    }

    static int ping(int n) {
        return n <= 0 ? 0 : 1 + pong(n - 1);
    }

    static int pong(int n) {
        return n <= 0 ? 0 : 2 + ping(n - 1);
    }

    static final class Counter {
        int v;

        void inc() {
            v++;
        }

        void add(int d) {
            v += d;
        }
    }

    static final class Account {
        int balance;

        Account(int balance) {
            this.balance = balance;
        }

        void withdraw(int amount) {
            if (amount > 0 && amount <= balance) {
                balance -= amount;
            }
        }
    }

    static final class Pair {
        int first;
        int second;

        Pair(int first, int second) {
            this.first = first;
            this.second = second;
        }

        void swap() {
            int t = first;
            first = second;
            second = t;
        }
    }

    static final class Rect {
        final int w;
        final int h;

        Rect(int w, int h) {
            this.w = w;
            this.h = h;
        }

        int area() {
            return w * h;
        }
    }

    static final class Temp {
        final int value;

        Temp(int v) {
            value = v < 0 ? 0 : (v > 100 ? 100 : v);
        }
    }

    static final class Item {
        int qty;
        int tax = 5;

        Item(int qty) {
            this.qty = qty;
        }
    }

    interface Animal {
        int sound();
    }

    static final class Dog implements Animal {
        public int sound() {
            return 1;
        }
    }

    static final class Cat implements Animal {
        public int sound() {
            return 2;
        }
    }

    interface Shape {
        int sides();
    }

    static final class Square implements Shape {
        public int sides() {
            return 4;
        }
    }

    static final class Triangle implements Shape {
        public int sides() {
            return 3;
        }
    }

    static final class Box {
        int v;

        Box(int v) {
            this.v = v;
        }
    }

    static int shared;

    static void bump(int d) {
        if (d > 0) {
            shared += d;
        }
    }

    static void tick() {
        shared = shared * 2 + 1;
    }

    // =====================================================================================
    // Category 1: Branching and control flow (branch_01 .. branch_20)
    // =====================================================================================

    // branch_01: UNREACHABLE pair
    // Type: predicate combination. Target 1's open interval (10, 12) contains exactly one
    // integer, 11, and Target 2 excludes it; over the reals the pair would be reachable.
    public static int branch_01(int x) {
        int a = 0, b = 0;
        if (x > 10 && x < 12) {
            a = 1; // Target 1
        }
        if (x > 9 && x != 11) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // branch_02: UNREACHABLE pair
    // Type: predicate combination over three variables. x < y < z forces z >= x + 2 on integers,
    // which contradicts z <= x + 1. Needs relational reasoning, not per-variable ranges.
    public static int branch_02(int x, int y, int z) {
        int a = 0, b = 0;
        if (x < y && y < z) {
            a = 1; // Target 1
        }
        if (z <= x + 1) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // branch_03: REACHABLE pair
    // Type: predicate combination. On integers only y == x + 1 satisfies both conditions;
    // a solver that treats the variables as reals would find many more witnesses.
    // Example: x = -1, y = 0 reaches both targets (returns 2).
    public static int branch_03(int x, int y) {
        int a = 0, b = 0;
        if (x < y) {
            a = 1; // Target 1
        }
        if (y < x + 2) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // branch_04: REACHABLE pair
    // Type: predicate combination with a large exact constant. Only x = y = 100003 reaches both;
    // the second condition's extra clause (y != 5) is satisfied by that witness.
    // Example: x = 100003, y = 100003 reaches both targets (returns 2).
    public static int branch_04(int x, int y) {
        int a = 0, b = 0;
        if (x == y) {
            a = 1; // Target 1
        }
        if (x == 100003 && y != 5) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // branch_05: UNREACHABLE pair
    // Type: derived value. score == 5 can only come from 2 + 3, i.e. x > 5 and y > 5, which
    // contradicts x < 6. The condition on score hides a condition on x.
    public static int branch_05(int x, int y) {
        int a = 0, b = 0;
        int score = 0;
        if (x > 5) {
            score += 2;
        }
        if (y > 5) {
            score += 3;
        }
        if (score == 5) {
            a = 1; // Target 1
        }
        if (x < 6) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // branch_06: REACHABLE pair
    // Type: derived value through boolean flags. inRange means 0 < x < 10 and tooBig is its
    // negation of "small"; the second guard keeps x in 5..9.
    // Example: x = 5 reaches both targets (returns 2).
    public static int branch_06(int x) {
        int a = 0, b = 0;
        boolean positive = x > 0;
        boolean small = x < 10;
        boolean inRange = positive && small;
        boolean tooBig = !small;
        if (inRange) {
            a = 1; // Target 1
        }
        if (!tooBig && x > 4) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // branch_07: UNREACHABLE pair
    // Type: derived value after a clamp. t == 10 holds exactly when x >= 10 (the assignment
    // t = 10 merges two cases), which contradicts x < 10.
    public static int branch_07(int x) {
        int a = 0, b = 0;
        int t = x;
        if (t > 10) {
            t = 10;
        }
        if (t == 10) {
            a = 1; // Target 1
        }
        if (x < 10) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // branch_08: REACHABLE pair
    // Type: structural exclusion with nested else-if. Target 1 runs for every positive x, and
    // Target 2 only in the middle arm (50 < x <= 100).
    // Example: x = 51 reaches both targets (returns 2).
    public static int branch_08(int x) {
        int a = 0, b = 0;
        if (x > 0) {
            a = 1; // Target 1
            if (x > 100) {
                return a + b;
            } else if (x > 50) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // branch_09: UNREACHABLE pair
    // Type: structural exclusion through a state variable. The flag done is set exactly when
    // Target 1 runs, and Target 2 is guarded by !done, so the two never meet.
    public static int branch_09(int x) {
        int a = 0, b = 0;
        boolean done = false;
        if (x > 5) {
            a = 1; // Target 1
            done = true;
        }
        if (!done && x > 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // branch_10: REACHABLE pair
    // Type: structural exclusion by early return. Negative x and x == 7 return before Target 2,
    // but any other non-negative x passes both targets.
    // Example: x = 0 reaches both targets (returns 2).
    public static int branch_10(int x) {
        int a = 0, b = 0;
        if (x < 0) {
            return a + b;
        }
        a = 1; // Target 1
        if (x == 7) {
            return a + b;
        }
        b = 1; // Target 2
        return a + b;
    }

    // branch_11: UNREACHABLE pair
    // Type: compound condition. By De Morgan, !(x > 0 || y > 0) means both are non-positive,
    // which contradicts x > 0 in Target 2's guard.
    public static int branch_11(int x, int y) {
        int a = 0, b = 0;
        if (!(x > 0 || y > 0)) {
            a = 1; // Target 1
        }
        if (x > 0 && y == 5) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // branch_12: REACHABLE pair
    // Type: compound condition with a ternary maximum. m == 10 needs max(x, y) == 10 and
    // x < y then forces y == 10.
    // Example: x = 0, y = 10 reaches both targets (returns 2).
    public static int branch_12(int x, int y) {
        int a = 0, b = 0;
        int m = x > y ? x : y;
        if (m == 10) {
            a = 1; // Target 1
        }
        if (x < y) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // branch_13: UNREACHABLE pair
    // Type: compound condition with a ternary minimum. min(x, y) > 5 means both exceed 5, so
    // neither can be below 3.
    public static int branch_13(int x, int y) {
        int a = 0, b = 0;
        int m = x < y ? x : y;
        if (m > 5) {
            a = 1; // Target 1
        }
        if (x < 3 || y < 3) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // branch_14: UNREACHABLE pair
    // Type: switch. Stacked case labels 1 and 2 share Target 1 and break, so Target 2's case 3
    // can never also run.
    public static int branch_14(int x) {
        int a = 0, b = 0;
        switch (x) {
            case 1:
            case 2:
                a = 1; // Target 1
                break;
            case 3:
                b = 1; // Target 2
                break;
            default:
                break;
        }
        return a + b;
    }

    // branch_15: REACHABLE pair
    // Type: switch with default placed first. Any x other than 5 and 6 jumps to default, which
    // falls through into case 5.
    // Example: x = 0 reaches both targets (returns 2).
    public static int branch_15(int x) {
        int a = 0, b = 0;
        switch (x) {
            default:
                a = 1; // Target 1
            case 5:
                b = 1; // Target 2
                break;
            case 6:
                break;
        }
        return a + b;
    }

    // branch_16: REACHABLE pair
    // Type: switch on a String with fallthrough. Case "ab" has no break and falls into "cd".
    // A null string throws before either target.
    // Example: s = "ab" reaches both targets (returns 2).
    public static int branch_16(String s) {
        int a = 0, b = 0;
        switch (s) {
            case "ab":
                a = 1; // Target 1
            case "cd":
                b = 1; // Target 2
                break;
            default:
                break;
        }
        return a + b;
    }

    // branch_17: REACHABLE pair
    // Type: exception with finally. The finally block runs on both the normal and the exceptional
    // path, so Target 2 runs whenever Target 1 does.
    // Example: x = 0 reaches both targets (returns 2).
    public static int branch_17(int x) {
        int a = 0, b = 0;
        try {
            if (x < 0) {
                throw new IllegalArgumentException("negative");
            }
            a = 1; // Target 1
        } catch (IllegalArgumentException e) {
            // handled, nothing to do
        } finally {
            b = 1; // Target 2
        }
        return a + b;
    }

    // branch_18: UNREACHABLE pair
    // Type: exception raised implicitly. The array store throws for any index outside 0..2, so
    // Target 1 (after the store) and Target 2 (the handler) exclude each other.
    public static int branch_18(int x) {
        int a = 0, b = 0;
        int[] arr = new int[3];
        try {
            arr[x] = 1;
            a = 1; // Target 1
        } catch (ArrayIndexOutOfBoundsException e) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // branch_19: REACHABLE pair
    // Type: exception swallowed, execution continues after the try. A throw skips Target 1
    // but not Target 2; with x = 0 nothing is thrown and both run.
    // Example: x = 0 reaches both targets (returns 2).
    public static int branch_19(int x) {
        int a = 0, b = 0;
        try {
            if (x > 5) {
                throw new IllegalStateException();
            }
            a = 1; // Target 1
        } catch (IllegalStateException e) {
            // swallowed
        }
        if (x > -100) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // branch_20: UNREACHABLE pair
    // Type: exception propagating through finally. The finally block runs during propagation,
    // but its guard (x > 0) is exactly the condition under which Target 1 is skipped.
    public static int branch_20(int x) {
        int a = 0, b = 0;
        try {
            try {
                if (x > 0) {
                    throw new RuntimeException();
                }
                a = 1; // Target 1
            } finally {
                if (x > 0) {
                    b = 1; // Target 2
                }
            }
        } catch (RuntimeException e) {
            // swallowed
        }
        return a + b;
    }

    // =====================================================================================
    // Category 2: Ideal arithmetic (arith_01 .. arith_20)
    // =====================================================================================

    // arith_01: REACHABLE pair
    // Type: linear relations. Two equations in two unknowns have a unique integer solution:
    // 2x + 3y = 12 and x - y = 1 give x = 3, y = 2. The bounds only keep the arithmetic from wrapping.
    // Example: x = 3, y = 2 reaches both targets (returns 2).
    public static int arith_01(int x, int y) {
        int a = 0, b = 0;
        if (x >= -1000 && x <= 1000 && y >= -1000 && y <= 1000) {
            if (2 * x + 3 * y == 12) {
                a = 1; // Target 1
            }
            if (x - y == 1) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // arith_02: UNREACHABLE pair
    // Type: linear relations. x + y = 10 and x - y = 5 give 2x = 15, so x would be 7.5.
    // Each equation alone has integer solutions; the system has none.
    public static int arith_02(int x, int y) {
        int a = 0, b = 0;
        if (x >= -1000 && x <= 1000 && y >= -1000 && y <= 1000) {
            if (x + y == 10) {
                a = 1; // Target 1
            }
            if (x - y == 5) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // arith_03: UNREACHABLE pair
    // Type: linear relations. 3x + 3y == 33 is x + y == 11 in disguise, which contradicts
    // x + y == 10. The analysis has to normalise the scaled equation.
    public static int arith_03(int x, int y) {
        int a = 0, b = 0;
        if (x >= -1000 && x <= 1000 && y >= -1000 && y <= 1000) {
            if (x + y == 10) {
                a = 1; // Target 1
            }
            if (3 * x + 3 * y == 33) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // arith_04: REACHABLE pair
    // Type: linear relations over three variables. x + y + z = 6 and x - z = 4 with y = 0 give
    // x = 5, z = 1.
    // Example: x = 5, y = 0, z = 1 reaches both targets (returns 2).
    public static int arith_04(int x, int y, int z) {
        int a = 0, b = 0;
        if (x >= -1000 && x <= 1000 && y >= -1000 && y <= 1000 && z >= -1000 && z <= 1000) {
            if (x + y + z == 6) {
                a = 1; // Target 1
            }
            if (x - z == 4 && y == 0) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // arith_05: UNREACHABLE pair
    // Type: division and modulo. x / 5 == 2 means x is in 10..14; x % 5 == 4 inside that range
    // gives only x = 14, which Target 2 then excludes with x > 14.
    public static int arith_05(int x) {
        int a = 0, b = 0;
        if (x / 5 == 2) {
            a = 1; // Target 1
        }
        if (x % 5 == 4 && x > 14) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arith_06: UNREACHABLE pair
    // Type: division and modulo (parity). An even x makes x + 1 odd. Adding 1 cannot wrap
    // for an even x, because Integer.MAX_VALUE is odd.
    public static int arith_06(int x) {
        int a = 0, b = 0;
        if (x % 2 == 0) {
            a = 1; // Target 1
        }
        if ((x + 1) % 2 == 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arith_07: REACHABLE pair
    // Type: division and modulo. x = 17 is the only value with quotient 2 and remainder 3
    // when divided by 7 (7 * 2 + 3).
    // Example: x = 17 reaches both targets (returns 2).
    public static int arith_07(int x) {
        int a = 0, b = 0;
        if (x % 7 == 3) {
            a = 1; // Target 1
        }
        if (x / 7 == 2) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arith_08: REACHABLE pair
    // Type: division and modulo tied to one variable. x / 3 == y and x % 3 == y give
    // x = 3y + y = 4y with y < 3.
    // Example: x = 0, y = 0 reaches both targets (returns 2).
    public static int arith_08(int x, int y) {
        int a = 0, b = 0;
        if (x / 3 == y) {
            a = 1; // Target 1
        }
        if (x % 3 == y) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arith_09: UNREACHABLE pair
    // Type: bounded product. The positive factor pairs of 30 have sums 31, 17, 13 and 11,
    // never 12. Needs a search over divisors, not just interval reasoning.
    public static int arith_09(int x, int y) {
        int a = 0, b = 0;
        if (x > 0 && y > 0 && x < 1000 && y < 1000) {
            if (x * y == 30) {
                a = 1; // Target 1
            }
            if (x + y == 12) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // arith_10: REACHABLE pair
    // Type: bounded product. Among the factor pairs of 30 only 6 and 5 differ by exactly 1.
    // Example: x = 6, y = 5 reaches both targets (returns 2).
    public static int arith_10(int x, int y) {
        int a = 0, b = 0;
        if (x > 0 && y > 0 && x < 1000 && y < 1000) {
            if (x * y == 30) {
                a = 1; // Target 1
            }
            if (x - y == 1) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // arith_11: REACHABLE pair
    // Type: bounded product with an inequality. x * y > 100 and x + y < 22 need factors close
    // together: 10 * 11 = 110 and 10 + 11 = 21.
    // Example: x = 8, y = 13 reaches both targets (returns 2).
    public static int arith_11(int x, int y) {
        int a = 0, b = 0;
        if (x > 0 && y > 0 && x < 1000 && y < 1000) {
            if (x * y > 100) {
                a = 1; // Target 1
            }
            if (x + y < 22) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // arith_12: UNREACHABLE pair
    // Type: bounded product (perfect square). x * x == y needs y to be a square, and 50 lies
    // between 49 and 64.
    public static int arith_12(int x, int y) {
        int a = 0, b = 0;
        if (x >= -1000 && x <= 1000) {
            if (x * x == y) {
                a = 1; // Target 1
            }
            if (y == 50) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // arith_13: REACHABLE pair
    // Type: congruence tied to a variable. x % 12 == y and y == 5 && x % 4 == 1 agree for x = 5
    // (5 % 12 == 5, 5 % 4 == 1).
    // Example: x = 5, y = 5 reaches both targets (returns 2).
    public static int arith_13(int x, int y) {
        int a = 0, b = 0;
        if (x % 12 == y) {
            a = 1; // Target 1
        }
        if (y == 5 && x % 4 == 1) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arith_14: UNREACHABLE pair
    // Type: congruence. x % 4 == 1 forces x to be odd, while x % 6 == 0 forces x to be even.
    // The moduli 4 and 6 are not coprime, so the contradiction is a parity clash, not a search.
    public static int arith_14(int x) {
        int a = 0, b = 0;
        if (x % 4 == 1) {
            a = 1; // Target 1
        }
        if (x % 6 == 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arith_15: UNREACHABLE pair
    // Type: congruence. x % 9 == 4 implies x % 3 == 1 (9 is a multiple of 3), contradicting x % 3 == 0.
    // The analysis must relate the two moduli; checking each remainder test alone finds witnesses.
    public static int arith_15(int x) {
        int a = 0, b = 0;
        if (x % 9 == 4) {
            a = 1; // Target 1
        }
        if (x % 3 == 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arith_16: REACHABLE pair
    // Type: congruence (Chinese remainder). x % 10 == 7 and x % 8 == 3 first meet at x = 27.
    // The moduli share the factor 2 but both residues are odd, so a common solution exists.
    // Example: x = 27 reaches both targets (returns 2).
    public static int arith_16(int x) {
        int a = 0, b = 0;
        if (x % 10 == 7) {
            a = 1; // Target 1
        }
        if (x % 8 == 3) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arith_17: REACHABLE pair
    // Type: bitwise operation. (x & 6) == 6 needs bits 1 and 2 set; combined with 5 < x < 8
    // this leaves x = 6 and x = 7.
    // Example: x = 6 reaches both targets (returns 2).
    public static int arith_17(int x) {
        int a = 0, b = 0;
        if ((x & 6) == 6) {
            a = 1; // Target 1
        }
        if (x < 8 && x > 5) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arith_18: REACHABLE pair
    // Type: bitwise operation (shift). x >> 2 == 3 means x is in 12..15; the low bit test then
    // keeps the odd ones.
    // Example: x = 13 reaches both targets (returns 2).
    public static int arith_18(int x) {
        int a = 0, b = 0;
        if ((x >> 2) == 3) {
            a = 1; // Target 1
        }
        if ((x & 1) == 1) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arith_19: UNREACHABLE pair
    // Type: bitwise operation. The low bit tells parity: (x & 1) == 1 means odd, which
    // contradicts x % 2 == 0. It holds for negative x as well.
    public static int arith_19(int x) {
        int a = 0, b = 0;
        if ((x & 1) == 1) {
            a = 1; // Target 1
        }
        if (x % 2 == 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arith_20: UNREACHABLE pair
    // Type: bitwise operation (power of two). A positive x with x & (x - 1) == 0 is a power of
    // two, and no power of two is divisible by 3.
    public static int arith_20(int x) {
        int a = 0, b = 0;
        if (x > 0 && (x & (x - 1)) == 0) {
            a = 1; // Target 1
        }
        if (x % 3 == 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // =====================================================================================
    // Category 3: Loops (loops_01 .. loops_20)
    // =====================================================================================

    // loops_01: REACHABLE pair
    // Type: counting loop. c ends as 3 * n, so c == 12 means n == 4, which is even.
    // Example: n = 4 reaches both targets (returns 2).
    public static int loops_01(int n) {
        int a = 0, b = 0;
        int c = 0;
        for (int k = 0; k < n; k++) {
            c += 3;
        }
        if (c == 12) {
            a = 1; // Target 1
        }
        if (n % 2 == 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // loops_02: UNREACHABLE pair
    // Type: counting loop that counts down. c = 21 - 3n reaches 0 only for n == 7, so n > 7
    // is impossible; for negative n the loop does not run and c stays 21.
    public static int loops_02(int n) {
        int a = 0, b = 0;
        int c = 21;
        for (int k = 0; k < n; k++) {
            c -= 3;
        }
        if (c == 0) {
            a = 1; // Target 1
        }
        if (n > 7) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // loops_03: UNREACHABLE pair
    // Type: counting loop with a doubling step. steps is floor(log2(n)) + 1, so steps == 4
    // means 8 <= n <= 15 and excludes n == 16. The guard keeps k from overflowing.
    public static int loops_03(int n) {
        int a = 0, b = 0;
        int steps = 0;
        if (n > 0 && n < 1000) {
            for (int k = 1; k <= n; k *= 2) {
                steps++;
            }
            if (steps == 4) {
                a = 1; // Target 1
            }
            if (n == 16) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // loops_04: REACHABLE pair
    // Type: accumulation. s is the sum of the even k below n; for n = 6 it is 0 + 2 + 4 = 6.
    // Several n give s == 6, and n == 6 is divisible by 3.
    // Example: n = 6 reaches both targets (returns 2).
    public static int loops_04(int n) {
        int a = 0, b = 0;
        int s = 0;
        for (int k = 0; k < n; k++) {
            if (k % 2 == 0) {
                s += k;
            }
        }
        if (s == 6) {
            a = 1; // Target 1
        }
        if (n % 3 == 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // loops_05: UNREACHABLE pair
    // Type: accumulation (iterative factorial). p == 120 holds only for n == 5, while Target 2
    // needs n == 4 (p == 24). The guard keeps the product from wrapping.
    public static int loops_05(int n) {
        int a = 0, b = 0;
        if (n >= 0 && n <= 10) {
            int p = 1;
            for (int k = 1; k <= n; k++) {
                p *= k;
            }
            if (p == 120) {
                a = 1; // Target 1
            }
            if (n == 4) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // loops_06: REACHABLE pair
    // Type: accumulation. The sum of the first n odd numbers is n * n, so s == 49 needs
    // n == 7, which is divisible by 7.
    // Example: n = 7 reaches both targets (returns 2).
    public static int loops_06(int n) {
        int a = 0, b = 0;
        int s = 0;
        for (int k = 0; k < n; k++) {
            s += 2 * k + 1;
        }
        if (s == 49) {
            a = 1; // Target 1
        }
        if (n % 7 == 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // loops_07: REACHABLE pair
    // Type: early-exit search loop. k is the first value with k * k >= n, so k == 5 means
    // 16 < n <= 25. n = 20 and n = 25 are multiples of 5. The guard keeps k * k from wrapping.
    // Example: n = 20 reaches both targets (returns 2).
    public static int loops_07(int n) {
        int a = 0, b = 0;
        if (n > 0 && n < 1000) {
            int k = 0;
            while (k * k < n) {
                k++;
            }
            if (k == 5) {
                a = 1; // Target 1
            }
            if (n % 5 == 0) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // loops_08: UNREACHABLE pair
    // Type: early-exit loop with break. The running sum first exceeds 10 at k == 5, so a break
    // always leaves k == 5. Target 2 needs k < 5, which only happens when no break occurred.
    public static int loops_08(int n) {
        int a = 0, b = 0;
        int s = 0, k = 0;
        while (k < n) {
            s += k;
            if (s > 10) {
                break;
            }
            k++;
        }
        if (s > 10) {
            a = 1; // Target 1
        }
        if (k < 5) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // loops_09: REACHABLE pair
    // Type: loop with continue. c counts the k below n that are not multiples of 3. For n = 6
    // these are 1, 2, 4, 5, so c == 4, and 6 is divisible by 6.
    // Example: n = 6 reaches both targets (returns 2).
    public static int loops_09(int n) {
        int a = 0, b = 0;
        int c = 0;
        for (int k = 0; k < n; k++) {
            if (k % 3 == 0) {
                continue;
            }
            c++;
        }
        if (c == 4) {
            a = 1; // Target 1
        }
        if (n % 6 == 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // loops_10: UNREACHABLE pair
    // Type: while(true) with break. The loop ends at the first k with 3k > n, so k == 4
    // pins n to 9..11. The only multiple of 3 there is 9, which Target 2 excludes with n > 11.
    public static int loops_10(int n) {
        int a = 0, b = 0;
        int k = 0;
        while (true) {
            if (k * 3 > n) {
                break;
            }
            k++;
        }
        if (k == 4) {
            a = 1; // Target 1
        }
        if (n % 3 == 0 && n > 11) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // loops_11: REACHABLE pair
    // Type: do-while. The body runs once even if the condition is false at the start, so
    // k == 5 holds for every n <= 5, including n == 0.
    // Example: n = 0 reaches both targets (returns 2).
    public static int loops_11(int n) {
        int a = 0, b = 0;
        int k = 0;
        do {
            k += 5;
        } while (k < n);
        if (k == 5) {
            a = 1; // Target 1
        }
        if (n < 1) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // loops_12: UNREACHABLE pair
    // Type: loop entry with a compound condition. i is n clamped to 0..3, so i == 3 needs
    // n >= 3, while Target 2 needs n < 3.
    public static int loops_12(int n) {
        int a = 0, b = 0;
        int i = 0;
        while (i < n && i < 3) {
            i++;
        }
        if (i == 3) {
            a = 1; // Target 1
        }
        if (n < 3) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // loops_13: UNREACHABLE pair
    // Type: loop with step 4. The iteration count is the ceiling of n / 4, so c == 3 means n is
    // in 9..12. Target 2 allows only n == 8 (c == 2) and n == 13 (c == 4).
    public static int loops_13(int n) {
        int a = 0, b = 0;
        int c = 0;
        for (int k = 0; k < n; k += 4) {
            c++;
        }
        if (c == 3) {
            a = 1; // Target 1
        }
        if (n == 8 || n == 13) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // loops_14: REACHABLE pair
    // Type: nested loops with a dependent bound. The inner loop runs i times, so c is
    // n * (n - 1) / 2; c == 10 gives n == 5.
    // Example: n = 5 reaches both targets (returns 2).
    public static int loops_14(int n) {
        int a = 0, b = 0;
        int c = 0;
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < i; j++) {
                c++;
            }
        }
        if (c == 10) {
            a = 1; // Target 1
        }
        if (n > 4) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // loops_15: UNREACHABLE pair
    // Type: nested loops with an inner break. The break leaves only the inner loop, so every
    // outer pass adds min(n, 2). c == 12 therefore means n == 6, not 5.
    public static int loops_15(int n) {
        int a = 0, b = 0;
        int c = 0;
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                if (j == 2) {
                    break;
                }
                c++;
            }
        }
        if (c == 12) {
            a = 1; // Target 1
        }
        if (n == 5) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // loops_16: REACHABLE pair
    // Type: nested loops with a labeled continue. Pass i adds i + 1 to c before the continue
    // restarts the outer loop, so c is n * (n + 1) / 2 and n = 3 gives 6.
    // Example: n = 3 reaches both targets (returns 2).
    public static int loops_16(int n) {
        int a = 0, b = 0;
        int c = 0;
        outer:
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                if (j > i) {
                    continue outer;
                }
                c++;
            }
        }
        if (c == 6) {
            a = 1; // Target 1
        }
        if (n % 3 == 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // loops_17: UNREACHABLE pair
    // Type: loop invariant. Both variables change in lockstep: i = 2n and j = 100 - 5n.
    // i == 10 gives n == 5, while j == 80 gives n == 4.
    public static int loops_17(int n) {
        int a = 0, b = 0;
        int i = 0, j = 100;
        for (int k = 0; k < n; k++) {
            i += 2;
            j -= 5;
        }
        if (i == 10) {
            a = 1; // Target 1
        }
        if (j == 80) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // loops_18: REACHABLE pair
    // Type: loop invariant (congruence). k stays congruent to x modulo 7, and 50 % 7 == 1,
    // so the loop ends exactly at 50 for x = 22, 29, 36, ...
    // Example: x = 22 reaches both targets (returns 2).
    public static int loops_18(int x) {
        int a = 0, b = 0;
        int k = x;
        while (k < 50) {
            k += 7;
        }
        if (k == 50) {
            a = 1; // Target 1
        }
        if (x % 7 == 1 && x > 20) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // loops_19: UNREACHABLE pair
    // Type: loop invariant. p + q equals x + y after every iteration, because one variable
    // goes up and the other goes down. So p + q == 10 contradicts x + y == 12.
    public static int loops_19(int n, int x, int y) {
        int a = 0, b = 0;
        int p = x, q = y;
        for (int k = 0; k < n; k++) {
            p++;
            q--;
        }
        if (p + q == 10) {
            a = 1; // Target 1
        }
        if (x + y == 12 && n > 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // loops_20: REACHABLE pair
    // Type: loop invariant (two pointers meeting). lo and hi move toward each other, so for
    // even n they meet at n / 2. With n = 6 both are 3, which is above 2.
    // Example: n = 6 reaches both targets (returns 2).
    public static int loops_20(int n) {
        int a = 0, b = 0;
        int lo = 0, hi = n;
        while (lo < hi) {
            lo++;
            hi--;
        }
        if (lo == hi) {
            a = 1; // Target 1
        }
        if (hi > 2) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // =====================================================================================
    // Category 4: Methods and recursion (methods_01 .. methods_20)
    // This is the only category where a target may live in a helper method. Such helpers
    // are placed directly after the test that uses them and are marked as helpers.
    // =====================================================================================

    // methods_01: REACHABLE pair
    // Type: helper summary. clampTo(x, 0, 10) returns 10 for EVERY x >= 10, not just x == 10,
    // so the summary is a range, not a point.
    // Example: x = 11 reaches both targets (returns 2).
    public static int methods_01(int x) {
        int a = 0, b = 0;
        if (clampTo(x, 0, 10) == 10) {
            a = 1; // Target 1
        }
        if (x % 11 == 0 && x > 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // methods_02: UNREACHABLE pair
    // Type: helper summary. sign(x) == 1 exactly when x > 0, while Target 2 needs x <= 0.
    // The analysis must derive that fact from the body of sign.
    public static int methods_02(int x) {
        int a = 0, b = 0;
        if (sign(x) == 1) {
            a = 1; // Target 1
        }
        if (x % 5 == 0 && x <= 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // methods_03: UNREACHABLE pair
    // Type: helper summary with three return values. classify(x) == 1 means 0 <= x < 10, and the
    // only multiple of 10 in that range is 0, which Target 2 excludes with x > 0.
    public static int methods_03(int x) {
        int a = 0, b = 0;
        if (classify(x) == 1) {
            a = 1; // Target 1
        }
        if (x % 10 == 0 && x > 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // methods_04: REACHABLE pair
    // Type: helper summary. classify returns 0 for every negative input, and isEven works on
    // negative numbers too (-2 % 2 == 0).
    // Example: x = -1 reaches both targets (returns 2).
    public static int methods_04(int x) {
        int a = 0, b = 0;
        if (classify(x) == 0) {
            a = 1; // Target 1
        }
        if (isEven(x + 1) && x > -10) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // methods_05: UNREACHABLE pair
    // Type: call chain. twice(inc(x)) is 2x + 2, so the value 8 forces x == 3. The bounds keep
    // the doubling from wrapping.
    public static int methods_05(int x) {
        int a = 0, b = 0;
        if (x >= -1000 && x <= 1000) {
            if (twice(inc(x)) == 8) {
                a = 1; // Target 1
            }
            if (x == 4) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // methods_06: REACHABLE pair
    // Type: call chain with two arguments. add(twice(x), inc(y)) is 2x + y + 1, so with x == y
    // the value 10 forces x == y == 3.
    // Example: x = 3, y = 3 reaches both targets (returns 2).
    public static int methods_06(int x, int y) {
        int a = 0, b = 0;
        if (x >= -1000 && x <= 1000 && y >= -1000 && y <= 1000) {
            if (add(twice(x), inc(y)) == 10) {
                a = 1; // Target 1
            }
            if (x == y) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // methods_07: UNREACHABLE pair
    // Type: call chain with cancellation. sub(add(x, y), y) is just x, so Target 1 pins x to 7
    // whatever y is; Target 2 needs x < 7.
    public static int methods_07(int x, int y) {
        int a = 0, b = 0;
        if (x >= -1000 && x <= 1000 && y >= -1000 && y <= 1000) {
            if (sub(add(x, y), y) == 7) {
                a = 1; // Target 1
            }
            if (x < 7) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // methods_08: REACHABLE pair
    // Type: target in a callee. Target 1 is inside h08, Target 2 in the entry method. A run
    // reaches the callee's line when x > 5; Target 2 needs x < 10.
    // Example: x = 6 reaches both targets (returns 2).
    public static int methods_08(int x) {
        int a = h08(x);
        int b = 0;
        if (x < 10) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // Helper for methods_08 (contains Target 1).
    static int h08(int v) {
        int a = 0;
        if (v > 5) {
            a = 1; // Target 1
        }
        return a;
    }

    // methods_09: UNREACHABLE pair
    // Type: target in a callee, called with a transformed argument. h09 runs its target when its
    // argument is even; the entry passes x + 1, so that is when x is odd, while Target 2 needs x even.
    public static int methods_09(int x) {
        int a = h09(x + 1);
        int b = 0;
        if (x % 2 == 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // Helper for methods_09 (contains Target 1).
    static int h09(int v) {
        int a = 0;
        if (v % 2 == 0) {
            a = 1; // Target 1
        }
        return a;
    }

    // methods_10: REACHABLE pair
    // Type: targets in two different callees. Target 1 runs when x - 3 > 0 (x > 3), Target 2
    // when x + 3 is even (x odd).
    // Example: x = 5 reaches both targets (returns 2).
    public static int methods_10(int x) {
        int a = h10a(x - 3);
        int b = h10b(x + 3);
        return a + b;
    }

    // Helper for methods_10 (contains Target 1).
    static int h10a(int v) {
        int a = 0;
        if (v > 0) {
            a = 1; // Target 1
        }
        return a;
    }

    // Helper for methods_10 (contains Target 2).
    static int h10b(int v) {
        int b = 0;
        if (v % 2 == 0) {
            b = 1; // Target 2
        }
        return b;
    }

    // methods_11: UNREACHABLE pair
    // Type: targets in two callees fed through a helper. Both callees see the clamped value of
    // x in 0..20: Target 1 needs it above 10, Target 2 below 5.
    public static int methods_11(int x) {
        int a = h11a(clampTo(x, 0, 20));
        int b = h11b(clampTo(x, 0, 20));
        return a + b;
    }

    // Helper for methods_11 (contains Target 1).
    static int h11a(int v) {
        int a = 0;
        if (v > 10) {
            a = 1; // Target 1
        }
        return a;
    }

    // Helper for methods_11 (contains Target 2).
    static int h11b(int v) {
        int b = 0;
        if (v < 5) {
            b = 1; // Target 2
        }
        return b;
    }

    // methods_12: UNREACHABLE pair
    // Type: callee with several return values. pick returns 2 only for x == 0, so Target 1 pins
    // x to 0, while Target 2 needs x < 0, where pick returns 1.
    public static int methods_12(int x) {
        int a = 0, b = 0;
        if (pick(x) == 2) {
            a = 1; // Target 1
        }
        if (x < 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    static int pick(int v) {
        if (v < 0) {
            return 1;
        }
        if (v == 0) {
            return 2;
        }
        return 3;
    }

    // methods_13: REACHABLE pair
    // Type: callee with several return values, called twice with related arguments. pick(x) == 3
    // needs x > 0 and pick(y) == 1 needs y < 0; x + y == 0 links them.
    // Example: x = 1, y = -1 reaches both targets (returns 2).
    public static int methods_13(int x, int y) {
        int a = 0, b = 0;
        if (pick(x) == 3) {
            a = 1; // Target 1
        }
        if (pick(y) == 1 && x + y == 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // methods_14: REACHABLE pair
    // Type: direct recursion with a base case that swallows negative input. sumTo(x) is 0 for every
    // x <= 0 (the recursion never starts), so x == 0 or x == -3 satisfies both.
    // Example: x = 0 reaches both targets (returns 2).
    public static int methods_14(int x) {
        int a = 0, b = 0;
        if (x >= -100 && x <= 100) {
            if (sumTo(x) == 0) {
                a = 1; // Target 1
            }
            if (x % 3 == 0) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // methods_15: REACHABLE pair
    // Type: direct recursion (Euclid). gcd(x, y) == 6 together with x + y == 30 is satisfied by
    // x = 12, y = 18. The analysis has to unroll or summarise the recursive remainder step.
    // Example: x = 6, y = 24 reaches both targets (returns 2).
    public static int methods_15(int x, int y) {
        int a = 0, b = 0;
        if (x >= 1 && x <= 1000 && y >= 1 && y <= 1000) {
            if (gcd(x, y) == 6) {
                a = 1; // Target 1
            }
            if (x + y == 30) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // methods_16: UNREACHABLE pair
    // Type: direct recursion (power of two). pow2(x) == 64 holds only for x == 6, and 6 is not a
    // multiple of 4. The guard keeps 2^x from wrapping.
    public static int methods_16(int x) {
        int a = 0, b = 0;
        if (x >= 0 && x <= 20) {
            if (pow2(x) == 64) {
                a = 1; // Target 1
            }
            if (x % 4 == 0 && x > 0) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // methods_17: UNREACHABLE pair
    // Type: targets inside a recursive method. walk17 counts down: the base case (n <= 0) holds
    // Target 1 and a multiple of 7 stops the recursion early at Target 2. A run takes exactly one of the
    // two exits, so only one target executes (the method returns 1 for either).
    public static int methods_17(int x) {
        return walk17(x);
    }

    // Helper for methods_17 (contains Target 1 and Target 2).
    static int walk17(int n) {
        if (n <= 0) {
            int a = 1; // Target 1
            return a;
        }
        if (n % 7 == 0) {
            int b = 1; // Target 2
            return b;
        }
        return walk17(n - 1);
    }

    // methods_18: REACHABLE pair
    // Type: targets inside a recursive method. Target 1 fires on the way down when the counter
    // passes 3, and Target 2 fires at the base case when y > 0. The entry
    // guard keeps the recursion depth bounded.
    // Example: x = 3, y = 1 reaches both targets (returns 2).
    public static int methods_18(int x, int y) {
        if (x < 0 || x > 500) {
            return 0;
        }
        return rec18(x, y);
    }

    // Helper for methods_18 (contains Target 1 and Target 2).
    static int rec18(int x, int y) {
        if (x <= 0) {
            int b = 0;
            if (y > 0) {
                b = 1; // Target 2
            }
            return b;
        }
        int a = 0;
        if (x == 3) {
            a = 1; // Target 1
        }
        return a + rec18(x - 1, y);
    }

    // methods_19: REACHABLE pair
    // Type: mutual recursion with accumulated values. ping and pong alternate adding 1 and 2, so
    // ping(4) = 1 + 2 + 1 + 2 = 6 and ping grows with n.
    // Example: x = 4 reaches both targets (returns 2).
    public static int methods_19(int x) {
        int a = 0, b = 0;
        if (x >= 0 && x <= 100) {
            if (ping(x) == 6) {
                a = 1; // Target 1
            }
            if (x > 2) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // methods_20: UNREACHABLE pair
    // Type: mutual recursion. evenRec(n) and oddRec(n) call each other and are complementary
    // for every n >= 0; the guard avoids non-terminating negative inputs.
    public static int methods_20(int x) {
        int a = 0, b = 0;
        if (x >= 0 && x <= 100) {
            if (evenRec(x)) {
                a = 1; // Target 1
            }
            if (oddRec(x)) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // =====================================================================================
    // Category 5: Arrays and strings (arrstr_01 .. arrstr_20)
    // A null array or string throws NullPointerException before any target, so null is never
    // part of a witness.
    // =====================================================================================

    // arrstr_01: REACHABLE pair
    // Type: fixed array and bounds. The array is a constant, so arr[x] == 15 means x == 2 (the
    // bounds check must come first).
    // Example: x = 2 reaches both targets (returns 2).
    public static int arrstr_01(int x) {
        int a = 0, b = 0;
        int[] arr = {4, 8, 15, 16, 23, 42};
        if (x >= 0 && x < arr.length && arr[x] == 15) {
            a = 1; // Target 1
        }
        if (x % 2 == 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arrstr_02: UNREACHABLE pair
    // Type: fixed array and bounds. arr[x] == 5 holds only at index 1, while Target 2 accepts only
    // the even valid indices 0 and 2. The index sets are disjoint.
    public static int arrstr_02(int x) {
        int a = 0, b = 0;
        int[] arr = {3, 5, 8};
        if (x >= 0 && x < arr.length && arr[x] == 5) {
            a = 1; // Target 1
        }
        if (x >= 0 && x < arr.length && x % 2 == 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arrstr_03: UNREACHABLE pair
    // Type: array length from an input. The array has n + 2 cells, so length 7 means n == 5, and
    // 5 is not a multiple of 4. The guard avoids NegativeArraySizeException.
    public static int arrstr_03(int n) {
        int a = 0, b = 0;
        if (n >= 0 && n <= 100) {
            int[] arr = new int[n + 2];
            if (arr.length == 7) {
                a = 1; // Target 1
            }
            if (n % 4 == 0 && n > 0) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // arrstr_04: REACHABLE pair
    // Type: array write then read. The write goes to index i, so arr[2] == 9 requires i == 2 and
    // v == 9; every other index leaves arr[2] at 0.
    // Example: i = 2, v = 9 reaches both targets (returns 2).
    public static int arrstr_04(int i, int v) {
        int a = 0, b = 0;
        if (i < 0 || i > 4) {
            return a + b;
        }
        int[] arr = new int[5];
        arr[i] = v;
        if (arr[2] == 9) {
            a = 1; // Target 1
        }
        if (v > 0 && i == 2) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arrstr_05: UNREACHABLE pair
    // Type: array write then dependent read. arr[1] is twice arr[0], so arr[1] == 14 forces x == 7,
    // which contradicts x == 6. The bounds keep the doubling from wrapping.
    public static int arrstr_05(int x) {
        int a = 0, b = 0;
        if (x >= -1000 && x <= 1000) {
            int[] arr = new int[2];
            arr[0] = x;
            arr[1] = arr[0] * 2;
            if (arr[1] == 14) {
                a = 1; // Target 1
            }
            if (x == 6) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // arrstr_06: REACHABLE pair
    // Type: array scan (maximum). The maximum starts at Integer.MIN_VALUE and is updated in the
    // loop. max == 5 together with length 3 is met by {1, 5, 2}.
    // Example: p = {0, 0, 5} reaches both targets (returns 2).
    public static int arrstr_06(int[] p) {
        int a = 0, b = 0;
        int max = Integer.MIN_VALUE;
        for (int k = 0; k < p.length; k++) {
            if (p[k] > max) {
                max = p[k];
            }
        }
        if (p.length > 0 && max == 5) {
            a = 1; // Target 1
        }
        if (p.length == 3) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arrstr_07: UNREACHABLE pair
    // Type: array scan (counting). Two negative elements need at least two elements, while
    // Target 2 needs fewer than two. The loop count is a function of the array length.
    public static int arrstr_07(int[] p) {
        int a = 0, b = 0;
        int negs = 0;
        for (int k = 0; k < p.length; k++) {
            if (p[k] < 0) {
                negs++;
            }
        }
        if (negs == 2) {
            a = 1; // Target 1
        }
        if (p.length < 2) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arrstr_08: UNREACHABLE pair
    // Type: array scan (relation between neighbours). If every adjacent pair is equal then, by
    // transitivity, the first and last elements are equal, contradicting Target 2.
    public static int arrstr_08(int[] p) {
        int a = 0, b = 0;
        int same = 0;
        for (int k = 0; k + 1 < p.length; k++) {
            if (p[k] == p[k + 1]) {
                same++;
            }
        }
        if (p.length >= 2 && same == p.length - 1) {
            a = 1; // Target 1
        }
        if (p.length >= 2 && p[0] != p[p.length - 1]) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arrstr_09: REACHABLE pair
    // Type: array copy into a second array in reverse order. If p[0] > p[last], the reversed copy r
    // satisfies r[0] < r[last].
    // Example: p = {0, -1} reaches both targets (returns 2).
    public static int arrstr_09(int[] p) {
        int a = 0, b = 0;
        int[] r = new int[p.length];
        for (int k = 0; k < p.length; k++) {
            r[p.length - 1 - k] = p[k];
        }
        if (p.length >= 2 && p[0] > p[p.length - 1]) {
            a = 1; // Target 1
        }
        if (r.length >= 2 && r[0] < r[r.length - 1]) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arrstr_10: UNREACHABLE pair
    // Type: array copy into a second array in reverse order. r[0] is p[last] and r[last] is p[0],
    // so r[0] > r[last] is the opposite of p[0] > p[last].
    public static int arrstr_10(int[] p) {
        int a = 0, b = 0;
        int[] r = new int[p.length];
        for (int k = 0; k < p.length; k++) {
            r[p.length - 1 - k] = p[k];
        }
        if (p.length >= 2 && p[0] > p[p.length - 1]) {
            a = 1; // Target 1
        }
        if (r.length >= 2 && r[0] > r[r.length - 1]) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arrstr_11: REACHABLE pair
    // Type: string inspection (length and charAt). Both conditions constrain individual characters
    // of the same string, here positions 1 and 0.
    // Example: s = "aba" reaches both targets (returns 2).
    public static int arrstr_11(String s) {
        int a = 0, b = 0;
        if (s.length() == 3 && s.charAt(1) == 'b') {
            a = 1; // Target 1
        }
        if (s.length() > 0 && s.charAt(0) == 'a') {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arrstr_12: UNREACHABLE pair
    // Type: string inspection (equals versus charAt). "hello" starts with a lower-case h, while
    // Target 2 needs an upper-case H as first character; chars are compared exactly.
    public static int arrstr_12(String s) {
        int a = 0, b = 0;
        if (s.equals("hello")) {
            a = 1; // Target 1
        }
        if (s.length() > 0 && s.charAt(0) == 'H') {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arrstr_13: REACHABLE pair
    // Type: string inspection (prefix and suffix that overlap). "ab" and "ba" share the middle
    // character when the string has length 3.
    // Example: s = "aba" reaches both targets (returns 2).
    public static int arrstr_13(String s) {
        int a = 0, b = 0;
        if (s.startsWith("ab")) {
            a = 1; // Target 1
        }
        if (s.endsWith("ba")) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arrstr_14: UNREACHABLE pair
    // Type: string inspection (prefix versus length). A string starting with "abc" has length at
    // least 3, so it cannot have length 2.
    public static int arrstr_14(String s) {
        int a = 0, b = 0;
        if (s.startsWith("abc")) {
            a = 1; // Target 1
        }
        if (s.length() == 2) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arrstr_15: UNREACHABLE pair
    // Type: string inspection (indexOf). indexOf('z') == 1 means the character at index 1 is 'z';
    // Target 2 requires that same character to differ from 'z'.
    public static int arrstr_15(String s) {
        int a = 0, b = 0;
        if (s.indexOf('z') == 1) {
            a = 1; // Target 1
        }
        if (s.length() > 1 && s.charAt(1) != 'z') {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arrstr_16: REACHABLE pair
    // Type: string inspection (substring). substring(1, 3) is the characters at positions 1 and 2,
    // so "bc" there says nothing about position 0.
    // Example: s = "abcd" reaches both targets (returns 2).
    public static int arrstr_16(String s) {
        int a = 0, b = 0;
        if (s.length() >= 4 && s.substring(1, 3).equals("bc")) {
            a = 1; // Target 1
        }
        if (s.length() > 0 && s.charAt(0) == 'a') {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arrstr_17: REACHABLE pair
    // Type: string construction in a loop. s becomes "ab" repeated n times, so length 6 means n == 3
    // and "ababab" is then a prefix of s. The guard keeps the loop small.
    // Example: n = 3 reaches both targets (returns 2).
    public static int arrstr_17(int n) {
        int a = 0, b = 0;
        if (n >= 0 && n <= 100) {
            String s = "";
            for (int k = 0; k < n; k++) {
                s = s + "ab";
            }
            if (s.length() == 6) {
                a = 1; // Target 1
            }
            if (s.startsWith("ababab")) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // arrstr_18: UNREACHABLE pair
    // Type: string construction in a loop. Length 6 means n == 3, but "abab" means n == 2.
    // The string and its length are two views of the same loop count.
    public static int arrstr_18(int n) {
        int a = 0, b = 0;
        if (n >= 0 && n <= 100) {
            String s = "";
            for (int k = 0; k < n; k++) {
                s = s + "ab";
            }
            if (s.length() == 6) {
                a = 1; // Target 1
            }
            if (s.equals("abab")) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // arrstr_19: REACHABLE pair
    // Type: string inspection (character relations). Target 1 needs two equal characters and
    // Target 2 fixes both to 'b'.
    // Example: s = "bb" reaches both targets (returns 2).
    public static int arrstr_19(String s) {
        int a = 0, b = 0;
        if (s.length() == 2 && s.charAt(0) == s.charAt(1)) {
            a = 1; // Target 1
        }
        if (s.equals("bb")) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // arrstr_20: REACHABLE pair
    // Type: string construction (concatenation with itself). (s + s).length() is twice s.length(),
    // so length 6 means s has length 3.
    // Example: s = "abc" reaches both targets (returns 2).
    public static int arrstr_20(String s) {
        int a = 0, b = 0;
        if ((s + s).length() == 6) {
            a = 1; // Target 1
        }
        if (s.equals("abc")) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // =====================================================================================
    // Category 6: Objects and types (objs_01 .. objs_20)
    // Ordinary object-oriented reasoning: fields, constructors, type checks, dispatch,
    // aliasing and static state. None of it depends on a Java quirk.
    // =====================================================================================

    // objs_01: REACHABLE pair
    // Type: field mutation. The counter reaches 2 only when both x and y are positive; the second
    // condition then asks for x > y.
    // Example: x = 2, y = 1 reaches both targets (returns 2).
    public static int objs_01(int x, int y) {
        int a = 0, b = 0;
        Counter c = new Counter();
        if (x > 0) {
            c.inc();
        }
        if (y > 0) {
            c.inc();
        }
        if (c.v == 2) {
            a = 1; // Target 1
        }
        if (x > y) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // objs_02: UNREACHABLE pair
    // Type: field mutation with different increments. 7 = 3 + 4 needs both increments to happen,
    // so x > 0 and y > 0, while Target 2 needs x <= 0. Either increment alone gives 3 or 4.
    public static int objs_02(int x, int y) {
        int a = 0, b = 0;
        Counter c = new Counter();
        if (x > 0) {
            c.add(3);
        }
        if (y > 0) {
            c.add(4);
        }
        if (c.v == 7) {
            a = 1; // Target 1
        }
        if (x <= 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // objs_03: REACHABLE pair
    // Type: field mutation through a guarded method. withdraw silently ignores bad amounts, so the
    // balance reaches 0 when the two valid withdrawals add up to 100.
    // Example: x = 50, y = 50 reaches both targets (returns 2).
    public static int objs_03(int x, int y) {
        int a = 0, b = 0;
        Account acc = new Account(100);
        acc.withdraw(x);
        acc.withdraw(y);
        if (acc.balance == 0) {
            a = 1; // Target 1
        }
        if (x == y) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // objs_04: UNREACHABLE pair
    // Type: field mutation that may be skipped. The balance stays 100 only if the withdrawal was
    // ignored (x <= 0 or x > 100); Target 2 needs 0 < x <= 100, where it is not ignored.
    public static int objs_04(int x) {
        int a = 0, b = 0;
        Account acc = new Account(100);
        acc.withdraw(x);
        if (acc.balance == 100) {
            a = 1; // Target 1
        }
        if (x > 0 && x <= 100) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // objs_05: REACHABLE pair
    // Type: field mutation by swapping. After swap() the first field holds the original second
    // value, so first == 5 means y == 5.
    // Example: x = 3, y = 5 reaches both targets (returns 2).
    public static int objs_05(int x, int y) {
        int a = 0, b = 0;
        Pair p = new Pair(x, y);
        p.swap();
        if (p.first == 5) {
            a = 1; // Target 1
        }
        if (x == 3) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // objs_06: UNREACHABLE pair
    // Type: field mutation by swapping. After the swap, first < second means y < x, the opposite
    // of Target 2's x < y.
    public static int objs_06(int x, int y) {
        int a = 0, b = 0;
        Pair p = new Pair(x, y);
        p.swap();
        if (p.first < p.second) {
            a = 1; // Target 1
        }
        if (x < y) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // objs_07: REACHABLE pair
    // Type: constructor that clamps. Temp stores values in 0..100, so any x above 100 gives
    // value 100.
    // Example: x = 121 reaches both targets (returns 2).
    public static int objs_07(int x) {
        int a = 0, b = 0;
        Temp t = new Temp(x);
        if (t.value == 100) {
            a = 1; // Target 1
        }
        if (x > 120) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // objs_08: UNREACHABLE pair
    // Type: constructor that clamps. A stored value of 100 needs x >= 100, so x < 50 is impossible.
    // The constructor hides the dependence of the field on the argument.
    public static int objs_08(int x) {
        int a = 0, b = 0;
        Temp t = new Temp(x);
        if (t.value == 100) {
            a = 1; // Target 1
        }
        if (x < 50) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // objs_09: REACHABLE pair
    // Type: constructor and derived method. area() is w * h, so area 24 with w + h == 10 is met by
    // 4 and 6. The bounds keep the product from wrapping.
    // Example: x = 4, y = 6 reaches both targets (returns 2).
    public static int objs_09(int x, int y) {
        int a = 0, b = 0;
        if (x >= 1 && x <= 1000 && y >= 1 && y <= 1000) {
            Rect r = new Rect(x, y);
            if (r.area() == 24) {
                a = 1; // Target 1
            }
            if (x + y == 10) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // objs_10: UNREACHABLE pair
    // Type: constructor and derived method. The positive factor pairs of 24 have sums 25, 14, 11
    // and 10, never 9.
    public static int objs_10(int x, int y) {
        int a = 0, b = 0;
        if (x >= 1 && x <= 1000 && y >= 1 && y <= 1000) {
            Rect r = new Rect(x, y);
            if (r.area() == 24) {
                a = 1; // Target 1
            }
            if (x + y == 9) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // objs_11: REACHABLE pair
    // Type: type check and cast. A String is also a CharSequence, and the cast is safe inside the
    // instanceof guard.
    // Example: o = "abc" reaches both targets (returns 2).
    public static int objs_11(Object o) {
        int a = 0, b = 0;
        if (o instanceof String && ((String) o).length() == 3) {
            a = 1; // Target 1
        }
        if (o instanceof CharSequence) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // objs_12: UNREACHABLE pair
    // Type: type check. No object is both an Integer and a String, since both classes are final
    // and unrelated.
    public static int objs_12(Object o) {
        int a = 0, b = 0;
        if (o instanceof Integer) {
            a = 1; // Target 1
        }
        if (o instanceof String) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // objs_13: UNREACHABLE pair
    // Type: null check. null is never an instance of anything, so o == null excludes
    // o instanceof Object even though every non-null object matches the second test.
    public static int objs_13(Object o) {
        int a = 0, b = 0;
        if (o == null) {
            a = 1; // Target 1
        }
        if (o instanceof Object) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // objs_14: REACHABLE pair
    // Type: type check with a cast and a comparison. An Integer above 5 is also a Number.
    // Example: o = Integer.valueOf(6) reaches both targets (returns 2).
    public static int objs_14(Object o) {
        int a = 0, b = 0;
        if (o instanceof Integer && ((Integer) o) > 5) {
            a = 1; // Target 1
        }
        if (o instanceof Number) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // objs_15: REACHABLE pair
    // Type: dynamic dispatch. The receiver is a Dog for x > 0, so sound() returns 1 there.
    // Example: x = 6 reaches both targets (returns 2).
    public static int objs_15(int x) {
        int a = 0, b = 0;
        Animal an = x > 0 ? new Dog() : new Cat();
        if (an.sound() == 1) {
            a = 1; // Target 1
        }
        if (x > 5) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // objs_16: UNREACHABLE pair
    // Type: dynamic dispatch with two receivers. The sides add up to 7 only for one square and one
    // triangle, i.e. exactly one of x, y positive; Target 2 needs both positive (8 sides).
    public static int objs_16(int x, int y) {
        int a = 0, b = 0;
        Shape s1 = x > 0 ? new Square() : new Triangle();
        Shape s2 = y > 0 ? new Square() : new Triangle();
        if (s1.sides() + s2.sides() == 7) {
            a = 1; // Target 1
        }
        if (x > 0 && y > 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // objs_17: REACHABLE pair
    // Type: aliasing. For x > 0 the variable q refers to the same Box as p, so writing p.v is seen
    // through q.v; otherwise q is a fresh Box.
    // Example: x = 1 reaches both targets (returns 2).
    public static int objs_17(int x) {
        int a = 0, b = 0;
        Box p = new Box(0);
        Box q = x > 0 ? p : new Box(0);
        p.v = 5;
        if (q.v == 5) {
            a = 1; // Target 1
        }
        if (x < 3) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // objs_18: UNREACHABLE pair
    // Type: aliasing. The write through q reaches p only when they are the same object (x > 0);
    // for x <= 0 q is a different Box, so p.v stays 1.
    public static int objs_18(int x) {
        int a = 0, b = 0;
        Box p = new Box(1);
        Box q = x > 0 ? p : new Box(1);
        q.v = 2;
        if (p.v == 2) {
            a = 1; // Target 1
        }
        if (x <= 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // objs_19: REACHABLE pair
    // Type: static state. The static field accumulates the positive arguments across both calls,
    // so 7 = 4 + 3 needs both calls to count.
    // Example: x = 4, y = 3 reaches both targets (returns 2).
    public static int objs_19(int x, int y) {
        int a = 0, b = 0;
        shared = 0;
        bump(x);
        bump(y);
        if (shared == 7) {
            a = 1; // Target 1
        }
        if (x > 3) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // objs_20: UNREACHABLE pair
    // Type: static state through repeated updates. tick() maps s to 2s + 1, so two ticks give 3 and
    // three ticks give 7; the third tick happens only for x > 0.
    public static int objs_20(int x) {
        int a = 0, b = 0;
        shared = 0;
        tick();
        tick();
        if (x > 0) {
            tick();
        }
        if (shared == 7) {
            a = 1; // Target 1
        }
        if (x < 1) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // =====================================================================================
    // Category 7: Java edge cases (edge_01 .. edge_20)
    // The verdict comes out right only if a Java rule is modelled. Replacing int by a
    // mathematical integer or double by a real number would flip the answer or make it
    // wrong. Sub-types: numeric representation (overflow, narrowing, float rounding, special
    // float values), operator semantics, reference identity, library rules.
    // Some tests are taken over from LineReachabilityHard under a new name.
    // =====================================================================================

    // edge_01: REACHABLE pair
    // Type: int overflow (from h15). x * x wraps around to a negative int for |x| >= 46341, so
    // Target 1 is reachable even though a square is never negative in real arithmetic.
    // Example: x = 46341 reaches both targets (returns 2).
    public static int edge_01(int x) {
        int a = 0, b = 0;
        if (x * x < 0) {
            a = 1; // Target 1
        }
        if (x > 46340) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // edge_02: REACHABLE pair
    // Type: int overflow in a library call (from h17). Math.abs(Integer.MIN_VALUE) is still
    // negative, because +2^31 does not fit in an int.
    // Example: x = Integer.MIN_VALUE reaches both targets (returns 2).
    public static int edge_02(int x) {
        int a = 0, b = 0;
        if (Math.abs(x) < 0) {
            a = 1; // Target 1
        }
        if (x < 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // edge_03: REACHABLE pair
    // Type: narrowing to byte (from h22). (byte) keeps the low 8 bits as a signed value, so
    // (byte) 200 is -56 although 200 itself is positive.
    // Example: x = 200 reaches both targets (returns 2).
    public static int edge_03(int x) {
        int a = 0, b = 0;
        if ((byte) x < 0) {
            a = 1; // Target 1
        }
        if (x >= 200) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // edge_04: REACHABLE pair
    // Type: narrowing to char (from h23). char is unsigned 16-bit, so a negative int is reduced
    // modulo 65536: (char) -65471 is 65, i.e. 'A'.
    // Example: x = -65471 reaches both targets (returns 2).
    public static int edge_04(int x) {
        int a = 0, b = 0;
        if ((char) x == 'A') {
            a = 1; // Target 1
        }
        if (x < 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // edge_05: REACHABLE pair
    // Type: double to int conversion (from h09). The cast truncates toward zero, so (int) -0.5
    // is 0, not -1.
    // Example: y = -0.5 reaches both targets (returns 2).
    public static int edge_05(double y) {
        int a = 0, b = 0;
        if ((int) y == 0) {
            a = 1; // Target 1
        }
        if (y < 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // edge_06: REACHABLE pair
    // Type: float rounding in a loop (from h02). 0.1f is not exactly representable, and in float
    // arithmetic ten additions give 1.0000001f, which is >= 1.0f.
    // Example: n = 10 reaches both targets (returns 2).
    public static int edge_06(int n) {
        int a = 0, b = 0;
        float y = 0.0f;
        for (int k = 0; k < n; k++) {
            y = y + 0.1f;
        }
        if (n == 10) {
            a = 1; // Target 1
        }
        if (y >= 1.0f) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // edge_07: REACHABLE pair
    // Type: NaN (from h05). x != x holds only for NaN, and NaN also fails both x < 0 and x >= 0,
    // so !(x < 0) && !(x >= 0) holds.
    // Example: x = Float.NaN reaches both targets (returns 2).
    public static int edge_07(float x) {
        int a = 0, b = 0;
        if (x != x) {
            a = 1; // Target 1
        }
        if (!(x < 0) && !(x >= 0)) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // edge_08: REACHABLE pair
    // Type: negative zero (from h07). -0.0f == 0.0f is true, yet 1 / -0.0f is -Infinity, which is
    // negative.
    // Example: x = -0.0f reaches both targets (returns 2).
    public static int edge_08(float x) {
        int a = 0, b = 0;
        if (x == 0.0f) {
            a = 1; // Target 1
        }
        if (1 / x < 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // edge_09: REACHABLE pair
    // Type: shift distance (from h27). The shift distance of an int shift is taken modulo 32, so
    // 1 << 33 equals 1 << 1 == 2.
    // Example: x = 33 reaches both targets (returns 2).
    public static int edge_09(int x) {
        int a = 0, b = 0;
        if ((1 << x) == 2) {
            a = 1; // Target 1
        }
        if (x > 1) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // edge_10: REACHABLE pair
    // Type: reference identity (from h48). Equal content does not imply the same object: with
    // s = "a" and t = new String("a") the equals test succeeds and the != test succeeds too.
    // Note that a null s throws NullPointerException at the first condition.
    // Example: s = "a", t = new String("a") reaches both targets (returns 2).
    public static int edge_10(String s, String t) {
        int a = 0, b = 0;
        if (s.equals(t)) {
            a = 1; // Target 1
        }
        if (s != t) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // edge_11: UNREACHABLE pair
    // Type: double rounding of literals (from h03). 0.1 + 0.2 is 0.30000000000000004 in double,
    // which is not the double nearest to 0.3, so no x equals both expressions.
    public static int edge_11(double x) {
        int a = 0, b = 0;
        if (x == 0.3) {
            a = 1; // Target 1
        }
        if (x == 0.1 + 0.2) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // edge_12: UNREACHABLE pair
    // Type: sign of the remainder. In Java x % 3 == -1 means x is congruent to 2 modulo 3 (for
    // example -1, -4), while Math.floorMod(x, 3) == 1 means x is congruent to 1.
    public static int edge_12(int x) {
        int a = 0, b = 0;
        if (x % 3 == -1) {
            a = 1; // Target 1
        }
        if (Math.floorMod(x, 3) == 1) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // edge_13: UNREACHABLE pair
    // Type: float absorption (from h12). x + 1f == x needs x >= 2^24 (or Infinity), where the
    // spacing of floats exceeds 1, and that excludes every x with 0 < x < 2^24.
    public static int edge_13(float x) {
        int a = 0, b = 0;
        if (x + 1f == x) {
            a = 1; // Target 1
        }
        if (x > 0 && x < 16777216f) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // edge_14: UNREACHABLE pair
    // Type: int to float conversion (from h14). Every int with |x| < 2^24 is exactly representable
    // as a float, and adjacent ints are then distinct floats. Collisions need |x| >= 2^24.
    public static int edge_14(int x) {
        int a = 0, b = 0;
        if ((float) x == (float) (x + 1)) {
            a = 1; // Target 1
        }
        if (x > -16777216 && x < 16777216) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // edge_15: UNREACHABLE pair
    // Type: String.hashCode (from h40). A 2-char string c0 c1 has hashCode 31 * c0 + c1. For
    // c0 >= 'E' (69) this is at least 2139, above the hashCode 2112 of "BB". Collisions such
    // as "Aa" / "BB" exist only for smaller first characters.
    public static int edge_15(String s) {
        int a = 0, b = 0;
        if (s.length() == 2 && s.charAt(0) >= 'E') {
            a = 1; // Target 1
        }
        if (s.hashCode() == "BB".hashCode()) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // edge_16: UNREACHABLE pair
    // Type: Integer cache (from h29). Boxed Integers are == only for equal values in -128..127,
    // where valueOf returns cached objects, so p == q rules out x == y > 127.
    public static int edge_16(int x, int y) {
        int a = 0, b = 0;
        Integer p = x;
        Integer q = y;
        if (p == q) {
            a = 1; // Target 1
        }
        if (x == y && x > 127) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // edge_17: UNREACHABLE pair
    // Type: compound assignment with implicit narrowing. s += 1 on a short wraps silently, so
    // s == Short.MIN_VALUE needs (short) x == 32767, which for ints in the open range of Target 2
    // never happens (32767 itself is excluded).
    public static int edge_17(int x) {
        int a = 0, b = 0;
        short s = (short) x;
        s += 1;
        if (s == Short.MIN_VALUE) {
            a = 1; // Target 1
        }
        if (x > -32768 && x < 32767) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // edge_18: UNREACHABLE pair
    // Type: unsigned shift. x >>> 28 is 15 exactly when the top four bits are 1111, which requires
    // the sign bit and hence x < 0; Target 2 needs x > 0.
    public static int edge_18(int x) {
        int a = 0, b = 0;
        if ((x >>> 28) == 15) {
            a = 1; // Target 1
        }
        if (x > 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // edge_19: UNREACHABLE pair
    // Type: Math.round. It rounds half up, so Math.round(y) == 3 means 2.5 <= y < 3.5, which
    // excludes Target 2's y < 2.5. A truncating cast would give a different range.
    public static int edge_19(double y) {
        int a = 0, b = 0;
        if (Math.round(y) == 3) {
            a = 1; // Target 1
        }
        if (y < 2.5) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // edge_20: UNREACHABLE pair
    // Type: evaluation order. In i = i++ the old value of i is stored back after the increment,
    // so i keeps the value x; i == 5 therefore means x == 5, not 4.
    public static int edge_20(int x) {
        int a = 0, b = 0;
        int i = x;
        i = i++;
        if (i == 5) {
            a = 1; // Target 1
        }
        if (x == 4) {
            b = 1; // Target 2
        }
        return a + b;
    }
}
