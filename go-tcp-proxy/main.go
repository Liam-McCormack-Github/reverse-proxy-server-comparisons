package main

import (
	"fmt"
	"io"
	"log"
	"net"
	"os"
)

// https://pkg.go.dev/fmt
// https://pkg.go.dev/io
// https://pkg.go.dev/log
// https://pkg.go.dev/net
// https://pkg.go.dev/os

func main() {
	listenPort := os.Getenv("PROXY_SERVER_GO_PORT")
	if listenPort == "" {
		log.Fatal("PROXY_SERVER_GO_PORT environment variable not set")
	}

	targetHost := os.Getenv("TARGET_SERVER_HOST")
	if targetHost == "" {
		log.Fatal("TARGET_SERVER_HOST environment variable not set")
	}

	targetPort := os.Getenv("TARGET_SERVER_PORT")
	if targetPort == "" {
		log.Fatal("TARGET_SERVER_PORT environment variable not set")
	}

	listenAddress := fmt.Sprintf(":%s", listenPort)
	targetAddress := fmt.Sprintf("%s:%s", targetHost, targetPort)

	listener, err := net.Listen("tcp", listenAddress)
	if err != nil {
		log.Fatalf("Failed to start listener on %s: %v", listenAddress, err)
	}

	defer listener.Close()

	log.Printf("TCP proxy listening on %s, forwarding to %s", listenAddress, targetAddress)

	for {
		clientConnection, err := listener.Accept()
		if err != nil {
			log.Printf("Failed to accept new connection: %v", err)
			continue
		}
		go handleConnection(clientConnection, targetAddress)
	}
}

func handleConnection(clientConnection net.Conn, targetAddress string) {
	defer clientConnection.Close()

	targetConnection, err := net.Dial("tcp", targetAddress)
	if err != nil {
		log.Printf("Failed to connect to target %s: %v", targetAddress, err)
		return
	}
	
	defer targetConnection.Close()

	log.Printf("New connection from %s, proxying to %s", clientConnection.RemoteAddr(), targetAddress)

	// Bidirectional transfer using goroutines to copy data in both directions.
	go copyData(clientConnection, targetConnection)
	copyData(targetConnection, clientConnection)
	
	log.Printf("Connection closed for %s", clientConnection.RemoteAddr())
}

func copyData(dst io.Writer, src io.Reader) {
	if _, err := io.Copy(dst, src); err != nil {
		log.Printf("Error copying data: %v", err)
	}
}