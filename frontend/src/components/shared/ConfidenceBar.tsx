interface ConfidenceBarProps {
  high: number;
  medium: number;
  low: number;
}

export function ConfidenceBar({ high, medium, low }: ConfidenceBarProps) {
  const total = high + medium + low || 1;
  const highPct = (high / total) * 100;
  const mediumPct = (medium / total) * 100;
  const lowPct = (low / total) * 100;

  return (
    <div className="card-custom">
      <div className="card-header">提取置信度</div>
      <div className="flex h-2 rounded-full overflow-hidden mb-3">
        <div style={{ width: `${highPct}%`, background: '#22c55e' }} />
        <div style={{ width: `${mediumPct}%`, background: '#f59e0b' }} />
        <div style={{ width: `${lowPct}%`, background: '#ef4444' }} />
      </div>
      <div className="flex gap-5 text-xs">
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full inline-block" style={{ background: '#22c55e' }} />
          <span className="text-text-2">高置信度:</span>
          <span className="text-text font-medium">{high}</span>
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full inline-block" style={{ background: '#f59e0b' }} />
          <span className="text-text-2">中置信度:</span>
          <span className="text-text font-medium">{medium}</span>
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full inline-block" style={{ background: '#ef4444' }} />
          <span className="text-text-2">低置信度:</span>
          <span className="text-text font-medium">{low}</span>
        </span>
      </div>
    </div>
  );
}
