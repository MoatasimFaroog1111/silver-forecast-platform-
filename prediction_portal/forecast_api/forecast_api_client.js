const jsonRequest = async (path, options = {}) => {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${detail}`);
  }
  const type = response.headers.get('content-type') || '';
  return type.includes('application/json') ? response.json() : response.text();
};

export const ForecastApi = {
  health: () => jsonRequest('/health'),
  dashboard: (mode = 'challenger') => jsonRequest(`/api/forecast/dashboard?mode=${mode}`),
  latestForecasts: (mode = 'challenger') => jsonRequest(`/api/forecast/latest?mode=${mode}`),
  marketHistory: (limit = 300) => jsonRequest(`/api/market/history?limit=${limit}`),
  models: () => jsonRequest('/api/models'),
  backtesting: (horizon = '') => jsonRequest(`/api/backtesting${horizon ? `?horizon=${horizon}` : ''}`),
  backtestingFolds: (horizon = '') => jsonRequest(`/api/backtesting/folds?limit=500${horizon ? `&horizon=${horizon}` : ''}`),
  forecastHistory: (limit = 300) => jsonRequest(`/api/forecast-history?limit=${limit}`),
  annualReports: () => jsonRequest('/api/reports/historical/annual'),
  reports: () => jsonRequest('/api/reports'),
  quality: () => jsonRequest('/api/data-quality'),
  settings: () => jsonRequest('/api/platform/settings'),
  registerObservation: (payload) => jsonRequest('/api/market/observations', { method: 'POST', body: JSON.stringify(payload) }),
};
