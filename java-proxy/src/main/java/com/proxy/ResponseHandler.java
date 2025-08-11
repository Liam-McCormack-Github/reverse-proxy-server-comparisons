package com.proxy;

import io.undertow.server.HttpServerExchange;
import io.undertow.util.Headers;

import java.nio.charset.StandardCharsets;

public class ResponseHandler {

    public static boolean hasCustomHandler(String path) {
        switch (path) {
            case "/wheredidicomefrom":
                return true;
            default:
                return false;
        }
    }

    public static void handle(String path, byte[] originalBody, HttpServerExchange exchange) {
        switch (path) {
            case "/wheredidicomefrom":
                handleWheredidicomefrom(originalBody, exchange);
                break;
            default:
                exchange.getResponseSender().send(new String(originalBody, StandardCharsets.UTF_8));
                break;
        }
    }

    private static void handleWheredidicomefrom(byte[] originalBody, HttpServerExchange exchange) {
        String originalHtml = new String(originalBody, StandardCharsets.UTF_8);
        String injectedHtml = "<p style=\"color: red; font-weight: bold;\">Injected by the Java Proxy!</p>";
        String modifiedHtml = originalHtml.replace("</body>", injectedHtml + "</body>");

        exchange.getResponseHeaders().put(Headers.CONTENT_LENGTH, (long) modifiedHtml.getBytes(StandardCharsets.UTF_8).length);
        exchange.getResponseHeaders().put(Headers.CONTENT_TYPE, "text/html");

        Logger.log(Logger.Level.INFO, "Successfully injected custom HTML into response");

        exchange.getResponseSender().send(modifiedHtml);
    }
}
