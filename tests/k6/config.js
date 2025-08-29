// tests/k6/config.js
export const SERVERS = {
  "go-proxy": "https://localhost:8080",
  "java-proxy": "https://localhost:8081",
  "node-proxy": "https://localhost:8082",
};

export const TARGET_SERVER = "https://localhost:9090";

export const COMMON_OPTIONS = {
  insecureSkipTLSVerify: true,
};
