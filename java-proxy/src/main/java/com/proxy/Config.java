package com.proxy;

public class Config {

    private final int listenPort;
    private final String targetHost;
    private final int targetPort;
    private final String clientId;
    private final String clientSecret;
    private final long reauthCooldownMs;
    private final int maxRetries;
    private final long retryIntervalMs;

    public Config() {
        this.listenPort = Integer.parseInt(getRequiredEnv("JAVA_PROXY_SERVER_PORT"));
        this.targetHost = getRequiredEnv("TARGET_SERVER_HOST");
        this.targetPort = Integer.parseInt(getRequiredEnv("TARGET_SERVER_PORT"));
        this.clientId = getRequiredEnv("JAVA_PROXY_ADMIN_ID");
        this.clientSecret = getRequiredEnv("JAVA_PROXY_ADMIN_SECRET");
        this.reauthCooldownMs = Long.parseLong(getRequiredEnv("JAVA_PROXY_REAUTH_COOLDOWN_MS"));
        this.maxRetries = Integer.parseInt(getRequiredEnv("JAVA_PROXY_RETRY_ATTEMPTS"));
        this.retryIntervalMs = Long.parseLong(getRequiredEnv("JAVA_PROXY_RETRY_INTERVAL_MS"));
    }

    private String getRequiredEnv(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("Required environment variable '" + name + "' is not set.");
        }
        return value;
    }

    public void logValues() {
        Logger.log(Logger.Level.INFO, "Configuration loaded successfully");
        Logger.log(Logger.Level.INFO, " - Listen Port: " + this.listenPort);
        Logger.log(Logger.Level.INFO, " - Target Host: " + this.targetHost);
        Logger.log(Logger.Level.INFO, " - Target Port: " + this.targetPort);
        Logger.log(Logger.Level.INFO, " - Client ID: " + this.clientId);
        Logger.log(Logger.Level.INFO, " - Client Secret: [REDACTED]");
        Logger.log(Logger.Level.INFO, " - Max Retries: " + this.maxRetries);
        Logger.log(Logger.Level.INFO, " - Retry Interval: " + (this.retryIntervalMs / 1000) + "s");
        Logger.log(Logger.Level.INFO, " - Re-auth Cooldown: " + (this.reauthCooldownMs / 1000) + "s");
    }

    public int getListenPort() {
        return listenPort;
    }

    public String getTargetHost() {
        return targetHost;
    }

    public int getTargetPort() {
        return targetPort;
    }

    public String getClientId() {
        return clientId;
    }

    public String getClientSecret() {
        return clientSecret;
    }

    public long getReauthCooldownMs() {
        return reauthCooldownMs;
    }

    public int getMaxRetries() {
        return maxRetries;
    }

    public long getRetryIntervalMs() {
        return retryIntervalMs;
    }
}