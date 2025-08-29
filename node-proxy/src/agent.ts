import { Agent } from 'https';

export const sharedHttpsAgent = new Agent({
  rejectUnauthorized: false,
  keepAlive: true,
});
