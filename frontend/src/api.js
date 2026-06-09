export const API_URL = import.meta.env.VITE_API_URL || '';

export function assetUrl(url) {
  if (!url || typeof url !== 'string') return '';
  if (/^(https?:|data:|blob:)/i.test(url)) return url;
  if (url.startsWith('/') && API_URL) return `${API_URL}${url}`;
  return url;
}
