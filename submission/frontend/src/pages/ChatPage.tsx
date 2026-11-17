import React, { useState, useRef, useEffect } from 'react';
import {
  Sparkles,
  BookOpen,
  ShieldCheck,
  Zap,
  Trash2,
} from 'lucide-react';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { QuestionComposer } from '../components/chat/QuestionComposer';
import { ChatMessageItem } from '../components/chat/ChatMessageItem';
import { api } from '../services/api';
import type {
  ConnectionState,
  ReadyResponse,
  ChatMessage,
  AskRequest,
} from '../types/api';

interface ChatPageProps {
  connectionState: ConnectionState;
  ready: ReadyResponse | null;
}

const SUGGESTED_QUESTIONS = [
  {
    paperId: '1706.03762v7',
    paperTitle: 'Attention Is All You Need',
    question: 'What BLEU score did the Transformer base model achieve on English-to-German?',
    category: 'Hyperparameters & Metrics',
  },
  {
    paperId: '2410.00037v1',
    paperTitle: 'Moshi: Speech-Text Foundation',
    question: 'How does the Mimi neural audio codec in Moshi achieve streaming 12.5 Hz latency?',
    category: 'Architecture & Codec',
  },
  {
    paperId: '2507.07955v2',
    paperTitle: 'Dynamic Chunking',
    question: 'Why does Dynamic Chunking outperform fixed-size chunking on multi-hop retrieval?',
    category: 'Retrieval Quality',
  },
];

const CORPUS_PAPERS = [
  {
    id: '1706.03762v7',
    title: 'Attention Is All You Need',
    authors: 'Vaswani et al. (Google Brain & Research)',
    pages: 15,
    description: 'Introduces the Transformer architecture based entirely on self-attention mechanisms without recurrence or convolution.',
  },
  {
    id: '2410.00037v1',
    title: 'Moshi: Speech-Text Foundation Model',
    authors: 'Défossez et al. (Kyutai)',
    pages: 66,
    description: 'Real-time multi-stream full-duplex spoken dialogue model powered by the Mimi 12.5 Hz neural audio codec and Helium LLM.',
  },
  {
    id: '2507.07955v2',
    title: 'Dynamic Chunking for Retrieval',
    authors: 'Research Team',
    pages: 39,
    description: 'Demonstrates content-aware variable document boundary segmentation to reduce semantic fragmentation in long-context RAG.',
  },
];

