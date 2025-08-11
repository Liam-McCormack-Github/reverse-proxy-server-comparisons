import httpProxy from 'http-proxy';
import { Agent } from 'https';
import { IncomingMessage, ServerResponse } from 'http';
import { logger, LogLevel } from './logger';
import { AuthManager } from './auth-manager';
import config from './config';
import { customHandlers, handleCustomResponse } from './response-handler';

const proxy = httpProxy.createProxyServer();
const targetUrl = `https://${config.targetHost}:${config.targetPort}`;
const customHttpsAgent = new Agent({
  rejectUnauthorized: false,
  keepAlive: false,
});

export const createRequestHandler = (authManager: AuthManager) => {
  proxy.on('proxyRes', (proxyRes, req, res) => {
    logger(LogLevel.INFO, 'Received response from target', `Status: ${proxyRes.statusCode} ${proxyRes.statusMessage}`);

    if (customHandlers[req.url || '']) {
      logger(LogLevel.INFO, 'Intercepting response for custom handling', `Route: ${req.url}`);
      handleCustomResponse(proxyRes, req, res);
      return;
    }
    if (proxyRes.statusCode === 403) {
      authManager.handleForbiddenStatus();
    }
  });

  proxy.on('error', (err, req, res) => {
    const nodeError = err as NodeJS.ErrnoException;
    if (['ECONNRESET', 'EPIPE', 'ETIMEDOUT'].includes(nodeError.code!)) {
      logger(LogLevel.INFO, 'Client connection closed prematurely during proxying', nodeError.code);
    } else {
      logger(LogLevel.ERROR, 'Proxy failed', nodeError.message);
    }
    if (res instanceof ServerResponse && !res.headersSent) {
      res.writeHead(502, { 'Content-Type': 'text/plain' }).end('Proxy Error');
    }
  });

  proxy.on('proxyReq', (proxyReq, req) => {
    if (customHandlers[req.url || '']) {
      proxyReq.removeHeader('Accept-Encoding');
    }
    req.socket.on('close', () => proxyReq.destroy());
  });

  return (req: IncomingMessage, res: ServerResponse) => {
    logger(LogLevel.INFO, `Received request`, `Client IP: ${req.socket.remoteAddress}, Request: "${req.method} ${req.url}"`);
    req.headers['x-proxy-token'] = authManager.getToken();

    const needsManualResponse = !!customHandlers[req.url || ''];
    logger(LogLevel.INFO, 'Forwarding request to target', `URI: ${req.url}`);

    proxy.web(req, res, {
      target: targetUrl,
      secure: false,
      changeOrigin: true,
      agent: customHttpsAgent,
      selfHandleResponse: needsManualResponse,
    });
  };
};
