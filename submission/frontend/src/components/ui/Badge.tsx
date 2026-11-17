import React from 'react';

export type BadgeVariant =
  | 'neutral'
  | 'emerald'
  | 'amber'
  | 'rose'
  | 'blue'
  | 'purple'
  | 'outline';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: 'sm' | 'md';
  icon?: React.ReactNode;
  title?: string;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  size = 'md',
  icon,
  title,
  className = '',
}) => {
  const variantClasses: Record<BadgeVariant, string> = {
    neutral: 'bg-slate-100 text-slate-700 border-slate-200/90',
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200/90',
    amber: 'bg-amber-50 text-amber-800 border-amber-200/90',
    rose: 'bg-rose-50 text-rose-700 border-rose-200/90',
    blue: 'bg-sky-50 text-sky-700 border-sky-200/90',
    purple: 'bg-indigo-50 text-indigo-700 border-indigo-200/90',
    outline: 'bg-transparent text-slate-600 border-slate-300',
  };

  const sizeClasses = {
    sm: 'text-[11px] px-2 py-0.5 tracking-wide',
    md: 'text-xs px-2.5 py-1 tracking-normal',
  };

  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1.5 font-medium rounded-md border font-mono ${sizeClasses[size]} ${variantClasses[variant]} ${className}`}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      <span>{children}</span>
    </span>
  );
};
