interface CardProps {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
  noPadding?: boolean;
}

export default function Card({ children, className = "", hover = false, noPadding = false }: CardProps) {
  return (
    <div
      className={`bg-slate-900 rounded-xl ring-1 ring-white/[0.08] ${hover ? "hover:ring-white/[0.15] transition-all duration-200" : ""} ${noPadding ? "" : "px-5 py-4"} ${className}`}
    >
      {children}
    </div>
  );
}
