"use client";
import { useEffect, useState, useMemo } from "react";
import { Subject, Topic, VectorChunk, VectorSearchResult } from "@/lib/types";
import { api } from "@/lib/api";
import {
  Search,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  BookOpen,
  Filter,
  Copy,
  Check,
} from "lucide-react";

export function VectorStoreManager({ subject }: { subject?: Subject }) {
  const [chunks, setChunks] = useState<VectorChunk[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<VectorSearchResult[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [topics, setTopics] = useState<Topic[]>([]);
  const [selectedTopicId, setSelectedTopicId] = useState<string>("all");
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const size = 15;

  // Load subject topics for the dropdown selector
  useEffect(() => {
    if (!subject?.subject_id) return;
    api
      .getTopics(subject.subject_id)
      .then(setTopics)
      .catch(() => setTopics([]));
  }, [subject?.subject_id]);

  // Reset pagination & filters when switching subjects
  useEffect(() => {
    setPage(0);
    setQuery("");
    setResults(null);
    setSelectedTopicId("all");
    setExpandedIds(new Set());
  }, [subject?.subject_id]);

  // Fetch paginated chunks & collection stats
  useEffect(() => {
    let alive = true;
    if (!subject) return;
    setBusy(true);
    setError("");

    Promise.all([
      api.getChunks(subject.subject_key, page * size, size),
      api.getCollectionStats(subject.subject_key),
    ])
      .then(([rows, stats]) => {
        if (alive) {
          setChunks(rows);
          setTotal(stats.total_chunks);
        }
      })
      .catch((e) => {
        if (alive) setError(e.message);
      })
      .finally(() => {
        if (alive) setBusy(false);
      });

    return () => {
      alive = false;
    };
  }, [subject?.subject_key, page]);

  if (!subject) {
    return <p className="text-zinc-400">Select a course to inspect its knowledge base.</p>;
  }

  const rawItems = results ?? chunks;

  // Filter items by chapter dropdown if selected
  const filteredItems = useMemo(() => {
    if (selectedTopicId === "all") return rawItems;
    const targetTopic = topics.find((t) => String(t.topic_id) === selectedTopicId);
    return rawItems.filter((item) => {
      const itemTopicId = item.metadata?.topic_id;
      if (itemTopicId !== undefined && String(itemTopicId) === selectedTopicId) {
        return true;
      }
      if (targetTopic && item.metadata?.chapter) {
        const cleanCh = item.metadata.chapter.toLowerCase().replace(/^\d+\.\s*/, "");
        const cleanT = targetTopic.topic_name.toLowerCase().replace(/^\d+\.\s*/, "");
        return cleanCh.includes(cleanT) || cleanT.includes(cleanCh);
      }
      return false;
    });
  }, [rawItems, selectedTopicId, topics]);

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (expandedIds.size === filteredItems.length) {
      setExpandedIds(new Set());
    } else {
      setExpandedIds(new Set(filteredItems.map((i) => i.id)));
    }
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    setError("");
    try {
      const res = await api.searchVectors(subject.subject_key, query, 10);
      setResults(res.results);
      setPage(0);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / size));

  return (
    <section className="w-full max-w-6xl mx-auto space-y-4">
      {/* Header Info */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-3">
        <div>
          <p className="text-xs text-orange-400 font-medium">Knowledge Base Manager</p>
          <h1 className="text-xl font-semibold text-zinc-100">{subject.subject_name}</h1>
        </div>
        <div className="flex items-center gap-2 text-xs text-zinc-400">
          <span className="px-2.5 py-1 rounded-md bg-zinc-900 border border-zinc-800">
            {total.toLocaleString()} total passages
          </span>
          {results !== null && (
            <span className="px-2.5 py-1 rounded-md bg-orange-950/60 border border-orange-500/40 text-orange-300">
              {results.length} search matches
            </span>
          )}
        </div>
      </div>

      {/* Clean Filters & Controls Toolbar */}
      <div className="flex flex-wrap items-center gap-2.5 bg-zinc-900/60 p-2.5 rounded-xl border border-zinc-800">
        {/* Chapter Filter Dropdown */}
        <div className="flex items-center gap-1.5 min-w-[200px] flex-1 sm:flex-initial">
          <Filter className="h-3.5 w-3.5 text-zinc-500 shrink-0 ml-1" />
          <select
            aria-label="Filter passages by chapter"
            value={selectedTopicId}
            onChange={(e) => setSelectedTopicId(e.target.value)}
            className="w-full bg-zinc-950 border border-zinc-700/80 rounded-lg px-2.5 py-1.5 text-xs text-zinc-200 focus:outline-none focus:border-orange-500 cursor-pointer"
          >
            <option value="all">All Chapters ({topics.length || totalPages})</option>
            {topics.map((t) => (
              <option key={t.topic_id} value={String(t.topic_id)}>
                {t.topic_name.replace(/^\d+\.\s*/, "")}
              </option>
            ))}
          </select>
        </div>

        {/* Search Bar */}
        <form onSubmit={handleSearch} className="flex items-center gap-2 flex-1 min-w-[240px]">
          <div className="relative flex-1">
            <input
              aria-label="Search course material"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search concepts, formulas, keywords..."
              className="w-full bg-zinc-950 border border-zinc-700/80 rounded-lg pl-8 pr-3 py-1.5 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-orange-500"
            />
            <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-zinc-500 pointer-events-none" />
          </div>
          <button
            type="submit"
            disabled={busy || !query.trim()}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-orange-600 hover:bg-orange-500 disabled:opacity-40 text-white text-xs font-medium transition shadow-sm"
          >
            {busy ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : "Search"}
          </button>
          {results !== null && (
            <button
              type="button"
              onClick={() => {
                setResults(null);
                setQuery("");
              }}
              className="px-2.5 py-1.5 rounded-lg border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-300 transition"
            >
              Reset
            </button>
          )}
        </form>

        {/* Expand / Collapse All Toggle */}
        {filteredItems.length > 0 && (
          <button
            type="button"
            onClick={toggleAll}
            className="px-2.5 py-1.5 rounded-lg border border-zinc-800 bg-zinc-950 hover:bg-zinc-800 text-xs text-zinc-400 hover:text-zinc-200 transition shrink-0 ml-auto"
          >
            {expandedIds.size === filteredItems.length ? "Collapse all" : "Expand all"}
          </button>
        )}
      </div>

      {error && <p role="alert" className="text-xs text-red-400 bg-red-950/20 border border-red-900/40 p-2.5 rounded-lg">{error}</p>}

      {/* Pagination Bar (when browsing all) */}
      {results === null && total > size && (
        <div className="flex items-center justify-between text-xs text-zinc-400 px-1">
          <span>
            Showing passages {page * size + 1}–{Math.min((page + 1) * size, total)} of {total}
          </span>
          <div className="flex items-center gap-1.5">
            <button
              disabled={busy || page === 0}
              onClick={() => setPage((p) => p - 1)}
              className="p-1 rounded border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 disabled:opacity-30 transition"
              title="Previous page"
            >
              <ChevronLeft size={14} />
            </button>
            <span className="font-mono px-2">
              {page + 1} / {totalPages}
            </span>
            <button
              disabled={busy || (page + 1) * size >= total}
              onClick={() => setPage((p) => p + 1)}
              className="p-1 rounded border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 disabled:opacity-30 transition"
              title="Next page"
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Compact Accordion Passage List */}
      <div className="space-y-2">
        {filteredItems.map((item, idx) => {
          const isExpanded = expandedIds.has(item.id);
          const meta = item.metadata || {};
          const pageNum = meta.page_number || "—";
          const chapterName = meta.chapter || meta.topic_name || "General Section";
          const searchRes = item as VectorSearchResult;
          const simPct = searchRes.similarity !== undefined ? `${roundPct(searchRes.similarity)}%` : null;

          return (
            <div
              key={item.id}
              className={`rounded-xl border transition-all ${
                isExpanded
                  ? "border-zinc-700 bg-zinc-900/70 shadow-sm"
                  : "border-zinc-800/80 bg-zinc-900/30 hover:border-zinc-700/60"
              }`}
            >
              {/* Accordion Row Header */}
              <button
                type="button"
                onClick={() => toggleExpand(item.id)}
                className="w-full flex items-center justify-between gap-3 p-3 text-left transition"
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 shrink-0">
                    <span className="text-[11px] font-mono font-medium text-zinc-400 bg-zinc-950 px-2 py-0.5 rounded border border-zinc-800 shrink-0">
                      #{idx + 1 + (results === null ? page * size : 0)}
                    </span>

                    <span className="text-[11px] font-semibold text-orange-400 bg-orange-950/40 px-2 py-0.5 rounded border border-orange-900/40 shrink-0">
                      Page {pageNum}
                    </span>

                    {simPct && (
                      <span className="text-[11px] font-semibold text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800/50 shrink-0">
                        Match: {simPct}
                      </span>
                    )}
                  </div>

                  <span className="text-xs font-semibold text-zinc-200 shrink-0 w-44 lg:w-56 truncate">
                    {chapterName.replace(/^\d+\.\s*/, "")}
                  </span>

                  <span className="hidden md:block min-w-0 flex-1 text-xs text-zinc-400 font-mono truncate">
                    {item.document.replace(/\s+/g, " ")}
                  </span>
                </div>

                <div className="flex items-center gap-1.5 shrink-0 ml-2">
                  <span className="text-[11px] text-zinc-400 font-medium">
                    {isExpanded ? "Collapse" : "Read"}
                  </span>
                  {isExpanded ? (
                    <ChevronUp className="h-4 w-4 text-orange-400" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-zinc-400" />
                  )}
                </div>
              </button>

              {/* Expanded Full Passage Reader */}
              {isExpanded && (
                <div className="px-3.5 pb-3.5 pt-1 space-y-3 border-t border-zinc-800/60">
                  <div className="flex items-center justify-between text-xs text-zinc-500 pt-2">
                    <div className="flex items-center gap-2">
                      <BookOpen size={13} />
                      <span>Source: {meta.file_name || "Uploaded Document"}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleCopy(item.id, item.document)}
                      className="inline-flex items-center gap-1 text-[11px] text-zinc-400 hover:text-zinc-200 transition bg-zinc-950 px-2 py-1 rounded border border-zinc-800"
                    >
                      {copiedId === item.id ? (
                        <>
                          <Check size={11} className="text-emerald-400" />
                          <span className="text-emerald-400">Copied</span>
                        </>
                      ) : (
                        <>
                          <Copy size={11} />
                          <span>Copy</span>
                        </>
                      )}
                    </button>
                  </div>

                  <div className="p-3.5 rounded-lg bg-zinc-950 border border-zinc-800/80 text-xs leading-relaxed text-zinc-200 font-mono whitespace-pre-wrap break-words select-text">
                    {item.document}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {!busy && !filteredItems.length && (
        <div className="p-8 text-center rounded-xl border border-zinc-800 bg-zinc-900/30 text-zinc-400 space-y-2">
          <p className="text-sm">
            {results
              ? "No matching passages found for your query."
              : selectedTopicId !== "all"
              ? "No passages recorded for this selected chapter."
              : "No passages indexed yet."}
          </p>
        </div>
      )}
    </section>
  );
}

function roundPct(val: number): number {
  return Math.round(val * 1000) / 10;
}
