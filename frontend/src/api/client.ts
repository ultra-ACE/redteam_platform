import axios from 'axios';

function formatErrorDetail(value: unknown): string {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object') {
          const detail = item as { loc?: unknown; msg?: unknown };
          const location = Array.isArray(detail.loc)
            ? detail.loc.map(String).join('.')
            : '';
          const message = typeof detail.msg === 'string'
            ? detail.msg
            : JSON.stringify(item);
          return location ? `${location}: ${message}` : message;
        }
        return String(item);
      })
      .join('；');
  }
  if (value && typeof value === 'object') return JSON.stringify(value);
  return '请求失败';
}

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api/v1',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('local_token');
  const operator = localStorage.getItem('operator') ?? 'local';
  if (token) {
    config.headers['X-Local-Token'] = token;
  }
  config.headers['X-Operator'] = operator;
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = formatErrorDetail(
      error?.response?.data?.message ??
        error?.response?.data?.detail ??
        error.message,
    );
    return Promise.reject(new Error(message));
  },
);
