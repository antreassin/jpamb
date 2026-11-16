package group15;

/**
 * Harder two-line-reachability benchmarks.
 * Each test has two assignments marked "// Target 1" and "// Target 2", and the question
 * is whether BOTH can execute in the SAME run. Every method returns a + b, so a run that
 * reaches both targets returns 2.
 * In every test each target is reachable on its own; only the pair is in question.
 * The tests mix int, float, double, String and int[] parameters and use loops, casts,
 * overflow, NaN, aliasing and other Java semantics that are easy to get wrong.
 * Each family has a "NOT reachable" test and a "reachable" test that look alike.
 */
public final class LineReachabilityHard {

    // H1_float_accumulation (double), expected: NOT reachable in one run
    // ten additions of 0.1 give 0.9999999999999999, so y >= 1.0 fails whenever n == 10
    public static int h01(int n) {
        int a = 0;
        int b = 0;
        double y = 0.0;
        for (int k = 0; k < n; k++) {
            y = y + 0.1;
        }
        if (n == 10) {
            a = 1; // Target 1
        }
        if (y >= 1.0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H1_float_accumulation (float), expected: reachable in one run
    // witness n = 10: ten additions of 0.1f give 1.0000001f in float arithmetic
    public static int h02(int n) {
        int a = 0;
        int b = 0;
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

    // H2_float_literal_sums (double), expected: NOT reachable in one run
    // 0.1 + 0.2 is 0.30000000000000004 in double, which is not the literal 0.3
    public static int h03(double x) {
        int a = 0;
        int b = 0;
        if (x == 0.3) {
            a = 1; // Target 1
        }
        if (x == 0.1 + 0.2) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H2_float_literal_sums (float), expected: reachable in one run
    // witness x = 0.3f: 0.1f + 0.2f rounds to exactly 0.3f in float
    public static int h04(float x) {
        int a = 0;
        int b = 0;
        if (x == 0.3f) {
            a = 1; // Target 1
        }
        if (x == 0.1f + 0.2f) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H3_nan, expected: reachable in one run
    // witness x = NaN: both !(x < 0) and !(x >= 0) hold for NaN
    public static int h05(float x) {
        int a = 0;
        int b = 0;
        if (x != x) {
            a = 1; // Target 1
        }
        if (!(x < 0) && !(x >= 0)) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H3_nan, expected: NOT reachable in one run
    // x != x holds only for NaN, and NaN fails both x < 0 and x >= 0
    public static int h06(float x) {
        int a = 0;
        int b = 0;
        if (x != x) {
            a = 1; // Target 1
        }
        if (x < 0 || x >= 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H4_negative_zero, expected: reachable in one run
    // witness x = -0.0f: -0.0f == 0.0f is true and 1 / -0.0f is -Infinity
    public static int h07(float x) {
        int a = 0;
        int b = 0;
        if (x == 0.0f) {
            a = 1; // Target 1
        }
        if (1 / x < 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H4_negative_zero, expected: NOT reachable in one run
    // x == 0.0f holds for -0.0f too, but -0.0f < 0 is false
    public static int h08(float x) {
        int a = 0;
        int b = 0;
        if (x == 0.0f) {
            a = 1; // Target 1
        }
        if (x < 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H5_cast_truncation, expected: reachable in one run
    // witness y = -0.5: (int) -0.5 truncates toward zero to 0
    public static int h09(double y) {
        int a = 0;
        int b = 0;
        if ((int) y == 0) {
            a = 1; // Target 1
        }
        if (y < 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H5_cast_truncation, expected: NOT reachable in one run
    // (int) y == 0 implies y > -1, so y <= -1.0 is impossible
    public static int h10(double y) {
        int a = 0;
        int b = 0;
        if ((int) y == 0) {
            a = 1; // Target 1
        }
        if (y <= -1.0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H6_float_absorption, expected: reachable in one run
    // witness x = 16777216f (2^24): adding 1f is absorbed
    public static int h11(float x) {
        int a = 0;
        int b = 0;
        if (x + 1f == x) {
            a = 1; // Target 1
        }
        if (x > 16777000f) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H6_float_absorption, expected: NOT reachable in one run
    // x + 1f == x needs x >= 2^24 (or Infinity), which excludes 0 < x < 2^24
    public static int h12(float x) {
        int a = 0;
        int b = 0;
        if (x + 1f == x) {
            a = 1; // Target 1
        }
        if (x > 0 && x < 16777216f) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H7_int_to_float_rounding, expected: reachable in one run
    // witness x = 16777216: (float) 16777217 rounds to 16777216f
    public static int h13(int x) {
        int a = 0;
        int b = 0;
        if ((float) x == (float) (x + 1)) {
            a = 1; // Target 1
        }
        if (x > 16777000) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H7_int_to_float_rounding, expected: NOT reachable in one run
    // adjacent ints are distinct floats whenever -2^24 < x < 2^24
    public static int h14(int x) {
        int a = 0;
        int b = 0;
        if ((float) x == (float) (x + 1)) {
            a = 1; // Target 1
        }
        if (x > -16777216 && x < 16777216) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H8_int_overflow, expected: reachable in one run
    // witness x = 50000: x * x wraps around to a negative int
    public static int h15(int x) {
        int a = 0;
        int b = 0;
        if (x * x < 0) {
            a = 1; // Target 1
        }
        if (x > 46340) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H8_int_overflow, expected: NOT reachable in one run
    // x * x only wraps for |x| >= 46341
    public static int h16(int x) {
        int a = 0;
        int b = 0;
        if (x * x < 0) {
            a = 1; // Target 1
        }
        if (x > -46341 && x < 46341) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H9_abs_min_value, expected: reachable in one run
    // witness x = Integer.MIN_VALUE: Math.abs returns a negative number
    public static int h17(int x) {
        int a = 0;
        int b = 0;
        if (Math.abs(x) < 0) {
            a = 1; // Target 1
        }
        if (x < 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H9_abs_min_value, expected: NOT reachable in one run
    // Math.abs(x) < 0 only for Integer.MIN_VALUE
    public static int h18(int x) {
        int a = 0;
        int b = 0;
        if (Math.abs(x) < 0) {
            a = 1; // Target 1
        }
        if (x > Integer.MIN_VALUE) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H10_remainder_sign, expected: NOT reachable in one run
    // in Java x % 2 == 1 forces x > 0, since the remainder takes the sign of x
    public static int h19(int x) {
        int a = 0;
        int b = 0;
        if (x % 2 == 1) {
            a = 1; // Target 1
        }
        if (x < 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H10_remainder_sign, expected: reachable in one run
    // witness x = -3: x % 2 is -1, which is != 0
    public static int h20(int x) {
        int a = 0;
        int b = 0;
        if (x % 2 != 0) {
            a = 1; // Target 1
        }
        if (x < 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H11_byte_narrowing, expected: NOT reachable in one run
    // (byte) x is non-negative for every x in 0..127
    public static int h21(int x) {
        int a = 0;
        int b = 0;
        if ((byte) x < 0) {
            a = 1; // Target 1
        }
        if (x >= 0 && x < 128) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H11_byte_narrowing, expected: reachable in one run
    // witness x = 200: (byte) 200 is -56
    public static int h22(int x) {
        int a = 0;
        int b = 0;
        if ((byte) x < 0) {
            a = 1; // Target 1
        }
        if (x >= 200) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H12_char_narrowing, expected: reachable in one run
    // witness x = -65471: (char) -65471 is 65, i.e. 'A'
    public static int h23(int x) {
        int a = 0;
        int b = 0;
        if ((char) x == 'A') {
            a = 1; // Target 1
        }
        if (x < 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H12_char_narrowing, expected: NOT reachable in one run
    // (char) x == 'A' needs x == 65 + 65536 * m, none lie in 66..65600
    public static int h24(int x) {
        int a = 0;
        int b = 0;
        if ((char) x == 'A') {
            a = 1; // Target 1
        }
        if (x > 65 && x < 65601) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H13_bit_tricks, expected: reachable in one run
    // witness x = Integer.MIN_VALUE: MIN_VALUE & (MIN_VALUE - 1) is 0
    public static int h25(int x) {
        int a = 0;
        int b = 0;
        if ((x & (x - 1)) == 0) {
            a = 1; // Target 1
        }
        if (x < 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H13_bit_tricks, expected: NOT reachable in one run
    // a positive power of two is never divisible by 3
    public static int h26(int x) {
        int a = 0;
        int b = 0;
        if (x > 0 && (x & (x - 1)) == 0) {
            a = 1; // Target 1
        }
        if (x % 3 == 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H14_shift_distance, expected: reachable in one run
    // witness x = 33: shift distances are taken mod 32, so 1 << 33 == 2
    public static int h27(int x) {
        int a = 0;
        int b = 0;
        if ((1 << x) == 2) {
            a = 1; // Target 1
        }
        if (x > 1) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H14_shift_distance, expected: NOT reachable in one run
    // (1 << x) == 2 needs x mod 32 == 1, none in 2..31
    public static int h28(int x) {
        int a = 0;
        int b = 0;
        if ((1 << x) == 2) {
            a = 1; // Target 1
        }
        if (x > 1 && x < 32) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H15_integer_cache, expected: NOT reachable in one run
    // boxed Integers are == only for equal values in -128..127 (default cache)
    public static int h29(int x, int y) {
        int a = 0;
        int b = 0;
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

    // H15_integer_cache, expected: reachable in one run
    // witness x = y = 5 (inside the Integer cache)
    public static int h30(int x, int y) {
        int a = 0;
        int b = 0;
        Integer p = x;
        Integer q = y;
        if (p == q) {
            a = 1; // Target 1
        }
        if (x == y) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H16_loop_congruence, expected: NOT reachable in one run
    // k stays congruent to x mod 3; k == 100 needs x % 3 == 1, not 0
    public static int h31(int x) {
        int a = 0;
        int b = 0;
        int k = x;
        while (k < 100) {
            k += 3;
        }
        if (k == 100) {
            a = 1; // Target 1
        }
        if (x < 100 && x % 3 == 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H16_loop_congruence, expected: reachable in one run
    // witness x = 97: loop runs once and ends with k == 100
    public static int h32(int x) {
        int a = 0;
        int b = 0;
        int k = x;
        while (k < 100) {
            k += 3;
        }
        if (k == 100) {
            a = 1; // Target 1
        }
        if (x < 100 && x % 3 == 1) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H17_loop_bit_length, expected: NOT reachable in one run
    // count == 31 needs x >= 2^30, so x < 1073741824 is impossible
    public static int h33(int x) {
        int a = 0;
        int b = 0;
        int k = x;
        int count = 0;
        while (k > 0) {
            k = k / 2;
            count++;
        }
        if (count == 31) {
            a = 1; // Target 1
        }
        if (x < 1073741824) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H17_loop_bit_length, expected: reachable in one run
    // witness x = Integer.MAX_VALUE: 31 halvings
    public static int h34(int x) {
        int a = 0;
        int b = 0;
        int k = x;
        int count = 0;
        while (k > 0) {
            k = k / 2;
            count++;
        }
        if (count == 31) {
            a = 1; // Target 1
        }
        if (x > 1073741824) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H18_loop_string_length, expected: NOT reachable in one run
    // s.length() is n * t.length(); with t.length() == 4 it is never 6
    public static int h35(int n, String t) {
        int a = 0;
        int b = 0;
        String s = "";
        for (int k = 0; k < n; k++) {
            s = s + t;
        }
        if (s.length() == 6) {
            a = 1; // Target 1
        }
        if (t.length() == 4) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H18_loop_string_length, expected: reachable in one run
    // witness n = 2, t = "abc"
    public static int h36(int n, String t) {
        int a = 0;
        int b = 0;
        String s = "";
        for (int k = 0; k < n; k++) {
            s = s + t;
        }
        if (s.length() == 6) {
            a = 1; // Target 1
        }
        if (t.length() == 3) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H19_loop_over_array, expected: NOT reachable in one run
    // strictly ascending arrays always have p[0] < p[p.length - 1]
    public static int h37(int[] p) {
        int a = 0;
        int b = 0;
        int ascents = 0;
        for (int k = 0; k + 1 < p.length; k++) {
            if (p[k] < p[k + 1]) {
                ascents++;
            }
        }
        if (p.length > 1 && ascents == p.length - 1) {
            a = 1; // Target 1
        }
        if (p.length > 0 && p[0] >= p[p.length - 1]) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H19_loop_over_array, expected: reachable in one run
    // witness p = {1, 2}
    public static int h38(int[] p) {
        int a = 0;
        int b = 0;
        int ascents = 0;
        for (int k = 0; k + 1 < p.length; k++) {
            if (p[k] < p[k + 1]) {
                ascents++;
            }
        }
        if (p.length > 1 && ascents == p.length - 1) {
            a = 1; // Target 1
        }
        if (p.length > 0 && p[0] < p[p.length - 1]) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H20_string_hash_collision, expected: reachable in one run
    // witness s = "Aa": "Aa" and "BB" share hashCode 2112
    public static int h39(String s) {
        int a = 0;
        int b = 0;
        if (s.length() == 2 && s.charAt(0) == 'A') {
            a = 1; // Target 1
        }
        if (s.hashCode() == "BB".hashCode()) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H20_string_hash_collision, expected: NOT reachable in one run
    // a 2-char string with first char >= 'E' has hashCode >= 69 * 31 > 2112
    public static int h40(String s) {
        int a = 0;
        int b = 0;
        if (s.length() == 2 && s.charAt(0) >= 'E') {
            a = 1; // Target 1
        }
        if (s.hashCode() == "BB".hashCode()) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H21_string_concat_length, expected: NOT reachable in one run
    // (s + t) has length 4, so both parts cannot be longer than 2
    public static int h41(String s, String t) {
        int a = 0;
        int b = 0;
        if ((s + t).equals("abcd")) {
            a = 1; // Target 1
        }
        if (s.length() > 2 && t.length() > 2) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H21_string_concat_length, expected: reachable in one run
    // witness s = "a", t = "bcd"
    public static int h42(String s, String t) {
        int a = 0;
        int b = 0;
        if ((s + t).equals("abcd")) {
            a = 1; // Target 1
        }
        if (s.length() == 1) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H22_string_prefix_suffix, expected: NOT reachable in one run
    // startsWith("ab") fixes s[1] == 'b', endsWith("cb") fixes s[1] == 'c' (length 3)
    public static int h43(String s) {
        int a = 0;
        int b = 0;
        if (s.startsWith("ab")) {
            a = 1; // Target 1
        }
        if (s.length() == 3 && s.endsWith("cb")) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H22_string_prefix_suffix, expected: reachable in one run
    // witness s = "aba"
    public static int h44(String s) {
        int a = 0;
        int b = 0;
        if (s.startsWith("ab")) {
            a = 1; // Target 1
        }
        if (s.length() == 3 && s.endsWith("ba")) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H23_string_ordering, expected: NOT reachable in one run
    // compareTo is antisymmetric: s < t and t < s cannot both hold
    public static int h45(String s, String t) {
        int a = 0;
        int b = 0;
        if (s.compareTo(t) < 0) {
            a = 1; // Target 1
        }
        if (t.compareTo(s) < 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H23_string_ordering, expected: reachable in one run
    // witness s = "B", t = "a": compareTo is negative, compareToIgnoreCase is positive
    public static int h46(String s, String t) {
        int a = 0;
        int b = 0;
        if (s.compareTo(t) < 0) {
            a = 1; // Target 1
        }
        if (s.compareToIgnoreCase(t) > 0) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H24_string_identity, expected: NOT reachable in one run
    // s == t means same object, so s.equals(t) is true (NPE if s is null)
    public static int h47(String s, String t) {
        int a = 0;
        int b = 0;
        if (s == t) {
            a = 1; // Target 1
        }
        if (!s.equals(t)) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H24_string_identity, expected: reachable in one run
    // witness s = "a", t = new String("a"): equal content, different objects
    public static int h48(String s, String t) {
        int a = 0;
        int b = 0;
        if (s.equals(t)) {
            a = 1; // Target 1
        }
        if (s != t) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H25_array_aliasing, expected: NOT reachable in one run
    // if p == q the write p[0] = 1 is visible as q[0] == 1, so q[0] == 0 fails
    public static int h49(int[] p, int[] q) {
        int a = 0;
        int b = 0;
        if (p.length > 0 && q.length > 0) {
            p[0] = 1;
            if (p == q) {
                a = 1; // Target 1
            }
            if (q[0] == 0) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // H25_array_aliasing, expected: reachable in one run
    // witness p == q (same array), or any q with q[0] == 1
    public static int h50(int[] p, int[] q) {
        int a = 0;
        int b = 0;
        if (p.length > 0 && q.length > 0) {
            p[0] = 1;
            if (p == q) {
                a = 1; // Target 1
            }
            if (q[0] == 1) {
                b = 1; // Target 2
            }
        }
        return a + b;
    }

    // H26_array_length, expected: NOT reachable in one run
    // length is n when n > 0, else 1; a length > 5 needs n > 5, so n < 6 fails
    public static int h51(int n) {
        int a = 0;
        int b = 0;
        int[] arr = new int[n > 0 ? n : 1];
        if (arr.length > 5) {
            a = 1; // Target 1
        }
        if (n < 6) {
            b = 1; // Target 2
        }
        return a + b;
    }

    // H26_array_length, expected: reachable in one run
    // witness n = 101
    public static int h52(int n) {
        int a = 0;
        int b = 0;
        int[] arr = new int[n > 0 ? n : 1];
        if (arr.length > 5) {
            a = 1; // Target 1
        }
        if (n > 100) {
            b = 1; // Target 2
        }
        return a + b;
    }
}