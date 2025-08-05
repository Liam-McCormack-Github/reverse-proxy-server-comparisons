package com.proxy;

import java.text.SimpleDateFormat;
import java.util.Date;

public class Logger {
    public static void log(String level, String message, String... extras) {
        String timestamp = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS").format(new Date());
        String extraStr = extras.length > 0 ? " :: " + String.join(" ", extras) : "";
        System.out.printf("[%s] %-7s :: %s%s%n", timestamp, level.toUpperCase(), message, extraStr);
    }
}
