package group15;

/**
 * Loop-free line-reachability benchmarks over unchanged Java int arguments.
 * Each TARGET marker identifies the single assignment queried by targets.json.
 * Return values expose whether that assignment executed; returns are not targets.
 * The unused noise locals in the two-argument families supply irrelevant literals.
 */
public final class LineReachability {

    // T1_exact_match, C1 (c = -7)
    public static int q01(int x) {
        int hit = 0;
        if (x == -7) {
            hit = 1; // TARGET: G15-Q01
        }
        return hit;
    }

    // T1_exact_match, C1 (c = -7)
    public static int q02(int x) {
        int hit = 0;
        if (x == -7) {
            if (x > -7) {
                hit = 1; // TARGET: G15-Q02
            }
        }
        return hit;
    }

    // T1_exact_match, C2 (c = 0)
    public static int q03(int x) {
        int hit = 0;
        if (x == 0) {
            hit = 1; // TARGET: G15-Q03
        }
        return hit;
    }

    // T1_exact_match, C2 (c = 0)
    public static int q04(int x) {
        int hit = 0;
        if (x == 0) {
            if (x > 0) {
                hit = 1; // TARGET: G15-Q04
            }
        }
        return hit;
    }

    // T1_exact_match, C3 (c = 100003)
    public static int q05(int x) {
        int hit = 0;
        if (x == 100003) {
            hit = 1; // TARGET: G15-Q05
        }
        return hit;
    }

    // T1_exact_match, C3 (c = 100003)
    public static int q06(int x) {
        int hit = 0;
        if (x == 100003) {
            if (x > 100003) {
                hit = 1; // TARGET: G15-Q06
            }
        }
        return hit;
    }

    // T2_integer_gap, C1 (c = -7)
    public static int q07(int x) {
        int hit = 0;
        if (x > -8) {
            if (x < -6) {
                hit = 1; // TARGET: G15-Q07
            }
        }
        return hit;
    }

    // T2_integer_gap, C1 (c = -7)
    public static int q08(int x) {
        int hit = 0;
        if (x > -7) {
            if (x < -6) {
                hit = 1; // TARGET: G15-Q08
            }
        }
        return hit;
    }

    // T2_integer_gap, C2 (c = 0)
    public static int q09(int x) {
        int hit = 0;
        if (x > -1) {
            if (x < 1) {
                hit = 1; // TARGET: G15-Q09
            }
        }
        return hit;
    }

    // T2_integer_gap, C2 (c = 0)
    public static int q10(int x) {
        int hit = 0;
        if (x > 0) {
            if (x < 1) {
                hit = 1; // TARGET: G15-Q10
            }
        }
        return hit;
    }

    // T2_integer_gap, C3 (c = 100003)
    public static int q11(int x) {
        int hit = 0;
        if (x > 100002) {
            if (x < 100004) {
                hit = 1; // TARGET: G15-Q11
            }
        }
        return hit;
    }

    // T2_integer_gap, C3 (c = 100003)
    public static int q12(int x) {
        int hit = 0;
        if (x > 100003) {
            if (x < 100004) {
                hit = 1; // TARGET: G15-Q12
            }
        }
        return hit;
    }

    // T3_early_return, C1 (c = -7)
    public static int q13(int x) {
        int hit = 0;
        if (x < -7) {
            return 0;
        }
        if (x > -7) {
            return 0;
        }
        hit = 1; // TARGET: G15-Q13
        return hit;
    }

    // T3_early_return, C1 (c = -7)
    public static int q14(int x) {
        int hit = 0;
        if (x < -7) {
            return 0;
        }
        if (x >= -7) {
            return 0;
        }
        hit = 1; // TARGET: G15-Q14
        return hit;
    }

    // T3_early_return, C2 (c = 0)
    public static int q15(int x) {
        int hit = 0;
        if (x < 0) {
            return 0;
        }
        if (x > 0) {
            return 0;
        }
        hit = 1; // TARGET: G15-Q15
        return hit;
    }

