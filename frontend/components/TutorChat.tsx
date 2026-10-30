"use client";

import React, { useState, useEffect, useRef } from "react";
import { Subject, Topic, PrerequisiteItem, VectorSearchResult } from "@/lib/types";
import { api } from "@/lib/api";
import { CustomDropdown } from "@/components/CustomDropdown";
import {
  Send,
  Bot,
  RefreshCw,
  ArrowRight,
} from "lucide-react";
import katex from "katex";

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

  // Helper to get natural concept label for suggestions
  const getCleanTopicTitle = (topicName?: string) => {
    if (!topicName) return "this concept";
    return topicName
      .replace(/^\d+[\s_-]*/, "")
      .replace(/:\s*(Fundamental Concepts|Structural Models|Dynamic Processes|Advanced Synthesis).*$/i, "")
      .replace(/[_\-]+/g, " ")
      .trim();
  };

  const cleanTopicTitle = getCleanTopicTitle(currentTopic?.topic_name);

  // Topic specific suggestions
  const suggestions = [
    `Explain the fundamental mechanisms and invariants of ${cleanTopicTitle}.`,
    `What are the prerequisite concepts required to understand ${cleanTopicTitle}?`,
    `How does ${cleanTopicTitle} handle core operations and edge cases?`,
  ];

  return (
    <div className="w-full max-w-5xl mx-auto flex flex-col h-[calc(100vh-8rem)] min-h-[640px] rounded-xl border border-zinc-800 bg-zinc-950 overflow-hidden shadow-xl">
      {/* Header Bar */}
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
              className="rounded bg-zinc-900 border-zinc-700 text-orange-500 focus:ring-0"
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
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5">
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
                  className={`max-w-[88%] sm:max-w-[80%] rounded-xl px-4 py-3 text-xs leading-relaxed space-y-2.5 ${
                    isUser
                      ? "bg-orange-600 text-white font-normal shadow-md shadow-orange-600/25 border border-orange-500/40"
                      : "bg-zinc-900/80 border border-zinc-800 text-zinc-200 shadow-sm"
                  }`}
                >
                  {/* Clean Direct Educational Answer & Grounded Follow-up */}
                  <div className="space-y-2">
                    {renderFormattedContent(msg.content, isUser)}
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

      {/* Input Composer */}
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
            placeholder={`Ask a question about ${cleanTopicTitle || "the curriculum"}...`}
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
  type: "h2" | "h3" | "h4" | "p" | "display_math" | "reflection" | "ol" | "ul";
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

    // Check if reflection block
    if (
      trimmed.startsWith("> ") ||
      trimmed.startsWith("Think about this:") ||
      trimmed.startsWith("**Socratic Reflection")
    ) {
      blocks.push({ type: "reflection", content: trimmed.replace(/^>\s*/, "") });
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

      if (lineTrim.startsWith("### ")) {
        flushCurrent();
        blocks.push({ type: "h4", content: lineTrim.replace(/^###\s+/, "") });
      } else if (lineTrim.startsWith("## ")) {
        flushCurrent();
        blocks.push({ type: "h3", content: lineTrim.replace(/^##\s+/, "") });
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

        if (b.type === "reflection") {
          return (
            <div
              key={idx}
              className={`p-3 rounded-lg border-l-2 text-xs leading-relaxed my-2 ${
                isUser
                  ? "bg-orange-700/40 border-white text-white"
                  : "bg-orange-950/20 border-orange-500/80 text-zinc-200 italic"
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
