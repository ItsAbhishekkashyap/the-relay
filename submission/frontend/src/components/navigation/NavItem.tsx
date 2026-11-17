import React from 'react';
import type { NavigationTab } from '../../types/api';

interface NavItemProps {
  id: NavigationTab;
  label: string;
  icon: React.ReactNode;
  isActive: boolean;
  badge?: string;
  onClick: (id: NavigationTab) => void;
}

export const NavItem: React.FC<NavItemProps> = ({
  id,
  label,
  icon,
  isActive,
  badge,
  onClick,
}) => {
  return (
    <button
      type="button"
      onClick={() => onClick(id)}
      className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all text-left select-none cursor-pointer group ${
        isActive
          ? 'bg-indigo-50 text-indigo-700 border border-indigo-100/90 shadow-xs'
          : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80 border border-transparent'
      }`}
    >
      <span
        className={`shrink-0 transition-colors ${
          isActive ? 'text-indigo-600' : 'text-slate-400 group-hover:text-slate-600'
        }`}
      >
        {icon}
      </span>
      <span className="flex-1 truncate font-medium">{label}</span>
      {badge && (
        <span
          className={`text-[10px] uppercase font-mono px-1.5 py-0.5 rounded font-semibold tracking-wider ${
            isActive
              ? 'bg-indigo-100/80 text-indigo-700'
              : 'bg-slate-100 text-slate-500'
          }`}
        >
          {badge}
        </span>
      )}
    </button>
  );
};
