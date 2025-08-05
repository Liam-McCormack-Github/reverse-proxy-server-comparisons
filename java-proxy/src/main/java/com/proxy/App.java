package com.proxy;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.undertow.Undertow;
import io.undertow.server.HttpHandler;

import javax.net.ssl.KeyManagerFactory;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.security.KeyStore;
import java.time.Instant;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.locks.ReentrantLock;
import java.util.concurrent.locks.ReentrantReadWriteLock;

public class App {
    static final AtomicReference<String> masterToken = new AtomicReference<>();
    static final ReentrantReadWriteLock tokenLock = new ReentrantReadWriteLock();
    static final ReentrantLock reauthMutex = new ReentrantLock();
    static volatile Instant lastReauthAttempt = Instant.MIN;
    private static final ObjectMapper objectMapper = new ObjectMapper();

    static final int BUFFER_POOL_SIZE = 2048;
    static final int BUFFER_SIZE_BYTES = 32768; // 32 KB to match Go's implementation
    static final BlockingQueue<byte[]> bufferPool = new ArrayBlockingQueue<>(BUFFER_POOL_SIZE);


    public static void main(String[] args) throws Exception {
        String listenPortStr = System.getenv("JAVA_PROXY_SERVER_PORT");
        String targetHost = System.getenv("TARGET_SERVER_HOST");
        String targetPortStr = System.getenv("TARGET_SERVER_PORT");
        String clientId = System.getenv("JAVA_PROXY_ADMIN_ID");
        String clientSecret = System.getenv("JAVA_PROXY_ADMIN_SECRET");
        long reauthCooldownMs = Long.parseLong(System.getenv("JAVA_PROXY_REAUTH_COOLDOWN_MS"));
        int maxRetries = Integer.parseInt(System.getenv("JAVA_PROXY_RETRY_ATTEMPTS"));
        long retryIntervalMs = Long.parseLong(System.getenv("JAVA_PROXY_RETRY_INTERVAL_MS"));

        for (int i = 0; i < BUFFER_POOL_SIZE; i++) {
            bufferPool.offer(new byte[BUFFER_SIZE_BYTES]);
        }
        Logger.log("INFO", "Buffer pool populated", String.format("Size: %d buffers * %d KB", BUFFER_POOL_SIZE, BUFFER_SIZE_BYTES / 1024));


        boolean authenticated = false;
        for (int i = 0; i < maxRetries; i++) {
            Logger.log("INFO", "Attempting to authenticate", String.format("(Attempt %d/%d)", i + 1, maxRetries));
            try {
                String token = authenticate(targetHost, targetPortStr, clientId, clientSecret);
                masterToken.set(token);
                authenticated = true;
                Logger.log("SUCCESS", "Authenticated and retrieved initial token.");
                break;
            } catch (Exception e) {
                Logger.log("ERROR", "Authentication failed", e.getMessage());
                if (i < maxRetries - 1) {
                    try {
                        Thread.sleep(retryIntervalMs);
                    } catch (InterruptedException interruptedException) {
                        Thread.currentThread().interrupt();
                    }
                }
            }
        }

        if (!authenticated) {
            Logger.log("ERROR", "Could not authenticate with target server after multiple retries. Exiting.");
            System.exit(1);
        }

        int listenPort = Integer.parseInt(listenPortStr);
        final URI targetUri = new URI("https://" + targetHost + ":" + targetPortStr);
        final ExecutorService virtualThreadExecutor = Executors.newVirtualThreadPerTaskExecutor();
        final HttpClient client = createTrustingHttpClient();
        final HttpHandler proxyHandler = new ProxyHandler(targetUri, client, virtualThreadExecutor, reauthCooldownMs, clientId, clientSecret, targetHost, targetPortStr, bufferPool);

        KeyStore keyStore = KeyStore.getInstance("PKCS12");
        try (InputStream keyStoreStream = new FileInputStream("keystore.p12")) {
            keyStore.load(keyStoreStream, "password".toCharArray());
        }

        KeyManagerFactory keyManagerFactory = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());
        keyManagerFactory.init(keyStore, "password".toCharArray());

        SSLContext sslContext = SSLContext.getInstance("TLS");
        sslContext.init(keyManagerFactory.getKeyManagers(), null, null);

        Undertow server = Undertow.builder()
                .addHttpsListener(listenPort, "0.0.0.0", sslContext)
                .setHandler(proxyHandler)
                .build();

        Logger.log("SUCCESS", "Starting HTTPS reverse proxy", "Port: " + listenPort);
        server.start();
    }

    static String authenticate(String targetHost, String targetPort, String clientId, String clientSecret) throws Exception {
        String authUrl = "https://" + targetHost + ":" + targetPort + "/api/v1/auth";
        AuthRequest authRequest = new AuthRequest(clientId, clientSecret);
        String requestBody = objectMapper.writeValueAsString(authRequest);

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(authUrl))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(requestBody))
                .build();

        HttpClient authClient = createTrustingHttpClient();
        HttpResponse<String> response = authClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new IOException("Authentication failed with status code: " + response.statusCode() + " " + response.body());
        }

        AuthResponse authResponse = objectMapper.readValue(response.body(), AuthResponse.class);
        return authResponse.master_token();
    }

    private static HttpClient createTrustingHttpClient() {
        TrustManager[] trustAllCerts = new TrustManager[]{
            new X509TrustManager() {
                public java.security.cert.X509Certificate[] getAcceptedIssuers() { return null; }
                public void checkClientTrusted(java.security.cert.X509Certificate[] certs, String authType) { }
                public void checkServerTrusted(java.security.cert.X509Certificate[] certs, String authType) { }
            }
        };

        try {
            SSLContext sslContext = SSLContext.getInstance("TLS");
            sslContext.init(null, trustAllCerts, new java.security.SecureRandom());

            return HttpClient.newBuilder()
                    .sslContext(sslContext)
                    .build();
        } catch (Exception e) {
            throw new RuntimeException("Failed to create trusting HTTP client", e);
        }
    }
}