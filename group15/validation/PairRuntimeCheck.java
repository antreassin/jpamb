package group15.validation;

import group15.PairReachability;

/**
 * Reports the return value of one p01–p08 invocation. The caller uses return == 2
 * as a temporary smoke-test oracle. Actual instruction tracking is separate.
 */
public final class PairRuntimeCheck {
    private PairRuntimeCheck() {}

    public static void main(String[] args) {
        if (args.length == 0) {
            throw new IllegalArgumentException("Expected a paired method name");
        }
        String method = args[0];
        int arity = method.equals("p06") || method.equals("p08") ? 2 : 1;
        if (args.length != 1 + arity) {
            throw new IllegalArgumentException(method + " expects " + arity + " int argument(s)");
        }
        int x = Integer.parseInt(args[1]);
        int result = switch (method) {
            case "p01" -> PairReachability.p01(x);
            case "p02" -> PairReachability.p02(x);
            case "p03" -> PairReachability.p03(x);
            case "p04" -> PairReachability.p04(x);
            case "p05" -> PairReachability.p05(x);
            case "p06" -> PairReachability.p06(x, Integer.parseInt(args[2]));
            case "p07" -> PairReachability.p07(x);
            case "p08" -> PairReachability.p08(x, Integer.parseInt(args[2]));
            default -> throw new IllegalArgumentException("Unsupported paired method: " + method);
        };
        System.out.println(result);
    }
}
