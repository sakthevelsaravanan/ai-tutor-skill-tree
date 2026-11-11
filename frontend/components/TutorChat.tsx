/**
 * Socratic RAG Tutor Interactive Chat Component.
 *
 * Capabilities:
 * 1. Slide-Grounded Vector Dialogue: Dispatches student queries to the backend RAG pipeline.
 * 2. KaTeX LaTeX Math Rendering: Formats inline $...$ and block $$...$$ equations into math formulas.
 * 3. Match Attributions: Renders cosine similarity badges and slide references for each extracted topic.
 * 4. Relational Prerequisite Toggle: Enables or disables prerequisite-bounded vector search.
 * 5. Dynamic Concept Context: Synchronizes current topic and conversation turns with PostgreSQL sessions.
 * 6. Manual Topic Completion Tracking: Allows students to click "Done" to persist topic completion
 *    in the database, triggering live UI updates across the chatbox and Skill Tree.
 */

"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import { Subject, Topic, PrerequisiteItem, VectorSearchResult, User } from "@/lib/types";
import { api } from "@/lib/api";
import { CustomDropdown } from "@/components/CustomDropdown";
import {
  Send,
  BookOpen,
  RefreshCw,
  ArrowRight,
  Check,
  Lock,
  CheckCircle2,
  AlertCircle,
  X,
} from "lucide-react";
import katex from "katex";

interface TutorChatProps {
  subjects: Subject[];
  activeSubjectId: number;
  initialTopicId?: number | null;
  onSubjectChange: (subjectId: number) => void;
  currentUser: User;
  completedTopicIds?: Set<number>;
  onTopicCompleted?: (topicId: number) => void;
  onNavigateToSkillTree?: () => void;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  topicName?: string;
  prerequisites?: PrerequisiteItem[];
  retrievedChunks?: VectorSearchResult[];
  relationalFilterApplied?: boolean;
  reflectionQuestion?: string | null;
  groundingExcerpt?: string | null;
  topSimilarity?: number | null;
  topSource?: string | null;
  timestamp: string;
}

