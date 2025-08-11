export interface Config {
  listenPort: number;
  targetHost: string;
  targetPort: string;
  clientId: string;
  clientSecret: string;
  reauthCooldownMs: number;
  maxRetries: number;
  retryIntervalMs: number;
}

function getRequiredEnv(key: string): string {
  const value = process.env[key];
  if (!value) {
    throw new Error(`FATAL: Environment variable ${key} must be set.`);
  }
  return value;
}

const config: Config = Object.freeze({
  listenPort: parseInt(getRequiredEnv('NODE_PROXY_SERVER_PORT'), 10),
  targetHost: getRequiredEnv('TARGET_SERVER_HOST'),
  targetPort: getRequiredEnv('TARGET_SERVER_PORT'),
  clientId: getRequiredEnv('NODE_PROXY_ADMIN_ID'),
  clientSecret: getRequiredEnv('NODE_PROXY_ADMIN_SECRET'),
  reauthCooldownMs: parseInt(getRequiredEnv('NODE_PROXY_REAUTH_COOLDOWN_MS'), 10),
  maxRetries: parseInt(getRequiredEnv('NODE_PROXY_RETRY_ATTEMPTS'), 10),
  retryIntervalMs: parseInt(getRequiredEnv('NODE_PROXY_RETRY_INTERVAL_MS'), 10),
});

export default config;
