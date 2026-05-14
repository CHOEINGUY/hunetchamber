import React, { useState, useEffect, useRef } from 'react';
import { useFetchReadings } from '../hooks/useFetchReadings';
import { formatValue, formatDuration } from '../utils/formatters';
import { initChart, renderAnalysisChart } from '../utils/chartUtils';
import styles from './AnalysisPanel.module.css';

export default function AnalysisPanel() {
  const [periodSeconds, setPeriodSeconds] = useState(600); // 10 min
  const [chartMode, setChartMode] = useState('temp'); // 'temp' or 'deviation'
  const [smoothStep, setSmoothStep] = useState(1); // 1,5,10
  const [steadyStart, setSteadyStart] = useState(null); // Date object or null
  const [steadyInputValue, setSteadyInputValue] = useState('');

  const chartRef = useRef(null);

  // Fetch data based on period and steadyStart
  const { rows, loading, error } = useFetchReadings({
    limit: Math.min(periodSeconds * 2, 10000),
    since_s: periodSeconds,
  });

  // Initialize chart
  useEffect(() => {
    const chart = initChart('analysisChart');
    chartRef.current = chart;
    return () => {
      if (chart) chart.dispose();
    };
  }, []);

  // Redraw chart when data or settings change
  useEffect(() => {
    if (chartRef.current && rows.length) {
      renderAnalysisChart(chartRef.current, rows, {
        mode: chartMode,
        smooth: smoothStep,
        steadyStart: steadyStart,
      });
    }
  }, [rows, chartMode, smoothStep, steadyStart]);

  // Handle steady start input change
  const handleSteadyChange = (e) => {
    const val = e.target.value;
    setSteadyInputValue(val);
    if (val) {
      try {
        const date = new Date(val);
        if (!isNaN(date.getTime())) setSteadyStart(date);
        else setSteadyStart(null);
      } catch (_) {
        setSteadyStart(null);
      }
    } else {
      setSteadyStart(null);
    }
  };

  const handleClearSteady = () => {
    setSteadyInputValue('');
    setSteadyStart(null);
  };

  // Compute summary stats
  const computeSummary = (rows) => {
    if (!rows.length) return null;
    const temps = rows.map(r => r.temp_c).filter(v => v !== null).map(Number);
    const deviations = rows
      .map(r => {
        if (r.temp_c === null || r.target_c === null) return null;
        return Math.abs(parseFloat(r.temp_c) - parseFloat(r.target_c));
      })
      .filter(v => v !== null);
    const inBand = rows.filter(r => {
      if (r.temp_c === null || r.target_c === null || r.band_c === null) return false;
      return Math.abs(parseFloat(r.temp_c) - parseFloat(r.target_c)) <= parseFloat(r.band_c);
    }).length;
    const inBandRatio = rows.length ? (inBand / rows.length) * 100 : 0;
    const avgTemp = temps.reduce((a, b) => a + b, 0) / temps.length;
    const minTemp = Math.min(...temps);
    const maxTemp = Math.max(...temps);
    // stddev
    const variance =
      temps.length > 1
        ? temps.reduce((sum, v) => sum + Math.pow(v - avgTemp, 2), 0) /
          temps.length
        : 0;
    const stddev = Math.sqrt(variance);
    const avgDev =
      deviations.length > 0
        ? deviations.reduce((a, b) => a + b, 0) / deviations.length
        : 0;
    // SSR stats
    const onRows = rows.filter(r => r.fridge_on === 1).length;
    const onRatio = rows.length ? (onRows / rows.length) * 100 : 0;
    // count cycles (off->on transitions)
    const ordered = [...rows].reverse();
    let onCount = 0;
    let last = null;
    ordered.forEach((r) => {
      const cur = r.fridge_on ?? 0;
      if (last !== null && cur !== last && cur === 1) onCount++;
      last = cur;
    });
    // duration hours
    let durationHours = 0;
    if (ordered.length >= 2) {
      const t0 = new Date(ordered[0].created_at.replace(' ', 'T'));
      const t1 = new Date(ordered[ordered.length - 1].created_at.replace(' ', 'T'));
      durationHours = Math.abs(t1 - t0) / 3.6e6;
    }
    const cyclesPerHour = durationHours > 0 ? onCount / durationHours : 0;

    return {
      avgTemp,
      minTemp,
      maxTemp,
      stddev,
      avgDev,
      inBandRatio,
      onRatio,
      cyclesPerHour,
      onCount,
    };
  };

  const summary = computeSummary(rows);

  return (
    <div className={styles.panel}>
      <div className={styles.toolbar}>
        <div className={styles.toolbarRow}>
          <span className={styles.optionLabel}>기간</span>
          <div className={styles.btnGroup}>
            <button
              className={`${styles.btn} ${periodSeconds === 600 ? styles.active : ''}`}
              onClick={() => setPeriodSeconds(600)}
            >
              10분
            </button>
            <button
              className={`${styles.btn} ${periodSeconds === 1800 ? styles.active : ''}`}
              onClick={() => setPeriodSeconds(1800)}
            >
              30분
            </button>
            <button
              className={`${styles.btn} ${periodSeconds === 3600 ? styles.active : ''}`}
              onClick={() => setPeriodSeconds(3600)}
            >
              1시간
            </button>
            <button
              className={`${styles.btn} ${periodSeconds === 21600 ? styles.active : ''}`}
              onClick={() => setPeriodSeconds(21600)}
            >
              6시간
            </button>
            <button
              className={`${styles.btn} ${periodSeconds === 86400 ? styles.active : ''}`}
              onClick={() => setPeriodSeconds(86400)}
            >
              24시간
            </button>
          </div>
          <div className={styles.spacer}></div>
        </div>
        <div className={styles.toolbarRow}>
          <span className={styles.optionLabel}>차트 모드</span>
          <div className={styles.btnGroup}>
            <button
              className={`${styles.btn} ${chartMode === 'temp' ? styles.active : ''}`}
              onClick={() => setChartMode('temp')}
            >
              온도
            </button>
            <button
              className={`${styles.btn} ${chartMode === 'deviation' ? styles.active : ''}`}
              onClick={() => setChartMode('deviation')}
            >
              편차
            </button>
          </div>
          <span className={styles.optionLabel} style={{ marginLeft: 12 }}>
            스무딩
          </span>
          <div className={styles.btnGroup}>
            <button
              className={`${styles.btn} ${smoothStep === 1 ? styles.active : ''}`}
              onClick={() => setSmoothStep(1)}
            >
              원본
            </button>
            <button
              className={`${styles.btn} ${smoothStep === 5 ? styles.active : ''}`}
              onClick={() => setSmoothStep(5)}
            >
              5초
            </button>
            <button
              className={`${styles.btn} ${smoothStep === 10 ? styles.active : ''}`}
              onClick={() => setSmoothStep(10)}
            >
              10초
            </button>
          </div>
        </div>
        <div className={styles.toolbarRow}>
          <span className={styles.optionLabel}>정상 운전 시작</span>
          <div className={styles.steadyInput}>
            <input
              type="datetime-local"
              value={steadyInputValue}
              onChange={handleSteadyChange}
            />
            <button onClick={handleClearSteady}>초기화</button>
          </div>
          {steadyStart && (
            <span className={styles.steadyBadge}>
              시작: {steadyStart.toLocaleString('ko-KR')}
            </span>
          )}
        </div>
      </div>

      <div className={styles.chartContainer}>
        <h2 className={styles.chartTitle}>
          {chartMode === 'temp'
            ? '온도 / 목표 범위 / SSR 상태'
            : '편차 / 목표 범위 / SSR 상태'}
        </h2>
        <div id="analysisChart" className={styles.chart}></div>
      </div>

      {summary && (
        <>
          <div className={styles.summaryHeader}>
            <h3>분석 요약</h3>
            <span className={styles.summaryNote}>
              {steadyStart
                ? `정상 운전 시작: ${steadyStart.toLocaleString(
                    'ko-KR'
                  )} (${rows.length}개 행)`
                : `전체 데이터 (${rows.length}개 행)`}
            </span>
          </div>
          <div className={styles.summary}>
            <div className={styles.metric}>
              <span>평균 온도</span>
              <strong>{formatValue(summary.avgTemp, '°C')}</strong>
            </div>
            <div className={styles.metric}>
              <span>최소 / 최대</span>
              <strong>
                {formatValue(summary.minTemp, '°C')} /
                {formatValue(summary.maxTemp, '°C')}
              </strong>
            </div>
            <div className={styles.metric}>
              <span>온도 표준편차</span>
              <strong>{formatValue(summary.stddev, '°C')}</strong>
            </div>
            <div className={styles.metric}>
              <span> 평균 편차 </span>
              <strong>{formatValue(summary.avgDev, '°C')}</strong>
            </div>
            <div className={styles.metric}>
              <span>목표 구간 내 비율</span>
              <strong>{summary.inBandRatio.toFixed(1)}%</strong>
            </div>
            <div className={styles.metric}>
              <span>SSR ON 비율</span>
              <strong>{summary.onRatio.toFixed(1)}%</strong>
            </div>
            <div className={styles.metric}>
              <span>SSR ON 횟수 / 시간</span>
              <strong>
                {summary.onCount}회 / {summary.cyclesPerHour.toFixed(1)}회/시간
              </strong>
            </div>
          </div>
        </>
      )}

      <div className={styles.tableWrap}>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>시간</th>
              <th>장치 ID</th>
              <th>온도 (°C)</th>
              <th>습도 (%)</th>
              <th>목표 (°C)</th>
              <th>SSR</th>
              <th>자동</th>
              <th>무장</th>
              <th>팬 (%)</th>
              <th>LED (%)</th>
              <th>대기 ON (s)</th>
              <th>대기 OFF (s)</th>
              <th>상태 경과 (s)</th>
              <th>센서 나이 (s)</th>
              <th>사유</th>
            </tr>
          </thead>
          <tbody>
            {rows
              .slice()
              .reverse()
              .map((r) => (
                <tr key={r.id}>
                  <td>{r.id}</td>
                  <td>{r.created_at}</td>
                  <td>{r.device_id}</td>
                  <td>{formatValue(r.temp_c, '°C')}</td>
                  <td>{formatValue(r.humidity, '%')}</td>
                  <td>{formatValue(r.target_c, '°C')}</td>
                  <td>{r.fridge_on ? 'ON' : 'OFF'}</td>
                  <td>{r.auto_mode ? 'ON' : 'OFF'}</td>
                  <td>{r.armed ? 'ON' : 'OFF'}</td>
                  <td>{formatValue(r.fan_percent, '%')}</td>
                  <td>{formatValue(r.led_percent, '%')}</td>
                  <td>{formatValue(r.wait_on_s, 's')}</td>
                  <td>{formatValue(r.wait_off_s, 's')}</td>
                  <td>{formatValue(r.state_elapsed_s, 's')}</td>
                  <td>{formatValue(r.sensor_age_s, 's')}</td>
                  <td>{r.reason ?? '-'}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
