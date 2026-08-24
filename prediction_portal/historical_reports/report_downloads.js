export const renderReportDownloads = async api => {
  const reports = await api.reports();
  const groups = Object.groupBy ? Object.groupBy(reports, item => item.category) : reports.reduce((acc,item)=>{(acc[item.category] ||= []).push(item);return acc;},{});
  const html = Object.entries(groups).map(([category,items]) => `<section class="report-group"><h2>${category === 'backtesting' ? 'Backtesting' : 'Verified Reports'}</h2><div class="report-grid">${items.map(item => `<a class="report-card panel" href="${item.download_url}" download><span>⇩</span><div><b>${item.title}</b><small>${item.name}</small></div></a>`).join('')}</div></section>`).join('');
  return `<section class="page-heading"><div><p class="eyebrow">REPORT CENTER</p><h1>التقارير</h1><p>تحميل تقارير الجودة، Features، الاختبار النهائي، Backtesting وModel Selection.</p></div><span class="status-badge">${reports.length} Files</span></section>${html}`;
};
