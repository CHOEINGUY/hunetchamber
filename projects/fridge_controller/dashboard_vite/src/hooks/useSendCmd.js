import { useState } from 'react';

export function useSendCmd() {
  const [status, setStatus] = useState({ text: '명령 없음', type: 'idle' });
  const send = async (cmd) => {
    setStatus({ text: `전송 중: ${cmd}`, type: 'pending' });
    try {
      const resp = await fetch('/api/cmd', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cmd })
      });
      const data = await resp.json();
      if (data.ok) {
        setStatus({ text: `완료: ${cmd}`, type: 'ok' });
      } else {
        setStatus({ text: `오류: ${data.error || '?'}`, type: 'err' });
      }
    } catch (err) {
      setStatus({ text: `예외: ${err.message}`, type: 'err' });
    }
    // auto-hide after 3s
    setTimeout(() => setStatus({ text: '명령 없음', type: 'idle' }), 3000);
  };
  return { status, send };
}
