const DEPLOYED_API_URL = 'https://ai-ecotourism-backend.onrender.com';
const isLocalHost = /^(localhost|127\.0\.0\.1)$/i.test(window.location.hostname);

export const API_URL = (import.meta.env.VITE_API_URL || (isLocalHost ? '' : DEPLOYED_API_URL)).replace(/\/$/, '');
export const PUBLIC_APP_URL = (
  import.meta.env.VITE_PUBLIC_APP_URL || 'https://ai-ecotourism-assistant.vercel.app'
).replace(/\/$/, '');

export function assetUrl(url) {
  if (!url || typeof url !== 'string') return '';
  if (/^(https?:|data:|blob:)/i.test(url)) return url;
  if (url.startsWith('/') && API_URL) return `${API_URL}${url}`;
  return url;
}
