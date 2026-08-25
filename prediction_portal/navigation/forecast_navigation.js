export const forecastNavigation = [
  { hash: '#overview', label: 'نظرة عامة', icon: '◫' },
  { hash: '#forecasts', label: 'التوقعات', icon: '↗' },
  { hash: '#backtesting', label: 'Backtesting', icon: '⌁' },
  { hash: '#models', label: 'النماذج', icon: '◇' },
  { hash: '#forecast-history', label: 'سجل التوقعات', icon: '◷' },
  { hash: '#historical-reports', label: 'التقارير التاريخية', icon: '▤' },
  { hash: '#reports', label: 'التقارير', icon: '⇩' },
  { hash: '#data-quality', label: 'جودة البيانات', icon: '✓' },
  { hash: '#settings', label: 'الإعدادات', icon: '⚙' },
];

export const activeRoute = () => {
  const hash = window.location.hash || '#overview';
  return forecastNavigation.some(item => item.hash === hash) ? hash : '#overview';
};
