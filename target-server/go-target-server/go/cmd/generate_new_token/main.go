package main

import (
	"crypto/rand"
	"encoding/base64"
	"os"

	// Local imports
	"target-server/internal/logger"
)

func main() {
	logger.Init()

	tokenBytes := make([]byte, 24)
	if _, err := rand.Read(tokenBytes); err != nil {
		logger.Log(logger.ERROR, "Failed to generate random bytes for token", err.Error())
		return
	}
	token := base64.URLEncoding.EncodeToString(tokenBytes)

	if err := os.WriteFile("master_token.txt", []byte(token), 0644); err != nil {
		logger.Log(logger.ERROR, "Failed to write token to master_token.txt", err.Error())
		return
	}

	logger.Log(logger.SUCCESS, "New random token generated successfully!")
}
