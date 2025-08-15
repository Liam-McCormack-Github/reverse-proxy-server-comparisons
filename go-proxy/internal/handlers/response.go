package handlers

import (
	"io"
	"net/http"
	"strconv"
	"strings"

	// Local imports
	"go-proxy/internal/logger"
)

func HasCustomHandler(path string) bool {
	switch path {
	case "/wheredidicomefrom":
		return true
	default:
		return false
	}
}

func HandleCustomResponse(res *http.Response) error {
	switch res.Request.URL.Path {
	case "/wheredidicomefrom":
		return handleWheredidicomefrom(res)
	default:
		return nil
	}
}

func handleWheredidicomefrom(res *http.Response) error {
	originalBody, err := io.ReadAll(res.Body)
	if err != nil {
		return err
	}
	res.Body.Close()
	injectedHTML := `<p style="color: green; font-weight: bold;">Injected by the Go Proxy!</p>`
	modifiedBody := strings.Replace(string(originalBody), "</body>", injectedHTML+"</body>", 1)
	res.Body = io.NopCloser(strings.NewReader(modifiedBody))
	res.Header.Set("Content-Length", strconv.Itoa(len(modifiedBody)))
	res.Header.Del("Content-Encoding")
	logger.Log(logger.INFO, "Successfully injected custom HTML into response")
	return nil
}
