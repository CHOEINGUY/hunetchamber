import React, { useEffect, useRef } from 'react';
import { useFetchReadings } from '../hooks/useFetchReadings';
import { formatValue, formatDuration } from '../utils/formatters';
import { initChart, renderLiveChart } from '../utils/chartUtils';
import styles from './LivePanel.module.css';

export default function LivePanel() {
  const { rows, loading, error } = useFetchReadings({ limit: 60, since_s: 60 });
  const chartRef = useRef(null);

  useEffect(() => {
    const chart = initChart('liveChart');
    chartRef.current = chart;
    return () => {
      if (chart) chart.dispose();
    };
  }, []);

  useEffect(() => {
    if (chartRef.current && rows.length) {
      renderLiveChart(chartRef.current, rows);
    }
  }, [rows]);

  if (loading) return <div className={styles.loading}>Loading...</div>;
  if (error) return <div className={styles.error}>Error: {error}</div>;
  if (!rows.length) return <div className={styles.empty}>No data</div>;

  const latest = rows[0];

  return (
    <div className={styles.panel}>
      <div className={styles.latestMetrics}>
        <div className={styles.metric}>
          <span>현재 온도</span>
          <strong>{formatValue(latest.temp_c, '°C')}</strong>
          <small>{latest.temp_c !== null ? formatDuration(latest.row_age_s) + ' 전' : ''}</small>
        </div>
        <div className={styles.metric}>
          <span>목표 온도</span>
          <strong>{formatValue(latest.target_c, '°C')}</strong>
          <small>±{formatValue(latest.band_c, '°C')}</small>
        </div>
        <div className={styles.metric}>
          <span>습도</span>
          <strong>{formatValue(latest.humidity, '%')}</strong>
        </div>
        <div className={styles.metric}>
          <span>SSR 출력</span>
          <strong>{latest.fridge_on ? 'ON' : 'OFF'}</strong>
          <small>{formatDuration(latest.state_elapsed_s)}</small>
        </div>
      </div>
      <div className={styles.chartContainer}>
        <h2 className={styles.chartTitle}>최근 10분 온도 / SSR</h2>
        <div id="liveChart" className={styles.chart}></div>
      </div>
    </div>
  );
}
