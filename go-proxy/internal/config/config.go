package config

import (
	"fmt"
	"os"
	"strconv"
	"time"

	// Local imports
	"go-proxy/internal/logger"
)

type Config struct {
	ListenPort    string
	TargetHost    string
	TargetPort    string
	ClientID      string
	ClientSecret  string
	Cooldown      time.Duration
	MaxRetries    int
	RetryInterval time.Duration
}

func New() (*Config, error) {
	cfg := &Config{}
	var err error

	if cfg.ListenPort, err = getRequiredEnv("GO_PROXY_SERVER_PORT"); err != nil {
		return nil, err
	}
	if cfg.TargetHost, err = getRequiredEnv("TARGET_SERVER_HOST"); err != nil {
		return nil, err
	}
	if cfg.TargetPort, err = getRequiredEnv("TARGET_SERVER_PORT"); err != nil {
		return nil, err
	}
	if cfg.ClientID, err = getRequiredEnv("GO_PROXY_ADMIN_ID"); err != nil {
		return nil, err
	}
	if cfg.ClientSecret, err = getRequiredEnv("GO_PROXY_ADMIN_SECRET"); err != nil {
		return nil, err
	}

	cooldownStr, err := getRequiredEnv("GO_PROXY_REAUTH_COOLDOWN_MS")
	if err != nil {
		return nil, err
	}
	cooldownMs, err := strconv.Atoi(cooldownStr)
	if err != nil {
		return nil, fmt.Errorf("invalid value for GO_PROXY_REAUTH_COOLDOWN_MS: %w", err)
	}
	cfg.Cooldown = time.Duration(cooldownMs) * time.Millisecond

	retriesStr, err := getRequiredEnv("GO_PROXY_RETRY_ATTEMPTS")
	if err != nil {
		return nil, err
	}
	if cfg.MaxRetries, err = strconv.Atoi(retriesStr); err != nil {
		return nil, fmt.Errorf("invalid value for GO_PROXY_RETRY_ATTEMPTS: %w", err)
	}

	intervalStr, err := getRequiredEnv("GO_PROXY_RETRY_INTERVAL_MS")
	if err != nil {
		return nil, err
	}
	intervalMs, err := strconv.Atoi(intervalStr)
	if err != nil {
		return nil, fmt.Errorf("invalid value for GO_PROXY_RETRY_INTERVAL_MS: %w", err)
	}
	cfg.RetryInterval = time.Duration(intervalMs) * time.Millisecond

	return cfg, nil
}

func (c *Config) GetCredentials() (clientID, clientSecret string) {
	return c.ClientID, c.ClientSecret
}

func getRequiredEnv(key string) (string, error) {
	value, ok := os.LookupEnv(key)
	if !ok || value == "" {
		return "", fmt.Errorf("required environment variable %q is not set or is empty", key)
	}
	return value, nil
}

func (c *Config) LogValues() {
	logger.Log(logger.INFO, "Configuration loaded successfully")
	logger.Log(logger.INFO, " - Listen Port: "+c.ListenPort)
	logger.Log(logger.INFO, " - Target Host: "+c.TargetHost)
	logger.Log(logger.INFO, " - Target Port: "+c.TargetPort)
	logger.Log(logger.INFO, " - Client ID: "+c.ClientID)
	logger.Log(logger.INFO, " - Client Secret: [REDACTED]")
	logger.Log(logger.INFO, " - Max Retries: "+strconv.Itoa(c.MaxRetries))
	logger.Log(logger.INFO, " - Retry Interval: "+c.RetryInterval.String())
	logger.Log(logger.INFO, " - Re-auth Cooldown: "+c.Cooldown.String())
}
