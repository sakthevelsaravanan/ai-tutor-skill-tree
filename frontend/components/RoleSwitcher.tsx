"use client";

import React from "react";
import { User, RolesPermissions } from "@/lib/types";
import { X, Check, GraduationCap, BookOpen, ShieldCheck } from "lucide-react";

interface RoleSwitcherModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentUser: User;
  onSelectUser: (user: User) => void;
  allUsers: User[];
  rolesData: RolesPermissions | null;
}

export const RoleSwitcherModal: React.FC<RoleSwitcherModalProps> = ({
  isOpen,
  onClose,
  currentUser,
  onSelectUser,
  allUsers,
}) => {
  if (!isOpen) return null;

  // The 3 primary personas
  const roles = [
    {
      role: "student" as const,
      name: "Roshan Kumar",
      email: "roshan@student.edu",
      badgeColor: "bg-emerald-500/20 text-emerald-300 border-emerald-500/30",
      icon: GraduationCap,
      description: "Prerequisite DAG exploration & Socratic AI tutoring",
    },
    {
      role: "instructor" as const,
      name: "Dr. Alan Turing",
      email: "turing@aitutor.edu",
      badgeColor: "bg-amber-500/20 text-amber-300 border-amber-500/30",
      icon: BookOpen,
      description: "Course document ingestion & curriculum design",
    },
    {
      role: "admin" as const,
      name: "Ada Lovelace",
      email: "admin@aitutor.edu",
      badgeColor: "bg-orange-500/20 text-orange-400 border-orange-500/40",
      icon: ShieldCheck,
      description: "ChromaDB vector store, dense search & chunk RUD",
    },
  ];

  const handleSelectRole = (r: (typeof roles)[number]) => {
    const matched = allUsers.find((u) => u.role === r.role);
    if (matched) {
      onSelectUser(matched);
    } else {
      onSelectUser({
        user_id: r.role === "student" ? 3 : r.role === "instructor" ? 1 : 6,
        full_name: r.name,
        email: r.email,
        role: r.role,
      });
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
      <div className="relative w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-950 p-6 shadow-2xl space-y-5">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100 transition"
        >
          <X className="h-4 w-4" />
        </button>

        {/* Header */}
        <div>
          <h2 className="text-base font-bold text-zinc-100 tracking-tight">Select Role & Profile</h2>
          <p className="text-xs text-zinc-400 mt-1">
            Switch your active profile to test student, instructor, or system admin permissions.
          </p>
        </div>

        {/* 3 Clean Persona Cards */}
        <div className="space-y-2.5">
          {roles.map((r) => {
            const Icon = r.icon;
            const isSelected = currentUser.role === r.role;
            return (
              <button
                key={r.role}
                type="button"
                onClick={() => handleSelectRole(r)}
                className={`w-full flex items-center justify-between p-3.5 rounded-xl border text-left transition-all group ${
                  isSelected
                    ? "border-orange-500/80 bg-zinc-900/90 ring-1 ring-orange-500/30 shadow-md shadow-orange-500/10"
                    : "border-zinc-800 bg-zinc-900/30 hover:border-zinc-700 hover:bg-zinc-900/70"
                }`}
              >
                <div className="flex items-center gap-3">
                  <div
                    className={`flex h-9 w-9 items-center justify-center rounded-lg border ${
                      isSelected
                        ? "bg-orange-500 text-white border-orange-400"
                        : "bg-zinc-900 border-zinc-800 text-zinc-400 group-hover:text-zinc-200"
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                  </div>

                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-zinc-100">{r.name}</span>
                      <span className={`rounded px-1.5 py-0.2 text-[9px] font-mono uppercase font-bold border ${r.badgeColor}`}>
                        {r.role}
                      </span>
                    </div>
                    <p className="text-[11px] text-zinc-400 mt-0.5 leading-snug">{r.description}</p>
                  </div>
                </div>

                <div className="pl-2">
                  {isSelected ? (
                    <div className="flex items-center gap-1 text-[11px] font-semibold text-orange-400 bg-orange-950/60 px-2 py-0.5 rounded-full border border-orange-800/60">
                      <Check className="h-3 w-3" />
                      <span>Active</span>
                    </div>
                  ) : (
                    <span className="text-[11px] text-zinc-500 group-hover:text-zinc-300">Switch →</span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
