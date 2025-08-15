package auth

import (
	"bytes"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"sync"
	"time"

	// Local imports
	"go-proxy/internal/config"
	"go-proxy/internal/logger"
)

type authRequest struct {
	ClientID     string `json:"client_id"`
	ClientSecret string `json:"client_secret"`
}

type authResponse struct {
	MasterToken string `json:"master_token"`
}

type Manager struct {
	config            *config.Config
	token             string
	lastReauthAttempt time.Time
	tokenMutex        sync.RWMutex
	reauthMutex       sync.Mutex
}

func NewManager(cfg *config.Config) *Manager {
	return &Manager{
		config: cfg,
	}
}

func (m *Manager) Authenticate() (string, error) {
	token, err := m.performAuthentication()
	if err != nil {
		return "", err
	}
	m.tokenMutex.Lock()
	m.token = token
	m.tokenMutex.Unlock()
	return token, nil
}

func (m *Manager) performAuthentication() (string, error) {
	authURL := "https://" + m.config.TargetHost + ":" + m.config.TargetPort + "/api/v1/auth"
	logger.Log(logger.INFO, "Posting to auth endpoint", "URL: "+authURL)

	requestBody := authRequest{
		ClientID:     m.config.ClientID,
		ClientSecret: m.config.ClientSecret,
	}

	requestBytes, err := json.Marshal(requestBody)
	if err != nil {
		return "", fmt.Errorf("failed to marshal auth request: %w", err)
	}

	transport := &http.Transport{TLSClientConfig: &tls.Config{InsecureSkipVerify: true}}
	client := &http.Client{Transport: transport}
	response, err := client.Post(authURL, "application/json", bytes.NewBuffer(requestBytes))
	if err != nil {
		return "", err
	}
	defer response.Body.Close()

	if response.StatusCode != http.StatusOK {
		logger.Log(logger.WARN, "Authentication failed with non-OK status.", fmt.Sprintf("Status: %d %s", response.StatusCode, http.StatusText(response.StatusCode)))
		bodyBytes, _ := io.ReadAll(response.Body)
		return "", &url.Error{Op: response.Request.Method, URL: authURL, Err: &net.AddrError{Err: "auth failed", Addr: string(bodyBytes)}}
	}

	var respData authResponse
	if err := json.NewDecoder(response.Body).Decode(&respData); err != nil {
		return "", fmt.Errorf("failed to decode auth response: %w", err)
	}
	return respData.MasterToken, nil
}

func (m *Manager) GetToken() string {
	m.tokenMutex.RLock()
	defer m.tokenMutex.RUnlock()
	return m.token
}

func (m *Manager) RefreshTokenIfNeeded() {
	m.reauthMutex.Lock()
	defer m.reauthMutex.Unlock()

	if time.Since(m.lastReauthAttempt) < m.config.Cooldown {
		logger.Log(logger.INFO, "Re-authentication cooldown active. Please wait.")
		return
	}
	m.lastReauthAttempt = time.Now()

	logger.Log(logger.INFO, "Attempting to refresh token in background.")
	newToken, err := m.performAuthentication()
	if err != nil {
		logger.Log(logger.ERROR, "Failed to refresh token", err)
		return
	}

	m.tokenMutex.Lock()
	m.token = newToken
	m.tokenMutex.Unlock()
	logger.Log(logger.SUCCESS, "Successfully refreshed master token.")
}
