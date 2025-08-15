package proxy

import (
	"crypto/tls"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"

	// Local imports
	"go-proxy/internal/auth"
	"go-proxy/internal/config"
	"go-proxy/internal/handlers"
	"go-proxy/internal/logger"
)

func New(cfg *config.Config, authManager *auth.Manager) *httputil.ReverseProxy {
	targetURL, _ := url.Parse("https://" + cfg.TargetHost + ":" + cfg.TargetPort)
	proxy := httputil.NewSingleHostReverseProxy(targetURL)

	proxy.Director = func(req *http.Request) {
		clientIP, _, _ := net.SplitHostPort(req.RemoteAddr)
		requestLine := fmt.Sprintf("%s %s", req.Method, req.URL.RequestURI())
		logger.Log(logger.INFO, "Received request", fmt.Sprintf("Client IP: %s, Request: \"%s\"", clientIP, requestLine))
		if handlers.HasCustomHandler(req.URL.Path) {
			req.Header.Del("Accept-Encoding")
		}

		req.URL.Scheme = targetURL.Scheme
		req.URL.Host = targetURL.Host
		req.Host = targetURL.Host
		req.Header.Set("X-Proxy-Token", authManager.GetToken())
		logger.Log(logger.INFO, "Forwarding request to target", "URI: "+req.URL.RequestURI())
	}

	proxy.ModifyResponse = func(res *http.Response) error {
		logger.Log(logger.INFO, "Received response from target", fmt.Sprintf("Status: %d %s", res.StatusCode, http.StatusText(res.StatusCode)))

		if res.StatusCode == http.StatusOK && handlers.HasCustomHandler(res.Request.URL.Path) {
			logger.Log(logger.INFO, "Intercepting response for custom handling", "Route: "+res.Request.URL.Path)
			return handlers.HandleCustomResponse(res)
		}

		if res.StatusCode == http.StatusForbidden {
			logger.Log(logger.WARN, "Received 403 Forbidden from target. Triggering re-authentication.")
			go authManager.RefreshTokenIfNeeded()
		}
		return nil
	}

	proxy.Transport = &http.Transport{
		TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
	}

	proxy.ErrorHandler = func(rw http.ResponseWriter, req *http.Request, err error) {
		if err != nil {
			if netErr, ok := err.(net.Error); ok && !netErr.Timeout() {
				logger.Log(logger.INFO, "Client connection closed prematurely during proxying", err.Error())
			} else if err == io.EOF {
				logger.Log(logger.INFO, "Client connection closed prematurely during proxying", "EOF")
			} else {
				logger.Log(logger.ERROR, "Proxying failed", err)
			}
		}
		rw.WriteHeader(http.StatusBadGateway)
	}

	return proxy
}
