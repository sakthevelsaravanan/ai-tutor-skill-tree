"use client";

import React from "react";
import { User } from "@/lib/types";
import { UploadCloud, GitFork, MessageSquare, Database, Shield, User as UserIcon } from "lucide-react";

interface NavbarProps {
  currentUser: User;
  onSwitchRole: () => void;
  onOpenUserModal: () => void;
  activeTab: "upload" | "skilltree" | "tutor" | "vectors";
  setActiveTab: (tab: "upload" | "skilltree" | "tutor" | "vectors") => void;
  selectedSubjectName?: string;
  hasDocument: boolean;
}

export function Navbar({
  currentUser,
  onSwitchRole,
  onOpenUserModal,
  activeTab,
  setActiveTab,
  selectedSubjectName,
  hasDocument,
}: NavbarProps) {
  const isAdmin = currentUser.role === "admin";

  const navItems = [
    { id: "upload" as const, label: "Ingest", icon: UploadCloud },
    { id: "skilltree" as const, label: "Skill Tree", icon: GitFork, disabled: !hasDocument },
    { id: "tutor" as const, label: "AI Tutor", icon: MessageSquare, disabled: !hasDocument },
    ...(isAdmin ? [{ id: "vectors" as const, label: "Vectors", icon: Database, disabled: false }] : []),
  ];

  return (
    <header className="sticky top-0 z-40 border-b border-zinc-800/80 bg-zinc-950/90 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-8">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setActiveTab("upload")}
            className="flex items-center gap-2 text-left focus:outline-none group"
          >
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-orange-500 text-white font-bold text-xs shadow-sm shadow-orange-500/30 transition-transform group-hover:scale-105">
              AI
            </div>
            <span className="text-sm font-semibold tracking-tight text-zinc-100">AI Tutor</span>
          </button>

          {hasDocument && selectedSubjectName && (
            <div className="hidden sm:flex items-center gap-1.5 pl-2 border-l border-zinc-800 text-xs text-zinc-400">
              <span className="h-1.5 w-1.5 rounded-full bg-orange-500" />
              <span className="truncate max-w-[180px] font-mono text-[11px] text-zinc-300">
                {selectedSubjectName}
              </span>
            </div>
          )}
        </div>

        {/* Minimal Uncluttered Center Tabs */}
        <nav className="flex items-center gap-1 bg-zinc-900/80 p-1 rounded-lg border border-zinc-800">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                disabled={item.disabled}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  isActive
                    ? "bg-zinc-800 text-orange-400 shadow-sm border border-orange-500/30"
                    : item.disabled
                    ? "text-zinc-600 cursor-not-allowed"
                    : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
                }`}
                title={item.disabled ? "Ingest a document first to unlock" : item.label}
              >
                <Icon className={`h-3.5 w-3.5 ${isActive ? "text-orange-400" : ""}`} />
                <span>{item.label}</span>
                {item.disabled && (
                  <span className="text-[9px] text-zinc-600 font-mono">lock</span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Streamlined Right Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={onOpenUserModal}
            className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs text-zinc-400 hover:text-zinc-200 border border-zinc-800 hover:border-zinc-700 transition"
            title="Inspect Database User"
          >
            {currentUser.role === "admin" ? (
              <Shield className="h-3 w-3 text-orange-400" />
            ) : currentUser.role === "instructor" ? (
              <Shield className="h-3 w-3 text-amber-300" />
            ) : (
              <UserIcon className="h-3 w-3 text-emerald-400" />
            )}
            <span className="max-w-[100px] truncate text-[11px] font-mono">{currentUser.full_name}</span>
          </button>

          <button
            onClick={onSwitchRole}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 text-zinc-200 transition"
            title="1-Click Switch Role"
          >
            <span className="text-[10px] uppercase text-zinc-500">Role:</span>
            <span
              className={`font-semibold capitalize ${
                currentUser.role === "admin"
                  ? "text-orange-400"
                  : currentUser.role === "instructor"
                  ? "text-amber-300"
                  : "text-emerald-400"
              }`}
            >
              {currentUser.role}
            </span>
          </button>
        </div>
      </div>
    </header>
  );
}
