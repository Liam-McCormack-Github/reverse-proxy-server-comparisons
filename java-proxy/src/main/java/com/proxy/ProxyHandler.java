package com.proxy;

import io.undertow.server.HttpHandler;
import io.undertow.server.HttpServerExchange;
import io.undertow.util.Headers;
import io.undertow.util.HttpString;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.Instant;
import java.util.Set;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ExecutorService;

public class ProxyHandler implements HttpHandler {
    private final URI targetUri;
    private final HttpClient client;
    private final ExecutorService virtualThreadExecutor;
    private final long reauthCooldownMs;
    private final String clientId;
    private final String clientSecret;
    private final String targetHost;
    private final String targetPort;
    private final BlockingQueue<byte[]> bufferPool;

    private static final Set<HttpString> RESTRICTED_HEADERS = Set.of(
            Headers.CONNECTION,
            Headers.HOST,
            Headers.KEEP_ALIVE,
            Headers.TRANSFER_ENCODING,
            Headers.UPGRADE
    );

    public ProxyHandler(URI targetUri, HttpClient client, ExecutorService virtualThreadExecutor, long reauthCooldownMs, String clientId, String clientSecret, String targetHost, String targetPort, BlockingQueue<byte[]> bufferPool) {
        this.targetUri = targetUri;
        this.client = client;
        this.virtualThreadExecutor = virtualThreadExecutor;
        this.reauthCooldownMs = reauthCooldownMs;
        this.clientId = clientId;
        this.clientSecret = clientSecret;
        this.targetHost = targetHost;
        this.targetPort = targetPort;
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
            Logger.log("INFO", "Received request", String.format("Client IP: %s, Request: \"%s\"", clientIp, requestLine));

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

            App.tokenLock.readLock().lock();
            try {
                requestBuilder.header("X-Proxy-Token", App.masterToken.get());
            } finally {
                App.tokenLock.readLock().unlock();
            }

            Logger.log("INFO", "Forwarding request to target service", String.format("Host IP: %s, Scheme: %s", targetUri.getHost(), targetUri.getScheme()));

            HttpResponse<InputStream> response = client.send(requestBuilder.build(), HttpResponse.BodyHandlers.ofInputStream());

            if (response.statusCode() == 403) {
                handleForbiddenStatus();
            }

            exchange.setStatusCode(response.statusCode());
            response.headers().map().forEach((key, values) -> {
                HttpString headerName = new HttpString(key);
                if (!RESTRICTED_HEADERS.contains(headerName)) {
                    exchange.getResponseHeaders().putAll(headerName, values);
                }
            });

            try (InputStream responseBody = response.body(); OutputStream outputStream = exchange.getOutputStream()) {
                int bytesRead;
                while ((bytesRead = responseBody.read(buffer)) != -1) {
                    outputStream.write(buffer, 0, bytesRead);
                }
                outputStream.flush();
            }

        } catch (Exception e) {
            String message = e.getMessage();
            if (message != null && (message.contains("UT000002") || message.contains("Broken pipe"))) {
                Logger.log("INFO", "Client connection closed during proxying.", message);
            } else {
                Logger.log("ERROR", "Proxying failed", e.getMessage() != null ? e.getMessage() : e.getClass().getName());
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

    private void handleForbiddenStatus() {
        Logger.log("WARN", "Received 403 Forbidden from target. Triggering re-authentication.");
        virtualThreadExecutor.submit(() -> {
            if (App.reauthMutex.tryLock()) {
                try {
                    if (Duration.between(App.lastReauthAttempt, Instant.now()).toMillis() < reauthCooldownMs) {
                        Logger.log("INFO", "Re-authentication cooldown active. Please wait.");
                        return;
                    }
                    App.lastReauthAttempt = Instant.now();
                    String newToken = App.authenticate(targetHost, targetPort, clientId, clientSecret);

                    App.tokenLock.writeLock().lock();
                    try {
                        App.masterToken.set(newToken);
                        Logger.log("SUCCESS", "Successfully refreshed master token in background.");
                    } finally {
                        App.tokenLock.writeLock().unlock();
                    }
                } catch (Exception e) {
                    Logger.log("ERROR", "Background re-authentication failed", e.getMessage());
                } finally {
                    App.reauthMutex.unlock();
                }
            }
        });
    }
}