export function TutorChat({
  subjects,
  activeSubjectId,
  initialTopicId,
  onSubjectChange,
  currentUser,
  completedTopicIds,
  onTopicCompleted,
  onNavigateToSkillTree,
}: TutorChatProps) {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [selectedTopicId, setSelectedTopicId] = useState<number | null>(initialTopicId || null);
  const [completedTopicIdsList, setCompletedTopicIdsList] = useState<number[]>([]);
  const [graphEdges, setGraphEdges] = useState<Array<{ source: number; target: number }>>([]);
  const [lockBanner, setLockBanner] = useState<string | null>(null);
  const [query, setQuery] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [topicMessages, setTopicMessages] = useState<Record<number, ChatMessage[]>>({});
  const activeTopicKey = selectedTopicId ?? (initialTopicId ?? 0);
  const messages = topicMessages[activeTopicKey] ?? [];

  const appendMessage = (msg: ChatMessage) => {
    setTopicMessages((prev) => ({
      ...prev,
      [activeTopicKey]: [...(prev[activeTopicKey] || []), msg],
    }));
  };

  const updateMessage = (msgId: string, content: string) => {
    setTopicMessages((prev) => ({
      ...prev,
      [activeTopicKey]: (prev[activeTopicKey] || []).map((m) =>
        m.id === msgId ? { ...m, content } : m
      ),
    }));
  };
  const [usePrereqFilter, setUsePrereqFilter] = useState<boolean>(true);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const [streamingMsgId, setStreamingMsgId] = useState<string | null>(null);
  const streamIntervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      if (streamIntervalRef.current) clearInterval(streamIntervalRef.current);
    };
  }, []);

  // Manual Topic Completion State
  const effectiveUserId = currentUser?.user_id ?? null;
  const [isCompleted, setIsCompleted] = useState<boolean>(false);
  const [completing, setCompleting] = useState<boolean>(false);
  const [completionToast, setCompletionToast] = useState<string | null>(null);
  const [completionError, setCompletionError] = useState<string | null>(null);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const sessionRef = useRef<Promise<string> | null>(null);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [sessionError, setSessionError] = useState("");
  useEffect(() => {
    let cancelled = false;
    api.getSessions(currentUser.user_id, activeSubjectId).then(async sessions => {
      if (!sessions.length) return;
      const latest = await api.getSession(sessions[0].session_id);
      if (cancelled) return;
      setSessionId(sessions[0].session_id);
      const grouped: Record<number, ChatMessage[]> = {};
      for (const m of latest.messages) {
        if (m.role !== "user" && m.role !== "assistant") continue;
        const tid = m.topic_id ?? 0;
        if (!grouped[tid]) grouped[tid] = [];
        grouped[tid].push({
          id: String(m.log_id),
          role: m.role,
          content: m.content,
          timestamp: new Date(m.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        });
      }
      setTopicMessages(grouped);
    }).catch(e=>{if(!cancelled)setSessionError(e.message);}).finally(()=>{if(!cancelled)setHistoryLoading(false);});
    return ()=>{cancelled=true;};
  }, [currentUser.user_id, activeSubjectId]);
  const ensureSession = async () => {
    if (sessionError) throw new Error(sessionError);
    if (sessionId) return sessionId;
    if (!sessionRef.current) sessionRef.current = api.startSession(currentUser.user_id,activeSubjectId,selectedTopicId || undefined).then(s=>{setSessionId(s.session_id);return s.session_id;}).catch(e=>{sessionRef.current=null;throw e;});
    return sessionRef.current;
  };

  // Synchronize topics, prerequisite edges, and completed topics for sequential locking
  useEffect(() => {
    let alive = true;
    async function loadData() {
      try {
        const isStudentRole = currentUser?.role === "student";
        const [topicList, graphData, doneData] = await Promise.all([
          api.getTopics(activeSubjectId),
          api.getSubjectGraph(activeSubjectId).catch(() => ({ nodes: [], edges: [] })),
          isStudentRole && currentUser?.user_id
            ? api.getCompletedTopics(currentUser.user_id, activeSubjectId).catch(() => ({ completed_topic_ids: [] }))
            : Promise.resolve({ completed_topic_ids: [] }),
        ]);

        if (!alive) return;

        const edges = (graphData as any)?.edges || [];
        const doneList: number[] = (doneData as any)?.completed_topic_ids || [];

        setTopics(topicList);
        setGraphEdges(edges);
        setCompletedTopicIdsList(doneList);

        // Compute locked IDs
        const locked = new Set<number>();
        if (isStudentRole && edges.length > 0) {
          for (const t of topicList) {
            const prereqs = edges.filter((e: any) => e.target === t.topic_id);
            const isDone = doneList.includes(t.topic_id);
            if (!isDone && prereqs.length > 0 && !prereqs.every((e: any) => doneList.includes(e.source))) {
              locked.add(t.topic_id);
            }
          }
        }

        // Determine target topic
        let targetId = initialTopicId || selectedTopicId;
        if (targetId && locked.has(targetId) && isStudentRole) {
          const firstUnlocked = topicList.find((t) => !locked.has(t.topic_id));
          targetId = firstUnlocked ? firstUnlocked.topic_id : topicList[0]?.topic_id || null;
        } else if (!targetId && topicList.length > 0) {
          const firstUnlocked = topicList.find((t) => !locked.has(t.topic_id));
          targetId = firstUnlocked ? firstUnlocked.topic_id : topicList[0]?.topic_id || null;
        }

        if (targetId !== null) {
          setSelectedTopicId(targetId);
        }
      } catch (err) {
        console.error("Failed to load topics for tutor:", err);
      }
    }
    loadData();
    return () => {
      alive = false;
    };
  }, [activeSubjectId, currentUser?.user_id, currentUser?.role, initialTopicId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Synchronize topic completion status whenever active concept or student changes
  useEffect(() => {
    let isMounted = true;
    async function checkCompletion() {
      const userId = effectiveUserId;
      if (!selectedTopicId) {
        setIsCompleted(false);
        return;
      }
      if (userId === null) {
        setIsCompleted(false);
        return;
      }

      // Check fast prop cache if available
      if (completedTopicIds && completedTopicIds.has(selectedTopicId)) {
        setIsCompleted(true);
        return;
      }

      setIsCompleted(false);

      try {
        const res = await api.getTopicCompletionStatus(selectedTopicId, userId);
        if (isMounted) {
          setIsCompleted(res.is_completed);
        }
      } catch (err) {
        console.error("Failed to fetch topic completion status:", err);
      }
    }

    setCompletionError(null);
    setCompletionToast(null);
    checkCompletion();

    return () => {
      isMounted = false;
    };
  }, [selectedTopicId, effectiveUserId, completedTopicIds]);

  const isStudent = currentUser?.role === "student";

  const lockedTopicIds = useMemo(() => {
    const set = new Set<number>();
    if (!isStudent || !graphEdges.length) return set;
    for (const t of topics) {
      const prereqs = graphEdges.filter((e) => e.target === t.topic_id);
      const isDone = completedTopicIdsList.includes(t.topic_id);
      if (!isDone && prereqs.length > 0 && !prereqs.every((e) => completedTopicIdsList.includes(e.source))) {
        set.add(t.topic_id);
      }
    }
    return set;
  }, [isStudent, graphEdges, topics, completedTopicIdsList]);

  const currentTopic = topics.find((t) => t.topic_id === selectedTopicId) || topics[0] || null;

  const handleDomainChange = async (newSubjectId: number) => {
    onSubjectChange(newSubjectId);
    try {
      const topicList = await api.getTopics(newSubjectId);
      setTopics(topicList);
      if (topicList.length > 0) {
        setSelectedTopicId(topicList[0].topic_id);
      }
    } catch (err) {
      console.error("Failed to update domain topics:", err);
    }
  };

  // Action: Mark current topic as completed by student
  const handleMarkDone = async () => {
    const targetTopicId = selectedTopicId || (currentTopic ? currentTopic.topic_id : null);
    if (!targetTopicId || !effectiveUserId || completing || isCompleted) return;

    setCompleting(true);
    setCompletionError(null);
    setCompletionToast(null);

    try {
      const res = await api.markTopicComplete(targetTopicId, effectiveUserId);
      if (res.is_completed) {
        setIsCompleted(true);
        setCompletedTopicIdsList((prev) => [...prev, targetTopicId]);
        setCompletionToast("Topic marked as completed! Returning to Skill Tree...");
        if (onTopicCompleted) {
          onTopicCompleted(targetTopicId);
        }
        setTimeout(() => {
          if (onNavigateToSkillTree) {
            onNavigateToSkillTree();
          }
          setCompletionToast(null);
        }, 850);
      }
    } catch (err: any) {
      console.error("Failed to mark topic as completed:", err);
      setCompletionError(err.message || "Failed to mark topic as completed. Please retry.");
    } finally {
      setCompleting(false);
    }
  };

  const handleSendMessage = async (customQuery?: string) => {
    const textToSend = customQuery || query;
    if (!textToSend.trim() || loading || historyLoading) return;

    const userMsgId = `user_${Date.now()}`;
    const userMsg: ChatMessage = {
      id: userMsgId,
      role: "user",
      content: textToSend.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    appendMessage(userMsg);
    setQuery("");
    setLoading(true);

    try {
      const activeSessionId = await ensureSession();
      const res = await api.queryTutor({
        session_id: activeSessionId,
        query: textToSend.trim(),
        subject_id: activeSubjectId,
        topic_id: selectedTopicId || (currentTopic ? currentTopic.topic_id : undefined),
        include_prereqs: usePrereqFilter,
      });

      const fullAnswer = res.answer || "";
      const assistantMsgId = `ast_${Date.now()}`;
      const assistantMsg: ChatMessage = {
        id: assistantMsgId,
        role: "assistant",
        content: "",
        topicName: res.target_topic?.topic_name || currentTopic?.topic_name,
        prerequisites: res.prerequisites,
        retrievedChunks: res.retrieved_chunks,
        relationalFilterApplied: res.relational_filter_applied,
        reflectionQuestion: res.reflection_question,
        groundingExcerpt: res.grounding_excerpt,
        topSimilarity: res.top_similarity,
        topSource: res.top_source,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };

      appendMessage(assistantMsg);
      setStreamingMsgId(assistantMsgId);

      if (streamIntervalRef.current) {
        clearInterval(streamIntervalRef.current);
      }

      let currentLen = 0;
      const totalLen = fullAnswer.length;
      // Slower, smooth typing animation: ~140 steps with 45ms interval (~6s)
      const step = Math.max(1, Math.ceil(totalLen / 140));
      streamIntervalRef.current = setInterval(() => {
        currentLen = Math.min(totalLen, currentLen + step);
        const chunk = fullAnswer.slice(0, currentLen);

        updateMessage(assistantMsgId, chunk);

        if (currentLen >= totalLen) {
          if (streamIntervalRef.current) {
            clearInterval(streamIntervalRef.current);
            streamIntervalRef.current = null;
          }
          setStreamingMsgId(null);
        }
      }, 45);
    } catch (err: any) {
      if (streamIntervalRef.current) {
        clearInterval(streamIntervalRef.current);
        streamIntervalRef.current = null;
      }
      setStreamingMsgId(null);
      const errorMsg: ChatMessage = {
        id: `err_${Date.now()}`,
        role: "assistant",
        content: `Error retrieving tutor response: ${err.message || "Unknown error"}`,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      appendMessage(errorMsg);
    } finally {
      setLoading(false);
    }
  };


  return (
    <div className="tutor-panel w-full min-w-0 min-h-0 flex-1 flex flex-col rounded-xl border border-zinc-800 bg-zinc-950 overflow-hidden shadow-xl">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800/80 bg-zinc-900/60 px-4 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-zinc-400 whitespace-nowrap">Chapter:</span>
            <div className="w-44 sm:w-72">
              <CustomDropdown
                value={String(selectedTopicId || (currentTopic ? currentTopic.topic_id : ""))}
                onChange={(val) => {
                  const tid = Number(val);
                  if (lockedTopicIds.has(tid) && isStudent) {
                    const opt = topics.find((t) => t.topic_id === tid);
                    setLockBanner(
                      `Chapter '${(opt?.topic_name || "").replace(/^\d+\.\s*/, "")}' is locked. Please complete prerequisite chapters first.`
                    );
                    setTimeout(() => setLockBanner(null), 4000);
                    return;
                  }
                  setSelectedTopicId(tid);
                }}
                onBlockedSelect={(opt) => {
                  setLockBanner(
                    `Chapter '${opt.label.replace(/^\d+\.\s*/, "")}' is locked. Please complete prerequisite chapters first.`
                  );
                  setTimeout(() => setLockBanner(null), 4000);
                }}
                options={topics.map((t) => ({
                  value: String(t.topic_id),
                  label: t.topic_name,
                  locked: lockedTopicIds.has(t.topic_id),
                  isDone: completedTopicIdsList.includes(t.topic_id),
                  lockReason: lockedTopicIds.has(t.topic_id) ? "Prerequisites not completed" : undefined,
                }))}
                placeholder="Select topic..."
              />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-xs text-zinc-400 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={usePrereqFilter}
              onChange={(e) => setUsePrereqFilter(e.target.checked)}
              className="rounded bg-zinc-900 border-zinc-700 text-orange-500 focus:ring-0"
            />
            <span className="hidden sm:inline">Include earlier chapters</span>
            <span className="sm:hidden">Earlier chapters</span>
          </label>

          {messages.length > 0 && (
            <button
              onClick={() => {
                if (streamIntervalRef.current) {
                  clearInterval(streamIntervalRef.current);
                  streamIntervalRef.current = null;
                }
                setStreamingMsgId(null);
                setTopicMessages((prev) => ({ ...prev, [activeTopicKey]: [] }));
              }}
              className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Locked Warning Banner */}
      {lockBanner && (
        <div className="bg-amber-950/70 border-b border-amber-800/80 px-4 py-2.5 text-xs text-amber-200 flex items-center justify-between animate-in fade-in">
          <span className="flex items-center gap-2 font-medium">
            <Lock className="h-3.5 w-3.5 text-amber-400 shrink-0" />
            <span>{lockBanner}</span>
          </span>
          <button
            onClick={() => setLockBanner(null)}
            className="text-amber-400/80 hover:text-amber-200 text-xs px-1.5 py-0.5 rounded hover:bg-amber-900/50 transition"
          >
            ✕
          </button>
        </div>
      )}

      {/* Messages Stream */}
      <div className="min-h-0 flex-1 overflow-y-auto p-4 space-y-5">
        {messages.length === 0 ? (
          <div className="flex min-h-full flex-col items-center justify-center text-center max-w-md mx-auto space-y-4 text-zinc-400">
            <div className="h-10 w-10 rounded-full bg-zinc-900 flex items-center justify-center text-orange-400 border border-zinc-800 shadow-sm">
              <BookOpen className="h-5 w-5" />
            </div>
            <div className="space-y-1">
              <h3 className="text-sm font-medium text-zinc-200">
                Chapter1 Tutor
              </h3>
              <p className="text-xs text-zinc-500 leading-relaxed">
                Ask questions about your course materials, explore concepts, and test your understanding.
              </p>
            </div>
          </div>
        ) : (
          messages.map((msg) => {
            const isUser = msg.role === "user";
            return (
              <div
                key={msg.id}
                className={`flex gap-3 transition-all duration-300 ease-out animate-in fade-in-50 slide-in-from-bottom-2 ${
                  isUser ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[88%] sm:max-w-[80%] rounded-xl px-4 py-3 text-xs leading-relaxed space-y-2.5 ${
                    isUser
                      ? "bg-orange-600 text-white font-normal shadow-md shadow-orange-600/25 border border-orange-500/40"
                      : "bg-zinc-900/80 border border-zinc-800 text-zinc-200 shadow-sm"
                  }`}
                >
                  {/* Clean Direct Educational Answer & Grounded Follow-up */}
                  <div className="space-y-2">
                    {renderFormattedContent(msg.content, isUser)}
                    {!isUser && streamingMsgId === msg.id && (
                      <span className="inline-block w-1.5 h-3.5 ml-1 bg-orange-400 animate-pulse rounded-sm align-middle" />
                    )}
                  </div>

                  {/* Timestamp */}
                  <div
                    className={`text-[9px] font-mono text-right ${
                      isUser ? "text-orange-200/80" : "text-zinc-500"
                    }`}
                  >
                    {msg.timestamp}
                  </div>
                </div>
              </div>
            );
          })
        )}

        {loading && (
          <div className="flex gap-3 justify-start">
            <div className="rounded-xl px-4 py-3 bg-zinc-900/60 border border-zinc-800 text-xs text-zinc-400 flex items-center gap-2">
              <RefreshCw className="h-3.5 w-3.5 animate-spin text-orange-400" />
              <span>Querying ChromaDB & Relational Prerequisite Chain...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {sessionError && <p role="alert" className="px-4 text-red-400 text-sm">{sessionError}</p>}
      {/* Input Composer & Topic Completion Area */}
      <div className="shrink-0 p-3 border-t border-zinc-800 bg-zinc-900/50 space-y-2">
        {/* Completion Toast Notification */}
        {completionToast && (
          <div className="flex items-center justify-between px-3.5 py-2 rounded-lg bg-emerald-950/70 border border-emerald-500/60 text-xs text-emerald-300 animate-in fade-in duration-200 shadow-sm">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
              <span className="font-semibold">{completionToast}</span>
              <span className="text-[11px] text-emerald-400/80 font-mono">
                • Green tick mark visible on Skill Tree
              </span>
            </div>
            <button
              onClick={() => setCompletionToast(null)}
              className="text-emerald-400 hover:text-emerald-200 transition"
              title="Dismiss"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {/* Completion Error Notification */}
        {completionError && (
          <div className="flex items-center justify-between px-3.5 py-2 rounded-lg bg-rose-950/70 border border-rose-500/60 text-xs text-rose-300 shadow-sm">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-rose-400 shrink-0" />
              <span>{completionError}</span>
            </div>
            <button
              onClick={handleMarkDone}
              className="text-xs font-semibold underline text-rose-200 hover:text-white ml-2"
            >
              Retry
            </button>
          </div>
        )}

        {/* Composer Form */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={currentTopic?.topic_name ? `Ask a question about ${currentTopic.topic_name.replace(/^\d+[.\s_-]*/, "")}...` : "Ask a question about this chapter..."}
            disabled={loading || historyLoading}
            className="min-w-0 flex-1 bg-zinc-900 border border-zinc-800 rounded-lg px-3.5 py-2.5 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-orange-500 disabled:opacity-50"
          />

          {/* Done Button Beside Composer — completely disappears once completed */}
          {!isCompleted && selectedTopicId && (
            <button
              type="button"
              onClick={handleMarkDone}
              disabled={completing || !selectedTopicId || !effectiveUserId}
              className="flex items-center gap-1.5 px-3 py-2.5 rounded-lg text-xs font-semibold border transition-all shrink-0 active:scale-95 bg-emerald-950/50 hover:bg-emerald-900/70 text-emerald-300 border-emerald-600/60 hover:border-emerald-500 shadow-sm"
              title="Click once finished studying this concept"
            >
              {completing ? (
                <RefreshCw className="h-3.5 w-3.5 animate-spin text-emerald-400" />
              ) : (
                <Check className="h-3.5 w-3.5 text-emerald-400" strokeWidth={2.5} />
              )}
              <span>Mark as Done</span>
            </button>
          )}

          <button
            type="submit"
            disabled={!query.trim() || loading || historyLoading}
            className="flex items-center justify-center h-9 w-9 rounded-lg bg-orange-500 hover:bg-orange-600 text-white disabled:opacity-30 disabled:hover:bg-orange-500 transition-all shrink-0 active:scale-95 shadow-sm shadow-orange-500/20"
            title="Send inquiry"
          >
            <Send className="h-3.5 w-3.5" />
          </button>
        </form>
      </div>
    </div>
  );
}

// Helper component to render KaTeX math expressions
function MathSnippet({
  tex,
  displayMode = false,
  isUser = false,
}: {
  tex: string;
  displayMode?: boolean;
  isUser?: boolean;
}) {
  if (!tex || !tex.trim()) return null;

  try {
    const html = katex.renderToString(tex.trim(), {
      displayMode,
      throwOnError: false,
      strict: false,
    });
    return (
      <span
        dangerouslySetInnerHTML={{ __html: html }}
        className={
          displayMode
            ? `block my-2.5 text-center overflow-x-auto py-1 ${
                isUser ? "text-white" : "text-orange-200"
              }`
            : `inline-block align-baseline mx-0.5 ${
                isUser ? "text-white" : "text-orange-100"
              }`
        }
      />
    );
  } catch {
    return <code className="font-mono text-xs">{tex}</code>;
  }
}

// Tokenize and render inline text, math ($...$, \(...\), $$...$$, \[...\]), bold (**...**), and code (`...`)
function renderInlineContent(rawText: string, isUser: boolean = false): React.ReactNode {
  // Normalize escaped asterisks if present e.g. \*\* -> **
  const text = rawText.replace(/\\\*/g, "*");

  const regex = /(\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\$[^\$\n]+?\$|\\\([^\n]+?\\\)|(?:\*\*|__)[^\*\n]+?(?:\*\*|__)|`[^`\n]+?`)/g;

  const elements: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      elements.push(text.slice(lastIndex, match.index));
    }

    const m = match[0];
    const key = `inline_${match.index}`;

    if (m.startsWith("$$") && m.endsWith("$$")) {
      elements.push(
        <MathSnippet key={key} tex={m.slice(2, -2)} displayMode={true} isUser={isUser} />
      );
    } else if (m.startsWith("\\[") && m.endsWith("\\]")) {
      elements.push(
        <MathSnippet key={key} tex={m.slice(2, -2)} displayMode={true} isUser={isUser} />
      );
    } else if (m.startsWith("$") && m.endsWith("$")) {
      elements.push(
        <MathSnippet key={key} tex={m.slice(1, -1)} displayMode={false} isUser={isUser} />
      );
    } else if (m.startsWith("\\(") && m.endsWith("\\)")) {
      elements.push(
        <MathSnippet key={key} tex={m.slice(2, -2)} displayMode={false} isUser={isUser} />
      );
    } else if (
      (m.startsWith("**") && m.endsWith("**")) ||
      (m.startsWith("__") && m.endsWith("__"))
    ) {
      elements.push(
        <strong
          key={key}
          className={`font-semibold ${isUser ? "text-white font-bold" : "text-zinc-100"}`}
        >
          {m.slice(2, -2)}
        </strong>
      );
    } else if (m.startsWith("`") && m.endsWith("`")) {
      elements.push(
        <code
          key={key}
          className={`font-mono text-[10.5px] px-1 py-0.5 rounded ${
            isUser ? "bg-orange-700/60 text-white" : "bg-zinc-800 text-zinc-300"
          }`}
        >
          {m.slice(1, -1)}
        </code>
      );
    } else {
      elements.push(m);
    }

    lastIndex = regex.lastIndex;
  }

  if (lastIndex < text.length) {
    elements.push(text.slice(lastIndex));
  }

  return elements;
}

interface ParsedBlock {
  type: "h2" | "h3" | "h4" | "p" | "display_math" | "callout" | "ol" | "ul";
  content: string;
}

function parseContentBlocks(markdown: string): ParsedBlock[] {
  const normalized = markdown.replace(/\r\n/g, "\n");
  const rawParagraphs = normalized.split(/\n\n+/);
  const blocks: ParsedBlock[] = [];

  for (const rawP of rawParagraphs) {
    const trimmed = rawP.trim();
    if (!trimmed) continue;

    // Check if entire paragraph is standalone display math: $$...$$ or \[...\]
    if (
      (trimmed.startsWith("$$") && trimmed.endsWith("$$") && trimmed.length > 4) ||
      (trimmed.startsWith("\\[") && trimmed.endsWith("\\]") && trimmed.length > 4)
    ) {
      const math = trimmed.startsWith("$$") ? trimmed.slice(2, -2) : trimmed.slice(2, -2);
      blocks.push({ type: "display_math", content: math.trim() });
      continue;
    }

    // Suppress any legacy reflection text if present
    if (
      trimmed.startsWith("Think about this:") ||
      trimmed.startsWith("**Socratic Reflection")
    ) {
      continue;
    }

    // Check if callout / formula block
    if (trimmed.startsWith("> ")) {
      blocks.push({ type: "callout", content: trimmed.replace(/^>\s*/, "") });
      continue;
    }

    // Line by line breakdown to handle headings and lists embedded in single newlines
    const lines = trimmed.split("\n");
    let currentLines: string[] = [];
    let currentType: "p" | "ol" | "ul" | null = null;

    const flushCurrent = () => {
      if (currentLines.length > 0) {
        blocks.push({ type: currentType || "p", content: currentLines.join("\n") });
        currentLines = [];
        currentType = null;
      }
    };

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const lineTrim = line.trim();

      if (lineTrim.startsWith("#### ")) {
        flushCurrent();
        blocks.push({ type: "h4", content: lineTrim.replace(/^####\s+/, "") });
      } else if (lineTrim.startsWith("### ")) {
        flushCurrent();
        blocks.push({ type: "h3", content: lineTrim.replace(/^###\s+/, "") });
      } else if (lineTrim.startsWith("## ")) {
        flushCurrent();
        blocks.push({ type: "h2", content: lineTrim.replace(/^##\s+/, "") });
      } else if (lineTrim.startsWith("# ")) {
        flushCurrent();
        blocks.push({ type: "h2", content: lineTrim.replace(/^#\s+/, "") });
      } else if (
        (lineTrim.startsWith("$$") && lineTrim.endsWith("$$") && lineTrim.length > 4) ||
        (lineTrim.startsWith("\\[") && lineTrim.endsWith("\\]") && lineTrim.length > 4)
      ) {
        flushCurrent();
        const math = lineTrim.startsWith("$$") ? lineTrim.slice(2, -2) : lineTrim.slice(2, -2);
        blocks.push({ type: "display_math", content: math.trim() });
      } else if (/^\d+\.\s/.test(lineTrim)) {
        if (currentType !== "ol") {
          flushCurrent();
          currentType = "ol";
        }
        currentLines.push(lineTrim);
      } else if (/^[-*]\s/.test(lineTrim)) {
        if (currentType !== "ul") {
          flushCurrent();
          currentType = "ul";
        }
        currentLines.push(lineTrim);
      } else {
        if (currentType === "ol" || currentType === "ul") {
          flushCurrent();
        }
        currentLines.push(line);
      }
    }

    flushCurrent();
  }

  return blocks;
}

// Clean helper to parse and render Markdown formatted text with KaTeX
function renderFormattedContent(content: string, isUser: boolean = false) {
  const blocks = parseContentBlocks(content);

  return (
    <div className="space-y-2.5">
      {blocks.map((b, idx) => {
        if (b.type === "h2") {
          return (
            <h2
              key={idx}
              className={`text-sm font-bold pt-2 pb-1 border-b ${
                isUser ? "text-white border-orange-400/40" : "text-zinc-100 border-zinc-800/80"
              }`}
            >
              {renderInlineContent(b.content, isUser)}
            </h2>
          );
        }

        if (b.type === "h3") {
          return (
            <h3
              key={idx}
              className={`text-xs font-bold pt-2 pb-1 border-b ${
                isUser ? "text-white border-orange-400/40" : "text-zinc-100 border-zinc-800/80"
              }`}
            >
              {renderInlineContent(b.content, isUser)}
            </h3>
          );
        }

        if (b.type === "h4") {
          return (
            <h4
              key={idx}
              className={`text-xs font-semibold pt-1.5 pb-0.5 ${
                isUser ? "text-white" : "text-orange-400"
              }`}
            >
              {renderInlineContent(b.content, isUser)}
            </h4>
          );
        }

        if (b.type === "display_math") {
          return <MathSnippet key={idx} tex={b.content} displayMode={true} isUser={isUser} />;
        }

        if (b.type === "callout") {
          return (
            <div
              key={idx}
              className={`p-2.5 rounded-lg border-l-2 text-xs leading-relaxed my-2 font-mono ${
                isUser
                  ? "bg-orange-700/40 border-white text-white"
                  : "bg-zinc-900 border-orange-500/80 text-orange-200"
              }`}
            >
              {renderInlineContent(b.content, isUser)}
            </div>
          );
        }

        if (b.type === "ol") {
          const items = b.content.split("\n");
          return (
            <ol
              key={idx}
              className={`space-y-1.5 pl-4 list-decimal list-outside text-xs leading-relaxed ${
                isUser ? "text-white" : "text-zinc-200"
              }`}
            >
              {items.map((it, iIdx) => (
                <li key={iIdx}>
                  {renderInlineContent(it.replace(/^\d+\.\s*/, ""), isUser)}
                </li>
              ))}
            </ol>
          );
        }

        if (b.type === "ul") {
          const items = b.content.split("\n");
          return (
            <ul
              key={idx}
              className={`space-y-1.5 pl-4 list-disc list-outside text-xs leading-relaxed ${
                isUser ? "text-white" : "text-zinc-200"
              }`}
            >
              {items.map((it, iIdx) => (
                <li key={iIdx}>
                  {renderInlineContent(it.replace(/^[-*]\s*/, ""), isUser)}
                </li>
              ))}
            </ul>
          );
        }

        return (
          <p
            key={idx}
            className={`leading-relaxed text-xs ${
              isUser ? "text-white font-normal" : "text-zinc-200"
            }`}
          >
            {renderInlineContent(b.content, isUser)}
          </p>
        );
      })}
    </div>
  );
}
