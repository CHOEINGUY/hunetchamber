import React from 'react';
import styles from './Header.module.css';

export default function Header() {
  return (
    <header className={styles.header}>
      <div>
        <h1>Fridge Dashboard</h1>
        <p className={styles.subtitle}>Pico WH 냉장고 온도 제어 모니터링</p>
      </div>
      <div className={styles.status}>
        <div id="connection">연결 확인 중...</div>
        <div id="updated">-</div>
      </div>
    </header>
  );
}
