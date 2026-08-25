const money = value => Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const renderLiveForecasts = async api => {
  const [challenger, primary] = await Promise.all([api.latestForecasts('challenger'), api.latestForecasts('primary')]);
  const rows = challenger.map(item => {
    const base = primary.find(p => p.horizon === item.horizon);
    return `<tr>
      <td><b>${item.horizon}</b><small>${item.horizon_sessions} جلسات</small></td>
      <td>$${money(item.current_price)}</td>
      <td class="prediction">$${money(item.predicted_price)}<small>${item.predicted_change_pct >= 0 ? '+' : ''}${item.predicted_change_pct.toFixed(2)}%</small></td>
      <td>$${money(base.predicted_price)}</td>
      <td>${item.price_accuracy_pct.toFixed(2)}%</td>
      <td>${item.directional_accuracy_pct.toFixed(2)}%</td>
      <td>${item.model_name.replaceAll('_',' ')}</td>
      <td><span class="eligibility ${item.production_eligible ? 'eligible' : 'challenger'}">${item.production_eligible ? 'Production' : 'Challenger'}</span></td>
    </tr>`;
  }).join('');
  return `<section class="page-heading"><div><p class="eyebrow">FORECASTS</p><h1>التوقعات الحالية</h1><p>مقارنة السعر الحالي وتوقع ML والـPrimary Guarded لكل أفق.</p></div></section>
  <section class="panel table-panel"><div class="table-wrap"><table><thead><tr><th>الأفق</th><th>السعر الحالي</th><th>ML المتوقع</th><th>Primary</th><th>دقة السعر</th><th>دقة الاتجاه</th><th>النموذج</th><th>الحالة</th></tr></thead><tbody>${rows}</tbody></table></div></section>
  <section class="panel explanation"><h3>كيف تقرأ النسبة؟</h3><p><b>Price Accuracy = 100 − MAPE</b>. هذه ليست نسبة إصابة السعر بالضبط، بل تحويل مبسط لمتوسط الخطأ النسبي المطلق. لذلك نظهر MAPE وMAE ودقة الاتجاه دائمًا بجانبها.</p></section>`;
};