export const ChatPage: React.FC<ChatPageProps> = ({ connectionState, ready }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState<string>('');
  const [selectedFilter, setSelectedFilter] = useState<string>('all');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Clean up abort controller on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const executeQuestion = async (questionText: string, filterId: string) => {
    const trimmed = questionText.trim();
    if (!trimmed || isSubmitting) return;

    const messageId = `msg-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const effectiveFilter = filterId !== 'all' ? filterId : null;

    const newTurn: ChatMessage = {
      id: messageId,
      question: trimmed,
      paperFilter: effectiveFilter,
      submittedAt: new Date(),
      status: 'loading',
    };

    setMessages((prev) => [...prev, newTurn]);
    setInput('');
    setIsSubmitting(true);

    const controller = new AbortController();
    abortControllerRef.current = controller;
    const startTime = performance.now();

    try {
      const askPayload: AskRequest = {
        question: trimmed,
        ...(effectiveFilter ? { paper_filter: effectiveFilter } : {}),
      };

      const response = await api.askQuestion(askPayload, controller.signal);
      const elapsed = Math.round(performance.now() - startTime);

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === messageId
            ? {
                ...msg,
                status: 'success',
                response,
                durationMs: elapsed,
              }
            : msg
        )
      );
    } catch (err: unknown) {
      const elapsed = Math.round(performance.now() - startTime);
      const errorMessage =
        err instanceof Error ? err.message : 'Failed to process question';

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === messageId
            ? {
                ...msg,
                status: 'error',
                error: errorMessage,
                durationMs: elapsed,
              }
            : msg
        )
      );
    } finally {
      setIsSubmitting(false);
      abortControllerRef.current = null;
    }
  };

  const handleSubmit = () => {
    executeQuestion(input, selectedFilter);
  };

  const handleSelectSuggestedQuestion = (q: string, paperId: string) => {
    setSelectedFilter(paperId);
    executeQuestion(q, paperId);
  };

  const handleRetry = (failedMsg: ChatMessage) => {
    executeQuestion(failedMsg.question, failedMsg.paperFilter || 'all');
  };

  const handleClearHistory = () => {
    setMessages([]);
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto flex flex-col min-h-[calc(100vh-8rem)]">
      {/* 1. Header Toolbar when in conversation */}
      {messages.length > 0 && (
        <div className="flex items-center justify-between pb-3 border-b border-[#E6E9EF]">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-medium text-slate-700">
              Session History: {messages.length} turn(s)
            </span>
            <span className="text-[11px] font-mono text-slate-400 hidden sm:inline">
              • In-memory session state (stateless backend)
            </span>
            <Badge variant="emerald" size="sm">
              Live Gateway Active
            </Badge>
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={handleClearHistory}
            disabled={isSubmitting}
            leftIcon={<Trash2 className="w-3.5 h-3.5" />}
            className="text-slate-500 hover:text-slate-800"
          >
            Clear Session
          </Button>
        </div>
      )}

      {/* 2. Initial Introductory State (when no messages yet) */}
      {messages.length === 0 && (
        <div className="space-y-8 my-auto py-4">
          {/* Hero Header */}
          <div className="text-center space-y-3 pt-2">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-xs font-mono text-indigo-700 font-medium">
              <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
              <span>THE RELAY • EVIDENCE-GROUNDED RESEARCH ASSISTANT</span>
            </div>

            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
              Ask technical questions across 3 engineering papers
            </h2>

            <p className="text-sm text-slate-600 max-w-2xl mx-auto leading-relaxed">
              Every answer is deterministically verified against retrieved preprint passages. Claims are accompanied by strict bracketed citations referencing arXiv version, page number, and section title.
            </p>

            {/* Feature Pills */}
            <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
              <Badge variant="emerald" size="sm" icon={<ShieldCheck className="w-3 h-3" />}>
                Deterministic Citation Checks
              </Badge>
              <Badge variant="blue" size="sm" icon={<BookOpen className="w-3 h-3" />}>
                RRF Hybrid Retrieval
              </Badge>
              <Badge variant="purple" size="sm" icon={<Zap className="w-3 h-3" />}>
                {ready?.provider ? `Provider: ${ready.provider}` : 'Traffic Managed'}
              </Badge>
            </div>
          </div>

          {/* Suggested Questions Grid */}
          <div className="space-y-3">
            <div className="flex items-center justify-between text-xs text-slate-500 font-mono px-1">
              <span>SUGGESTED RESEARCH QUERIES</span>
              <span>CLICK TO SUBMIT DIRECTLY</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {SUGGESTED_QUESTIONS.map((item, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() =>
                    handleSelectSuggestedQuestion(item.question, item.paperId)
                  }
                  disabled={isSubmitting}
                  className="p-4 rounded-xl bg-white border border-[#E6E9EF] hover:border-indigo-300 hover:shadow-xs transition-all text-left group cursor-pointer flex flex-col justify-between shadow-[0_1px_3px_rgba(0,0,0,0.03)] disabled:opacity-50"
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Badge variant="neutral" size="sm">
                        {item.category}
                      </Badge>
                      <span className="text-[10px] font-mono text-slate-400">
                        {item.paperId}
                      </span>
                    </div>
                    <p className="text-xs font-medium text-slate-800 group-hover:text-indigo-600 leading-snug line-clamp-3">
                      "{item.question}"
                    </p>
                  </div>

                  <div className="mt-3 pt-2 border-t border-[#E6E9EF] flex items-center justify-between text-[11px] text-slate-500">
                    <span className="truncate">{item.paperTitle}</span>
                    <span className="text-indigo-600 font-mono font-semibold opacity-0 group-hover:opacity-100 transition-opacity">
                      Ask →
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Target Papers Reference Grid */}
          <div className="space-y-3 pt-2">
            <div className="flex items-center gap-2 text-xs text-slate-500 font-mono">
              <BookOpen className="w-3.5 h-3.5 text-slate-400" />
              <span>TARGET RESEARCH PAPERS IN REPOSITORY</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {CORPUS_PAPERS.map((paper) => (
                <div
                  key={paper.id}
                  className="p-3.5 rounded-xl bg-white border border-[#E6E9EF] space-y-1.5 text-xs shadow-[0_1px_3px_rgba(0,0,0,0.02)]"
                >
                  <div className="flex items-center justify-between">
                    <Badge variant="blue" size="sm">
                      {paper.id}
                    </Badge>
                    <span className="font-mono text-slate-400 text-[11px]">
                      {paper.pages}p
                    </span>
                  </div>
                  <h4 className="font-semibold text-slate-900 text-xs leading-snug">
                    {paper.title}
                  </h4>
                  <p className="text-slate-500 text-[11px] leading-relaxed line-clamp-2">
                    {paper.description}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 3. Chat Turns Feed (when conversation exists) */}
      {messages.length > 0 && (
        <div className="flex-1 space-y-6">
          {messages.map((turn) => (
            <ChatMessageItem
              key={turn.id}
              message={turn}
              onRetry={handleRetry}
            />
          ))}
          <div ref={messagesEndRef} />
        </div>
      )}

      {/* 4. Persistent Question Composer */}
      <div className="sticky bottom-4 z-20 pt-2">
        <QuestionComposer
          input={input}
          onChangeInput={setInput}
          selectedFilter={selectedFilter}
          onSelectFilter={setSelectedFilter}
          onSubmit={handleSubmit}
          isSubmitting={isSubmitting}
          connectionState={connectionState}
        />
      </div>
    </div>
  );
};
