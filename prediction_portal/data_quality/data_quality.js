export const renderDataQuality = async api => {
  const quality = await api.quality();
  const q = quality.stage8_quality || {};
  const cards = [
    ['Features المختارة', quality.selected_feature_count],
    ['Leakage crossings', quality.leakage_crossings_stage10],
    ['Models loadable', quality.model_registry_health.loadable ? 'PASS' : 'FAIL'],
    ['Latest market date', quality.latest_market_date],
    ['Causality mismatches', q.causality_prefix_audit?.mismatches ?? '—'],
    ['Zero volume preserved', q.zero_volume_rows_preserved ?? '—'],
    ['Ready rows', q.model_ready_rows ?? '—'],
    ['Stage 8 status', q.status ?? '—'],
  ].map(([label,value]) => `<article class="quality-card panel"><span>${label}</span><strong>${value}</strong></article>`).join('');
  const failures = quality.model_registry_health.failures || [];
  return `<section class="page-heading"><div><p class="eyebrow">DATA QUALITY</p><h1>جودة البيانات والنماذج</h1><p>Checks قابلة للمراجعة تمنع Leakage وتكشف كسر عقد الـFeatures أو model artifacts.</p></div></section><section class="quality-grid">${cards}</section>
  <section class="panel explanation"><h3>Model Registry Health</h3><p>${failures.length ? failures.map(x=>`${x.artifact}: ${x.error}`).join('<br>') : 'جميع النماذج النشطة قابلة للتحميل بنجاح.'}</p></section>`;
};
