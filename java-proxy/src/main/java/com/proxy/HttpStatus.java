package com.proxy;

import java.util.Map;

public class HttpStatus {
    private static final Map<Integer, String> statusMap = Map.ofEntries(
            Map.entry(200, "OK"),
            Map.entry(201, "Created"),
            Map.entry(204, "No Content"),
            Map.entry(400, "Bad Request"),
            Map.entry(401, "Unauthorized"),
            Map.entry(403, "Forbidden"),
            Map.entry(404, "Not Found"),
            Map.entry(500, "Internal Server Error"),
            Map.entry(502, "Bad Gateway"),
            Map.entry(503, "Service Unavailable")
    );

    public static String getStatusText(int code) {
        return statusMap.getOrDefault(code, "Unknown Status");
    }
}