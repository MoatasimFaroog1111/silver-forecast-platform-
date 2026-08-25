const money = value => Number(value).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
export const renderHistoricalReports = async api => {
  const [annual, history] = await Promise.all([api.annualReports(), api.marketHistory(400)]);
  const rows = annual.slice().reverse().map(item => `<tr><td>${item.year}</td><td>$${money(item.start_price)}</td><td>$${money(item.end_price)}</td><td class="${item.change_pct>=0?'positive':'negative'}">${item.change_pct>=0?'+':''}${item.change_pct.toFixed(2)}%</td><td>$${money(item.high)}</td><td>$${money(item.low)}</td><td>${item.observations}</td></tr>`).join('');
  const closes = history.map(item => item.close);
  const min = Math.min(...closes), max = Math.max(...closes);
  const points = history.map((item,index) => {
    const x = index/(history.length-1)*1000;
    const y = 250 - ((item.close-min)/(max-min||1))*210;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  return `<section class="page-heading"><div><p class="eyebrow">HISTORICAL REPORTS</p><h1>التقارير التاريخية</h1><p>السجل التاريخي للسعر بالدولار لكل كيلوجرام وتحليل سنوي قابل للتدقيق.</p></div></section>
  <section class="panel chart-panel"><div class="section-head"><div><h2>آخر ${history.length} ملاحظة</h2><p>${history[0]?.date || ''} → ${history.at(-1)?.date || ''}</p></div></div><svg viewBox="0 0 1000 280" class="price-chart"><polyline points="${points}" fill="none" stroke="currentColor" stroke-width="3" vector-effect="non-scaling-stroke"/></svg><div class="chart-scale"><span>$${money(max)}</span><span>$${money(min)}</span></div></section>
  <section class="panel table-panel"><div class="table-wrap"><table><thead><tr><th>السنة</th><th>بداية</th><th>نهاية</th><th>التغير</th><th>High</th><th>Low</th><th>Rows</th></tr></thead><tbody>${rows}</tbody></table></div></section>`;
};
