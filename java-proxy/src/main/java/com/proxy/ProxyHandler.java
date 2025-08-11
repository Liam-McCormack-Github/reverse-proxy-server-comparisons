package com.proxy;

import io.undertow.server.HttpHandler;
import io.undertow.server.HttpServerExchange;
import io.undertow.util.Headers;
import io.undertow.util.HttpString;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.Set;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ExecutorService;

public class ProxyHandler implements HttpHandler {
    private static final Set<HttpString> RESTRICTED_HEADERS = Set.of(
            Headers.CONNECTION,
            Headers.HOST,
            Headers.KEEP_ALIVE,
            Headers.TRANSFER_ENCODING,
            Headers.UPGRADE
    );
    private final URI targetUri;
    private final HttpClient client;
    private final ExecutorService virtualThreadExecutor;
    private final AuthManager authManager;
    private final BlockingQueue<byte[]> bufferPool;

    public ProxyHandler(URI targetUri, HttpClient client, ExecutorService virtualThreadExecutor, AuthManager authManager, BlockingQueue<byte[]> bufferPool) {
        this.targetUri = targetUri;
        this.client = client;
        this.virtualThreadExecutor = virtualThreadExecutor;
        this.authManager = authManager;
        this.bufferPool = bufferPool;
    }

    @Override
    public void handleRequest(HttpServerExchange exchange) {
        if (exchange.isInIoThread()) {
            exchange.dispatch(this);
            return;
        }

        byte[] buffer = null;
        try {
            buffer = bufferPool.take();
            exchange.startBlocking();

            String clientIp = exchange.getSourceAddress().getAddress().getHostAddress();
            String requestLine = String.format("%s %s", exchange.getRequestMethod(), exchange.getRequestURI());
            Logger.log(Logger.Level.INFO, "Received request", String.format("Client IP: %s, Request: \"%s\"", clientIp, requestLine));

            URI newUri = new URI(
                    targetUri.getScheme(), null, targetUri.getHost(), targetUri.getPort(),
                    exchange.getRequestURI(), exchange.getQueryString(), null
            );

            HttpRequest.Builder requestBuilder = HttpRequest.newBuilder(newUri)
                    .method(exchange.getRequestMethod().toString(), HttpRequest.BodyPublishers.ofInputStream(exchange::getInputStream));

            exchange.getRequestHeaders().forEach(header -> {
                HttpString headerName = header.getHeaderName();
                if (!RESTRICTED_HEADERS.contains(headerName)) {
                    header.forEach(value -> requestBuilder.header(headerName.toString(), value));
                }
            });

            if (ResponseHandler.hasCustomHandler(exchange.getRequestURI())) {
                requestBuilder.setHeader("Accept-Encoding", "identity");
            }

            requestBuilder.header("X-Proxy-Token", authManager.getToken());

            Logger.log(Logger.Level.INFO, "Forwarding request to target", "URI: " + newUri);
            HttpResponse<InputStream> response = client.send(requestBuilder.build(), HttpResponse.BodyHandlers.ofInputStream());

            Logger.log(Logger.Level.INFO, "Received response from target", String.format("Status: %d %s", response.statusCode(), HttpStatus.getStatusText(response.statusCode())));

            if (response.statusCode() == 403) {
                Logger.log(Logger.Level.WARN, "Received 403 Forbidden from target. Triggering re-authentication.");

                virtualThreadExecutor.submit(authManager::refreshTokenIfNeeded);
            }

            exchange.setStatusCode(response.statusCode());
            response.headers().map().forEach((key, values) -> {
                HttpString headerName = new HttpString(key);
                if (!RESTRICTED_HEADERS.contains(headerName)) {
                    exchange.getResponseHeaders().putAll(headerName, values);
                }
            });

            if (ResponseHandler.hasCustomHandler(exchange.getRequestURI()) && response.statusCode() == 200) {
                Logger.log(Logger.Level.INFO, "Intercepting response for custom handling", "Route: " + exchange.getRequestURI());
                try (InputStream responseBody = response.body(); ByteArrayOutputStream baos = new ByteArrayOutputStream()) {
                    int bytesRead;
                    while ((bytesRead = responseBody.read(buffer)) != -1) {
                        baos.write(buffer, 0, bytesRead);
                    }
                    ResponseHandler.handle(exchange.getRequestURI(), baos.toByteArray(), exchange);
                }
            } else {
                try (InputStream responseBody = response.body(); OutputStream outputStream = exchange.getOutputStream()) {
                    int bytesRead;
                    while ((bytesRead = responseBody.read(buffer)) != -1) {
                        outputStream.write(buffer, 0, bytesRead);
                    }
                    outputStream.flush();
                }
            }

        } catch (Exception e) {
            String message = e.getMessage();
            if (message != null && (message.contains("UT000002") || message.contains("Broken pipe"))) {
                Logger.log(Logger.Level.INFO, "Client connection closed prematurely during proxying", message);
            } else {
                Logger.log(Logger.Level.ERROR, "Proxying failed", e);
                if (!exchange.isResponseStarted()) {
                    exchange.setStatusCode(500);
                    exchange.getResponseHeaders().put(Headers.CONTENT_TYPE, "text/plain");
                    exchange.getResponseSender().send("Internal Server Error");
                }
            }
        } finally {
            if (buffer != null) {
                bufferPool.offer(buffer);
            }
        }
    }
}
