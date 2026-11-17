import React, { useState } from 'react';
import {
  ShieldCheck,
  AlertTriangle,
  HelpCircle,
  Copy,
  Check,
  Cpu,
  Clock,
  Wrench,
  Terminal,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { Badge } from '../ui/Badge';
import { CitationList } from './CitationList';
import { EvidencePanel } from './EvidencePanel';
import type { AskResponse } from '../../types/api';

interface AnswerCardProps {
  response: AskResponse;
  durationMs?: number;
}

export const AnswerCard: React.FC<AnswerCardProps> = ({ response, durationMs }) => {
  const [copiedId, setCopiedId] = useState<boolean>(false);
  const [showMetadata, setShowMetadata] = useState<boolean>(false);

  const handleCopyRequestId = () => {
    navigator.clipboard.writeText(response.request_id);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  };

  const isRefusal = response.status === 'refused';

  const statusConfig = {
    verified: {
      badge: 'emerald' as const,
      label: 'Verified Provenance',
      icon: <ShieldCheck className="w-3.5 h-3.5" />,
      border: 'border-emerald-200',
      headerBg: 'bg-emerald-50/70 border-b border-emerald-100',
    },
    refused: {
      badge: 'amber' as const,
      label: 'Grounded Refusal',
      icon: <AlertTriangle className="w-3.5 h-3.5" />,
      border: 'border-amber-200',
      headerBg: 'bg-amber-50/70 border-b border-amber-100',
    },
    unverified: {
      badge: 'neutral' as const,
      label: 'Unverified Citation',
      icon: <HelpCircle className="w-3.5 h-3.5" />,
      border: 'border-slate-200',
      headerBg: 'bg-slate-50 border-b border-slate-200',
    },
  };

  const currentStatus =
    statusConfig[response.status as keyof typeof statusConfig] ||
    statusConfig.unverified;

  return (
    <div
      className={`rounded-xl bg-white border ${currentStatus.border} shadow-[0_1px_3px_rgba(0,0,0,0.04)] overflow-hidden text-slate-800 transition-colors`}
    >
      {/* Top Diagnostics & Metadata Bar */}
      <div
        className={`px-4 sm:px-5 py-3 ${currentStatus.headerBg} flex flex-wrap items-center justify-between gap-2`}
      >
        <div className="flex flex-wrap items-center gap-2">
          {/* Status Badge */}
          <Badge
            variant={currentStatus.badge}
            size="md"
            icon={currentStatus.icon}
          >
            {currentStatus.label}
          </Badge>

          {/* Provider Badge */}
          {response.provider && (
            <Badge
              variant={response.provider === 'simulator' ? 'purple' : 'blue'}
              size="sm"
              icon={<Cpu className="w-3 h-3" />}
            >
              {response.provider}
            </Badge>
          )}

          {/* Auto-Correction Badge */}
          {response.correction_occurred && (
            <Badge
              variant="amber"
              size="sm"
              icon={<Wrench className="w-3 h-3" />}
              title="Citations were automatically revised via the bounded single-attempt correction loop"
            >
              Auto-Corrected
            </Badge>
          )}
        </div>

        {/* Request ID & Duration */}
        <div className="flex items-center gap-3 text-xs font-mono text-slate-500">
          {durationMs !== undefined && (
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3 text-slate-400" />
              <span>{(durationMs / 1000).toFixed(2)}s</span>
            </span>
          )}

          <button
            type="button"
            onClick={handleCopyRequestId}
            className="flex items-center gap-1 hover:text-slate-900 transition-colors cursor-pointer"
            title="Copy Request ID"
          >
            <span className="truncate max-w-[120px]">
              ID: {response.request_id.slice(0, 8)}...
            </span>
            {copiedId ? (
              <Check className="w-3 h-3 text-emerald-600" />
            ) : (
              <Copy className="w-3 h-3" />
            )}
          </button>
        </div>
      </div>

      {/* Provenance Verification Note Bar */}
      <div className="px-4 sm:px-5 py-2 bg-slate-50/70 border-b border-[#E6E9EF] flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-[11px] font-mono text-slate-500">
        <div className="flex items-center gap-1.5">
          <ShieldCheck className="w-3 h-3 text-emerald-600 shrink-0" />
          <span className="text-slate-700 font-semibold">Provenance Validation:</span>
          <span>
            {response.status === 'verified'
              ? 'Cited paper, page, and section confirmed present in retrieved evidence.'
              : response.status === 'refused'
              ? 'Question refused due to insufficient or out-of-domain evidence.'
              : 'One or more citations could not be matched with retrieved evidence.'}
          </span>
        </div>
        <span className="text-slate-400 text-[10px]">
          (Validates document metadata • Not automated semantic proof)
        </span>
      </div>

      {/* Main Answer Body */}
      <div className="p-4 sm:p-5 space-y-4">
        {/* Explicit Refusal Banner if refused */}
        {isRefusal && (
          <div className="p-3.5 rounded-lg bg-amber-50 border border-amber-200 space-y-1.5 text-xs text-amber-900">
            <div className="flex items-center gap-2 font-semibold text-amber-800 font-mono">
              <AlertTriangle className="w-4 h-4 shrink-0 text-amber-600" />
              <span>Explicit Workflow Refusal</span>
            </div>
            <p className="text-amber-800/90 leading-relaxed pl-6">
              The research workflow evaluated the evidence retrieved from the 3 approved papers and concluded that sufficient factual support is not available to answer this question accurately.
            </p>
            {response.refusal_reason && (
              <div className="pl-6 pt-1 font-mono text-[11px] text-amber-700">
                Reason: {response.refusal_reason}
              </div>
            )}
          </div>
        )}

        {/* Answer Text */}
        <div className="text-sm text-slate-800 leading-relaxed font-sans whitespace-pre-wrap selection:bg-indigo-100">
          {response.answer}
        </div>

        {/* Traceable Citations Component */}
        <CitationList citations={response.citations} />

        {/* Retrieved Evidence Panel */}
        <EvidencePanel
          passages={response.retrieved_passages}
          citations={response.citations}
        />

        {/* Workflow Diagnostics Collapsible */}
        {response.workflow_metadata &&
          Object.keys(response.workflow_metadata).length > 0 && (
            <div className="pt-2 border-t border-[#E6E9EF]">
              <button
                type="button"
                onClick={() => setShowMetadata(!showMetadata)}
                className="text-xs font-mono text-slate-500 hover:text-slate-800 flex items-center gap-1.5 transition-colors cursor-pointer"
              >
                <Terminal className="w-3.5 h-3.5 text-slate-400" />
                <span>
                  {showMetadata ? 'Hide Workflow Diagnostics' : 'Workflow Diagnostics'}
                </span>
                {showMetadata ? (
                  <ChevronUp className="w-3.5 h-3.5" />
                ) : (
                  <ChevronDown className="w-3.5 h-3.5" />
                )}
              </button>

              {showMetadata && (
                <div className="mt-2 p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs font-mono text-slate-700 overflow-x-auto max-h-48">
                  <pre>{JSON.stringify(response.workflow_metadata, null, 2)}</pre>
                </div>
              )}
            </div>
          )}
      </div>
    </div>
  );
};
