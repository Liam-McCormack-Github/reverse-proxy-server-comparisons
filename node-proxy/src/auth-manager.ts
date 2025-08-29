import https from 'https';
import { sharedHttpsAgent } from './agent';
import { Config } from './config';
import { logger, LogLevel } from './logger';

export class AuthManager {
  private masterToken: string = '';
  private isReauthenticating = false;
  private lastReauthAttempt = 0;

  constructor(private cfg: Config) {}

  public getToken(): string {
    return this.masterToken;
  }

  public async initialAuthenticate(): Promise<void> {
    for (let i = 0; i < this.cfg.maxRetries; i++) {
      try {
        logger(LogLevel.INFO, `Attempting to authenticate`, `(Attempt ${i + 1}/${this.cfg.maxRetries})`);
        this.masterToken = await this.performAuthRequest();
        logger(LogLevel.SUCCESS, 'Authenticated and retrieved initial token.');
        return;
      } catch (err: any) {
        logger(LogLevel.ERROR, 'Authentication failed!', err.message);
        if (i < this.cfg.maxRetries - 1) {
          logger(LogLevel.INFO, `Retrying in ${this.cfg.retryIntervalMs}ms...`);
          await new Promise(resolve => setTimeout(resolve, this.cfg.retryIntervalMs));
        } else {
          logger(LogLevel.ERROR, `Could not authenticate after multiple retries. Exiting.`);
          throw new Error('Could not authenticate with target server after multiple retries. Exiting.');
        }
      }
    }
  }

  public handleForbiddenStatus(): void {
    logger(LogLevel.WARN, 'Received 403 Forbidden from target. Triggering re-authentication.');
    if (this.isReauthenticating) return;

    const now = Date.now();
    if (now - this.lastReauthAttempt < this.cfg.reauthCooldownMs) {
      logger(LogLevel.INFO, 'Re-authentication cooldown active. Please wait.');
      return;
    }

    this.isReauthenticating = true;
    this.lastReauthAttempt = now;

    logger(LogLevel.INFO, 'Attempting to refresh token in background.');
    this.performAuthRequest()
      .then(newToken => {
        this.masterToken = newToken;
        logger(LogLevel.SUCCESS, 'Successfully refreshed master token in background.');
      })
      .catch(err => {
        logger(LogLevel.ERROR, 'Failed to refresh token', err.message);
      })
      .finally(() => {
        this.isReauthenticating = false;
      });
  }

  private performAuthRequest(): Promise<string> {
    const authUrl = `${this.cfg.targetHost}:${this.cfg.targetPort}/api/v1/auth`;
    logger(LogLevel.INFO, 'Posting to auth endpoint', `URL: ${authUrl}`);

    return new Promise((resolve, reject) => {
      const postData = JSON.stringify({
        client_id: this.cfg.clientId,
        client_secret: this.cfg.clientSecret,
      });

      const options = {
        hostname: this.cfg.targetHost,
        port: this.cfg.targetPort,
        path: '/api/v1/auth',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(postData),
        },
        agent: sharedHttpsAgent,
      };

      const req = https.request(options, res => {
        let data = '';
        res.on('data', chunk => (data += chunk));
        res.on('end', () => {
          if (res.statusCode !== 200) {
            const statusText = res.statusMessage || '';
            logger(LogLevel.WARN, `Authentication failed with non-OK status. Status: ${res.statusCode} ${statusText}`);
            return reject(new Error(`${options.method} "${authUrl}": address ${data}: auth failed`));
          }
          try {
            resolve(JSON.parse(data).master_token);
          } catch (e) {
            reject(new Error('Failed to parse auth response JSON.'));
          }
        });
      });
      req.on('error', e => reject(new Error(`Auth request failed: ${e.message}`)));
      req.write(postData);
      req.end();
    });
  }
}
