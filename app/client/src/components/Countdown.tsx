import { useEffect, useRef, useState } from 'react';

import { formatRemaining, remainingMs, urgency, type Clock } from '../lib/timer';

export function Countdown({ deadlineAt, clock, onExpire }: { deadlineAt: string; clock: Clock; onExpire: () => void }) {
  const [ms, setMs] = useState(() => remainingMs(deadlineAt, clock));
  const fired = useRef(false);
  useEffect(() => {
    const tick = () => {
      const left = remainingMs(deadlineAt, clock);
      setMs(left);
      if (left <= 0 && !fired.current) {
        fired.current = true;
        onExpire();
      }
    };
    tick();
    const id = window.setInterval(tick, 250);
    return () => window.clearInterval(id);
  }, [deadlineAt, clock, onExpire]);
  const level = urgency(ms);
  return (
    <div className={`countdown ${level === 'calm' ? '' : level}`} role="timer" aria-live={level === 'calm' ? 'off' : 'polite'} aria-label="Time remaining">
      {formatRemaining(ms)}
    </div>
  );
}
