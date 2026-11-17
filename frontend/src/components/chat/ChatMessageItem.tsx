import React, { useEffect, useState } from 'react';
import {
  User,
  Sparkles,
  AlertCircle,
  RefreshCw,
  Loader2,
  FileText,
} from 'lucide-react';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { AnswerCard } from './AnswerCard';
import type { ChatMessage } from '../../types/api';

interface ChatMessageItemProps {
  message: ChatMessage;
  onRetry: (message: ChatMessage) => void;
}

function getErrorHint(error?: string): string | null {
  if (!error) return null;
  const lower = error.toLowerCase();
  if (lower.includes('connect') || lower.includes('offline') || lower.includes('network')) {
    return 'Backend service appears unreachable. Verify the FastAPI server is running on http://127.0.0.1:8000.';
  }
  if (lower.includes('rate limit') || lower.includes('429')) {
    return 'Rate limit reached on upstream provider. TrafficManager throttles requests; wait a few seconds before retrying.';
  }
  if (lower.includes('timeout') || lower.includes('504')) {
    return 'The request exceeded the processing deadline. Consider selecting a specific paper filter to focus the retrieval scope.';
  }
  if (lower.includes('queue') || lower.includes('503')) {
    return 'The backend request queue is currently at capacity. Please retry shortly.';
  }
  if (lower.includes('invalid') || lower.includes('400') || lower.includes('validation')) {
    return 'The request payload failed backend validation. Check query formatting or selected paper filter.';
  }
  return null;
}

export const ChatMessageItem: React.FC<ChatMessageItemProps> = ({
  message,
  onRetry,
}) => {
  const [elapsedSec, setElapsedSec] = useState<number>(0);
  const errorHint = getErrorHint(message.error);

  useEffect(() => {
    if (message.status !== 'loading') return;
    const interval = setInterval(() => {
      setElapsedSec((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [message.status]);

  const paperNames: Record<string, string> = {
    '1706.03762v7': 'Attention (1706.03762v7)',
    '2410.00037v1': 'Moshi (2410.00037v1)',
    '2507.07955v2': 'Dynamic Chunking (2507.07955v2)',
  };

  return (
    <div className="space-y-4 py-2">
      {/* 1. User Question Row */}
      <div className="flex items-start gap-3 justify-end">
        <div className="max-w-2xl w-full space-y-1.5 text-right">
          <div className="flex items-center justify-end gap-2 text-xs font-mono text-slate-400">
            {message.paperFilter ? (
              <Badge variant="blue" size="sm" icon={<FileText className="w-3 h-3" />}>
                Filter: {paperNames[message.paperFilter] || message.paperFilter}
              </Badge>
            ) : (
              <Badge variant="neutral" size="sm">
                Corpus: All 3 Papers
              </Badge>
            )}
            <span>{message.submittedAt.toLocaleTimeString()}</span>
          </div>

          <div className="inline-block p-4 rounded-2xl rounded-tr-xs bg-indigo-600 text-white text-sm text-left shadow-xs whitespace-pre-wrap selection:bg-indigo-400/40 font-sans leading-relaxed">
            {message.question}
          </div>
        </div>

        <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-700 shrink-0 mt-6 shadow-xs">
          <User className="w-4 h-4" />
        </div>
      </div>

      {/* 2. Assistant Response Row */}
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-white border border-[#E6E9EF] flex items-center justify-center text-indigo-600 shrink-0 mt-1 shadow-xs">
          <Sparkles className="w-4 h-4" />
        </div>

        <div className="flex-1 max-w-4xl space-y-2">
          {/* Loading State: Honest Non-Streaming Processing Indicator */}
          {message.status === 'loading' && (
            <div className="p-5 rounded-xl bg-white border border-[#E6E9EF] shadow-xs space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <Loader2 className="w-4 h-4 animate-spin text-indigo-600" />
                  <span className="text-xs font-semibold text-slate-800 font-mono">
                    Research Assistant Processing...
                  </span>
                </div>
                <span className="text-xs font-mono text-slate-400">
                  {elapsedSec}s elapsed
                </span>
              </div>

              <div className="text-xs text-slate-500 space-y-1.5 leading-relaxed font-mono">
                <p>
                  • Executing hybrid retrieval across ChromaDB (dense), Rank-BM25 (sparse), and SQLite FactStore.
                </p>
                <p>
                  • Evaluating evidence sufficiency and generating verified bracketed citations.
                </p>
              </div>

              <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
                <div className="bg-indigo-600 h-full w-2/5 animate-pulse rounded-full" />
              </div>
            </div>
          )}

          {/* Error State */}
          {message.status === 'error' && (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 shadow-xs space-y-3 text-xs">
              <div className="flex items-center gap-2 font-semibold text-rose-800 font-mono">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                <span>Request Execution Failed</span>
              </div>

              <p className="text-rose-800/90 leading-relaxed font-mono pl-6">
                {message.error || 'An unexpected failure occurred while processing this query.'}
              </p>

              {errorHint && (
                <div className="pl-6 text-[11px] text-rose-700/80 font-mono italic">
                  💡 {errorHint}
                </div>
              )}

              <div className="pl-6 pt-1">
                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => onRetry(message)}
                  leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
                >
                  Retry Question
                </Button>
              </div>
            </div>
          )}

          {/* Success State */}
          {message.status === 'success' && message.response && (
            <AnswerCard
              response={message.response}
              durationMs={message.durationMs}
            />
          )}
        </div>
      </div>
    </div>
  );
};
