package group15.validation;

import group15.PairReachability;

/**
 * Smoke-test harness only: reports the return value of one p03/p04 invocation.
 * Return 2 encodes both targets in order for these unchanged methods. This is
 * not instruction tracking and is not JPAMB's official outcome scoring.
 */
public final class PairRuntimeCheck {
    private PairRuntimeCheck() {}

    public static void main(String[] args) {
        if (args.length != 2) {
            throw new IllegalArgumentException("Expected p03 or p04 and one Java int");
        }
        int x = Integer.parseInt(args[1]);
        int result = switch (args[0]) {
            case "p03" -> PairReachability.p03(x);
            case "p04" -> PairReachability.p04(x);
            default -> throw new IllegalArgumentException("Only p03 and p04 are supported");
        };
        System.out.println(result);
    }
}
