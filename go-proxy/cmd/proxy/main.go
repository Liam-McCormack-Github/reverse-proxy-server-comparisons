package main

import (
	"fmt"
	"net/http"
	"os"
	"time"

	// Local imports
	"go-proxy/internal/auth"
	"go-proxy/internal/config"
	"go-proxy/internal/logger"
	"go-proxy/internal/proxy"
)

func main() {
	logger.Init()

	cfg, err := config.New()
	if err != nil {
		logger.Log(logger.ERROR, "Configuration error", err)
		os.Exit(1)
	}
	cfg.LogValues()

	authManager := auth.NewManager(cfg)

	var initialToken string
	for i := 0; i < cfg.MaxRetries; i++ {
		logger.Log(logger.INFO, "Attempting to authenticate", fmt.Sprintf("(Attempt %d/%d)", i+1, cfg.MaxRetries))
		token, err := authManager.Authenticate()
		if err == nil {
			initialToken = token
			break
		}
		logger.Log(logger.ERROR, "Authentication failed!", err)
		if i < cfg.MaxRetries-1 {
			logger.Log(logger.INFO, fmt.Sprintf("Retrying in %dms...", cfg.RetryInterval.Milliseconds()))
			time.Sleep(cfg.RetryInterval)
		}
	}
	if initialToken == "" {
		logger.Log(logger.ERROR, "Could not authenticate after multiple retries. Exiting.")
		os.Exit(1)
	}
	logger.Log(logger.SUCCESS, "Authenticated and retrieved initial token.")

	proxyHandler := proxy.New(cfg, authManager)

	listenAddress := ":" + cfg.ListenPort
	server := &http.Server{
		Addr:    listenAddress,
		Handler: proxyHandler,
	}

	logger.Log(logger.SUCCESS, "Starting HTTPS reverse proxy", fmt.Sprintf("Listening on %s", cfg.ListenPort))
	if err := server.ListenAndServeTLS("cert.pem", "key.pem"); err != nil {
		logger.Log(logger.ERROR, "Failed to start server", err)
		os.Exit(1)
	}
}
