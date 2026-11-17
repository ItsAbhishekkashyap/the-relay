import React, { useState } from 'react';
import { ShieldCheck, AlertTriangle, ChevronDown, ChevronUp, BookOpen } from 'lucide-react';
import { Badge } from '../ui/Badge';
import type { Citation } from '../../types/api';

interface CitationListProps {
  citations: Citation[];
}

const KNOWN_TITLES: Record<string, string> = {
  '1706.03762v7': 'Attention Is All You Need',
  '1706.03762': 'Attention Is All You Need',
  '2410.00037v1': 'Moshi: A Speech-Text Foundation Model for Real-Time Dialogue',
  '2410.00037': 'Moshi: A Speech-Text Foundation Model for Real-Time Dialogue',
  '2507.07955v2': 'Dynamic Chunking for End-to-End Hierarchical Sequence Modeling',
  '2507.07955': 'Dynamic Chunking for End-to-End Hierarchical Sequence Modeling',
};

function parsePaperIdAndVersion(rawId?: string | null): { arxivId: string; version: string | null } {
  if (!rawId) return { arxivId: '—', version: null };
  const match = rawId.match(/^(\d{4}\.\d{4,5})(v\d+)?$/i);
  if (match) {
    return {
      arxivId: match[1],
      version: match[2] ? match[2].toLowerCase() : null,
    };
  }
  return { arxivId: rawId, version: null };
}

export const CitationList: React.FC<CitationListProps> = ({ citations }) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);

  if (!citations || citations.length === 0) {
    return (
      <div className="text-xs text-slate-400 italic font-mono py-1">
        No formal citations provided in this response.
      </div>
    );
  }

  const verifiedCount = citations.filter((c) => c.is_verified).length;

  return (
    <div className="space-y-2 pt-2 border-t border-[#E6E9EF]">
      {/* Header with expand toggle */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen className="w-3.5 h-3.5 text-slate-500" />
          <span className="text-xs font-semibold text-slate-800 font-mono">
            Traceable Citations ({citations.length})
          </span>
          <Badge
            variant={verifiedCount === citations.length ? 'emerald' : 'amber'}
            size="sm"
          >
            {verifiedCount}/{citations.length} Verified
          </Badge>
        </div>

        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-xs font-mono text-slate-500 hover:text-slate-800 flex items-center gap-1 transition-colors cursor-pointer"
        >
          <span>{isExpanded ? 'Hide Details' : 'View Citations'}</span>
          {isExpanded ? (
            <ChevronUp className="w-3.5 h-3.5" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5" />
          )}
        </button>
      </div>

      {/* Citation Chips Summary (always visible when collapsed) */}
      {!isExpanded && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {citations.map((citation, idx) => {
            const { arxivId, version } = parsePaperIdAndVersion(citation.paper_id);
            return (
              <div
                key={idx}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-mono border transition-colors ${
                  citation.is_verified
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                    : 'bg-rose-50 border-rose-200 text-rose-800'
                }`}
              >
                {citation.is_verified ? (
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                ) : (
                  <AlertTriangle className="w-3.5 h-3.5 text-rose-600 shrink-0" />
                )}
                <span className="truncate max-w-[240px]">
                  arXiv:{arxivId}{version ? version : ''}
                  {citation.page_number ? `, p. ${citation.page_number}` : ''}
                  {citation.section ? `, Sec ${citation.section}` : ''}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Expanded Citation Cards */}
      {isExpanded && (
        <div className="space-y-2 pt-2">
          {citations.map((citation, idx) => {
            const { arxivId, version } = parsePaperIdAndVersion(citation.paper_id);
            const title =
              citation.paper_title ||
              (citation.paper_id ? KNOWN_TITLES[citation.paper_id] : null) ||
              'Target Research Paper';

            return (
              <div
                key={idx}
                className="p-3 rounded-lg bg-[#F9FAFB] border border-[#E6E9EF] space-y-2 text-xs font-mono"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <span className="font-semibold text-slate-900 font-sans text-xs">
                      [{idx + 1}] {title}
                    </span>
                  </div>
                  <Badge
                    variant={citation.is_verified ? 'emerald' : 'rose'}
                    size="sm"
                    icon={
                      citation.is_verified ? (
                        <ShieldCheck className="w-3 h-3" />
                      ) : (
                        <AlertTriangle className="w-3 h-3" />
                      )
                    }
                  >
                    {citation.is_verified ? 'Verified Provenance' : 'Unverified'}
                  </Badge>
                </div>

                {/* Provenance Metadata Details */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] text-slate-500 pt-1 border-t border-[#E6E9EF]">
                  <div>
                    <span className="text-slate-400">Paper Title: </span>
                    <span className="text-slate-700 font-sans block truncate" title={title}>
                      {title}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400">arXiv ID & Version: </span>
                    <span className="text-slate-700 block">
                      {arxivId} {version ? <span className="text-indigo-600 font-bold">({version})</span> : ''}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400">Page: </span>
                    <span className="text-slate-700 block">
                      {citation.page_number !== null && citation.page_number !== undefined
                        ? `Page ${citation.page_number}`
                        : '—'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400">Section: </span>
                    <span className="text-slate-700 block truncate" title={citation.section || '—'}>
                      {citation.section || '—'}
                    </span>
                  </div>
                </div>

                {/* Raw Citation Text */}
                <div className="text-[11px] text-slate-600 bg-white p-2 rounded border border-[#E6E9EF] break-words">
                  <span className="text-slate-400 select-none">Raw Citation: </span>
                  <code className="text-slate-800 font-mono">{citation.raw_text}</code>
                </div>

                {/* Verification Error Notice if present */}
                {citation.verification_error && (
                  <div className="text-[11px] text-rose-700 bg-rose-50 p-2 rounded border border-rose-200">
                    <span className="font-semibold">Verification Note: </span>
                    {citation.verification_error}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
