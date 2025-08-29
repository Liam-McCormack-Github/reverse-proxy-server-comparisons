package com.proxy;

import io.undertow.Undertow;
import io.undertow.server.HttpHandler;

import javax.net.ssl.KeyManagerFactory;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;
import java.io.FileInputStream;
import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.security.KeyStore;
import java.security.cert.X509Certificate;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class App {
    static final int BUFFER_POOL_SIZE = 2048;
    static final int BUFFER_SIZE_BYTES = 32768; // 32 KB
    static final BlockingQueue<byte[]> bufferPool = new ArrayBlockingQueue<>(BUFFER_POOL_SIZE);

    public static void main(String[] args) {
        try {
            Config config = new Config();
            config.logValues();

            for (int i = 0; i < BUFFER_POOL_SIZE; i++) {
                bufferPool.offer(new byte[BUFFER_SIZE_BYTES]);
            }
            Logger.log(Logger.Level.INFO, "Buffer pool populated", String.format("Size: %d buffers * %d KB", BUFFER_POOL_SIZE, BUFFER_SIZE_BYTES / 1024));


            final ExecutorService virtualThreadExecutor = Executors.newVirtualThreadPerTaskExecutor();
            final HttpClient client = createTrustingHttpClient();
            final AuthManager authManager = new AuthManager(config, client);

            authManager.performInitialAuthentication();

            final URI targetUri = new URI("https://" + config.getTargetHost() + ":" + config.getTargetPort());
            final HttpHandler proxyHandler = new ProxyHandler(targetUri, client, virtualThreadExecutor, authManager, bufferPool);

            SSLContext sslContext = createSslContext("keystore.p12", "password");
            Undertow server = Undertow.builder()
                    .addHttpsListener(config.getListenPort(), "0.0.0.0", sslContext)
                    .setHandler(proxyHandler)
                    .build();

            Logger.log(Logger.Level.SUCCESS, "Starting HTTPS reverse proxy", "Listening on " + config.getListenPort());
            server.start();

        } catch (Exception e) {
            Logger.log(Logger.Level.ERROR, "Failed to start server", e);
            System.exit(1);
        }
    }

    private static SSLContext createSslContext(String keyStorePath, String keyStorePassword) throws Exception {
        KeyStore keyStore = KeyStore.getInstance("PKCS12");
        try (InputStream keyStoreStream = new FileInputStream(keyStorePath)) {
            keyStore.load(keyStoreStream, keyStorePassword.toCharArray());
        }

        KeyManagerFactory keyManagerFactory = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());
        keyManagerFactory.init(keyStore, keyStorePassword.toCharArray());

        SSLContext sslContext = SSLContext.getInstance("TLSv1.2");
        sslContext.init(keyManagerFactory.getKeyManagers(), null, null);
        return sslContext;
    }

    private static HttpClient createTrustingHttpClient() {
        TrustManager[] trustAllCerts = new TrustManager[]{
                new X509TrustManager() {
                    public X509Certificate[] getAcceptedIssuers() {
                        return null;
                    }

                    public void checkClientTrusted(X509Certificate[] certs, String authType) {
                    }

                    public void checkServerTrusted(X509Certificate[] certs, String authType) {
                    }
                }
        };

        try {
            SSLContext sslContext = SSLContext.getInstance("TLS");
            sslContext.init(null, trustAllCerts, new java.security.SecureRandom());

            return HttpClient.newBuilder()
                    .executor(Executors.newVirtualThreadPerTaskExecutor())
                    .sslContext(sslContext)
                    .build();
        } catch (Exception e) {
            throw new RuntimeException("Failed to create trusting HTTP client", e);
        }
    }
}
