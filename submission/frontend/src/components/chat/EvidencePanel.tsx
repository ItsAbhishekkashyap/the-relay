import React, { useState } from 'react';
import { Database, ChevronDown, ChevronUp, Copy, Check, ShieldCheck } from 'lucide-react';
import { Badge } from '../ui/Badge';
import type { RetrievedDocument, Citation } from '../../types/api';

interface EvidencePanelProps {
  passages: RetrievedDocument[];
  citations?: Citation[];
}

function isPassageCited(doc: RetrievedDocument, citations?: Citation[]): boolean {
  if (!citations || citations.length === 0) return false;

  const docPaperId = (doc.paper_id || '').toLowerCase().trim();
  const docArxivId = (doc.arxiv_id || '').toLowerCase().trim();
  const docTitle = (doc.paper_title || '').toLowerCase().trim();
  const docPages = doc.page_numbers && doc.page_numbers.length > 0 
    ? doc.page_numbers 
    : (doc.page_number !== null && doc.page_number !== undefined ? [doc.page_number] : []);
  const docSec = (doc.section || '').toLowerCase().trim();

  return citations.some((c) => {
    const citPaperId = (c.paper_id || '').toLowerCase().trim();
    const citTitle = (c.paper_title || '').toLowerCase().trim();
    const citSec = (c.section || '').toLowerCase().trim();

    // Check paper match
    const paperMatches =
      (citPaperId && (docPaperId.includes(citPaperId) || citPaperId.includes(docPaperId) || docArxivId.includes(citPaperId))) ||
      (citTitle && docTitle && (docTitle.includes(citTitle) || citTitle.includes(docTitle)));

    if (!paperMatches) return false;

    // Check page match if citation specifies page
    if (c.page_number !== null && c.page_number !== undefined) {
      if (docPages.length > 0 && !docPages.includes(c.page_number)) {
        return false;
      }
    }

    // Check section match if both citation and passage specify section
    if (citSec && docSec) {
      const secNormalizedCit = citSec.replace(/^(section|sec\.?)\s*/i, '');
      const secNormalizedDoc = docSec.replace(/^(section|sec\.?)\s*/i, '');
      if (
        !secNormalizedDoc.includes(secNormalizedCit) &&
        !secNormalizedCit.includes(secNormalizedDoc)
      ) {
        return false;
      }
    }

    return true;
  });
}

export const EvidencePanel: React.FC<EvidencePanelProps> = ({ passages, citations = [] }) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  if (!passages || passages.length === 0) {
    return (
      <div className="text-xs text-slate-400 italic font-mono py-1">
        No evidence passages returned for this query.
      </div>
    );
  }

  const citedCount = passages.filter((p) => isPassageCited(p, citations)).length;

  const handleCopyPassage = (content: string, index: number) => {
    navigator.clipboard.writeText(content);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  return (
    <div className="space-y-2 pt-2 border-t border-[#E6E9EF]">
      {/* Header Bar with Toggle */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Database className="w-3.5 h-3.5 text-slate-500" />
          <span className="text-xs font-semibold text-slate-800 font-mono">
            Retrieved Evidence Chunks ({passages.length})
          </span>
          <Badge variant="blue" size="sm">
            RRF Hybrid
          </Badge>
          {citedCount > 0 && (
            <Badge variant="emerald" size="sm" icon={<ShieldCheck className="w-3 h-3" />}>
              {citedCount} Cited in Response
            </Badge>
          )}
        </div>

        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-xs font-mono text-slate-500 hover:text-slate-800 flex items-center gap-1 transition-colors cursor-pointer"
        >
          <span>{isExpanded ? 'Collapse Evidence' : 'Inspect Evidence'}</span>
          {isExpanded ? (
            <ChevronUp className="w-3.5 h-3.5" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5" />
          )}
        </button>
      </div>

      {/* Summary Line when collapsed */}
      {!isExpanded && (
        <div className="text-[11px] text-slate-500 font-mono flex items-center gap-2">
          <span>
            {passages.length} evidence passages retrieved across{' '}
            {new Set(passages.map((p) => p.paper_id)).size} paper(s)
            {citedCount > 0 ? ` (${citedCount} directly cited)` : ''}
          </span>
          <span className="text-slate-300">•</span>
          <span className="text-slate-400">Click 'Inspect Evidence' to read full context</span>
        </div>
      )}

      {/* Expanded Passages Container */}
      {isExpanded && (
        <div className="space-y-3 pt-2">
          {passages.map((doc, idx) => {
            const isCited = isPassageCited(doc, citations);
            return (
              <div
                key={doc.chunk_id || idx}
                className={`p-3.5 rounded-lg border space-y-2 text-xs transition-colors ${
                  isCited
                    ? 'bg-emerald-50/40 border-emerald-200 shadow-2xs'
                    : 'bg-[#F9FAFB] border-[#E6E9EF]'
                }`}
              >
                {/* Top Metadata Row */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 pb-2 border-b border-[#E6E9EF]">
                  <div className="flex items-center gap-2">
                    <span
                      className={`px-1.5 py-0.5 rounded font-mono font-bold text-[10px] ${
                        isCited
                          ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                          : 'bg-slate-200 text-slate-700'
                      }`}
                    >
                      #{idx + 1}
                    </span>
                    <span className="font-semibold text-slate-900 font-mono truncate max-w-[280px]">
                      {doc.paper_title || doc.paper_id}
                    </span>
                    {isCited ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
                        <ShieldCheck className="w-2.5 h-2.5" />
                        Cited Passage
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-100 text-slate-600 border border-slate-200">
                        Retrieved Context
                      </span>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-1.5 text-[10.5px] font-mono">
                    {/* Channels Badge */}
                    {doc.retrieval_channels && doc.retrieval_channels.length > 0 && (
                      <span className="px-2 py-0.5 rounded bg-white text-slate-700 border border-[#E6E9EF] uppercase">
                        {doc.retrieval_channels.join(' + ')}
                      </span>
                    )}
                    {/* Page and Section Badge */}
                    <span className="px-2 py-0.5 rounded bg-white text-slate-700 border border-[#E6E9EF]">
                      p. {doc.page_number ?? (doc.page_numbers?.length ? doc.page_numbers.join(', ') : '—')}
                      {doc.section ? ` • Sec ${doc.section}` : ''}
                    </span>
                    {/* Score */}
                    {doc.score !== undefined && (
                      <span className="text-slate-500">
                        score: {Number(doc.score).toFixed(4)}
                      </span>
                    )}
                  </div>
                </div>

                {/* Passage Content Box */}
                <div className="relative group">
                  <div className="p-3 rounded bg-white border border-[#E6E9EF] font-mono text-[11.5px] text-slate-800 leading-relaxed max-h-56 overflow-y-auto whitespace-pre-wrap selection:bg-indigo-100">
                    {doc.content}
                  </div>

                  {/* Copy button */}
                  <button
                    type="button"
                    onClick={() => handleCopyPassage(doc.content, idx)}
                    className="absolute top-2 right-2 p-1.5 rounded bg-slate-100 text-slate-600 hover:text-slate-900 hover:bg-slate-200 transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100 cursor-pointer shadow-xs border border-slate-200 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                    title="Copy passage content"
                    aria-label={`Copy passage #${idx + 1}`}
                  >
                    {copiedIndex === idx ? (
                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>

                {/* Provenance Footer */}
                <div className="flex items-center justify-between text-[10.5px] text-slate-500 font-mono">
                  <span className="truncate">Chunk: {doc.chunk_id}</span>
                  <span>arXiv:{doc.arxiv_id || doc.paper_id}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
