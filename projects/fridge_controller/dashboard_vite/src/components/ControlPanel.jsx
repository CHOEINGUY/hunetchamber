import React, { useState, useEffect, useRef } from 'react';
import { useFetchReadings } from '../hooks/useFetchReadings';
import { useSendCmd } from '../hooks/useSendCmd';
import { formatValue } from '../utils/formatters';
import styles from './ControlPanel.module.css';

export default function ControlPanel() {
  const { rows, loading, error } = useFetchReadings({ limit: 1, since_s: 0 });
  const { status, sendCmd } = useSendCmd();

  // Latest row
  const latest = rows[0];

  // Form state with dirty flags
  const [target, setTarget] = useState(latest ? latest.target_c : 15.0);
  const [targetDirty, setTargetDirty] = useState(false);
  const [bandHigh, setBandHigh] = useState(latest ? latest.band_c : 0.5);
  const [bandHighDirty, setBandHighDirty] = useState(false);
  const [bandLow, setBandLow] = useState(latest ? (latest.band_low_c ?? latest.band_c) : 0.5);
  const [bandLowDirty, setBandLowDirty] = useState(false);

  // Sync form with latest row when not dirty
  useEffect(() => {
    if (latest && !targetDirty) {
      setTarget(latest.target_c);
    }
    if (latest && !bandHighDirty) {
      setBandHigh(latest.band_c);
    }
    if (latest && !bandLowDirty) {
      setBandLow(latest.band_low_c ?? latest.band_c);
    }
  }, [latest, targetDirty, bandHighDirty, bandLowDirty]);

  const handleTargetChange = (delta) => {
    const newValue = Math.max(0, Math.min(25, target + delta));
    setTarget(newValue);
    setTargetDirty(true);
  };
  const handleBandHighChange = (delta) => {
    const newValue = Math.max(0.1, Math.min(5.0, bandHigh + delta));
    setBandHigh(newValue);
    setBandHighDirty(true);
  };
  const handleBandLowChange = (delta) => {
    const newValue = Math.max(0.1, Math.min(5.0, bandLow + delta));
    setBandLow(newValue);
    setBandLowDirty(true);
  };

  const applyTarget = () => {
    if (targetDirty) {
      sendCmd(`target ${target.toFixed(1)}`);
      setTargetDirty(false);
    }
  };
  const applyBandHigh = () => {
    if (bandHighDirty) {
      sendCmd(`bandhigh ${bandHigh.toFixed(1)}`);
      setBandHighDirty(false);
    }
  };
  const applyBandLow = () => {
    if (bandLowDirty) {
      sendCmd(`bandlow ${bandLow.toFixed(1)}`);
      setBandLowDirty(false);
    }
  };

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div className={styles.panel}>
      <section className={styles.latest} id="ctrlLive">
        {/* Live status will be added later if needed */}
      </section>

      <div className={styles.ctrlPanel}>
        <h2>목표 온도</h2>
        <div className={styles.ctrlRow}>
          <div className={styles.btnGroup}>
            <button onClick={() => handleTargetChange(-0.5)}>−</button>
            <span className={styles.ctrlTargetVal}>
              {formatValue(target, '°C')}
            </span>
            <button onClick={() => handleTargetChange(0.5)}>+</button>
          </div>
          <button className={styles.toggle} onClick={applyTarget}>
            적용
          </button>
        </div>
      </div>

      <div className={styles.ctrlPanel}>
        <h2>상한 편차 (켜기 기준: 목표 + X)</h2>
        <div className={styles.ctrlRow}>
          <div className={styles.btnGroup}>
            <button onClick={() => handleBandHighChange(-0.1)}>−</button>
            <span className={styles.ctrlTargetVal}>
              +{formatValue(bandHigh, '°C')}
            </span>
            <button onClick={() => handleBandHighChange(0.1)}>+</button>
          </div>
          <button className={styles.toggle} onClick={applyBandHigh}>
            적용
          </button>
        </div>
      </div>

      <div className={styles.ctrlPanel}>
        <h2>하한 편차 (끄기 기준: 목표 − X)</h2>
        <div className={styles.ctrlRow}>
          <div className={styles.btnGroup}>
            <button onClick={() => handleBandLowChange(-0.1)}>−</button>
            <span className={styles.ctrlTargetVal}>
              −{formatValue(bandLow, '°C')}
            </span>
            <button onClick={() => handleBandLowChange(0.1)}>+</button>
          </div>
          <button className={styles.toggle} onClick={applyBandLow}>
            적용
          </button>
        </div>
      </div>

      <div className={styles.ctrlPanel}>
        <h2>자동 제어 / 무장</h2>
        <div className={styles.ctrlRow}>
          <div className={styles.btnGroup}>
            <button onClick={() => sendCmd('auto 1')} disabled={!latest || latest.armed === 0}>
              AUTO ON
            </button>
            <button onClick={() => sendCmd('auto 0')}>
              AUTO OFF
            </button>
          </div>
          <div className={styles.btnGroup}>
            <button onClick={() => sendCmd('arm')} disabled={!latest || latest.armed === 1}>
              ARM
            </button>
            <button onClick={() => sendCmd('disarm')}>
              DISARM
            </button>
          </div>
        </div>
      </div>

      <div className={styles.ctrlPanel}>
        <h2>팬</h2>
        <div className={styles.btnGroup}>
          <button onClick={() => sendCmd('fan 100')}>ON</button>
          <button onClick={() => sendCmd('fan 0')}>OFF</button>
        </div>
      </div>

      <div className={`${styles.ctrlPanel} ${styles.danger}`}>
        <h2>위험</h2>
        <button
          className={styles.dangerBtn}
          onClick={() => {
            if (window.confirm('FORCE OFF 실행하시겠습니까?')) {
              sendCmd('forceoff');
            }
          }}
        >
          FORCE OFF
        </button>
        <p style={{ margin: '8px 0 0', fontSize: '12px', color: '#9ca3af' }}>
          즉시 OFF + disarm. 컴프레서 보호 무시.
        </p>
      </div>

      <div id="cmdStatus" className={`${styles.cmdStatus} ${status.type}`}>
        {status.text}
      </div>
    </div>
  );
}
