// tests/k6/config.js
export const SERVERS = {
  go: "https://localhost:8080",
  java: "https://localhost:8081",
  node: "https://localhost:8082",
};

export const TARGET_SERVER = "https://localhost:9090";

export const COMMON_OPTIONS = {
  insecureSkipTLSVerify: true,
};
