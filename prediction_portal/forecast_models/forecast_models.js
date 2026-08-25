export const renderForecastModels = async api => {
  const models = await api.models();
  const cards = models.map(item => `<article class="model-card panel">
    <div class="card-head"><strong>${item.horizon}</strong><span class="eligibility challenger">Challenger</span></div>
    <h3>${item.challenger_model.replaceAll('_',' ')}</h3>
    <p>Primary: <b>${item.primary_model.replaceAll('_',' ')}</b></p>
    <div class="mini-grid"><div><b>${item.price_accuracy_pct.toFixed(2)}%</b><span>Price Accuracy</span></div><div><b>${item.mae_usd_per_kg.toFixed(2)}</b><span>MAE</span></div><div><b>${item.directional_accuracy_pct.toFixed(2)}%</b><span>Direction</span></div></div>
    <dl><dt>Model version</dt><dd>${item.model_version}</dd><dt>Training end</dt><dd>${item.training_date_end}</dd><dt>Features</dt><dd>${item.selected_feature_count}</dd><dt>Artifact</dt><dd>${item.artifact}</dd></dl>
  </article>`).join('');
  return `<section class="page-heading"><div><p class="eyebrow">MODEL REGISTRY</p><h1>النماذج المسجلة</h1><p>النماذج الفعلية المحفوظة، إصدارها، Metrics ودورها في سياسة التنبؤ.</p></div></section><section class="model-grid">${cards}</section>`;
};
