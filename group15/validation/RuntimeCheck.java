package group15.validation;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.lang.reflect.Method;

/** Validation harness only; not an analysis target or part of the benchmark class. */
public final class RuntimeCheck {
    public static void main(String[] args) throws Exception {
        BufferedReader input = new BufferedReader(new InputStreamReader(System.in));
        Class<?> benchmark = Class.forName("group15.LineReachability");
        String line;
        while ((line = input.readLine()) != null) {
            String[] fields = line.split(" ");
            Class<?>[] types = new Class<?>[fields.length - 1];
            Object[] values = new Object[fields.length - 1];
            for (int i = 1; i < fields.length; i++) {
                types[i - 1] = int.class;
                values[i - 1] = Integer.parseInt(fields[i]);
            }
            Method method = benchmark.getMethod(fields[0], types);
            System.out.println(method.invoke(null, values));
        }
    }
}
