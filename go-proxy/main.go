package main

import (
	"bytes"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

type authRequest struct {
	ClientID     string `json:"client_id"`
	ClientSecret string `json:"client_secret"`
}

type authResponse struct {
	MasterToken string `json:"master_token"`
}

var masterToken string
var tokenMutex = &sync.RWMutex{}
var lastReauthAttempt time.Time
var reauthMutex = &sync.Mutex{}

func logger(level string, message string, extras ...interface{}) {
	timestamp := time.Now().Format("2006-01-02 15:04:05.000")
	levelStr := fmt.Sprintf("%-7s", strings.ToUpper(level))
	logMessage := fmt.Sprintf("[%s] %s :: %s", timestamp, levelStr, message)
	if len(extras) > 0 {
		logMessage += " :: " + fmt.Sprint(extras...)
	}
	log.Println(logMessage)
}

func authenticate(targetHost, targetPort, clientID, clientSecret string) (string, error) {
	authURL := "https://" + targetHost + ":" + targetPort + "/api/v1/auth"
	requestBody := authRequest{ClientID: clientID, ClientSecret: clientSecret}
	requestBytes, err := json.Marshal(requestBody)
	if err != nil {
		return "", err
	}
	transport := &http.Transport{TLSClientConfig: &tls.Config{InsecureSkipVerify: true}}
	client := &http.Client{Transport: transport}
	response, err := client.Post(authURL, "application/json", bytes.NewBuffer(requestBytes))
	if err != nil {
		return "", err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		bodyBytes, _ := io.ReadAll(response.Body)
		return "", &url.Error{Op: "Post", URL: authURL, Err: &net.AddrError{Err: "authentication failed", Addr: string(bodyBytes)}}
	}
	var authResponse authResponse
	if err := json.NewDecoder(response.Body).Decode(&authResponse); err != nil {
		return "", err
	}
	return authResponse.MasterToken, nil
}

func main() {
	log.SetFlags(0)

	// Set environment variables
	listenPort := os.Getenv("GO_PROXY_SERVER_PORT")
	targetHost := os.Getenv("TARGET_SERVER_HOST")
	targetPort := os.Getenv("TARGET_SERVER_PORT")
	clientID := os.Getenv("GO_PROXY_ADMIN_ID")
	clientSecret := os.Getenv("GO_PROXY_ADMIN_SECRET")
	cooldownMsStr := os.Getenv("GO_PROXY_REAUTH_COOLDOWN_MS")
	retryAttemptsStr := os.Getenv("GO_PROXY_RETRY_ATTEMPTS")
	retryIntervalStr := os.Getenv("GO_PROXY_RETRY_INTERVAL_MS")
	cooldownMs, _ := strconv.Atoi(cooldownMsStr)
	reauthCooldown := time.Duration(cooldownMs) * time.Millisecond
	maxRetries, err := strconv.Atoi(retryAttemptsStr)
	if err != nil {
		maxRetries = 5
	}
	retryIntervalMs, err := strconv.Atoi(retryIntervalStr)
	if err != nil {
		retryIntervalMs = 2000
	}
	retryInterval := time.Duration(retryIntervalMs) * time.Millisecond

	// Start server
	var initialToken string
	for i := 0; i < maxRetries; i++ {
		logger("INFO", "Attempting to authenticate", fmt.Sprintf("(Attempt %d/%d)", i+1, maxRetries))
		token, err := authenticate(targetHost, targetPort, clientID, clientSecret)
		if err == nil {
			initialToken = token
			break
		}
		logger("ERROR", "Authentication failed", err)
		if i < maxRetries-1 {
			logger("INFO", fmt.Sprintf("Retrying in %v...", retryInterval))
			time.Sleep(retryInterval)
		}
	}
	if initialToken == "" {
		logger("ERROR", "Could not authenticate with target server after multiple retries. Exiting.")
		os.Exit(1)
	}
	masterToken = initialToken
	logger("SUCCESS", "Authenticated and retrieved initial token.")
	targetURL, err := url.Parse("https://" + targetHost + ":" + targetPort)
	if err != nil {
		logger("ERROR", "Failed to parse target URL", err)
		os.Exit(1)
	}
	proxy := httputil.NewSingleHostReverseProxy(targetURL)
	proxy.Director = func(request *http.Request) {
		clientIP, _, _ := net.SplitHostPort(request.RemoteAddr)
		requestLine := fmt.Sprintf("%s %s", request.Method, request.URL.RequestURI())
		logger("INFO", "Received request", fmt.Sprintf("Client IP: %s, Request: \"%s\"", clientIP, requestLine))
		request.URL.Scheme = targetURL.Scheme
		request.URL.Host = targetURL.Host
		request.Host = targetURL.Host
		tokenMutex.RLock()
		request.Header.Set("X-Proxy-Token", masterToken)
		tokenMutex.RUnlock()
		logger("INFO", "Forwarding request to target service", fmt.Sprintf("Host IP: %s, Scheme: %s", targetURL.Host, targetURL.Scheme))
	}
	proxy.Transport = &http.Transport{
		TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
	}
	proxy.ModifyResponse = func(r *http.Response) error {
		if r.StatusCode == http.StatusForbidden {
			logger("WARN", "Received 403 Forbidden from target. Triggering re-authentication.")
			go func() {
				reauthMutex.Lock()
				defer reauthMutex.Unlock()
				if time.Since(lastReauthAttempt) < reauthCooldown {
					logger("INFO", "Re-authentication cooldown active. Please wait.")
					return
				}
				lastReauthAttempt = time.Now()
				newToken, _ := authenticate(targetHost, targetPort, clientID, clientSecret)
				if newToken != "" {
					tokenMutex.Lock()
					masterToken = newToken
					tokenMutex.Unlock()
					logger("SUCCESS", "Successfully refreshed master token in background.")
				}
			}()
		}
		return nil
	}

	listenAddress := ":" + listenPort

	server := &http.Server{
		Addr:    listenAddress,
		Handler: proxy,
	}

	logger("SUCCESS", "Starting HTTPS reverse proxy", fmt.Sprintf("Port: %s", listenAddress))
	err = server.ListenAndServeTLS("cert.pem", "key.pem")
	if err != nil {
		logger("ERROR", "Failed to start server", err)
		os.Exit(1)
	}
}