    // T3_early_return, C2 (c = 0)
    public static int q16(int x) {
        int hit = 0;
        if (x < 0) {
            return 0;
        }
        if (x >= 0) {
            return 0;
        }
        hit = 1; // TARGET: G15-Q16
        return hit;
    }

    // T3_early_return, C3 (c = 100003)
    public static int q17(int x) {
        int hit = 0;
        if (x < 100003) {
            return 0;
        }
        if (x > 100003) {
            return 0;
        }
        hit = 1; // TARGET: G15-Q17
        return hit;
    }

    // T3_early_return, C3 (c = 100003)
    public static int q18(int x) {
        int hit = 0;
        if (x < 100003) {
            return 0;
        }
        if (x >= 100003) {
            return 0;
        }
        hit = 1; // TARGET: G15-Q18
        return hit;
    }

    // T4_argument_order, C1 (c = -7)
    public static int q19(int x, int y) {
        int hit = 0;
        int noise = -7;
        if (x < y) {
            if (y > x) {
                hit = 1; // TARGET: G15-Q19
            }
        }
        return hit;
    }

    // T4_argument_order, C1 (c = -7)
    public static int q20(int x, int y) {
        int hit = 0;
        int noise = -7;
        if (x < y) {
            if (y <= x) {
                hit = 1; // TARGET: G15-Q20
            }
        }
        return hit;
    }

    // T4_argument_order, C2 (c = 0)
    public static int q21(int x, int y) {
        int hit = 0;
        int noise = 0;
        if (x < y) {
            if (y > x) {
                hit = 1; // TARGET: G15-Q21
            }
        }
        return hit;
    }

    // T4_argument_order, C2 (c = 0)
    public static int q22(int x, int y) {
        int hit = 0;
        int noise = 0;
        if (x < y) {
            if (y <= x) {
                hit = 1; // TARGET: G15-Q22
            }
        }
        return hit;
    }

    // T4_argument_order, C3 (c = 100003)
    public static int q23(int x, int y) {
        int hit = 0;
        int noise = 100003;
        if (x < y) {
            if (y > x) {
                hit = 1; // TARGET: G15-Q23
            }
        }
        return hit;
    }

    // T4_argument_order, C3 (c = 100003)
    public static int q24(int x, int y) {
        int hit = 0;
        int noise = 100003;
        if (x < y) {
            if (y <= x) {
                hit = 1; // TARGET: G15-Q24
            }
        }
        return hit;
    }

    // T5_shared_equality, C1 (c = -7)
    public static int q25(int x, int y) {
        int hit = 0;
        int noise = -7;
        if (x == y) {
            if (x <= y) {
                hit = 1; // TARGET: G15-Q25
            }
        }
        return hit;
    }

    // T5_shared_equality, C1 (c = -7)
    public static int q26(int x, int y) {
        int hit = 0;
        int noise = -7;
        if (x == y) {
            if (x < y) {
                hit = 1; // TARGET: G15-Q26
            }
        }
        return hit;
    }

    // T5_shared_equality, C2 (c = 0)
    public static int q27(int x, int y) {
        int hit = 0;
        int noise = 0;
        if (x == y) {
            if (x <= y) {
                hit = 1; // TARGET: G15-Q27
            }
        }
        return hit;
    }

    // T5_shared_equality, C2 (c = 0)
    public static int q28(int x, int y) {
        int hit = 0;
        int noise = 0;
        if (x == y) {
            if (x < y) {
                hit = 1; // TARGET: G15-Q28
            }
        }
        return hit;
    }

    // T5_shared_equality, C3 (c = 100003)
    public static int q29(int x, int y) {
        int hit = 0;
        int noise = 100003;
        if (x == y) {
            if (x <= y) {
                hit = 1; // TARGET: G15-Q29
            }
        }
        return hit;
    }

    // T5_shared_equality, C3 (c = 100003)
    public static int q30(int x, int y) {
        int hit = 0;
        int noise = 100003;
        if (x == y) {
            if (x < y) {
                hit = 1; // TARGET: G15-Q30
            }
        }
        return hit;
    }
}
