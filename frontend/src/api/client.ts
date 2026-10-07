import axios from 'axios';

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
    const message = error?.response?.data?.message ?? error.message ?? '请求失败';
    return Promise.reject(new Error(message));
  },
);
