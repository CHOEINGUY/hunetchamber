import * as echarts from 'echarts';

export function initChart(containerId) {
  const el = document.getElementById(containerId);
  if (!el) return null;
  const chart = echarts.init(el);
  // auto resize on window resize
  window.addEventListener('resize', () => chart.resize());
  return chart;
}

export function renderLiveChart(chart, rows) {
  if (!chart) return;
  const data = rows.slice().reverse(); // oldest first for chart
  const labels = data.map(r => r.created_at ? r.created_at.slice(11,16) : '');
  const tempData = data.map(r => r.temp_c !== null ? parseFloat(r.temp_c) : null);
  const targetData = data.map(r => r.target_c !== null ? parseFloat(r.target_c) : null);
  const onOffData = data.map(r => r.fridge_on ? 1 : 0);

  chart.setOption({
    animation: false,
    tooltip: { trigger: 'axis' },
    legend: { data: ['Temp', 'Target', 'SSR'], top: 0 },
    grid: { left: 50, right: 20, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 10 } },
    yAxis: [
      { type: 'value', name: '°C', position: 'left' },
      { type: 'value', name: 'SSR', min: 0, max: 1, position: 'right' }
    ],
    series: [
      {
        name: 'Temp',
        type: 'line',
        data: tempData,
        smooth: true,
        lineStyle: { width: 2 },
        itemSize: 5,
      },
      {
        name: 'Target',
        type: 'line',
        data: targetData,
        smooth: true,
        lineStyle: { width: 2, type: 'dashed' },
        itemSize: 5,
      },
      {
        name: 'SSR',
        type: 'bar',
        yAxisIndex: 1,
        data: onOffData,
        barWidth: '60%',
        itemStyle: { color: 'rgba(16,185,129,0.6)' },
      }
    ]
  });
}

export function renderAnalysisChart(chart, rows, { mode = 'temp', smooth = 1, steadyStart = null }) {
  if (!chart) return;
  let filtered = rows;
  if (steadyStart) {
    const startDate = new Date(steadyStart);
    filtered = rows.filter(r => new Date(r.created_at.replace(' ', 'T')) >= startDate);
  }
  // downsample if needed (simple step)
  if (smooth > 1) {
    const step = Math.max(1, Math.floor(smooth));
    const downsampled = [];
    for (let i = 0; i < filtered.length; i += step) {
      const chunk = filtered.slice(i, i + step);
      const mid = chunk[Math.floor(chunk.length/2)];
      downsampled.push(mid);
    }
    filtered = downsampled;
  }
  const labels = filtered.map(r => r.created_at ? r.created_at.slice(11,16) : '');
  let series = [];
  let yAxis = [
    { type: 'value', name: '°C' },
    { type: 'value', name: 'SSR', min: 0, max: 1, position: 'right' }
  ];
  if (mode === 'deviation') {
    const devData = filtered.map(r => {
      if (r.temp_c === null || r.target_c === null) return null;
      return parseFloat(r.temp_c) - parseFloat(r.target_c);
    });
    const bandVal = filtered.length && filtered[0].band_c !== null ? parseFloat(filtered[0].band_c) : 0.5;
    series = [
      {
        name: 'Deviation',
        type: 'line',
        smooth: true,
        data: devData,
        itemSize: 5,
        lineStyle: { width: 2 },
        areaStyle: { color: 'rgba(124,58,237,0.1)' },
      },
      {
        name: 'Band Upper',
        type: 'line',
        data: filtered.map(r => bandVal),
        lineStyle: { type: 'dashed', color: '#f97316' },
        showLegend: false,
      },
      {
        name: 'Band Lower',
        type: 'line',
        data: filtered.map(r => -bandVal),
        lineStyle: { type: 'dashed', color: '#f97316' },
        showLegend: false,
      },
      {
        name: 'SSR',
        type: 'bar',
        yAxisIndex: 1,
        data: filtered.map(r => r.fridge_on ? 1 : 0),
        barWidth: '60%',
        itemStyle: { color: 'rgba(16,185,129,0.6)' },
      }
    ];
    yAxis = [
      { type: 'value', name: 'Deviation °C' },
      { type: 'value', name: 'SSR', min: 0, max: 1, position: 'right' }
    ];
  } else {
    // temp mode
    const tempData = filtered.map(r => r.temp_c !== null ? parseFloat(r.temp_c) : null);
    const targetData = filtered.map(r => r.target_c !== null ? parseFloat(r.target_c) : null);
    const upper = filtered.map(r => r.target_c !== null && r.band_c !== null ? parseFloat(r.target_c) + parseFloat(r.band_c) : null);
    const lower = filtered.map(r => {
      const bl = r.band_low_c !== null ? r.band_low_c : r.band_c;
      return r.target_c !== null && bl !== null ? parseFloat(r.target_c) - parseFloat(bl) : null;
    });
    series = [
      {
        name: 'Temp',
        type: 'line',
        smooth: true,
        data: tempData,
        itemSize: 5,
        lineStyle: { width: 2 },
        color: '#0284c7',
      },
      {
        name: 'Target',
        type: 'line',
        smooth: true,
        data: targetData,
        itemSize: 5,
        lineStyle: { width: 2, type: 'dashed' },
        color: '#64748b',
      },
      {
        name: 'Upper',
        type: 'line',
        data: upper,
        lineStyle: { type: 'dashed', width: 1 },
        color: '#f97316',
      },
      {
        name: 'Lower',
        type: 'line',
        data: lower,
        lineStyle: { type: 'dashed', width: 1 },
        color: '#f97316',
      },
      {
        name: 'SSR',
        type: 'bar',
        yAxisIndex: 1,
        data: filtered.map(r => r.fridge_on ? 1 : 0),
        barWidth: '60%',
        itemStyle: { color: 'rgba(16,185,129,0.6)' },
      }
    ];
  }
  chart.setOption({
    animation: false,
    tooltip: { trigger: 'axis' },
    legend: { data: series.map(s => s.name).filter(Boolean), top: 0 },
    grid: { left: 60, right: 30, top: 50, bottom: 40 },
    xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 10 } },
    yAxis: yAxis,
    series: series,
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 20, bottom: 10 }],
  });
}
