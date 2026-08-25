export const renderWalkForwardBacktesting = async api => {
  const data = await api.backtesting();
  const summary = data.summary;
  const horizons = [...new Set(summary.map(row => row.Horizon_D))];
  const cards = horizons.map(h => {
    const rows = summary.filter(row => row.Horizon_D === h).sort((a,b) => a.Robust_Score - b.Robust_Score);
    const naive = rows.find(row => row.Model === 'Naive_LastClose');
    const ml = rows.find(row => row.Model !== 'Naive_LastClose');
    return `<article class="backtest-card panel"><div class="card-head"><strong>${h}D</strong><span>${ml.Model.replaceAll('_',' ')}</span></div>
      <div class="metric-pair"><div><span>Naive MAE</span><b>${naive.MAE_Mean.toFixed(2)}</b></div><div><span>Best ML MAE</span><b>${ml.MAE_Mean.toFixed(2)}</b></div></div>
      <div class="mini-grid"><div><b>${ml.MAPE_Mean_Pct.toFixed(2)}%</b><span>ML MAPE</span></div><div><b>${ml.Directional_Accuracy_Mean_Pct.toFixed(2)}%</b><span>Direction</span></div><div><b>${ml.Folds_Beating_Naive_MAE}/6</b><span>Beats Naive</span></div></div>
      <small class="muted">Robust score: ${ml.Robust_Score.toFixed(2)}</small></article>`;
  }).join('');
  const topRows = data.shortlist.map(row => `<tr><td>${row.Horizon_D}D</td><td>${row.Shortlist_Rank}</td><td>${row.Model.replaceAll('_',' ')}</td><td>${row.MAE_Mean.toFixed(3)}</td><td>${row.MAPE_Mean_Pct.toFixed(3)}%</td><td>${row.Directional_Accuracy_Mean_Pct.toFixed(2)}%</td><td>${row.Folds_Beating_Naive_MAE}/6</td></tr>`).join('');
  return `<section class="page-heading"><div><p class="eyebrow">PURGED WALK-FORWARD</p><h1>Backtesting</h1><p>6 نوافذ زمنية، Purge 30 جلسة، بدون Shuffle وبدون Leakage.</p></div><span class="status-badge">360 Evaluations</span></section>
  <section class="backtest-grid">${cards}</section>
  <section class="panel table-panel"><div class="section-head"><div><h2>Ensemble Shortlist</h2><p>أفضل 4 نماذج ML لكل أفق قبل أي Ensemble جديد.</p></div></div><div class="table-wrap"><table><thead><tr><th>الأفق</th><th>الترتيب</th><th>النموذج</th><th>MAE</th><th>MAPE</th><th>Direction</th><th>Beats Naive</th></tr></thead><tbody>${topRows}</tbody></table></div></section>`;
};
