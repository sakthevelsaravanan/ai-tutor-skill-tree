"use client";

import React, { useState } from "react";
import { Subject, User } from "@/lib/types";
import { api } from "@/lib/api";
import { ConfirmModal } from "@/components/ConfirmModal";
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Database,
  ArrowRight,
  Sparkles,
  GitFork,
  MessageSquare,
  Tag,
  Trash2,
} from "lucide-react";

interface DocumentUploadProps {
  subjects: Subject[];
  activeSubjectId: number;
  onSubjectChange: (subjectId: number) => void;
  onSubjectCreated?: (newSubject: Subject) => void;
  onProceedToSkillTree: () => void;
  onProceedToTutor: () => void;
  hasDocument: boolean;
  setHasDocument: (val: boolean) => void;
  currentUser?: User;
  onDeleteSubject?: (subjectId: number) => void;
}

export function DocumentUpload({
  subjects,
  activeSubjectId,
  onSubjectChange,
  onSubjectCreated,
  onProceedToSkillTree,
  onProceedToTutor,
  hasDocument,
  setHasDocument,
  currentUser,
  onDeleteSubject,
}: DocumentUploadProps) {
  const isAdmin = currentUser?.role === "admin";
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    title: string;
    description: string;
    subjectId: number;
    subjectName: string;
  }>({
    isOpen: false,
    title: "",
    description: "",
    subjectId: 0,
    subjectName: "",
  });
  const [deleting, setDeleting] = useState<boolean>(false);
  const [courseName, setCourseName] = useState<string>("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<{
    subject_id: number;
    subject_name: string;
    file_name: string;
    pages_parsed: number;
    chunks_indexed: number;
    collection: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selected = e.target.files[0];
      const validExts = [".pdf", ".ppt", ".pptx", ".txt", ".md"];
      const lower = selected.name.toLowerCase();
      if (!validExts.some((ext) => lower.endsWith(ext))) {
        setError("Invalid file type. Supported formats: PDF, PPT, PPTX, TXT, MD.");
        return;
      }
      if (selected.size > 50 * 1024 * 1024) {
        setError("File size exceeds 50MB limit. Please upload a smaller document.");
        return;
      }
      setFile(selected);
      setError(null);
      // Auto-populate course name from filename if empty
      if (!courseName.trim()) {
        const rawName = selected.name.replace(/\.[^/.]+$/, "").replace(/[_-]/g, " ");
        // Title case
        const titleCase = rawName.replace(/\w\S*/g, (txt) => txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase());
        setCourseName(titleCase);
      }
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Please select a course document (PDF, PPT, PPTX, TXT, or MD) to ingest.");
      return;
    }
    if (!courseName.trim()) {
      setError("Please enter a name for this course / subject.");
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("subject_name", courseName.trim());


    try {
      const data = await api.uploadDocument(formData);
      const createdSubject: Subject = {
        subject_id: data.subject_id,
        subject_key: data.subject_key || `sub_${data.subject_id}`,
        subject_name: data.subject_name || courseName.trim(),
        description: "Course materials",
        is_indexed: true,
        total_topics: 0,
        total_textbooks: 1,
      };

      if (onSubjectCreated) {
        onSubjectCreated(createdSubject);
      }
      setResult({
        subject_id: data.subject_id,
        subject_name: data.subject_name || courseName.trim(),
        file_name: data.file_name,
        pages_parsed: data.pages_parsed || 1,
        chunks_indexed: data.chunks_indexed || 1,
        collection: data.collection,
      });
      onSubjectChange(data.subject_id);
      setHasDocument(true);
      setFile(null);
    } catch (err: any) {
      setError(err.message || "Document indexing and course generation failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmDelete = async () => {
    if (!confirmModal.subjectId) return;
    setDeleting(true);
    try {
      await api.deleteCourse(confirmModal.subjectId, currentUser?.role, currentUser?.user_id);
      if (onDeleteSubject) {
        onDeleteSubject(confirmModal.subjectId);
      }
      setConfirmModal((prev) => ({ ...prev, isOpen: false }));
    } catch (err: any) {
      setError(err.message || "Failed to delete course.");
      setConfirmModal((prev) => ({ ...prev, isOpen: false }));
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="w-full max-w-6xl mx-auto space-y-6">
      {/* Pristine Clean Header */}
      <div className="space-y-2">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange-950/40 border border-orange-800/60 text-xs font-mono text-orange-400">
          <Sparkles className="h-3.5 w-3.5" />
          <span>Course library</span>
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-zinc-100">
          Ingest Course Materials
        </h1>
        <p className="text-sm text-zinc-400 leading-relaxed">
          Upload a textbook, syllabus, or lecture notes to build your course and start learning.
        </p>
      </div>

      {/* Confirmation Card after Document Ingestion */}
      {result && hasDocument ? (
        <div className="rounded-2xl border border-orange-500/40 bg-zinc-900/60 p-6 space-y-6 shadow-xl shadow-orange-500/5">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
            <div className="flex items-center gap-2.5 text-orange-400 text-sm font-semibold">
              <CheckCircle2 className="h-5 w-5" />
              <span>Course ready</span>
            </div>
            <button
              onClick={() => {
                setResult(null);
                setHasDocument(subjects.some(s => !!s.is_indexed));
                setCourseName("");
                setFile(null);
              }}
              className="text-xs text-zinc-400 hover:text-zinc-200 underline"
            >
              Upload Another Course
            </button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-mono text-xs text-zinc-300">
            <div className="p-3 rounded-xl bg-zinc-950 border border-zinc-800">
              <span className="text-zinc-500 block text-[10px] uppercase">Course Name</span>
              <span className="truncate block font-semibold text-zinc-100 mt-0.5">{result.subject_name}</span>
            </div>
            <div className="p-3 rounded-xl bg-zinc-950 border border-zinc-800">
              <span className="text-zinc-500 block text-[10px] uppercase">Document File</span>
              <span className="truncate block font-semibold text-zinc-100 mt-0.5">{result.file_name}</span>
            </div>
            <div className="p-3 rounded-xl bg-zinc-950 border border-zinc-800">
              <span className="text-zinc-500 block text-[10px] uppercase">ChromaDB Chunks</span>
              <span className="font-semibold text-orange-400 mt-0.5">{result.chunks_indexed} vectors</span>
            </div>
            <div className="p-3 rounded-xl bg-zinc-950 border border-zinc-800">
              <span className="text-zinc-500 block text-[10px] uppercase">Status</span>
              <span className="font-semibold text-emerald-400 mt-0.5">Ready for Tutor</span>
            </div>
          </div>

          {/* Primary Action Buttons */}
          <div className="pt-2 flex flex-col sm:flex-row gap-3">
            <button
              onClick={onProceedToSkillTree}
              className="flex-1 flex items-center justify-center gap-2 rounded-xl bg-orange-500 hover:bg-orange-600 text-white py-3 px-5 text-xs font-semibold transition shadow-md shadow-orange-500/25 active:scale-[0.98]"
            >
              <GitFork className="h-4 w-4" />
              <span>Explore skill tree</span>
            </button>

            <button
              onClick={onProceedToTutor}
              className="flex-1 flex items-center justify-center gap-2 rounded-xl border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 py-3 px-5 text-xs font-semibold transition active:scale-[0.98]"
            >
              <MessageSquare className="h-4 w-4 text-orange-400" />
              <span>Open tutor</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="w-full max-w-2xl mx-auto">
          {/* Document Input Form with Custom Name & Classification */}
          <form onSubmit={handleUpload} className="course-form w-full space-y-5 rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 sm:p-7 shadow-xl">
          {/* 1. Drag and Drop File Zone */}
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
              Document (PDF, PPT, PPTX, TXT, MD)
            </label>
            <div className="border-2 border-dashed border-zinc-800 hover:border-orange-500/60 rounded-xl p-5 text-center transition bg-zinc-900/40 group">
              <input
                id="doc-file-input"
                type="file"
                accept=".pdf,.ppt,.pptx,.txt,.md"
                onChange={handleFileChange}
                className="hidden"
              />
              <label htmlFor="doc-file-input" className="cursor-pointer space-y-2.5 block">
                <div className="h-12 w-12 mx-auto rounded-xl bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-400 group-hover:text-orange-400 group-hover:border-orange-500/40 transition">
                  <UploadCloud className="h-6 w-6" />
                </div>
                <div>
                  <span className="text-xs font-semibold text-zinc-200 group-hover:text-orange-400 transition underline">
                    Click to select document file
                  </span>
                  <span className="text-xs text-zinc-500"></span>
                </div>
                <p className="text-[11px] font-mono text-zinc-500">
                  Accepts textbook PDFs, PowerPoint slides (.ppt, .pptx), and lecture notes
                </p>
              </label>

              {file && (
                <div className="mt-3 flex flex-wrap justify-center items-center gap-2 break-all px-3 py-1.5 rounded-lg bg-orange-950/40 border border-orange-800/60 text-xs text-orange-300 font-mono">
                  <FileText className="h-3.5 w-3.5 text-orange-400" />
                  <span>{file.name}</span>
                  <span className="text-zinc-500">({(file.size / (1024 * 1024)).toFixed(1)} MB)</span>
                </div>
              )}
            </div>
          </div>

          {/* 2. Custom Course Name & Classification */}
          <div className="grid grid-cols-1 gap-4">
            <div className="space-y-1.5">
              <label htmlFor="course-name" className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
                Course name
              </label>
              <input
                id="course-name"
                type="text"
                maxLength={100}
                value={courseName}
                onChange={(e) => setCourseName(e.target.value)}
                placeholder="e.g. Linear Algebra, DBMS, Quantum Physics"
                className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3.5 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-orange-500"
                required
              />
            </div>


          </div>

          {/* Submit Action */}
          <button
            type="submit"
            disabled={!file || loading}
            className="w-full flex items-center justify-center gap-2 rounded-xl bg-orange-500 hover:bg-orange-600 text-white font-semibold py-3 text-xs transition shadow-md shadow-orange-500/25 disabled:opacity-40 active:scale-[0.99]"
          >
            {loading ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin" />
                <span>Processing document in batches. Large books may take several minutes...</span>
              </>
            ) : (
              <>
                <Database className="h-4 w-4" />
                <span>Upload & build course</span>
              </>
            )}
          </button>
        </form>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-xl border border-red-800/60 bg-red-950/20 text-xs flex items-center gap-2 text-red-400">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* On-screen confirmation modal */}
      <ConfirmModal
        isOpen={confirmModal.isOpen}
        onClose={() => setConfirmModal((prev) => ({ ...prev, isOpen: false }))}
        onConfirm={handleConfirmDelete}
        title={confirmModal.title}
        description={confirmModal.description}
        confirmLabel="Delete Course"
        variant="danger"
        loading={deleting}
      />
    </div>
  );
}
