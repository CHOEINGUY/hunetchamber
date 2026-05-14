export function formatValue(value, unit = '') {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'number') {
    // Show one decimal for temperature, humidity, etc.
    return value.toFixed(1) + (unit ? ' ' + unit : '');
  }
  return String(value) + (unit ? ' ' + unit : '');
}

export function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || seconds < 0) return '-';
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${sec}s`;
  return `${sec}s`;
}
