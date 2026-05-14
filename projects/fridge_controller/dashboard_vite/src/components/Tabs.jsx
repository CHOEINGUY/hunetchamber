import React from 'react';
import styles from './Tabs.module.css';

export default function Tabs({ activeTab, onChange }) {
  const tabs = [
    { id: 'live', label: '실시간 상태' },
    { id: 'analysis', label: '데이터 분석' },
    { id: 'control', label: '제어' },
  ];

  return (
    <nav className={styles.tabs}>
      {tabs.map(tab => (
        <button
          key={tab.id}
          className={`${styles.tab} ${activeTab === tab.id ? styles.active : ''}`}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );
}
