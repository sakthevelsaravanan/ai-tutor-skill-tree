"use client";

import React, { useEffect, useState, useMemo } from "react";
import { Subject, SubjectGraph, Topic, PrerequisiteItem, UnlockedTopicItem } from "@/lib/types";
import { api } from "@/lib/api";
import { GitFork, BookOpen, Layers, Play, MessageSquare, ArrowRight, CheckCircle2, ShieldAlert } from "lucide-react";

interface SkillTreeDagProps {
  subject: Subject;
  onSelectTopicForTutor: (topicId: number) => void;
}

export function SkillTreeDag({
  subject,
  onSelectTopicForTutor,
}: SkillTreeDagProps) {
  const [graph, setGraph] = useState<SubjectGraph | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedTopicId, setSelectedTopicId] = useState<number | null>(null);
  const [prereqChain, setPrereqChain] = useState<PrerequisiteItem[]>([]);
  const [unlockedTopics, setUnlockedTopics] = useState<UnlockedTopicItem[]>([]);
  const [chainLoading, setChainLoading] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>("");

  useEffect(() => {
    async function loadGraph() {
      setLoading(true);
      try {
        const data = await api.getSubjectGraph(subject.subject_id);
        setGraph(data);
        if (data.nodes.length > 0) {
          // Select first node by default or retain
          setSelectedTopicId(data.nodes[0].id);
        }
      } catch (err) {
        console.error("Failed to load skill tree graph:", err);
      } finally {
        setLoading(false);
      }
    }
    loadGraph();
  }, [subject.subject_id]);

  useEffect(() => {
    if (!selectedTopicId) {
      setPrereqChain([]);
      setUnlockedTopics([]);
      return;
    }

    async function loadNodeDetails() {
      setChainLoading(true);
      try {
        const [prereqs, unlocked] = await Promise.all([
          api.getPrerequisites(selectedTopicId!),
          api.getUnlockedTopics(selectedTopicId!).catch(() => []),
        ]);
        setPrereqChain(prereqs);
        setUnlockedTopics(unlocked);
      } catch (err) {
        console.error("Error loading node prerequisites:", err);
      } finally {
        setChainLoading(false);
      }
    }
    loadNodeDetails();
  }, [selectedTopicId]);

  // Group nodes by difficulty level (Tiers 1 to 5)
  const tiers = useMemo(() => {
    if (!graph) return [];
    const filteredNodes = graph.nodes.filter((n) =>
      n.label.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const levelMap: Record<number, typeof graph.nodes> = {};
    for (const node of filteredNodes) {
      const lvl = node.difficulty_level || 1;
      if (!levelMap[lvl]) levelMap[lvl] = [];
      levelMap[lvl].push(node);
    }

    const tierLabels: Record<number, string> = {
      1: "Foundations",
      2: "Core Principles",
      3: "Intermediate Systems",
      4: "Advanced Applications",
      5: "Specialization",
    };

    return Object.keys(levelMap)
      .map(Number)
      .sort((a, b) => a - b)
      .map((lvl) => ({
        level: lvl,
        label: tierLabels[lvl] || `Level ${lvl} Topics`,
        nodes: levelMap[lvl],
      }));
  }, [graph, searchQuery]);

  // Selected node metadata
  const selectedNode = useMemo(() => {
    if (!graph || !selectedTopicId) return null;
    return graph.nodes.find((n) => n.id === selectedTopicId) || null;
  }, [graph, selectedTopicId]);

  // Set of ancestor IDs for active highlighting
  const ancestorIds = useMemo(() => {
    return new Set(prereqChain.map((p) => p.prereq_topic_id));
  }, [prereqChain]);

  // Set of unlocked IDs for active highlighting
  const descendantIds = useMemo(() => {
    return new Set(unlockedTopics.map((u) => u.unlocked_topic_id));
  }, [unlockedTopics]);

  // Deduplicate unlocked topics to guarantee 1 badge per concept
  const uniqueUnlocked = useMemo(() => {
    const map = new Map<number, UnlockedTopicItem>();
    for (const u of unlockedTopics) {
      if (!map.has(u.unlocked_topic_id) || map.get(u.unlocked_topic_id)!.unlock_tier > u.unlock_tier) {
        map.set(u.unlocked_topic_id, u);
      }
    }
    return Array.from(map.values()).sort(
      (a, b) => a.unlock_tier - b.unlock_tier || a.difficulty_level - b.difficulty_level
    );
  }, [unlockedTopics]);

  // Deduplicate prerequisite ancestors
  const uniquePrereqs = useMemo(() => {
    const map = new Map<number, PrerequisiteItem>();
    for (const p of prereqChain) {
      if (!map.has(p.prereq_topic_id) || map.get(p.prereq_topic_id)!.traversal_depth > p.traversal_depth) {
        map.set(p.prereq_topic_id, p);
      }
    }
    return Array.from(map.values()).sort((a, b) => a.traversal_depth - b.traversal_depth);
  }, [prereqChain]);

  return (
    <div className="space-y-6">
      {/* Minimal Top Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-zinc-800/80 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold tracking-tight text-zinc-100">
              {subject.subject_name}
            </h2>
            <span className="text-xs text-orange-400 bg-orange-950/40 border border-orange-800/50 px-2 py-0.5 rounded-md font-medium">
              Skill Tree
            </span>
          </div>
          <p className="text-xs text-zinc-400 mt-1">
            Prerequisite progression across learning tiers. Select any concept to explore prerequisites or launch the Socratic tutor.
          </p>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <input
            type="text"
            placeholder="Search concepts..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full sm:w-64 bg-zinc-900/60 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-orange-500/60 transition"
          />
        </div>
      </div>

      {loading ? (
        <div className="flex h-64 flex-col items-center justify-center gap-2 text-zinc-500">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-zinc-300 border-t-transparent" />
          <span className="text-xs font-mono">Loading skill tree...</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Main Structured Skill Tree Grid */}
          <div className="lg:col-span-8 space-y-6">
            {tiers.length === 0 ? (
              <div className="p-8 text-center border border-dashed border-zinc-800 rounded-xl text-zinc-500 text-xs">
                No topics found matching "{searchQuery}"
              </div>
            ) : (
              tiers.map((tier) => (
                <div key={tier.level} className="space-y-3">
                  <div className="flex items-center justify-between border-b border-zinc-800/50 pb-1.5">
                    <span className="text-xs font-semibold text-zinc-300 tracking-wide">
                      Tier {tier.level} • {tier.label}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                    {tier.nodes.map((node) => {
                      const isSelected = selectedTopicId === node.id;
                      const isAncestor = ancestorIds.has(node.id);
                      const isDescendant = descendantIds.has(node.id);

                      let borderClass = "border-zinc-800/80 hover:border-zinc-700 bg-zinc-900/40 hover:bg-zinc-900/70";
                      if (isSelected) {
                        borderClass = "border-orange-500 bg-orange-950/20 ring-1 ring-orange-500/60 shadow-lg shadow-orange-500/5";
                      } else if (isAncestor) {
                        borderClass = "border-amber-500/60 bg-amber-950/15";
                      } else if (isDescendant) {
                        borderClass = "border-emerald-500/60 bg-emerald-950/15";
                      }

                      return (
                        <div
                          key={node.id}
                          onClick={() => setSelectedTopicId(node.id)}
                          className={`group cursor-pointer rounded-xl border p-4 transition-all duration-150 flex flex-col justify-between ${borderClass}`}
                        >
                          <div>
                            <h4 className="text-sm font-medium text-zinc-100 group-hover:text-orange-300 transition-colors leading-snug">
                              {node.label}
                            </h4>
                          </div>

                          <div className="mt-3 flex items-center justify-between text-xs pt-2.5 border-t border-zinc-800/60">
                            <div>
                              {isSelected ? (
                                <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-orange-400">
                                  <span className="h-1.5 w-1.5 rounded-full bg-orange-400" />
                                  Active Concept
                                </span>
                              ) : isAncestor ? (
                                <span className="text-amber-400/90 text-xs font-medium">
                                  Prerequisite
                                </span>
                              ) : isDescendant ? (
                                <span className="text-emerald-400/90 text-xs font-medium">
                                  Unlocks Next
                                </span>
                              ) : (
                                <span className="text-xs text-zinc-500 group-hover:text-zinc-400 transition-colors">
                                  Select concept
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Minimal Relational Inspection & Action Sidebar */}
          <div className="lg:col-span-4 sticky top-20 space-y-4">
            {selectedNode ? (
              <div className="rounded-xl border border-zinc-800/90 bg-zinc-900/50 p-5 space-y-5">
                <div className="space-y-1.5 border-b border-zinc-800 pb-3.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-medium text-zinc-400 uppercase tracking-wider">
                      Selected Concept
                    </span>
                    <span className="text-xs font-medium text-orange-400 bg-orange-950/60 border border-orange-800/60 px-2 py-0.5 rounded-md">
                      Tier {selectedNode.difficulty_level}
                    </span>
                  </div>
                  <h3 className="text-base font-semibold text-zinc-100 leading-snug">
                    {selectedNode.label}
                  </h3>
                </div>

                {/* Primary Action Button */}
                <div>
                  <button
                    onClick={() => onSelectTopicForTutor(selectedNode.id)}
                    className="w-full flex items-center justify-center gap-2 rounded-xl bg-orange-500 hover:bg-orange-600 text-white px-4 py-3 text-xs font-semibold transition-all shadow-md shadow-orange-500/20 active:scale-[0.98]"
                  >
                    <MessageSquare className="h-4 w-4" />
                    <span>Ask Socratic AI Tutor</span>
                  </button>
                </div>

                {/* Prerequisite Knowledge */}
                <div className="space-y-2.5 pt-2 border-t border-zinc-800/80">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-zinc-300">
                      Prerequisite Knowledge
                    </span>
                    <span className="text-xs text-zinc-500">
                      {uniquePrereqs.length} required
                    </span>
                  </div>

                  {chainLoading ? (
                    <div className="py-2 text-xs text-zinc-500">
                      Tracing prerequisite hierarchy...
                    </div>
                  ) : uniquePrereqs.length === 0 ? (
                    <div className="p-3 rounded-lg bg-zinc-900/60 border border-zinc-800/60 text-xs text-zinc-400">
                      Foundational concept — No prior prerequisites required.
                    </div>
                  ) : (
                    <div className="space-y-1.5">
                      {uniquePrereqs.map((p) => (
                        <div
                          key={p.prereq_topic_id}
                          className="flex items-center justify-between text-xs p-2.5 rounded-lg bg-zinc-900/80 border border-zinc-800"
                        >
                          <div className="flex items-center gap-2 truncate">
                            <span className="h-1.5 w-1.5 rounded-full bg-amber-400 shrink-0" />
                            <span className="text-zinc-200 truncate">
                              {p.prereq_topic_name}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Unlocks Forward */}
                <div className="space-y-2.5 pt-2 border-t border-zinc-800/80">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-zinc-300">
                      Unlocks Forward
                    </span>
                    <span className="text-xs text-zinc-500">
                      {uniqueUnlocked.length} concepts
                    </span>
                  </div>

                  {uniqueUnlocked.length === 0 ? (
                    <div className="text-xs text-zinc-500">
                      Terminal concept or advanced elective.
                    </div>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {uniqueUnlocked.map((u) => (
                        <span
                          key={u.unlocked_topic_id}
                          className="text-xs px-2.5 py-1 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300"
                        >
                          {u.unlocked_topic_name}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-zinc-800 p-6 text-center text-xs text-zinc-500">
                Select a concept from the skill tree to inspect prerequisites and launch the AI tutor.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
