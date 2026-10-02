import { type ReactNode } from "react";

interface CardProps {
  title?: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
  id?: string;
}

export function Card({ title, subtitle, children, className = "", id }: CardProps) {
  return (
    <section
      id={id}
      className={`rounded-xl border border-slate-200/80 bg-surface-card p-6 shadow-card transition-shadow duration-300 hover:shadow-cardHover ${className}`}
    >
      {(title || subtitle) && (
        <header className="mb-4 border-b border-slate-100 pb-3">
          {title && (
            <h2 className="text-lg font-semibold tracking-tight text-slate-900">
              {title}
            </h2>
          )}
          {subtitle && (
            <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>
          )}
        </header>
      )}
      {children}
    </section>
  );
}
