import type { Exam } from '../../../shared/types';

export interface RailSection {
  id: string;
  accuracy: number; // 0..1
  seen: number;
  total: number;
}

/** Bar width = share of the real exam. Fill = your accuracy. Click one to focus. */
export function ReadinessRail({
  exam,
  stats,
  selected,
  onSelect,
}: {
  exam: Exam;
  stats: Record<string, RailSection>;
  selected: string | null;
  onSelect: (sectionId: string | null) => void;
}) {
  return (
    <section className="rail">
      <div className="rail-head">
        <span className="rail-title">Readiness by section</span>
        <span className="muted">Bar width = share of the real exam. Fill = your accuracy. Click one to focus.</span>
      </div>
      <div className="bars">
        {exam.sections.map((s) => {
          const a = stats[s.id] ?? { accuracy: 0, seen: 0, total: 0 };
          const h = a.seen ? Math.max(6, Math.round(a.accuracy * 100)) : 0;
          return (
            <button
              key={s.id}
              type="button"
              className="bar"
              style={{ flex: s.weight }}
              aria-pressed={selected === s.id}
              title={`${s.title} — ${s.weight}% of the exam, ${a.total} questions`}
              onClick={() => onSelect(selected === s.id ? null : s.id)}
            >
              <div className="fill" style={{ height: `${h}%` }} />
              <span className="tag">
                <span className="code">S{s.number}</span>
                <span className="pct">{s.weight}%</span>
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
