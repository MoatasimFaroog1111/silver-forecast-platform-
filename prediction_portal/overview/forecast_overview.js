const money = value => Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const pct = value => `${Number(value).toFixed(2)}%`;

const forecastCard = item => {
  const direction = item.predicted_change_pct > 0 ? 'up' : item.predicted_change_pct < 0 ? 'down' : 'flat';
  const arrow = direction === 'up' ? '▲' : direction === 'down' ? '▼' : '•';
  return `<article class="forecast-card">
    <div class="card-head"><strong>${item.horizon}</strong><span class="model-pill">${item.model_name.replaceAll('_',' ')}</span></div>
    <div class="price-pair"><span>$${money(item.current_price)}</span><b>→</b><span>$${money(item.predicted_price)}</span></div>
    <div class="change ${direction}">${arrow} ${item.predicted_change_pct >= 0 ? '+' : ''}${pct(item.predicted_change_pct)}</div>
    <div class="accuracy-line"><span>دقة السعر</span><b>${pct(item.price_accuracy_pct)}</b></div>
    <div class="meter"><i style="width:${item.price_accuracy_pct}%"></i></div>
    <div class="mini-grid">
      <div><b>${item.mape_pct.toFixed(3)}%</b><span>MAPE</span></div>
      <div><b>${money(item.mae_usd_per_kg)}</b><span>MAE USD/KG</span></div>
      <div><b>${pct(item.directional_accuracy_pct)}</b><span>دقة الاتجاه</span></div>
    </div>
  </article>`;
};

export const renderForecastOverview = async (api) => {
  const challenger = await api.dashboard('challenger');
  const primary = await api.dashboard('primary');
  const bestPriceAccuracy = Math.max(...challenger.forecasts.map(item => item.price_accuracy_pct));
  const bestDirection = Math.max(...challenger.forecasts.map(item => item.directional_accuracy_pct));
  return `<section class="page-heading">
      <div><p class="eyebrow">SILVER FORECAST PLATFORM</p><h1>مركز التنبؤ بالسعر</h1><p>آخر سعر مسجل، التوقعات، الدقة، وحالة نموذج الإنتاج في مكان واحد.</p></div>
      <span class="status-badge">Verified Walk-Forward</span>
    </section>
    <section class="hero-grid">
      <article class="hero-price panel">
        <span>آخر سعر متاح</span><strong>$${money(challenger.market.close)}</strong><small>USD/KG · ${challenger.market.date}</small>
      </article>
      <article class="headline-stat panel"><span>أفضل دقة سعر ML</span><strong>${pct(bestPriceAccuracy)}</strong><small>100 − MAPE</small></article>
      <article class="headline-stat panel"><span>أفضل دقة اتجاه</span><strong>${pct(bestDirection)}</strong><small>Walk-Forward</small></article>
      <article class="headline-stat panel"><span>Leakage</span><strong>${challenger.leakage_crossings}</strong><small>Stage 10 crossings</small></article>
    </section>
    <section class="section-head"><div><h2>توقعات ML Challenger</h2><p>السعر المتوقع من CatBoost لكل Horizon مع المقاييس التاريخية المثبتة.</p></div><span class="policy-note">Primary Guarded = Last Close</span></section>
    <section class="forecast-grid">${challenger.forecasts.map(forecastCard).join('')}</section>
    <section class="panel guard-panel">
      <div><h3>Production Guard</h3><p>الـPrimary Forecast لا يزال Last Close لأن Stage 10 لم يثبت تفوق ML في MAE. الـML يعرض كـChallenger وليس كدقة إنتاج مزعومة.</p></div>
      <div class="guard-comparison"><span>Primary 30D</span><b>$${money(primary.forecasts.find(x=>x.horizon==='30D').predicted_price)}</b><span>ML 30D</span><b>$${money(challenger.forecasts.find(x=>x.horizon==='30D').predicted_price)}</b></div>
    </section>`;
};
