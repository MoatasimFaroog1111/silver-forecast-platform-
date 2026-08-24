import { ForecastApi } from './forecast_api/forecast_api_client.js';
import { forecastNavigation, activeRoute } from './navigation/forecast_navigation.js';
import { renderForecastOverview } from './overview/forecast_overview.js';
import { renderLiveForecasts } from './live_forecasts/live_forecasts.js';
import { renderWalkForwardBacktesting } from './walk_forward_backtesting/walk_forward_backtesting.js';
import { renderForecastModels } from './forecast_models/forecast_models.js';
import { renderForecastHistory } from './forecast_history/forecast_history.js';
import { renderHistoricalReports } from './historical_reports/historical_reports.js';
import { renderReportDownloads } from './historical_reports/report_downloads.js';
import { renderDataQuality } from './data_quality/data_quality.js';
import { renderPlatformSettings } from './platform_settings/platform_settings.js';

const renderers = {
  '#overview': renderForecastOverview,
  '#forecasts': renderLiveForecasts,
  '#backtesting': renderWalkForwardBacktesting,
  '#models': renderForecastModels,
  '#forecast-history': renderForecastHistory,
  '#historical-reports': renderHistoricalReports,
  '#reports': renderReportDownloads,
  '#data-quality': renderDataQuality,
  '#settings': renderPlatformSettings,
};

const navigationHtml = () => forecastNavigation.map(item => `<a href="${item.hash}" data-route="${item.hash}"><span>${item.icon}</span>${item.label}</a>`).join('');

const shell = document.querySelector('#portal');
shell.innerHTML = `<aside class="sidebar"><div class="logo"><span>Ag</span><div><b>Silver Forecast</b><small>USD / KG Intelligence</small></div></div><nav>${navigationHtml()}</nav><div class="sidebar-foot"><span class="online-dot"></span><div><b>Prediction Platform</b><small>Models loaded via API</small></div></div></aside><main><header class="topbar"><button class="menu-button" aria-label="القائمة">☰</button><div><span class="api-state" id="apiState">Checking API…</span></div><div class="top-actions"><a href="/docs" target="_blank">API Docs</a><span id="latestDate"></span></div></header><div id="page" class="page"></div></main>`;

const sidebar = document.querySelector('.sidebar');
document.querySelector('.menu-button').addEventListener('click', () => sidebar.classList.toggle('open'));

const showError = error => {
  document.querySelector('#page').innerHTML = `<section class="error-panel panel"><h2>تعذر تحميل الصفحة</h2><p>${error.message}</p><button onclick="location.reload()">إعادة المحاولة</button></section>`;
};

const updateNavigation = route => {
  document.querySelectorAll('[data-route]').forEach(link => link.classList.toggle('active', link.dataset.route === route));
  sidebar.classList.remove('open');
};

const renderRoute = async () => {
  const route = activeRoute();
  updateNavigation(route);
  const page = document.querySelector('#page');
  page.innerHTML = '<div class="loading">Loading verified data…</div>';
  try {
    page.innerHTML = await renderers[route](ForecastApi);
  } catch (error) {
    console.error(error);
    showError(error);
  }
};

const checkHealth = async () => {
  try {
    const health = await ForecastApi.health();
    const state = document.querySelector('#apiState');
    state.textContent = health.status === 'ok' ? 'API Healthy' : 'API Degraded';
    state.classList.add(health.status === 'ok' ? 'healthy' : 'degraded');
    document.querySelector('#latestDate').textContent = `Market: ${health.latest_market_date}`;
  } catch {
    document.querySelector('#apiState').textContent = 'API Offline';
  }
};

window.addEventListener('hashchange', renderRoute);
checkHealth();
renderRoute();
