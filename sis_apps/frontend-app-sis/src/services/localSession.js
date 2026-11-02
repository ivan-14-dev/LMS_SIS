import axios from 'axios';
import { getConfig } from '@edx/frontend-platform';

const client = axios.create({ withCredentials: true });

export const usesLocalSession = () => getConfig().SIS_AUTH_MODE === 'local';
export const isRecoveryPage = () => /^\/(forgot-password|reset-password)(\/|$)/.test(window.location.pathname);

client.interceptors.request.use(async (request) => {
  if (!['get', 'head', 'options'].includes((request.method || 'get').toLowerCase())) {
    const { origin } = new URL(request.url, window.location.origin);
    const response = await axios.get(`${origin}/csrf/api/v1/token`, { withCredentials: true });
    request.headers['X-CSRFToken'] = response.data.csrfToken;
  }
  return request;
});

export const localHttpClient = client;
