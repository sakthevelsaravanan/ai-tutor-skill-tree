"use client";

import React, { useEffect, useState } from "react";
import { User, CollectionItem, CollectionStats, VectorSearchResult, VectorChunk } from "@/lib/types";
import { api } from "@/lib/api";
import { CustomDropdown } from "@/components/CustomDropdown";
import { ConfirmModal } from "@/components/ConfirmModal";
import {
  Database,
  Search,
  PlusCircle,
  Edit2,
  Trash2,
  Sparkles,
  FileText,
  UploadCloud,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  ArrowRightLeft,
  X,
  AlertTriangle,
  Shield,
} from "lucide-react";

interface VectorStoreManagerProps {
  currentUser: User;
  onSwitchToAdmin: () => void;
  onCoursesUpdated?: () => void;
}

export const VectorStoreManager: React.FC<VectorStoreManagerProps> = ({
  currentUser,
  onSwitchToAdmin,
  onCoursesUpdated,
}) => {
  const isAdmin = currentUser.role === "admin";

  const [collections, setCollections] = useState<CollectionItem[]>([]);
  const [selectedSubject, setSelectedSubject] = useState<string>("");
  const [stats, setStats] = useState<CollectionStats | null>(null);
  const [chunks, setChunks] = useState<VectorChunk[]>([]);
  const [loadingChunks, setLoadingChunks] = useState<boolean>(false);

  const [query, setQuery] = useState<string>("");
  const [topK, setTopK] = useState<number>(4);
  const [searchResults, setSearchResults] = useState<VectorSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState<boolean>(false);

  const [activeTab, setActiveTab] = useState<"search" | "chunks" | "upload">("search");

  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [newChunkId, setNewChunkId] = useState<string>("");
  const [newChunkText, setNewChunkText] = useState<string>("");
  const [newChunkChapter, setNewChunkChapter] = useState<string>("");

  const [editingChunk, setEditingChunk] = useState<VectorChunk | null>(null);
  const [editText, setEditText] = useState<string>("");
  const [editChapter, setEditChapter] = useState<string>("");
  const [modalError, setModalError] = useState<string | null>(null);

  const [actionMessage, setActionMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isClearing, setIsClearing] = useState<boolean>(false);

  // On-screen warning modal state
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    title: string;
    description: string;
    confirmLabel: string;
    variant: "danger" | "warning";
    onConfirm: () => Promise<void>;
  }>({
    isOpen: false,
    title: "",
    description: "",
    confirmLabel: "Confirm",
    variant: "danger",
    onConfirm: async () => {},
  });

  useEffect(() => {
    loadCollections();
  }, []);

  useEffect(() => {
    if (selectedSubject) {
      loadSubjectData(selectedSubject);
    } else {
      setStats(null);
      setChunks([]);
    }
  }, [selectedSubject]);

  const loadCollections = async () => {
    try {
      const data = await api.getCollections();
      setCollections(data);
      if (data.length > 0) {
        setSelectedSubject((prev) => {
          if (prev && data.some((c) => c.name.replace(/^chroma_/, "") === prev)) {
            return prev;
          }
          const bigData = data.find((c) => c.name.includes("big_data"));
          return (bigData || data[0]).name.replace(/^chroma_/, "");
        });
      } else {
        setSelectedSubject("");
      }
    } catch (err) {
      console.error(err);
    }
  };

  const loadSubjectData = async (subKey: string) => {
    setLoadingChunks(true);
    setActionMessage(null);
    try {
      const [statsRes, chunksRes] = await Promise.all([
        api.getCollectionStats(subKey),
        api.getChunks(subKey).catch(() => []),
      ]);
      setStats(statsRes);
      setChunks(chunksRes);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoadingChunks(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsSearching(true);
    setActionMessage(null);
    try {
      const data = await api.searchVectors(selectedSubject, query, topK);
      setSearchResults(data.results || []);
    } catch (err: any) {
      setActionMessage({ type: "error", text: err.message || "Vector search failed" });
    } finally {
      setIsSearching(false);
    }
  };

  const handleAddChunk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newChunkId.trim() || !newChunkText.trim()) return;

    try {
      await api.addChunk(selectedSubject, newChunkId, newChunkText, {
        chapter: newChunkChapter || "General",
        subject: selectedSubject,
      });
      setShowAddModal(false);
      setNewChunkId("");
      setNewChunkText("");
      setNewChunkChapter("");
      setActionMessage({ type: "success", text: `Chunk '${newChunkId}' created and indexed successfully.` });
      loadSubjectData(selectedSubject);
    } catch (err: any) {
      setModalError(err.message || "Failed to create chunk");
    }
  };

  const handleUpdateChunk = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingChunk || !editText.trim()) return;

    try {
      await api.updateChunk(selectedSubject, editingChunk.id, editText, {
        ...editingChunk.metadata,
        chapter: editChapter || editingChunk.metadata?.chapter || "General",
        updated_at: new Date().toISOString(),
      });
      setEditingChunk(null);
      setActionMessage({ type: "success", text: `Chunk '${editingChunk.id}' updated and re-embedded successfully.` });
      loadSubjectData(selectedSubject);
    } catch (err: any) {
      setModalError(err.message || "Failed to update chunk");
    }
  };

  const handleDeleteChunk = (chunkId: string) => {
    setConfirmModal({
      isOpen: true,
      title: "Delete Vector Chunk",
      description: `Permanently delete chunk '${chunkId}' from ChromaDB collection 'chroma_${selectedSubject}'?`,
      confirmLabel: "Delete Chunk",
      variant: "danger",
      onConfirm: async () => {
        try {
          await api.deleteChunks(selectedSubject, [chunkId]);
          setActionMessage({ type: "success", text: `Chunk '${chunkId}' deleted from vector store.` });
          loadSubjectData(selectedSubject);
        } catch (err: any) {
          setActionMessage({ type: "error", text: err.message || "Failed to delete chunk" });
        } finally {
          setConfirmModal((prev) => ({ ...prev, isOpen: false }));
        }
      },
    });
  };

  const handleClearCollection = () => {
    if (!selectedSubject) return;
    setConfirmModal({
      isOpen: true,
      title: `Clear Collection 'chroma_${selectedSubject}'`,
      description: `Permanently wipe all vector embeddings for '${selectedSubject}' from ChromaDB? The relational topic index will also be reset.`,
      confirmLabel: "Clear Collection",
      variant: "danger",
      onConfirm: async () => {
        setIsClearing(true);
        setActionMessage(null);
        try {
          const res = await api.clearCollection(selectedSubject, currentUser.role, currentUser.user_id);
          setActionMessage({
            type: "success",
            text: `Successfully wiped ${res.deleted_count} vectors from 'chroma_${selectedSubject}'.`,
          });
          await loadCollections();
          await loadSubjectData(selectedSubject);
          if (onCoursesUpdated) onCoursesUpdated();
        } catch (err: any) {
          setActionMessage({
            type: "error",
            text: err.message || "Failed to clear collection vectors.",
          });
        } finally {
          setIsClearing(false);
          setConfirmModal((prev) => ({ ...prev, isOpen: false }));
        }
      },
    });
  };

  const handleClearAllVectors = () => {
    setConfirmModal({
      isOpen: true,
      title: "Purge All Courses & Clear Everything",
      description: "DANGER: This will permanently delete ALL ChromaDB vector collections, textbook embeddings, and course records across the entire system. Ready courses will be completely wiped.",
      confirmLabel: "Purge Everything",
      variant: "danger",
      onConfirm: async () => {
        setIsClearing(true);
        setActionMessage(null);
        try {
          const res = await api.clearAllVectors(currentUser.role, currentUser.user_id);
          setActionMessage({
            type: "success",
            text: `Admin Purge Complete: Wiped ${res.total_chunks_deleted} vectors across ${res.collections_cleared?.length || 0} collections. All courses and stores cleared.`,
          });
          await loadCollections();
          setStats(null);
          setChunks([]);
          if (onCoursesUpdated) onCoursesUpdated();
        } catch (err: any) {
          setActionMessage({
            type: "error",
            text: err.message || "Failed to purge all vectors.",
          });
        } finally {
          setIsClearing(false);
          setConfirmModal((prev) => ({ ...prev, isOpen: false }));
        }
      },
    });
  };

  const handlePdfUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pdfFile) return;

    setIsUploading(true);
    setActionMessage(null);
    try {
      const subjectIdMap: Record<string, number> = { dsa: 1, dvlsi: 2, cs: 3, networks: 4 };
      const formData = new FormData();
      formData.append("file", pdfFile);
      formData.append("subject_id", String(subjectIdMap[selectedSubject] || 1));
      formData.append("subject_key", selectedSubject);
      formData.append("uploaded_by", String(currentUser.user_id));

      const res = await api.uploadPdf(formData);
      setActionMessage({
        type: "success",
        text: `Indexed ${res.chunks_indexed} chunks from ${res.file_name} into ChromaDB collection.`,
      });
      setPdfFile(null);
      loadSubjectData(selectedSubject);
    } catch (err: any) {
      setActionMessage({ type: "error", text: err.message || "Document indexing failed." });
    } finally {
      setIsUploading(false);
    }
  };

  if (!isAdmin) {
    return null;
  }

  const collectionOptions = collections.length > 0
    ? collections.map((c) => ({
        value: c.name.replace(/^chroma_/, ""),
        label: `${c.name} (${c.count} chunks)`,
      }))
    : [
        { value: "", label: "No vector collections indexed yet" },
      ];

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Top Header Card */}
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-5 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-zinc-800 border border-orange-500/30 text-orange-400 shadow-sm shadow-orange-500/10">
              <Database className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-semibold text-zinc-100">
                  ChromaDB Vector Store Manager
                </h2>
                <span className="rounded bg-orange-950/40 border border-orange-800/60 px-2 py-0.5 text-[10px] font-mono text-orange-400">
                  MiniLM-L6-v2 Embeddings
                </span>
              </div>
              <p className="text-xs text-zinc-400 mt-0.5">
                Dense Vector Search • Cosine Similarity • Relational Metadata Tagging
              </p>
            </div>
          </div>

          {/* Collection Selector & Stats */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="w-56">
              <label className="block text-[10px] font-mono uppercase text-zinc-400 mb-1">
                Target Collection
              </label>
              <CustomDropdown
                value={selectedSubject}
                onChange={setSelectedSubject}
                options={collectionOptions}
              />
            </div>

            <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-3.5 py-1.5 text-center">
              <div className="text-base font-bold text-orange-400">
                {stats?.total_chunks ?? chunks.length}
              </div>
              <div className="text-[10px] font-mono uppercase text-zinc-500">
                Chunks
              </div>
            </div>

            <button
              onClick={() => loadSubjectData(selectedSubject)}
              className="rounded-lg border border-zinc-800 bg-zinc-900 p-2 text-zinc-400 hover:text-orange-400 hover:border-orange-500/40 transition"
              title="Refresh Collection"
            >
              <RefreshCw className={`h-4 w-4 ${loadingChunks || isClearing ? "animate-spin text-orange-400" : ""}`} />
            </button>
          </div>
        </div>

        {/* Admin Privilege Actions: Clear Collection & Purge Everything */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-zinc-800/80">
          <div className="flex items-center gap-2 text-xs text-zinc-400">
            <Shield className="h-3.5 w-3.5 text-orange-400" />
            <span className="font-semibold text-zinc-300">Admin Vector Privileges:</span>
            <span className="text-zinc-500 hidden sm:inline">Delete indexed vectors or purge all knowledge bases</span>
          </div>

          <div className="flex items-center gap-2.5">
            {/* Clear Active Collection */}
            <button
              type="button"
              disabled={isClearing || !selectedSubject || (stats?.total_chunks === 0 && chunks.length === 0)}
              onClick={handleClearCollection}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-800 bg-zinc-900/80 hover:bg-zinc-800 hover:border-zinc-700 text-xs text-zinc-300 disabled:opacity-40 disabled:cursor-not-allowed transition"
              title={`Clear all vectors from chroma_${selectedSubject}`}
            >
              <Trash2 className="h-3.5 w-3.5 text-zinc-400" />
              <span>Clear Collection Vectors</span>
            </button>

            {/* Purge All Vectors & Clear Everything */}
            <button
              type="button"
              disabled={isClearing || collections.length === 0}
              onClick={handleClearAllVectors}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-500/40 bg-red-950/30 hover:bg-red-950/50 hover:border-red-500/70 text-xs font-semibold text-red-300 disabled:opacity-40 disabled:cursor-not-allowed transition shadow-sm shadow-red-500/10 active:scale-[0.98]"
              title="Permanently wipe all vector collections across ChromaDB"
            >
              <AlertTriangle className="h-3.5 w-3.5 text-red-400" />
              <span>Purge & Clear Everything</span>
            </button>
          </div>
        </div>

        {actionMessage && (
          <div
            className={`flex items-center gap-2 rounded-lg border p-3 text-xs ${
              actionMessage.type === "success"
                ? "border-emerald-800/60 bg-emerald-950/20 text-emerald-400"
                : "border-red-800/60 bg-red-950/20 text-red-400"
            }`}
          >
            {actionMessage.type === "success" ? (
              <CheckCircle2 className="h-4 w-4 shrink-0" />
            ) : (
              <AlertCircle className="h-4 w-4 shrink-0" />
            )}
            <span>{actionMessage.text}</span>
          </div>
        )}
      </div>

      {/* Tabs with Vibrant Orange Active State */}
      <div className="flex border-b border-zinc-800 gap-2">
        <button
          onClick={() => setActiveTab("search")}
          className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs font-medium transition ${
            activeTab === "search"
              ? "border-orange-500 text-orange-400 font-semibold"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <Search className="h-3.5 w-3.5" />
          Semantic Search Tester
        </button>
        <button
          onClick={() => setActiveTab("chunks")}
          className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs font-medium transition ${
            activeTab === "chunks"
              ? "border-orange-500 text-orange-400 font-semibold"
              : "border-transparent text-zinc-400 hover:text-zinc-200"
          }`}
        >
          <FileText className="h-3.5 w-3.5" />
          Vector RUD Manager ({chunks.length})
        </button>
        {isAdmin && (
          <button
            onClick={() => setActiveTab("upload")}
            className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-xs font-medium transition ${
              activeTab === "upload"
                ? "border-orange-500 text-orange-400 font-semibold"
                : "border-transparent text-zinc-400 hover:text-zinc-200"
            }`}
          >
            <UploadCloud className="h-3.5 w-3.5" />
            Direct Document Ingestion
          </button>
        )}
      </div>

      {/* TAB 1: Semantic Search Tester */}
      {activeTab === "search" && (
        <div className="space-y-6">
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-5 space-y-4">
            <div>
              <h3 className="text-xs font-semibold text-zinc-200 flex items-center gap-2">
                <Sparkles className="h-3.5 w-3.5 text-orange-400" />
                Dense Vector Top-K Cosine Similarity Search
              </h3>
              <p className="text-xs text-zinc-400 mt-0.5">
                Queries collection <code className="text-orange-300 font-mono">chroma_{selectedSubject}</code>
              </p>
            </div>

            <form onSubmit={handleSearch} className="space-y-4">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Enter semantic query to search ChromaDB vectors..."
                  className="flex-1 rounded-lg border border-zinc-800 bg-zinc-900 px-3.5 py-2 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-orange-500"
                  required
                />
                <button
                  type="submit"
                  disabled={isSearching || !selectedSubject}
                  className="rounded-lg bg-orange-500 hover:bg-orange-600 text-white font-medium px-5 py-2 text-xs transition shadow-sm shadow-orange-500/25 disabled:opacity-40"
                >
                  {isSearching ? "Searching..." : "Search"}
                </button>
              </div>

              <div className="flex items-center justify-between gap-3 pt-1">
                <div className="flex items-center gap-3">
                  <span className="text-xs text-zinc-400">
                    Top-K: <strong className="text-orange-400">{topK}</strong>
                  </span>
                  <input
                    type="range"
                    min="1"
                    max="8"
                    value={topK}
                    onChange={(e) => setTopK(parseInt(e.target.value))}
                    className="accent-orange-500 cursor-pointer w-28"
                  />
                </div>
                <div className="text-[11px] font-mono text-zinc-500">
                  Cosine Similarity Ranked
                </div>
              </div>
            </form>
          </div>

          {/* Search Results */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-mono font-semibold uppercase text-zinc-400">
                Search Results ({searchResults.length} Matches)
              </h4>
              {searchResults.length > 0 && (
                <span className="font-mono text-[11px] text-orange-400 font-semibold">
                  Top Score: {(searchResults[0].similarity * 100).toFixed(1)}%
                </span>
              )}
            </div>

            {searchResults.length === 0 ? (
              <div className="rounded-xl border border-dashed border-zinc-800 p-8 text-center text-zinc-500 text-xs">
                Run a query above to see semantic matches ranked by cosine similarity.
              </div>
            ) : (
              <div className="space-y-2.5">
                {searchResults.map((res, idx) => (
                  <div
                    key={res.id || idx}
                    className="rounded-xl border border-zinc-800/80 bg-zinc-900/30 p-4 space-y-2 hover:border-orange-500/40 transition"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800/60 pb-2">
                      <div className="flex items-center gap-2">
                        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-orange-500/20 text-orange-400 border border-orange-500/30 font-mono text-[10px] font-bold">
                          #{idx + 1}
                        </span>
                        <span className="font-mono text-xs font-medium text-zinc-200">
                          {res.id}
                        </span>
                        {res.metadata?.chapter && (
                          <span className="rounded bg-zinc-800 px-2 py-0.5 text-[10px] text-zinc-300 font-mono">
                            {res.metadata.chapter}
                          </span>
                        )}
                        {res.metadata?.topic_id && (
                          <span className="rounded bg-orange-950/40 border border-orange-800/60 px-2 py-0.5 text-[10px] text-orange-400 font-mono">
                            Topic #{res.metadata.topic_id}
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-2 text-xs font-mono">
                        <span className="text-zinc-500 text-[11px]">Similarity:</span>
                        <span className="text-orange-400 font-bold">
                          {(res.similarity * 100).toFixed(1)}%
                        </span>
                      </div>
                    </div>

                    <p className="text-xs text-zinc-300 leading-relaxed font-mono text-[11.5px]">
                      "{res.document}"
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: Vector RUD Manager */}
      {activeTab === "chunks" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold text-zinc-200">
              Collection Chunks: <code className="text-orange-400 font-mono">chroma_{selectedSubject}</code>
            </h3>
            {isAdmin && (
              <button
                onClick={() => {
                  setNewChunkId(`${selectedSubject}_manual_${Date.now()}`);
                  setShowAddModal(true);
                }}
                className="flex items-center gap-1.5 rounded-lg bg-orange-500 hover:bg-orange-600 text-white px-3 py-1.5 text-xs font-medium transition shadow-sm shadow-orange-500/20"
              >
                <PlusCircle className="h-3.5 w-3.5" />
                Add Vector Chunk
              </button>
            )}
          </div>

          {loadingChunks ? (
            <div className="flex h-40 items-center justify-center gap-2 text-zinc-500 text-xs font-mono">
              <RefreshCw className="h-4 w-4 animate-spin text-orange-400" />
              <span>Fetching collection vectors...</span>
            </div>
          ) : chunks.length === 0 ? (
            <div className="p-8 text-center rounded-xl border border-dashed border-zinc-800 text-xs text-zinc-500">
              No chunks in this collection. Use "Add Vector Chunk" or "Direct Document Ingestion".
            </div>
          ) : (
            <div className="space-y-2">
              {chunks.map((c) => (
                <div
                  key={c.id}
                  className="rounded-xl border border-zinc-800/80 bg-zinc-900/30 p-3.5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 hover:border-zinc-700 transition"
                >
                  <div className="space-y-1 flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-medium text-zinc-200 truncate">
                        {c.id}
                      </span>
                      {c.metadata?.topic_id && (
                        <span className="rounded bg-orange-950/40 border border-orange-800/50 px-1.5 py-0.2 text-[10px] text-orange-400 font-mono">
                          Topic #{c.metadata.topic_id}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-zinc-400 line-clamp-2 leading-relaxed">
                      {c.document}
                    </p>
                  </div>

                  {isAdmin && (
                    <div className="flex items-center gap-1.5 shrink-0">
                      <button
                        onClick={() => {
                          setEditingChunk(c);
                          setEditText(c.document);
                          setEditChapter(c.metadata?.chapter || "");
                        }}
                        className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-orange-400 transition"
                        title="Edit Chunk"
                      >
                        <Edit2 className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => handleDeleteChunk(c.id)}
                        className="p-1.5 rounded-md hover:bg-red-950/40 text-zinc-500 hover:text-red-400 transition"
                        title="Delete Chunk"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: Direct Upload */}
      {activeTab === "upload" && (
        <form onSubmit={handlePdfUpload} className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-6 space-y-4 max-w-2xl">
          <div>
            <h3 className="text-sm font-semibold text-zinc-100">
              Textbook / Course Materials Indexer
            </h3>
            <p className="text-xs text-zinc-400 mt-1">
              Select a PDF or text file to parse, chunk, and embed directly into <code className="text-orange-400 font-mono">chroma_{selectedSubject}</code>.
            </p>
          </div>

          <div className="space-y-2">
            <input
              type="file"
              accept=".pdf,.txt,.md"
              onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
              className="block w-full text-xs text-zinc-400 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-orange-500 file:text-white hover:file:bg-orange-600 cursor-pointer"
            />
          </div>

          <button
            type="submit"
            disabled={!pdfFile || isUploading}
            className="flex items-center gap-2 rounded-lg bg-orange-500 hover:bg-orange-600 text-white font-medium px-4 py-2 text-xs transition shadow-sm shadow-orange-500/20 disabled:opacity-40"
          >
            {isUploading ? (
              <>
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                <span>Vectorizing & Storing...</span>
              </>
            ) : (
              <>
                <UploadCloud className="h-3.5 w-3.5" />
                <span>Upload & Index into ChromaDB</span>
              </>
            )}
          </button>
        </form>
      )}

      {/* Add Chunk Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-xl border border-zinc-800 bg-zinc-950 p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h3 className="text-sm font-semibold text-zinc-100">Create New Vector Chunk</h3>
              <button onClick={() => setShowAddModal(false)} className="text-zinc-400 hover:text-zinc-100">
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleAddChunk} className="space-y-3">
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Chunk ID</label>
                <input
                  type="text"
                  value={newChunkId}
                  onChange={(e) => setNewChunkId(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-md px-3 py-1.5 text-xs text-zinc-200 font-mono focus:border-orange-500 focus:outline-none"
                  required
                />
              </div>
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Chapter / Tag</label>
                <input
                  type="text"
                  value={newChunkChapter}
                  onChange={(e) => setNewChunkChapter(e.target.value)}
                  placeholder="e.g. Balanced Trees"
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-md px-3 py-1.5 text-xs text-zinc-200 focus:border-orange-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Text Content</label>
                <textarea
                  value={newChunkText}
                  onChange={(e) => setNewChunkText(e.target.value)}
                  rows={4}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-md p-3 text-xs text-zinc-200 focus:border-orange-500 focus:outline-none"
                  required
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 text-xs font-medium rounded-md bg-orange-500 text-white hover:bg-orange-600 shadow-sm"
                >
                  Create & Embed
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Chunk Modal */}
      {editingChunk && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-xl border border-zinc-800 bg-zinc-950 p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <h3 className="text-sm font-semibold text-zinc-100">Edit Chunk: {editingChunk.id}</h3>
              <button onClick={() => setEditingChunk(null)} className="text-zinc-400 hover:text-zinc-100">
                <X className="h-4 w-4" />
              </button>
            </div>
            <form onSubmit={handleUpdateChunk} className="space-y-3">
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Chapter / Tag</label>
                <input
                  type="text"
                  value={editChapter}
                  onChange={(e) => setEditChapter(e.target.value)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-md px-3 py-1.5 text-xs text-zinc-200 focus:border-orange-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="text-xs text-zinc-400 block mb-1">Text Content</label>
                <textarea
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  rows={4}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-md p-3 text-xs text-zinc-200 focus:border-orange-500 focus:outline-none"
                  required
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setEditingChunk(null)}
                  className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 text-xs font-medium rounded-md bg-orange-500 text-white hover:bg-orange-600 shadow-sm"
                >
                  Save & Re-embed
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* On-Screen Interactive Confirmation Modal */}
      <ConfirmModal
        isOpen={confirmModal.isOpen}
        onClose={() => setConfirmModal((prev) => ({ ...prev, isOpen: false }))}
        onConfirm={confirmModal.onConfirm}
        title={confirmModal.title}
        description={confirmModal.description}
        confirmLabel={confirmModal.confirmLabel}
        variant={confirmModal.variant}
        loading={isClearing}
      />
    </div>
  );
};
