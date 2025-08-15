package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	// Local imports
	"target-server/internal/database"
	"target-server/internal/logger"
)

var (
	masterToken string
	tokenLock   sync.RWMutex
)

func rereadTokenPeriodically() {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for range ticker.C {
		newToken, err := os.ReadFile("master_token.txt")
		if err != nil {
			logger.Log(logger.ERROR, "master_token.txt not found during periodic reread.", err.Error())
			continue
		}

		cleanToken := strings.TrimSpace(string(newToken))
		if cleanToken == "" {
			logger.Log(logger.WARN, "Skipping token update because master_token.txt is empty.")
			continue
		}

		tokenLock.Lock()
		if cleanToken != masterToken {
			masterToken = cleanToken
			logger.Log(logger.INFO, "Master token has been updated from file.")
		}
		tokenLock.Unlock()
	}
}

func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		lrw := &loggingResponseWriter{ResponseWriter: w}
		start := time.Now()
		next.ServeHTTP(lrw, r)

		extras := fmt.Sprintf("Code: %d, Client IP: %s, Method: %s, Path: %s, Duration: %s",
			lrw.statusCode, r.RemoteAddr, r.Method, r.URL.Path, time.Since(start))

		if lrw.statusCode >= 400 {
			logger.Log(logger.ERROR, "Request failed", extras)
		} else {
			logger.Log(logger.INFO, "Request handled successfully", extras)
		}
	})
}

func authMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedToken := r.Header.Get("X-Proxy-Token")

		tokenLock.RLock()
		isValid := receivedToken != "" && receivedToken == masterToken
		tokenLock.RUnlock()

		if !isValid {
			msg := "Forbidden: Invalid or missing proxy token."
			logger.Log(logger.WARN, msg, fmt.Sprintf("IP: %s", r.RemoteAddr))
			http.Error(w, msg, http.StatusForbidden)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func authApiHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method Not Allowed", http.StatusMethodNotAllowed)
		return
	}

	var creds struct {
		ClientID     string `json:"client_id"`
		ClientSecret string `json:"client_secret"`
	}

	if err := json.NewDecoder(r.Body).Decode(&creds); err != nil {
		http.Error(w, "Bad Request: "+err.Error(), http.StatusBadRequest)
		return
	}

	db, err := database.New("users.db")
	if err != nil {
		http.Error(w, "Internal Server Error", http.StatusInternalServerError)
		return
	}
	defer db.Close()

	isValid, err := db.VerifyUser(creds.ClientID, creds.ClientSecret)
	if err != nil || !isValid {
		logger.Log(logger.WARN, "Unauthorized authentication attempt", fmt.Sprintf("client_id: %s", creds.ClientID))
		http.Error(w, "Unauthorized", http.StatusUnauthorized)
		return
	}

	logger.Log(logger.SUCCESS, "Authentication successful", fmt.Sprintf("client_id: %s", creds.ClientID))
	w.Header().Set("Content-Type", "application/json")

	tokenLock.RLock()
	resp := map[string]string{"master_token": masterToken}
	tokenLock.RUnlock()

	json.NewEncoder(w).Encode(resp)
}

func streamHandler(w http.ResponseWriter, r *http.Request) {
	logger.Log(logger.INFO, "GET /stream request received", fmt.Sprintf("Client IP: %s", r.RemoteAddr))

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.WriteHeader(http.StatusOK)

	var counter int
	for {
		message := fmt.Sprintf("data: message %d\n\n", counter)

		_, err := w.Write([]byte(message))
		if err != nil {
			logger.Log(logger.INFO, "Client disconnected from stream.", fmt.Sprintf("Client IP: %s", r.RemoteAddr))
			break
		}

		if f, ok := w.(http.Flusher); ok {
			f.Flush()
		}

		counter++
	}
}

func fileServerWithHTMLFallback(fs http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		path := filepath.Join("website", r.URL.Path)

		if _, err := os.Stat(path); os.IsNotExist(err) {
			htmlPath := path + ".html"
			if _, err := os.Stat(htmlPath); err == nil {
				r.URL.Path += ".html"
			}
		}
		fs.ServeHTTP(w, r)
	})
}

func imageApiHandler(w http.ResponseWriter, r *http.Request) {
	http.ServeFile(w, r, "website/img/test.png")
}

type loggingResponseWriter struct {
	http.ResponseWriter
	statusCode int
}

func (lrw *loggingResponseWriter) WriteHeader(code int) {
	lrw.statusCode = code
	lrw.ResponseWriter.WriteHeader(code)
}

func main() {
	logger.Init()

	tokenBytes, err := os.ReadFile("master_token.txt")
	if err != nil {
		logger.Log(logger.ERROR, "Could not read initial master token at startup. The server will not start.", err.Error())
		return
	}
	masterToken = strings.TrimSpace(string(tokenBytes))
	if masterToken == "" {
		logger.Log(logger.ERROR, "Master token file is empty on startup. The server will not start.")
		return
	}
	logger.Log(logger.INFO, "Initial master token loaded into memory.")

	go rereadTokenPeriodically()
	logger.Log(logger.INFO, "Started background thread for polling master_token.txt.")

	host := os.Getenv("TARGET_SERVER_HOST")
	port := os.Getenv("TARGET_SERVER_PORT")
	if port == "" || host == "" {
		logger.Log(logger.ERROR, "TARGET_SERVER_PORT and TARGET_SERVER_HOST environment variables must be set")
		return
	}
	addr := fmt.Sprintf("%s:%s", host, port)

	fs := http.FileServer(http.Dir("website"))
	fileHandler := fileServerWithHTMLFallback(fs)

	http.HandleFunc("/api/v1/auth", authApiHandler)
	http.Handle("/api/v1/image", authMiddleware(http.HandlerFunc(imageApiHandler)))
	http.Handle("/stream", authMiddleware(http.HandlerFunc(streamHandler)))
	http.Handle("/", authMiddleware(fileHandler))

	logger.Log(logger.INFO, fmt.Sprintf("Starting secure HTTPS server on https://%s", addr))
	logger.Log(logger.INFO, "Authentication endpoint active at /api/v1/auth")
	logger.Log(logger.INFO, "Image endpoint active at /api/v1/image")
	logger.Log(logger.INFO, "Streaming test endpoint active at /stream")

	loggedRouter := loggingMiddleware(http.DefaultServeMux)

	err = http.ListenAndServeTLS(addr, "cert.pem", "key.pem", loggedRouter)
	if err != nil {
		logger.Log(logger.ERROR, "Server failed to start", err.Error())
	}
}
