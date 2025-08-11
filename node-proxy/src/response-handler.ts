import { IncomingMessage, ServerResponse } from 'http';
import { logger, LogLevel } from './logger';

type ResponseHandler = (proxyRes: IncomingMessage, req: IncomingMessage, res: ServerResponse) => void;

export const customHandlers: { [key: string]: ResponseHandler } = {
  '/wheredidicomefrom': handleWheredidicomefrom,
};

export function handleCustomResponse(proxyRes: IncomingMessage, req: IncomingMessage, res: ServerResponse) {
  const handler = customHandlers[req.url || ''];
  if (handler) {
    handler(proxyRes, req, res);
  }
}

function handleWheredidicomefrom(proxyRes: IncomingMessage, req: IncomingMessage, res: ServerResponse) {
  const body: Buffer[] = [];
  proxyRes.on('data', chunk => {
    body.push(chunk);
  });
  proxyRes.on('end', () => {
    const originalBody = Buffer.concat(body).toString();
    const injectedHtml = '<p style="color: blue; font-weight: bold;">Injected by the Node.js Proxy!</p>';
    const modifiedBody = originalBody.replace('</body>', `${injectedHtml}</body>`);

    res.writeHead(200, {
      'Content-Type': 'text/html',
      'Content-Length': Buffer.byteLength(modifiedBody),
    });
    res.end(modifiedBody);
    logger(LogLevel.INFO, 'Successfully injected custom HTML into response');
  });
}
