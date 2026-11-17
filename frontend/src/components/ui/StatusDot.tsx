import React from 'react';
import type { ConnectionState } from '../../types/api';

interface StatusDotProps {
  state: ConnectionState;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const StatusDot: React.FC<StatusDotProps> = ({
  state,
  size = 'md',
  className = '',
}) => {
  const sizeClasses = {
    sm: 'w-2 h-2',
    md: 'w-2.5 h-2.5',
    lg: 'w-3 h-3',
  };

  const pingSizes = {
    sm: 'w-2 h-2',
    md: 'w-2.5 h-2.5',
    lg: 'w-3 h-3',
  };

  const colorClasses: Record<ConnectionState, { dot: string; ping?: string }> = {
    connected: {
      dot: 'bg-emerald-500',
      ping: 'bg-emerald-400',
    },
    checking: {
      dot: 'bg-amber-400',
      ping: 'bg-amber-300',
    },
    disconnected: {
      dot: 'bg-rose-500',
    },
    error: {
      dot: 'bg-rose-500',
    },
  };

  const colors = colorClasses[state] || colorClasses.disconnected;

  return (
    <span className={`relative inline-flex items-center justify-center ${className}`}>
      {(state === 'connected' || state === 'checking') && (
        <span
          className={`absolute inline-flex ${pingSizes[size]} rounded-full opacity-75 animate-ping ${colors.ping}`}
        />
      )}
      <span
        className={`relative inline-flex ${sizeClasses[size]} rounded-full ${colors.dot}`}
      />
    </span>
  );
};
