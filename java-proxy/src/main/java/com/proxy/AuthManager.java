package com.proxy;

import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Instant;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.locks.ReentrantLock;
import java.util.concurrent.locks.ReentrantReadWriteLock;

public class AuthManager {
    private final Config config;
    private final HttpClient httpClient;
    private final ObjectMapper objectMapper = new ObjectMapper();

    private final AtomicReference<String> masterToken = new AtomicReference<>();
    private final ReentrantReadWriteLock tokenLock = new ReentrantReadWriteLock();
    private final ReentrantLock reauthMutex = new ReentrantLock();
    private volatile Instant lastReauthAttempt = Instant.MIN;

    public AuthManager(Config config, HttpClient httpClient) {
        this.config = config;
        this.httpClient = httpClient;
    }

    public String getToken() {
        tokenLock.readLock().lock();
        try {
            return masterToken.get();
        } finally {
            tokenLock.readLock().unlock();
        }
    }

    public void performInitialAuthentication() throws InterruptedException {
        boolean authenticated = false;
        String token = null;

        for (int i = 0; i < config.getMaxRetries(); i++) {
            Logger.log(Logger.Level.INFO, "Attempting to authenticate", String.format("(Attempt %d/%d)", i + 1, config.getMaxRetries()));
            try {
                token = authenticate();
                masterToken.set(token);
                authenticated = true;
                Logger.log(Logger.Level.SUCCESS, "Authenticated and retrieved initial token.");
                break;
            } catch (Exception e) {
                Logger.log(Logger.Level.ERROR, "Authentication failed!", e.getMessage());
                if (i < config.getMaxRetries() - 1) {
                    Logger.log(Logger.Level.INFO, String.format("Retrying in %dms...", config.getRetryIntervalMs()));
                    Thread.sleep(config.getRetryIntervalMs());
                }
            }
        }

        if (!authenticated) {
            Logger.log(Logger.Level.ERROR, "Could not authenticate after multiple retries. Exiting.");
            throw new RuntimeException("Could not authenticate with target server after multiple retries. Exiting.");
        }
    }

    public void refreshTokenIfNeeded() {
        if (!reauthMutex.tryLock()) {
            return;
        }
        try {
            if (Instant.now().isBefore(lastReauthAttempt.plusMillis(config.getReauthCooldownMs()))) {
                Logger.log(Logger.Level.INFO, "Re-authentication cooldown active. Please wait.");
                return;
            }
            lastReauthAttempt = Instant.now();
            Logger.log(Logger.Level.INFO, "Attempting to refresh token in background.");
            String newToken = authenticate();

            tokenLock.writeLock().lock();
            try {
                masterToken.set(newToken);
                Logger.log(Logger.Level.SUCCESS, "Successfully refreshed master token.");
            } finally {
                tokenLock.writeLock().unlock();
            }
        } catch (Exception e) {
            Logger.log(Logger.Level.ERROR, "Failed to refresh token", e);
        } finally {
            reauthMutex.unlock();
        }
    }

    private String authenticate() throws IOException, InterruptedException {
        String authUrl = "https://" + config.getTargetHost() + ":" + config.getTargetPort() + "/api/v1/auth";
        Logger.log(Logger.Level.INFO, "Posting to auth endpoint", "URL: " + authUrl);

        AuthRequest authRequest = new AuthRequest(config.getClientId(), config.getClientSecret());
        String requestBody = objectMapper.writeValueAsString(authRequest);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(authUrl))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(requestBody))
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            Logger.log(Logger.Level.WARN, "Authentication failed with non-OK status.", String.format("Status: %d %s", response.statusCode(), HttpStatus.getStatusText(response.statusCode())));
            throw new AuthenticationException("auth failed", request.method(), authUrl, response.statusCode(), response.body());
        }

        AuthResponse authResponse = objectMapper.readValue(response.body(), AuthResponse.class);
        return authResponse.master_token();
    }

    public static class AuthenticationException extends IOException {
        private final String operation;
        private final String url;
        private final int statusCode;
        private final String responseBody;

        public AuthenticationException(String message, String operation, String url, int statusCode, String responseBody) {
            super(String.format("%s \"%s\": address %s : %s", operation, url, responseBody, message));
            
            this.operation = operation;
            this.url = url;
            this.statusCode = statusCode;
            this.responseBody = responseBody;
        }

        public String getOperation() {
            return operation;
        }

        public String getUrl() {
            return url;
        }

        public int getStatusCode() {
            return statusCode;
        }

        public String getResponseBody() {
            return responseBody;
        }
    }
}
