package com.proxy;

import java.io.PrintWriter;
import java.io.StringWriter;
import java.text.SimpleDateFormat;
import java.util.Date;

public class Logger {
    public static void log(Level level, String message, String... extras) {
        String timestamp = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS").format(new Date());
        String extraStr = extras.length > 0 ? " :: " + String.join(" ", extras) : "";
        System.out.printf("[%s] %-7s :: %s%s%n", timestamp, level.name(), message, extraStr);
    }

    public static void log(Level level, String message, Throwable throwable) {
        StringWriter sw = new StringWriter();
        PrintWriter pw = new PrintWriter(sw);
        throwable.printStackTrace(pw);
        String stackTrace = sw.toString();

        log(level, message, throwable.getMessage() + "\n" + stackTrace);
    }

    public enum Level {INFO, WARN, ERROR, SUCCESS}
}