const money = value => value == null ? '—' : `$${Number(value).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}`;
export const renderForecastHistory = async api => {
  const history = await api.forecastHistory(500);
  const rows = history.map(row => `<tr><td>${row.observation_date}</td><td>${row.horizon_sessions}D</td><td>${row.forecast_mode}</td><td>${money(row.current_price)}</td><td>${money(row.predicted_price)}</td><td>${money(row.actual_price)}</td><td>${row.realized_accuracy_pct == null ? 'Pending' : row.realized_accuracy_pct.toFixed(2)+'%'}</td><td>${row.model_name.replaceAll('_',' ')}</td></tr>`).join('');
  return `<section class="page-heading"><div><p class="eyebrow">FORECAST HISTORY</p><h1>سجل التوقعات</h1><p>كل Forecast يتم حفظه بهويته وإصداره، ثم تتم تسويته عندما تتوفر الجلسة المستقبلية الفعلية.</p></div><span class="status-badge">${history.length} Records</span></section>
  <section class="panel table-panel"><div class="table-wrap"><table><thead><tr><th>تاريخ التوقع</th><th>الأفق</th><th>Mode</th><th>السعر الحالي</th><th>المتوقع</th><th>الفعلي</th><th>Realized Accuracy</th><th>Model</th></tr></thead><tbody>${rows || '<tr><td colspan="8">لا توجد توقعات محفوظة بعد.</td></tr>'}</tbody></table></div></section>`;
};
