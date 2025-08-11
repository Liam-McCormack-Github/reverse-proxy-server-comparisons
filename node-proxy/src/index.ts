import https from 'https';
import fs from 'fs';
import config from './config';
import { logger, LogLevel } from './logger';
import { AuthManager } from './auth-manager';
import { createRequestHandler } from './proxy-handler';

const startServer = async () => {
  logger(LogLevel.INFO, 'Configuration loaded successfully');
  logger(LogLevel.INFO, ` - Listen Port: ${config.listenPort}`);
  logger(LogLevel.INFO, ` - Target Host: ${config.targetHost}`);
  logger(LogLevel.INFO, ` - Target Port: ${config.targetPort}`);
  logger(LogLevel.INFO, ` - Client ID: ${config.clientId}`);
  logger(LogLevel.INFO, ` - Client Secret: [REDACTED]`);
  logger(LogLevel.INFO, ` - Max Retries: ${config.maxRetries}`);
  logger(LogLevel.INFO, ` - Retry Interval: ${config.retryIntervalMs}ms`);
  logger(LogLevel.INFO, ` - Re-auth Cooldown: ${config.reauthCooldownMs}ms`);

  const authManager = new AuthManager(config);
  try {
    await authManager.initialAuthenticate();
  } catch (err: any) {
    logger(LogLevel.ERROR, err.message);
    process.exit(1);
  }

  const requestHandler = createRequestHandler(authManager);

  const options = {
    key: fs.readFileSync('key.pem'),
    cert: fs.readFileSync('cert.pem'),
  };

  const server = https.createServer(options, requestHandler);

  server.on('error', (err: any) => {
    logger(LogLevel.ERROR, 'Failed to start server', err);
    process.exit(1);
  });

  server.listen(config.listenPort, () => {
    logger(LogLevel.SUCCESS, `Starting HTTPS reverse proxy`, `Listening on  ${config.listenPort}`);
  });
};

startServer();
