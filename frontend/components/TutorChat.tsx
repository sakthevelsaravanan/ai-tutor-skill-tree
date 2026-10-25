"use client";

import React, { useState, useEffect, useRef } from "react";
import { Subject, Topic, PrerequisiteItem, VectorSearchResult } from "@/lib/types";
import { api } from "@/lib/api";
import { CustomDropdown } from "@/components/CustomDropdown";
import {
  Send,
  Sparkles,
  BookOpen,
  ChevronDown,
  ChevronUp,
  Bot,
  User,
  RefreshCw,
  GitFork,
  CheckCircle2,
  HelpCircle,
  ArrowRight,
} from "lucide-react";

interface TutorChatProps {
  subjects: Subject[];
  activeSubjectId: number;
  initialTopicId?: number | null;
  onSubjectChange: (subjectId: number) => void;
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
}: TutorChatProps) {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [selectedTopicId, setSelectedTopicId] = useState<number | null>(initialTopicId || null);
  const [query, setQuery] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [expandedSources, setExpandedSources] = useState<Record<string, boolean>>({});
  const [usePrereqFilter, setUsePrereqFilter] = useState<boolean>(true);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Sync topics when activeSubjectId changes
  useEffect(() => {
    async function loadTopics() {
      try {
        const topicList = await api.getTopics(activeSubjectId);
        setTopics(topicList);
        if (topicList.length > 0) {
          const match = topicList.find((t) => t.topic_id === selectedTopicId);
          if (!match) {
            setSelectedTopicId(topicList[0].topic_id);
          }
        }
      } catch (err) {
        console.error("Failed to load topics for tutor:", err);
      }
    }
    loadTopics();
  }, [activeSubjectId]);

  useEffect(() => {
    if (initialTopicId) {
      setSelectedTopicId(initialTopicId);
    }
  }, [initialTopicId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

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

  const handleSendMessage = async (customQuery?: string) => {
    const textToSend = customQuery || query;
    if (!textToSend.trim() || loading) return;

    const userMsgId = `user_${Date.now()}`;
    const userMsg: ChatMessage = {
      id: userMsgId,
      role: "user",
      content: textToSend.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setQuery("");
    setLoading(true);

    try {
      const res = await api.queryTutor({
        query: textToSend.trim(),
        subject_id: activeSubjectId,
        topic_id: selectedTopicId || (currentTopic ? currentTopic.topic_id : undefined),
        include_prereqs: usePrereqFilter,
      });

      const assistantMsg: ChatMessage = {
        id: `ast_${Date.now()}`,
        role: "assistant",
        content: res.answer,
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

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: ChatMessage = {
        id: `err_${Date.now()}`,
        role: "assistant",
        content: `Error retrieving tutor response: ${err.message || "Unknown error"}`,
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const toggleSources = (msgId: string) => {
    setExpandedSources((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  // Topic specific suggestions
  const suggestions = [
    `Explain the fundamental mechanisms and invariants of ${currentTopic ? currentTopic.topic_name : "this topic"}.`,
    `What are the prerequisite concepts required to understand ${currentTopic ? currentTopic.topic_name : "this"}?`,
    `How does this concept handle corner cases and scalability?`,
  ];

  return (
    <div className="w-full max-w-5xl mx-auto flex flex-col h-[calc(100vh-8rem)] min-h-[640px] rounded-xl border border-zinc-800 bg-zinc-950 overflow-hidden shadow-xl">
      {/* Pristine Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800/80 bg-zinc-900/60 px-4 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-zinc-400 whitespace-nowrap">Domain:</span>
            <div className="w-48 sm:w-60">
              <CustomDropdown
                value={String(activeSubjectId)}
                onChange={(val) => handleDomainChange(Number(val))}
                options={subjects.map((s) => ({ value: String(s.subject_id), label: s.subject_name }))}
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-zinc-400 whitespace-nowrap">Active Concept:</span>
            <div className="w-56 sm:w-72">
              <CustomDropdown
                value={String(selectedTopicId || (currentTopic ? currentTopic.topic_id : ""))}
                onChange={(val) => setSelectedTopicId(Number(val))}
                options={topics.map((t) => ({ value: String(t.topic_id), label: t.topic_name }))}
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
              className="rounded bg-zinc-900 border-zinc-700 text-blue-500 focus:ring-0"
            />
            <span className="hidden sm:inline">Relational Prerequisite Filter</span>
            <span className="sm:hidden">Prereq Filter</span>
          </label>

          {messages.length > 0 && (
            <button
              onClick={() => setMessages([])}
              className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Messages Stream */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center text-center max-w-md mx-auto space-y-4 text-zinc-400">
            <div className="h-10 w-10 rounded-full bg-zinc-900 flex items-center justify-center text-zinc-200 border border-zinc-800">
              <Bot className="h-5 w-5" />
            </div>
            <div className="space-y-1">
              <h3 className="text-sm font-medium text-zinc-200">
                Socratic AI STEM Tutor
              </h3>
              <p className="text-xs text-zinc-500 leading-relaxed">
                Grounded in your textbook embeddings (ChromaDB) and guided by the relational prerequisite DAG (MySQL 8.0 CTE).
              </p>
            </div>

            <div className="w-full space-y-2 pt-2">
              <p className="text-[11px] font-mono text-zinc-500 uppercase tracking-wider text-left">
                Suggested Inquiries
              </p>
              {suggestions.map((s, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendMessage(s)}
                  className="w-full text-left text-xs p-3 rounded-lg border border-zinc-800/80 bg-zinc-900/40 hover:bg-zinc-800/60 hover:border-zinc-700 text-zinc-300 transition-colors flex items-center justify-between group"
                >
                  <span className="truncate pr-2">{s}</span>
                  <ArrowRight className="h-3 w-3 text-zinc-500 group-hover:text-zinc-200 shrink-0" />
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => {
            const isUser = msg.role === "user";
            return (
              <div
                key={msg.id}
                className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}
              >
                {!isUser && (
                  <div className="h-7 w-7 rounded-full bg-zinc-900 border border-zinc-700 flex items-center justify-center text-zinc-300 shrink-0 text-[10px] font-bold mt-0.5">
                    AI
                  </div>
                )}

                <div
                  className={`max-w-[88%] sm:max-w-[80%] rounded-xl px-4 py-3 text-xs leading-relaxed space-y-3 ${
                    isUser
                      ? "bg-zinc-100 text-zinc-950 font-medium"
                      : "bg-zinc-900/60 border border-zinc-800 text-zinc-200"
                  }`}
                >
                  {/* Topic badge for assistant */}
                  {!isUser && msg.topicName && (
                    <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-zinc-800 text-[10px] text-zinc-400 font-mono">
                      <span>Concept: <strong className="text-zinc-200">{msg.topicName}</strong></span>
                      {msg.relationalFilterApplied && (
                        <span className="text-orange-400 bg-orange-950/40 border border-orange-800/60 px-1.5 py-0.2 rounded font-mono text-[10px]">
                          Prerequisite Filter Active
                        </span>
                      )}
                    </div>
                  )}

                  {/* Formatted Direct Educational Answer */}
                  <div className="space-y-2">
                    {renderFormattedContent(msg.content)}
                  </div>

                  {/* Optional Collapsible Dropdown: Grounding Stats, Excerpts & Reflection Challenge */}
                  {!isUser && (msg.topSimilarity !== undefined || msg.reflectionQuestion || (msg.retrievedChunks && msg.retrievedChunks.length > 0)) && (
                    <div className="pt-2 border-t border-zinc-800/80">
                      <button
                        type="button"
                        onClick={() => toggleSources(msg.id)}
                        className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-zinc-950/70 border border-zinc-800/80 hover:border-zinc-700 text-xs text-zinc-400 hover:text-zinc-200 transition group"
                      >
                        <div className="flex items-center gap-2">
                          <Sparkles className="h-3.5 w-3.5 text-orange-400" />
                          <span className="font-medium text-zinc-300">Grounding Stats & Reflection</span>
                          {msg.topSimilarity !== null && msg.topSimilarity !== undefined && (
                            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-orange-950/50 text-orange-400 border border-orange-800/50">
                              {roundPercent(msg.topSimilarity)}% match
                            </span>
                          )}
                        </div>
                        {expandedSources[msg.id] ? (
                          <ChevronUp className="h-3.5 w-3.5 text-zinc-400 group-hover:text-zinc-200" />
                        ) : (
                          <ChevronDown className="h-3.5 w-3.5 text-zinc-400 group-hover:text-zinc-200" />
                        )}
                      </button>

                      {expandedSources[msg.id] && (
                        <div className="mt-2 space-y-3 p-3.5 rounded-xl bg-zinc-950 border border-zinc-800 text-xs">
                          {/* 1. Retrieval & RAG Metrics */}
                          <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-zinc-800/80 font-mono text-[11px]">
                            <div className="flex items-center gap-1.5 text-zinc-400">
                              <span>Source Document:</span>
                              <strong className="text-zinc-200">{msg.topSource || (msg.retrievedChunks && msg.retrievedChunks[0]?.metadata?.file_name) || "Course Materials"}</strong>
                            </div>
                            {msg.topSimilarity !== null && msg.topSimilarity !== undefined && (
                              <div className="text-orange-400 font-semibold">
                                Cosine Similarity: {roundPercent(msg.topSimilarity)}%
                              </div>
                            )}
                          </div>

                          {/* 2. Matched Slide / Textbook Excerpt */}
                          {(msg.groundingExcerpt || (msg.retrievedChunks && msg.retrievedChunks[0]?.document)) && (
                            <div className="space-y-1">
                              <span className="text-[10px] font-mono uppercase text-zinc-500 block">
                                Matched Course Excerpt
                              </span>
                              <div className="p-2.5 rounded-lg bg-zinc-900 border border-zinc-800 text-[11px] text-zinc-300 italic font-mono leading-relaxed">
                                "{msg.groundingExcerpt || msg.retrievedChunks?.[0]?.document}"
                              </div>
                            </div>
                          )}

                          {/* 3. Socratic Reflection Challenge */}
                          {msg.reflectionQuestion && (
                            <div className="p-3 rounded-lg bg-orange-950/20 border border-orange-500/30 space-y-1.5">
                              <div className="flex items-center gap-1.5 text-orange-400 font-semibold text-[11px]">
                                <HelpCircle className="h-3.5 w-3.5" />
                                <span>Socratic Reflection Challenge</span>
                              </div>
                              <p className="text-zinc-200 text-xs italic">
                                "{msg.reflectionQuestion}"
                              </p>
                              <button
                                type="button"
                                onClick={() => setQuery(`In response to the reflection challenge: ${msg.reflectionQuestion}`)}
                                className="text-[10px] font-mono text-orange-400 hover:text-orange-300 underline pt-1 block"
                              >
                                Click to answer this reflection question
                              </button>
                            </div>
                          )}

                          {/* 4. Prerequisite Context Trace */}
                          {msg.prerequisites && msg.prerequisites.length > 0 && (
                            <div className="pt-2 border-t border-zinc-800/60 flex items-center gap-2 text-[10px] font-mono text-zinc-400">
                              <span>Prerequisites:</span>
                              <div className="flex flex-wrap gap-1">
                                {msg.prerequisites.slice(0, 3).map((p, idx) => (
                                  <span key={idx} className="px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-800 text-zinc-300">
                                    {p.prereq_topic_name}
                                  </span>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* 5. All Retrieved Passages (if multiple) */}
                          {msg.retrievedChunks && msg.retrievedChunks.length > 1 && (
                            <div className="pt-2 border-t border-zinc-800/60 space-y-1.5">
                              <span className="text-[10px] font-mono uppercase text-zinc-500 block">
                                All Retrieved Vector Chunks ({msg.retrievedChunks.length})
                              </span>
                              <div className="space-y-1.5 max-h-36 overflow-y-auto">
                                {msg.retrievedChunks.map((chunk, cIdx) => (
                                  <div
                                    key={chunk.id || cIdx}
                                    className="p-2 rounded bg-zinc-900/60 border border-zinc-800/60 text-[10.5px] space-y-1 text-zinc-300 font-mono"
                                  >
                                    <div className="flex items-center justify-between text-[9.5px] text-zinc-500">
                                      <span>{chunk.metadata?.file_name || "Textbook"}</span>
                                      <span className="text-orange-400 font-semibold">
                                        {roundPercent(chunk.similarity)}%
                                      </span>
                                    </div>
                                    <p className="text-zinc-400 italic line-clamp-2">
                                      "{chunk.document}"
                                    </p>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Timestamp */}
                  <div
                    className={`text-[9px] font-mono text-right ${
                      isUser ? "text-zinc-500" : "text-zinc-500"
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
            <div className="h-7 w-7 rounded-full bg-zinc-900 border border-zinc-700 flex items-center justify-center text-orange-400 shrink-0 text-[10px] font-bold">
              AI
            </div>
            <div className="rounded-xl px-4 py-3 bg-zinc-900/60 border border-zinc-800 text-xs text-zinc-400 flex items-center gap-2">
              <RefreshCw className="h-3.5 w-3.5 animate-spin text-orange-400" />
              <span>Querying ChromaDB & Relational Prerequisite Chain...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Pristine Input Bar */}
      <div className="p-3 border-t border-zinc-800 bg-zinc-900/50">
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
            placeholder={`Ask a question about ${currentTopic ? currentTopic.topic_name : "the curriculum"}...`}
            disabled={loading}
            className="flex-1 bg-zinc-900 border border-zinc-800 rounded-lg px-3.5 py-2.5 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-orange-500 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!query.trim() || loading}
            className="flex items-center justify-center h-9 w-9 rounded-lg bg-orange-500 hover:bg-orange-600 text-white disabled:opacity-30 disabled:hover:bg-orange-500 transition-all shrink-0 active:scale-95 shadow-sm shadow-orange-500/20"
          >
            <Send className="h-3.5 w-3.5" />
          </button>
        </form>
      </div>
    </div>
  );
}

// Clean helper to parse and render Markdown formatted text
function renderFormattedContent(content: string) {
  // Strip any Socratic Reflection Question from main answer body (handled in dropdown)
  const reflectionMarker = "**Socratic Reflection Question**:";
  let mainBody = content;

  if (content.includes(reflectionMarker)) {
    const parts = content.split(reflectionMarker);
    mainBody = parts[0].trim();
  }

  // Split paragraphs
  const paragraphs = mainBody.split("\n\n");

  return (
    <div className="space-y-3">
      {paragraphs.map((p, pIdx) => {
        // Heading
        if (p.startsWith("### ")) {
          return (
            <h4 key={pIdx} className="text-xs font-semibold text-zinc-100 pt-1.5 border-b border-zinc-800/60 pb-1">
              {p.replace("### ", "")}
            </h4>
          );
        }

        // Blockquote
        if (p.startsWith("> ")) {
          return (
            <div
              key={pIdx}
              className="p-2.5 rounded-lg bg-zinc-950/80 border-l-2 border-orange-500 text-[11px] text-zinc-300 leading-relaxed font-mono"
            >
              {formatInlineText(p.replace("> ", ""))}
            </div>
          );
        }

        // Numbered list items
        if (/^\d+\.\s/.test(p.trim())) {
          const items = p.split("\n");
          return (
            <ol key={pIdx} className="space-y-1.5 pl-3 list-decimal list-inside text-xs leading-relaxed text-zinc-200">
              {items.map((it, iIdx) => (
                <li key={iIdx}>
                  {formatInlineText(it.replace(/^\d+\.\s/, ""))}
                </li>
              ))}
            </ol>
          );
        }

        // Bullet list items
        if (/^-\s/.test(p.trim())) {
          const items = p.split("\n");
          return (
            <ul key={pIdx} className="space-y-1.5 pl-3 list-disc list-inside text-xs leading-relaxed text-zinc-200">
              {items.map((it, iIdx) => (
                <li key={iIdx}>
                  {formatInlineText(it.replace(/^-\s/, ""))}
                </li>
              ))}
            </ul>
          );
        }

        return (
          <p key={pIdx} className="leading-relaxed text-zinc-200 text-xs">
            {formatInlineText(p)}
          </p>
        );
      })}
    </div>
  );
}

// Parse inline bold, code, and emphasis
function formatInlineText(text: string): React.ReactNode {
  // Regex to match **bold** and `code`
  const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={index} className="font-semibold text-zinc-100">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={index} className="font-mono text-[10.5px] px-1 py-0.5 rounded bg-zinc-800 text-zinc-300">
          {part.slice(1, -1)}
        </code>
      );
    }
    return part;
  });
}

function roundPercent(val?: number): string {
  if (val === undefined || val === null) return "N/A";
  return (val * 100).toFixed(1);
}
