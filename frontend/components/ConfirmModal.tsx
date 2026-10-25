"use client";

import React, { useEffect } from "react";
import { AlertTriangle, Trash2, X, RefreshCw } from "lucide-react";

interface ConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void | Promise<void>;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "warning";
  loading?: boolean;
}

export function ConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = "Confirm Delete",
  cancelLabel = "Cancel",
  variant = "danger",
  loading = false,
}: ConfirmModalProps) {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && !loading) {
        onClose();
      }
    }
    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
    }
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, loading, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-4 backdrop-blur-md animate-in fade-in duration-150">
      <div
        className="relative w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-950 p-6 shadow-2xl space-y-5 animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close Button */}
        <button
          type="button"
          disabled={loading}
          onClick={onClose}
          className="absolute right-4 top-4 rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100 transition disabled:opacity-50"
        >
          <X className="h-4 w-4" />
        </button>

        {/* Warning Icon & Heading */}
        <div className="flex items-start gap-3.5">
          <div
            className={`h-11 w-11 rounded-xl flex items-center justify-center shrink-0 border ${
              variant === "danger"
                ? "bg-red-950/50 border-red-500/40 text-red-400"
                : "bg-orange-950/50 border-orange-500/40 text-orange-400"
            }`}
          >
            {variant === "danger" ? (
              <Trash2 className="h-5 w-5" />
            ) : (
              <AlertTriangle className="h-5 w-5" />
            )}
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-semibold text-zinc-100 tracking-tight">
              {title}
            </h3>
            <p className="text-xs text-zinc-400 leading-relaxed">
              {description}
            </p>
          </div>
        </div>

        {/* Warning Callout Box */}
        <div className="rounded-xl border border-red-900/50 bg-red-950/20 p-3 text-xs text-red-300 flex items-start gap-2.5">
          <AlertTriangle className="h-4 w-4 text-red-400 shrink-0 mt-0.5" />
          <span className="leading-snug">
            This action is irreversible. All related vector chunks, embeddings, and relational curriculum records will be wiped immediately.
          </span>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            disabled={loading}
            onClick={onClose}
            className="px-4 py-2 rounded-xl border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 text-xs font-medium text-zinc-300 transition disabled:opacity-50"
          >
            {cancelLabel}
          </button>

          <button
            type="button"
            disabled={loading}
            onClick={onConfirm}
            className={`flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold text-white transition shadow-md disabled:opacity-50 active:scale-[0.98] ${
              variant === "danger"
                ? "bg-red-600 hover:bg-red-700 shadow-red-600/20"
                : "bg-orange-500 hover:bg-orange-600 shadow-orange-500/20"
            }`}
          >
            {loading ? (
              <>
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                <span>Processing...</span>
              </>
            ) : (
              <>
                <Trash2 className="h-3.5 w-3.5" />
                <span>{confirmLabel}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
