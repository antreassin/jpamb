package group15;

/**
 * Ordered two-line reachability benchmarks.
 *
 * Each method contains Target 1 and Target 2.
 * The question is whether both assignments can execute
 * in the same invocation, in that order.
 *
 * Each target sets one flag to 1:
 * return 0 = neither target executed
 * return 1 = exactly one target executed
 * return 2 = both targets executed
 *
 * The return value helps validate the benchmarks.
 * An analyser should still observe the marked lines.
 */
public final class PairReachability {

    private PairReachability() {}

    // P01: UNREACHABLE pair
    // Both targets individually reachable, but never together.
    public static int p01(int x) {
        int a = 0, b = 0;

        if (x < 0) {
            a = 1; // Target 1
        }
        if (x > 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // P02: REACHABLE pair
    // Witness: x = 6
    public static int p02(int x) {
        int a = 0, b = 0;

        if (x > 5) {
            a = 1; // Target 1
        }
        if (x < 10) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // P03: UNREACHABLE pair
    // Exact value versus its opposite condition.
    public static int p03(int x) {
        int a = 0, b = 0;

        if (x == 100003) {
            a = 1; // Target 1
        }
        if (x != 100003) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // P04: REACHABLE pair
    // Only x = 100003 reaches both.
    public static int p04(int x) {
        int a = 0, b = 0;

        if (x >= 100003) {
            a = 1; // Target 1
        }
        if (x <= 100003) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // P05: UNREACHABLE pair
    // An early return prevents the second target.
    public static int p05(int x) {
        int a = 0, b = 0;

        if (x < 0) {
            a = 1; // Target 1
            return a + b;
        }

        b = 1; // Target 2
        return a + b;
    }

    // P06: REACHABLE pair
    // Two arguments; witness: x = 0, y = 1.
    public static int p06(int x, int y) {
        int a = 0, b = 0;

        if (x < y) {
            a = 1; // Target 1
        }
        if (y >= x) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // P07: UNREACHABLE pair
    // A changed local variable prevents the second target.
    public static int p07(int x) {
        int a = 0, b = 0;
        int state = 0;

        if (x < 0) {
            state = 1;
            a = 1; // Target 1
        }
        if (state == 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // P08: REACHABLE pair
    // Two arguments and an exact value combination.
    // Witness: x = 100003, y = 100003.
    public static int p08(int x, int y) {
        int a = 0, b = 0;

        if (x == y) {
            a = 1; // Target 1
        }
        if (x == 100003 && y == 100003) {
            b = 1; // Target 2
        }
        return a + b;
    }
}
