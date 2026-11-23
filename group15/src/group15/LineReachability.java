package group15;

/**
 * Loop-free two-line-reachability benchmarks over unchanged Java int arguments.
 * Each test has two assignments marked "// Target 1" and "// Target 2".
 * The question is whether BOTH targets can execute in the SAME run.
 * Return values (a + b) expose which targets executed; returns are not targets.
 * The unused noise local in the two-argument family supplies an irrelevant literal.
 */
public final class LineReachability {

    // T1_exact_then_relational, C1 (c = -7), expected: both targets reachable in one run
    public static int q01(int x) {
        int a = 0;
        int b = 0;
        if (x == -7) {
            a = 1; // Target 1
        }
        if (x <= -7) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T1_exact_then_relational, C1 (c = -7), expected: both targets NOT reachable in one run
    public static int q02(int x) {
        int a = 0;
        int b = 0;
        if (x == -7) {
            a = 1; // Target 1
        }
        if (x != -7) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T1_exact_then_relational, C2 (c = 0), expected: both targets reachable in one run
    public static int q03(int x) {
        int a = 0;
        int b = 0;
        if (x == 0) {
            a = 1; // Target 1
        }
        if (x <= 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T1_exact_then_relational, C2 (c = 0), expected: both targets NOT reachable in one run
    public static int q04(int x) {
        int a = 0;
        int b = 0;
        if (x == 0) {
            a = 1; // Target 1
        }
        if (x != 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T1_exact_then_relational, C3 (c = 100003), expected: both targets reachable in one run
    public static int q05(int x) {
        int a = 0;
        int b = 0;
        if (x == 100003) {
            a = 1; // Target 1
        }
        if (x <= 100003) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T1_exact_then_relational, C3 (c = 100003), expected: both targets NOT reachable in one run
    public static int q06(int x) {
        int a = 0;
        int b = 0;
        if (x == 100003) {
            a = 1; // Target 1
        }
        if (x != 100003) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T2_split_range, C1 (c = -7), expected: both targets reachable in one run
    public static int q07(int x) {
        int a = 0;
        int b = 0;
        if (x < -6) {
            a = 1; // Target 1
        }
        if (x > -8) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T2_split_range, C1 (c = -7), expected: both targets NOT reachable in one run
    public static int q08(int x) {
        int a = 0;
        int b = 0;
        if (x < -7) {
            a = 1; // Target 1
        }
        if (x > -7) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T2_split_range, C2 (c = 0), expected: both targets reachable in one run
    public static int q09(int x) {
        int a = 0;
        int b = 0;
        if (x < 1) {
            a = 1; // Target 1
        }
        if (x > -1) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T2_split_range, C2 (c = 0), expected: both targets NOT reachable in one run
    public static int q10(int x) {
        int a = 0;
        int b = 0;
        if (x < 0) {
            a = 1; // Target 1
        }
        if (x > 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T2_split_range, C3 (c = 100003), expected: both targets reachable in one run
    public static int q11(int x) {
        int a = 0;
        int b = 0;
        if (x < 100004) {
            a = 1; // Target 1
        }
        if (x > 100002) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T2_split_range, C3 (c = 100003), expected: both targets NOT reachable in one run
    public static int q12(int x) {
        int a = 0;
        int b = 0;
        if (x < 100003) {
            a = 1; // Target 1
        }
        if (x > 100003) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T3_integer_gap, C1 (c = -7), expected: both targets reachable in one run
    public static int q13(int x) {
        int a = 0;
        int b = 0;
        if (x > -9) {
            a = 1; // Target 1
        }
        if (x < -7) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T3_integer_gap, C1 (c = -7), expected: both targets NOT reachable in one run
    public static int q14(int x) {
        int a = 0;
        int b = 0;
        if (x > -8) {
            a = 1; // Target 1
        }
        if (x < -7) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T3_integer_gap, C2 (c = 0), expected: both targets reachable in one run
    public static int q15(int x) {
        int a = 0;
        int b = 0;
        if (x > -2) {
            a = 1; // Target 1
        }
        if (x < 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T3_integer_gap, C2 (c = 0), expected: both targets NOT reachable in one run
    public static int q16(int x) {
        int a = 0;
        int b = 0;
        if (x > -1) {
            a = 1; // Target 1
        }
        if (x < 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T3_integer_gap, C3 (c = 100003), expected: both targets reachable in one run
    public static int q17(int x) {
        int a = 0;
        int b = 0;
        if (x > 100001) {
            a = 1; // Target 1
        }
        if (x < 100003) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T3_integer_gap, C3 (c = 100003), expected: both targets NOT reachable in one run
    public static int q18(int x) {
        int a = 0;
        int b = 0;
        if (x > 100002) {
            a = 1; // Target 1
        }
        if (x < 100003) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T4_nested_targets, C1 (c = -7), expected: both targets reachable in one run
    public static int q19(int x) {
        int a = 0;
        int b = 0;
        if (x >= -7) {
            a = 1; // Target 1
            if (x <= -7) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // T4_nested_targets, C1 (c = -7), expected: both targets NOT reachable in one run
    public static int q20(int x) {
        int a = 0;
        int b = 0;
        if (x == -7) {
            a = 1; // Target 1
            if (x > -7) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // T4_nested_targets, C2 (c = 0), expected: both targets reachable in one run
    public static int q21(int x) {
        int a = 0;
        int b = 0;
        if (x >= 0) {
            a = 1; // Target 1
            if (x <= 0) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // T4_nested_targets, C2 (c = 0), expected: both targets NOT reachable in one run
    public static int q22(int x) {
        int a = 0;
        int b = 0;
        if (x == 0) {
            a = 1; // Target 1
            if (x > 0) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // T4_nested_targets, C3 (c = 100003), expected: both targets reachable in one run
    public static int q23(int x) {
        int a = 0;
        int b = 0;
        if (x >= 100003) {
            a = 1; // Target 1
            if (x <= 100003) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // T4_nested_targets, C3 (c = 100003), expected: both targets NOT reachable in one run
    public static int q24(int x) {
        int a = 0;
        int b = 0;
        if (x == 100003) {
            a = 1; // Target 1
            if (x > 100003) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // T5_two_arguments, C1 (c = -7), expected: both targets reachable in one run
    public static int q25(int x, int y) {
        int a = 0;
        int b = 0;
        int noise = -7;
        if (x <= y) {
            a = 1; // Target 1
        }
        if (y <= x) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T5_two_arguments, C1 (c = -7), expected: both targets NOT reachable in one run
    public static int q26(int x, int y) {
        int a = 0;
        int b = 0;
        int noise = -7;
        if (x < y) {
            a = 1; // Target 1
        }
        if (y < x) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T5_two_arguments, C2 (c = 0), expected: both targets reachable in one run
    public static int q27(int x, int y) {
        int a = 0;
        int b = 0;
        int noise = 0;
        if (x <= y) {
            a = 1; // Target 1
        }
        if (y <= x) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T5_two_arguments, C2 (c = 0), expected: both targets NOT reachable in one run
    public static int q28(int x, int y) {
        int a = 0;
        int b = 0;
        int noise = 0;
        if (x < y) {
            a = 1; // Target 1
        }
        if (y < x) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T5_two_arguments, C3 (c = 100003), expected: both targets reachable in one run
    public static int q29(int x, int y) {
        int a = 0;
        int b = 0;
        int noise = 100003;
        if (x <= y) {
            a = 1; // Target 1
        }
        if (y <= x) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // T5_two_arguments, C3 (c = 100003), expected: both targets NOT reachable in one run
    public static int q30(int x, int y) {
        int a = 0;
        int b = 0;
        int noise = 100003;
        if (x < y) {
            a = 1; // Target 1
        }
        if (y < x) {
            b = 1; // Target 2
        }
        return a + b;
    }

    public static int pairUnreachableSign(int x) {
        int i = 2;
        if (x < 0) {
            i = 0;          // TARGET 1
        }
        if (x > 0) {
            return 10 / i;  // TARGET 2
        }
        return 0;
    }

    public static int pairReachableRange(int x) {
        int i = 2;
        if (x > 5) {
            i = 0;          // TARGET 1
        }
        if (x < 10) {
            return i + 1;   // TARGET 2
        }
        return 0;
    }

    public static int f(float y) {
        int i = 2;
        while (y < 1) {
            y = y + 1;
        }
        if (y != 1) {
            i = 0;          // TARGET 1
        }
        return (int)(y / i); // TARGET 2
    }

    public static int pairUnreachableLoop(int x) {
        int i = 2;
        while (x < 0) {
            i = 0;          // TARGET 1
            x = x + 1;
        }
        if (x != 0) {
            return 10 / i;  // TARGET 2
        }
        return 0;
    }
}
