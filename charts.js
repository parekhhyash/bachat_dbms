async function loadCharts() {
  const pieRes = await fetch('/api/analytics/category_pie');
  const pie = await pieRes.json();
  const barRes = await fetch('/api/analytics/monthly_bar');
  const bar = await barRes.json();

  const pieCtx = document.getElementById('pieChart');
  if (pieCtx) {
    new Chart(pieCtx, {
      type: 'pie',
      data: { labels: pie.labels, datasets: [{ data: pie.data }] },
      options: { responsive:true }
    });
  }

  const barCtx = document.getElementById('barChart');
  if (barCtx) {
    new Chart(barCtx, {
      type: 'bar',
      data: { labels: bar.labels, datasets: [{ label: 'Spent', data: bar.data }] },
      options: { responsive:true }
    });
  }
}

window.addEventListener('load', loadCharts);
