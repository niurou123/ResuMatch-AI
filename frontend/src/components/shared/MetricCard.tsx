interface MetricCardProps {
  label: string;
  value: number | string;
}

export function MetricCard({ label, value }: MetricCardProps) {
  return (
    <div className="metric-card">
      <p className="text-text-3 text-[0.7rem] font-medium uppercase tracking-wider mb-1">
        {label}
      </p>
      <p className="text-text text-2xl font-bold">{value}</p>
    </div>
  );
}
