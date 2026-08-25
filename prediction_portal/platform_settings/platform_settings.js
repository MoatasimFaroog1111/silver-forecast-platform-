export const renderPlatformSettings = async api => {
  const settings = await api.settings();
  const rows = Object.entries(settings).map(([key,value]) => `<div class="setting-row"><span>${key.replaceAll('_',' ')}</span><b>${typeof value === 'boolean' ? (value ? 'YES' : 'NO') : value}</b></div>`).join('');
  return `<section class="page-heading"><div><p class="eyebrow">PLATFORM SETTINGS</p><h1>الإعدادات</h1><p>إعدادات التشغيل وسياسة النماذج وقاعدة البيانات، بدون كشف أسرار Environment.</p></div></section>
  <section class="settings-grid"><article class="panel settings-card"><h2>Runtime</h2>${rows}</article><article class="panel settings-card"><h2>Railway</h2><p>أضف PostgreSQL واضبط <code>DATABASE_URL</code>. الخدمة تستخدم <code>PORT</code> تلقائيًا وHealthcheck على <code>/health</code>.</p><p>الـFrontend والـAPI يعملان من نفس الـOrigin، لذلك لا تحتاج CORS في Production.</p></article></section>`;
};
