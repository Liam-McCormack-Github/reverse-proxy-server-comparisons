export enum LogLevel {
  INFO = 'INFO',
  SUCCESS = 'SUCCESS',
  ERROR = 'ERROR',
  WARN = 'WARN',
}

export const logger = (level: LogLevel, message: string, ...extras: any[]) => {
  const timestamp = new Date().toISOString().replace('T', ' ').substring(0, 23);
  const extraStr = extras.length > 0 ? ` :: ${extras.join(' ')}` : '';
  console.log(`[${timestamp}] ${level.padEnd(7)} :: ${message}${extraStr}`);
};
