import React, { useRef, useEffect } from 'react';
import { Send, AlertCircle, FileText } from 'lucide-react';
import { Button } from '../ui/Button';
import type { ConnectionState } from '../../types/api';

interface QuestionComposerProps {
  input: string;
  onChangeInput: (val: string) => void;
  selectedFilter: string;
  onSelectFilter: (filter: string) => void;
  onSubmit: () => void;
  isSubmitting: boolean;
  connectionState: ConnectionState;
}

const PAPER_OPTIONS = [
  { id: 'all', label: 'All 3 Papers', paperId: null },
  { id: '1706.03762v7', label: '1706.03762v7 (Attention)', paperId: '1706.03762v7' },
  { id: '2410.00037v1', label: '2410.00037v1 (Moshi)', paperId: '2410.00037v1' },
  { id: '2507.07955v2', label: '2507.07955v2 (Chunking)', paperId: '2507.07955v2' },
];

export const QuestionComposer: React.FC<QuestionComposerProps> = ({
  input,
  onChangeInput,
  selectedFilter,
  onSelectFilter,
  onSubmit,
  isSubmitting,
  connectionState,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-focus on mount
  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (input.trim() && !isSubmitting) {
        onSubmit();
      }
    }
  };

  const isInputEmpty = !input.trim();
  const isBackendOffline = connectionState === 'disconnected';

  return (
    <div className="rounded-xl bg-white border border-[#E6E9EF] shadow-[0_1px_3px_rgba(0,0,0,0.04)] p-3 sm:p-4 space-y-3 transition-colors">
      {/* Paper Filter Pills */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
        <span className="text-slate-500 font-mono text-[11px] mr-1 shrink-0 flex items-center gap-1">
          <FileText className="w-3.5 h-3.5 text-slate-400" />
          Filter:
        </span>
        {PAPER_OPTIONS.map((opt) => {
          const isActive = selectedFilter === opt.id;
          return (
            <button
              key={opt.id}
              type="button"
              onClick={() => onSelectFilter(opt.id)}
              disabled={isSubmitting}
              className={`px-2.5 py-1 rounded-md text-xs font-mono transition-colors shrink-0 cursor-pointer disabled:opacity-50 ${
                isActive
                  ? 'bg-indigo-50 text-indigo-700 border border-indigo-200/90 font-medium'
                  : 'bg-slate-100 text-slate-600 hover:text-slate-900 hover:bg-slate-200/70 border border-slate-200/70'
              }`}
            >
              {opt.label}
            </button>
          );
        })}
      </div>

      {/* Controlled Textarea */}
      <div className="relative">
        <textarea
          ref={textareaRef}
          rows={3}
          value={input}
          onChange={(e) => onChangeInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isSubmitting}
          aria-label="Research Question Input"
          placeholder="Ask a research question regarding attention formulas, neural codec frames, or chunking evaluations... (Enter to send, Shift+Enter for newline)"
          className="w-full bg-[#F9FAFB] border border-[#E6E9EF] rounded-lg p-3 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:border-indigo-400 focus:bg-white focus:ring-2 focus:ring-indigo-500/10 resize-none font-sans disabled:opacity-60 transition-all"
        />
      </div>

      {/* Footer Actions & Status */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pt-1">
        {/* Offline Warning or Grounding Hint */}
        <div className="flex items-center gap-2 text-xs font-mono">
          {isBackendOffline ? (
            <div className="flex items-center gap-1.5 text-rose-600">
              <AlertCircle className="w-3.5 h-3.5 shrink-0" />
              <span>Backend API is currently offline. Start server to query.</span>
            </div>
          ) : (
            <span className="text-slate-400 text-[11px]">
              Answers strictly grounded in 3 arXiv PDFs with verified citations
            </span>
          )}
        </div>

        {/* Submit Button */}
        <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
          <Button
            variant="primary"
            size="md"
            onClick={onSubmit}
            disabled={isInputEmpty || isSubmitting || isBackendOffline}
            isLoading={isSubmitting}
            rightIcon={!isSubmitting ? <Send className="w-3.5 h-3.5" /> : undefined}
            className="w-full sm:w-auto min-w-[130px]"
          >
            {isSubmitting ? 'Consulting...' : 'Ask Question'}
          </Button>
        </div>
      </div>
    </div>
  );
};
