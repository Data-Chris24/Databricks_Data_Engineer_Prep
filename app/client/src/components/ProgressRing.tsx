export function ProgressRing({ percent, size = 112 }: { percent: number; size?: number }) {
  const r = size * 0.43;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, percent));
  const offset = c * (1 - clamped / 100);
  return (
    <svg className="ring" width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`${clamped}% complete`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--raised)" strokeWidth={size * 0.09} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="var(--accent)"
        strokeWidth={size * 0.09}
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={offset}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dashoffset .5s ease' }}
      />
      <text
        x="50%"
        y="47%"
        textAnchor="middle"
        fontFamily="var(--cond)"
        fontWeight={700}
        fontSize={size * 0.25}
        fill="var(--ink)"
      >
        {clamped}%
      </text>
      <text
        x="50%"
        y="63%"
        textAnchor="middle"
        fontFamily="var(--mono)"
        fontSize={size * 0.09}
        fill="var(--ink-mute)"
      >
        COMPLETE
      </text>
    </svg>
  );
}
