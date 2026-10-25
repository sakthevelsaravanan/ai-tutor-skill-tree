"use client";

import React, { useState } from "react";
import { Subject, User } from "@/lib/types";
import { api } from "@/lib/api";
import { CustomDropdown } from "@/components/CustomDropdown";
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
  const [classification, setClassification] = useState<string>("Computer Science & Engineering");
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

  const academicFields = [
    "Computer Science & Engineering",
    "Data Science & Artificial Intelligence",
    "Electrical & Electronics Engineering",
    "Mathematics & Statistics",
    "Physics & Applied Sciences",
    "Mechanical & Aerospace Engineering",
    "Biomedical Engineering",
    "General STEM",
  ];

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selected = e.target.files[0];
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
      setError("Please select a course document (PDF, TXT, or MD) to ingest.");
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
    formData.append("classification", classification);
    formData.append("uploaded_by", "1");

    try {
      const data = await api.uploadDocument(formData);
      const createdSubject: Subject = {
        subject_id: data.subject_id,
        subject_key: data.subject_key || `sub_${data.subject_id}`,
        subject_name: data.subject_name || courseName.trim(),
        description: `Classification: ${classification}. Course curriculum.`,
        is_indexed: true,
        total_topics: 4,
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
      // Auto-recovery: check if backend completed indexing before fetch returned
      try {
        const fresh = await api.getSubjects();
        const match = fresh.find(
          (s) =>
            s.subject_name.toLowerCase() === courseName.trim().toLowerCase() ||
            s.subject_key.toLowerCase() === courseName.trim().toLowerCase()
        );
        if (match) {
          if (onSubjectCreated) onSubjectCreated(match);
          onSubjectChange(match.subject_id);
          setHasDocument(true);
          setResult({
            subject_id: match.subject_id,
            subject_name: match.subject_name,
            file_name: file?.name || "Uploaded Document",
            pages_parsed: 1,
            chunks_indexed: match.total_topics || 4,
            collection: `chroma_${match.subject_key}`,
          });
          return;
        }
      } catch (_) {}

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
    <div className="max-w-4xl mx-auto py-8 space-y-8">
      {/* Pristine Clean Header */}
      <div className="text-center space-y-3">
        <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-orange-950/40 border border-orange-800/60 text-xs font-mono text-orange-400">
          <Sparkles className="h-3.5 w-3.5" />
          <span>Step 1: Course Ingestion & Relational Setup</span>
        </div>
        <h1 className="text-3xl font-bold tracking-tight text-zinc-100">
          Ingest Course Materials
        </h1>
        <p className="text-xs sm:text-sm text-zinc-400 max-w-lg mx-auto leading-relaxed">
          Upload any STEM textbook, syllabus, or lecture notes. Name and classify your course—the system dynamically builds the relational skill tree and vectorizes chunks into ChromaDB.
        </p>
      </div>

      {/* Confirmation Card after Document Ingestion */}
      {result && hasDocument ? (
        <div className="rounded-2xl border border-orange-500/40 bg-zinc-900/60 p-6 space-y-6 shadow-xl shadow-orange-500/5">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
            <div className="flex items-center gap-2.5 text-orange-400 text-sm font-semibold">
              <CheckCircle2 className="h-5 w-5" />
              <span>Course Registered & Relational DAG Generated</span>
            </div>
            <button
              onClick={() => {
                setResult(null);
                setHasDocument(false);
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
              <span>Step 2: Explore Prerequisite Skill Tree (DAG) →</span>
            </button>

            <button
              onClick={onProceedToTutor}
              className="flex-1 flex items-center justify-center gap-2 rounded-xl border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 py-3 px-5 text-xs font-semibold transition active:scale-[0.98]"
            >
              <MessageSquare className="h-4 w-4 text-orange-400" />
              <span>Step 3: Launch Socratic AI Tutor Chat →</span>
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Quick Selector for Already-Ingested Courses */}
          {(() => {
            const indexedSubjects = subjects.filter((s) => s.is_indexed);
            if (indexedSubjects.length === 0) return null;
            return (
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
                    Ready Courses ({indexedSubjects.length})
                  </span>
                  <span className="text-[11px] text-zinc-500">
                    Select an indexed course to open its skill tree
                  </span>
                </div>
                <div className="flex flex-wrap gap-2.5">
                  {indexedSubjects.map((sub) => {
                    const isSelected = sub.subject_id === activeSubjectId;
                    return (
                      <div
                        key={sub.subject_id}
                        className={`inline-flex items-center rounded-lg border transition ${
                          isSelected
                            ? "bg-orange-950/50 border-orange-500/70 text-orange-300 shadow-sm shadow-orange-500/10"
                            : "bg-zinc-900/60 border-zinc-800 hover:border-zinc-700 text-zinc-200"
                        }`}
                      >
                        <button
                          type="button"
                          onClick={() => {
                            onSubjectChange(sub.subject_id);
                            setHasDocument(true);
                            onProceedToSkillTree();
                          }}
                          className="flex items-center gap-2 px-3.5 py-2 text-xs font-medium focus:outline-none"
                        >
                          <span className="h-2 w-2 rounded-full bg-orange-500" />
                          <span className="font-semibold">{sub.subject_name}</span>
                          <ArrowRight className="h-3 w-3 text-orange-400 opacity-70 ml-0.5" />
                        </button>

                        {isAdmin && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setConfirmModal({
                                isOpen: true,
                                title: `Delete Course '${sub.subject_name}'`,
                                description: `Permanently delete '${sub.subject_name}' and wipe all its indexed vectors, topics, and documents?`,
                                subjectId: sub.subject_id,
                                subjectName: sub.subject_name,
                              });
                            }}
                            className="pr-2.5 pl-1 py-2 text-zinc-500 hover:text-red-400 transition"
                            title={`Delete course '${sub.subject_name}'`}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })()}

          {/* Document Input Form with Custom Name & Classification */}
          <form onSubmit={handleUpload} className="space-y-6 rounded-2xl border border-zinc-800 bg-zinc-900/30 p-6 sm:p-8">
          {/* 1. Drag and Drop File Zone */}
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
              1. Select Course Document (PDF, TXT, MD)
            </label>
            <div className="border-2 border-dashed border-zinc-800 hover:border-orange-500/60 rounded-2xl p-8 text-center transition bg-zinc-900/40 group">
              <input
                id="doc-file-input"
                type="file"
                accept=".pdf,.txt,.md"
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
                  <span className="text-xs text-zinc-500"> or drag and drop</span>
                </div>
                <p className="text-[11px] font-mono text-zinc-500">
                  Accepts textbook PDFs, syllabus files, and markdown lecture notes
                </p>
              </label>

              {file && (
                <div className="mt-4 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-orange-950/40 border border-orange-800/60 text-xs text-orange-300 font-mono">
                  <FileText className="h-3.5 w-3.5 text-orange-400" />
                  <span>{file.name}</span>
                  <span className="text-zinc-500">({(file.size / 1024).toFixed(1)} KB)</span>
                </div>
              )}
            </div>
          </div>

          {/* 2. Custom Course Name & Classification */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
                2. Course / Subject Name
              </label>
              <input
                type="text"
                value={courseName}
                onChange={(e) => setCourseName(e.target.value)}
                placeholder="e.g. Linear Algebra, DBMS, Quantum Physics"
                className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3.5 py-2.5 text-xs text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-orange-500"
                required
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
                3. Academic Classification / Field
              </label>
              <CustomDropdown
                value={classification}
                onChange={setClassification}
                options={academicFields}
                placeholder="Select academic discipline..."
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
                <span>Vectorizing Chunks & Generating Relational Skill Tree...</span>
              </>
            ) : (
              <>
                <Database className="h-4 w-4" />
                <span>Ingest Document & Build Relational Skill Tree</span>
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
