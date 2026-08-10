import type { ReactNode } from "react";

interface MetricProps {
  label: string;
  value?: string;
  valueNode?: ReactNode;
  className?: string;
}

export default function Metric({ label, value, valueNode, className = "" }: MetricProps) {
  return (
    <div className={`flex items-center justify-between text-sm ${className}`}>
      <span className="text-text-muted">{label}</span>
      <span className="font-semibold text-text">{valueNode ?? value}</span>
    </div>
  );
}
