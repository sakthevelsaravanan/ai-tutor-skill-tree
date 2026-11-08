"use client";
import { useEffect, useState } from "react";
import { Subject, SubjectGraph, User, GraphNode } from "@/lib/types";
import { api } from "@/lib/api";
import { ArrowRight, Check, BookOpen, Lock } from "lucide-react";

export function SkillTreeDag({
  subject,
  currentUser,
  onSelectTopicForTutor,
}: {
  subject: Subject;
  currentUser?: User;
  onSelectTopicForTutor: (id: number) => void;
}) {
  const [graph, setGraph] = useState<SubjectGraph>({ nodes: [], edges: [] });
  const [selected, setSelected] = useState<number | null>(null);
  const [completed, setCompleted] = useState<number[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    Promise.all([
      api.getSubjectGraph(subject.subject_id),
      currentUser
        ? api.getCompletedTopics(currentUser.user_id, subject.subject_id)
        : Promise.resolve({ completed_topic_ids: [] }),
    ])
      .then(([data, done]) => {
        if (alive) {
          setGraph(data);
          setSelected(data.nodes[0]?.id || null);
          setCompleted(done.completed_topic_ids);
        }
      })
      .catch((e) => {
        if (alive) setError(e.message);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [subject.subject_id, currentUser?.user_id]);

  const node = graph.nodes.find((n) => n.id === selected);
  const before = graph.edges.filter((e) => e.target === selected);
  const after = graph.edges.filter((e) => e.source === selected);

  const link = (id: number) => {
    const n = graph.nodes.find((n) => n.id === id);
    const isDone = completed.includes(id);
    return (
      n && (
        <button
          key={id}
          onClick={() => setSelected(id)}
          className={`w-full text-left flex items-center justify-between gap-3 rounded-lg border p-3 text-sm transition-colors ${
            isDone
              ? "border-emerald-800/60 bg-emerald-950/20 hover:border-emerald-600"
              : "border-zinc-800 bg-zinc-900/40 hover:border-orange-500"
          }`}
        >
          <span className="flex items-center gap-2 min-w-0 truncate">
            {isDone && <Check size={14} className="text-emerald-400 shrink-0" strokeWidth={2.5} />}
            <span className="truncate">{n.label}</span>
          </span>
          <ArrowRight
            size={16}
            className={`shrink-0 ${isDone ? "text-emerald-400" : "text-orange-400"}`}
          />
        </button>
      )
    );
  };

  const location = (n: GraphNode) =>
    n.start_page ? `PDF pages ${n.start_page}–${n.end_page}` : "Course material";

  return (
    <section className="space-y-4 min-w-0">
      <div>
        <p className="text-xs text-orange-400 mb-1">Learning path</p>
        <h1 className="text-xl font-semibold">{subject.subject_name}</h1>
        <p className="text-sm text-zinc-400 mt-1">
          Chapters follow the book’s order. Links suggest what to study first; you can open any chapter.
        </p>
      </div>

      {error && <p role="alert" className="text-red-400">{error}</p>}

      {loading ? (
        <p className="text-zinc-400">Loading chapters...</p>
      ) : !graph.nodes.length ? (
        <p>No chapters are available yet. Upload course material to get started.</p>
      ) : (
        <div className="grid lg:grid-cols-[minmax(300px,1fr)_minmax(0,1.4fr)] gap-5 items-start">
          <ol
            aria-label="Chapters in reading order"
            className="space-y-2 lg:max-h-[calc(100dvh-13rem)] overflow-y-auto pr-1"
          >
            {graph.nodes.map((n, i) => {
              const isSelected = n.id === selected;
              const isDone = completed.includes(n.id);
              const isStudent = currentUser?.role === "student";
              const prereqEdges = graph.edges.filter((e) => e.target === n.id);
              const isLocked = isStudent && !isDone && prereqEdges.length > 0 && !prereqEdges.every((e) => completed.includes(e.source));

              let cardClass = "border-zinc-800 bg-zinc-900/40 hover:border-zinc-600";
              if (isSelected && isDone) {
                cardClass = "border-emerald-500 bg-emerald-950/40 ring-1 ring-emerald-500/50 shadow-sm";
              } else if (isSelected && !isLocked) {
                cardClass = "border-orange-500 bg-orange-950/30";
              } else if (isSelected && isLocked) {
                cardClass = "border-zinc-700 bg-zinc-900/60 ring-1 ring-zinc-700/50";
              } else if (isDone) {
                cardClass = "border-emerald-800/60 bg-emerald-950/20 hover:border-emerald-600/70";
              } else if (isLocked) {
                cardClass = "border-zinc-800/60 bg-zinc-950/40 opacity-70 hover:opacity-90";
              }

              let badgeClass = "bg-zinc-800 text-zinc-300";
              if (isDone) {
                badgeClass =
                  "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 font-semibold shadow-sm";
              } else if (isLocked) {
                badgeClass = "bg-zinc-900 text-zinc-500 border border-zinc-800";
              } else if (isSelected) {
                badgeClass = "bg-orange-500/20 text-orange-300 border border-orange-500/40";
              }

              return (
                <li key={n.id}>
                  <button
                    onClick={() => setSelected(n.id)}
                    aria-pressed={isSelected}
                    className={`w-full flex gap-3 items-center text-left border rounded-xl p-3 transition-colors ${cardClass}`}
                  >
                    <span
                      className={`w-8 h-8 shrink-0 grid place-items-center rounded-full text-sm ${badgeClass}`}
                    >
                      {isDone ? (
                        <Check size={16} strokeWidth={2.5} />
                      ) : isLocked ? (
                        <Lock size={14} className="text-zinc-500" />
                      ) : (
                        i + 1
                      )}
                    </span>
                    <span className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className={`block text-sm font-medium ${
                            isDone ? "text-emerald-100" : isLocked ? "text-zinc-400" : "text-zinc-100"
                          }`}
                        >
                          {n.label.replace(/^\d+\.\s*/, "")}
                        </span>
                        {isDone ? (
                          <span className="shrink-0 text-[11px] font-semibold text-emerald-400 bg-emerald-950/80 border border-emerald-500/40 px-2 py-0.5 rounded-full flex items-center gap-1">
                            <Check size={11} strokeWidth={2.5} /> Done
                          </span>
                        ) : isLocked ? (
                          <span className="shrink-0 text-[11px] font-medium text-zinc-500 bg-zinc-900 border border-zinc-800 px-2 py-0.5 rounded-full flex items-center gap-1">
                            <Lock size={10} /> Locked
                          </span>
                        ) : null}
                      </div>
                      <span className="text-xs text-zinc-500">{location(n)}</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>

          {node && (() => {
            const nodeDone = completed.includes(node.id);
            const isStudent = currentUser?.role === "student";
            const nodePrereqs = graph.edges.filter((e) => e.target === node.id);
            const nodeLocked = isStudent && !nodeDone && nodePrereqs.length > 0 && !nodePrereqs.every((e) => completed.includes(e.source));
            const missingPrereqNode = nodeLocked
              ? graph.nodes.find((n) => nodePrereqs.some((e) => e.source === n.id && !completed.includes(n.id)))
              : null;

            return (
              <article className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 space-y-5 lg:sticky lg:top-4 min-w-0">
                <div>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <p className="text-xs text-zinc-500 flex items-center gap-2">
                      <BookOpen size={14} />
                      {location(node)}
                    </p>
                    {nodeDone ? (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/40">
                        <Check size={12} strokeWidth={2.5} /> Completed
                      </span>
                    ) : nodeLocked ? (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-zinc-900 text-zinc-400 border border-zinc-800">
                        <Lock size={12} /> Locked
                      </span>
                    ) : null}
                  </div>
                  <h2 className="text-xl font-semibold text-zinc-100">{node.label}</h2>
                  {node.source_file && (
                    <p className="text-xs text-zinc-500 mt-2 break-words">{node.source_file}</p>
                  )}
                </div>

                {nodeLocked ? (
                  <div className="space-y-3">
                    <button
                      disabled
                      className="rounded-lg px-4 py-2 text-sm font-medium border border-zinc-800 bg-zinc-900 text-zinc-500 cursor-not-allowed flex items-center gap-2 shadow-sm"
                      title={missingPrereqNode ? `Complete '${missingPrereqNode.label}' first` : "Complete prerequisite chapter first"}
                    >
                      <Lock size={15} /> Locked — Complete prerequisite first
                    </button>
                    {missingPrereqNode && (
                      <p className="text-xs text-amber-500/90 bg-amber-950/20 border border-amber-900/40 rounded-lg p-2.5">
                        Please complete <strong>{missingPrereqNode.label.replace(/^\d+\.\s*/, "")}</strong> before accessing this chapter.
                      </p>
                    )}
                  </div>
                ) : (
                  <button
                    onClick={() => onSelectTopicForTutor(node.id)}
                    className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors shadow-sm ${
                      nodeDone
                        ? "bg-emerald-600 hover:bg-emerald-700 text-white shadow-emerald-900/20"
                        : "bg-orange-500 hover:bg-orange-600 text-white shadow-orange-950/20"
                    }`}
                  >
                    {nodeDone ? "Review this chapter" : "Study this chapter"}{" "}
                    <ArrowRight className="inline ml-2" size={16} />
                  </button>
                )}

                <div className="border-t border-zinc-800 pt-4 space-y-2">
                  <h3 className="font-medium text-sm">Learn first</h3>
                  <p className="text-xs text-zinc-500">
                    {before.some((e) => e.basis === "book_order")
                      ? "Suggested prerequisite from the book’s reading order."
                      : before.length
                      ? "Prerequisite chapters."
                      : "This is the starting chapter."}
                  </p>
                  {before.map((e) => link(e.source))}
                </div>

                <div className="border-t border-zinc-800 pt-4 space-y-2">
                  <h3 className="font-medium text-sm">Continue with</h3>
                  {after.length ? (
                    after.map((e) => link(e.target))
                  ) : (
                    <p className="text-sm text-zinc-400">You’ve reached the end of this reading path.</p>
                  )}
                </div>
              </article>
            );
          })()}
        </div>
      )}
    </section>
  );
}
