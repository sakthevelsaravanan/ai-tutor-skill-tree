"use client";

import React, { useEffect, useState } from "react";
import { User, Subject, Topic, RolesPermissions } from "@/lib/types";
import { api } from "@/lib/api";
import { Navbar } from "@/components/Navbar";
import { SkillTreeDag } from "@/components/SkillTreeDag";
import { TutorChat } from "@/components/TutorChat";
import { DocumentUpload } from "@/components/DocumentUpload";
import { VectorStoreManager } from "@/components/VectorStoreManager";
import { RoleSwitcherModal } from "@/components/RoleSwitcher";
import { X, Sparkles, RefreshCw } from "lucide-react";

export default function Home() {
  const [currentUser, setCurrentUser] = useState<User>({
    user_id: 3,
    full_name: "Roshan Kumar",
    email: "roshan@student.edu",
    role: "student",
  });

  const [allUsers, setAllUsers] = useState<User[]>([]);
  const [rolesData, setRolesData] = useState<RolesPermissions | null>(null);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [selectedSubjectId, setSelectedSubjectId] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);

  // Workflow: Blank/clean Document Ingestion first until user explicitly inputs a document
  const [hasDocument, setHasDocument] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<"upload" | "skilltree" | "tutor" | "vectors">("upload");

  // Selection states
  const [selectedTopicIdForTutor, setSelectedTopicIdForTutor] = useState<number | null>(null);
  const [isRoleModalOpen, setIsRoleModalOpen] = useState<boolean>(false);

  // Manual Topic Completion State for active student
  const [completedTopicIds, setCompletedTopicIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    async function initData() {
      setLoading(true);
      try {
        const [usersRes, rolesRes, subjectsRes] = await Promise.all([
          api.getUsers().catch(() => []),
          api.getRoles().catch(() => null),
          api.getSubjects().catch(() => []),
        ]);

        setAllUsers(usersRes);
        setRolesData(rolesRes);
        setSubjects(subjectsRes);

        if (subjectsRes.length > 0) {
          const defaultSub = subjectsRes[0];
          setSelectedSubjectId(defaultSub.subject_id);
          setHasDocument(true);
        }

        // Restore persisted user if exists in localStorage, else default to student
        let resolvedUser: User | null = null;
        if (typeof window !== "undefined") {
          const savedUserStr = localStorage.getItem("ai_tutor_user");
          if (savedUserStr) {
            try {
              const parsed = JSON.parse(savedUserStr);
              const matched = usersRes.find((u) => u.user_id === parsed.user_id);
              if (matched) resolvedUser = matched;
            } catch {
              // Ignore invalid storage
            }
          }
        }

        if (!resolvedUser && usersRes.length > 0) {
          resolvedUser = usersRes.find((u) => u.role === "student") || usersRes[0];
        }

        if (resolvedUser) {
          setCurrentUser(resolvedUser);
        }

        if (typeof window !== "undefined") {
          const params = new URLSearchParams(window.location.search);
          const tab = params.get("tab");
          if (tab === "skilltree" || tab === "tutor" || tab === "vectors" || tab === "upload") {
            setActiveTab(tab);
          }
          const role = params.get("role");
          if (role === "admin") {
            const adminUser = usersRes.find((u) => u.role === "admin");
            if (adminUser) setCurrentUser(adminUser);
          }
        }
      } catch (err) {
        console.error("Initialization error:", err);
      } finally {
        setLoading(false);
      }
    }
    initData();
  }, []);

  // Persist user selection across page reloads
  useEffect(() => {
    if (typeof window !== "undefined" && currentUser) {
      localStorage.setItem("ai_tutor_user", JSON.stringify(currentUser));
    }
  }, [currentUser]);

  // Synchronize completed topics for active user and subject
  useEffect(() => {
    let active = true;
    setCompletedTopicIds(new Set());
    async function fetchUserCompletions() {
      if (!currentUser?.user_id) return;
      try {
        const res = await api.getCompletedTopics(currentUser.user_id, selectedSubjectId || undefined);
        if (active) setCompletedTopicIds(new Set(res.completed_topic_ids));
      } catch (err) {
        console.error("Failed to load student topic completions:", err);
      }
    }
    fetchUserCompletions();
    return () => {
      active = false;
    };
  }, [currentUser?.user_id, selectedSubjectId]);

  const handleTopicCompleted = (topicId: number) => {
    setCompletedTopicIds((prev) => new Set([...Array.from(prev), topicId]));
  };

  useEffect(() => {
    if (currentUser.role !== "admin" && activeTab === "vectors") {
      setActiveTab("upload");
    }
  }, [currentUser.role, activeTab]);

  const handle1ClickSwitchRole = () => {
    const roleCycle: Record<string, "student" | "instructor" | "admin"> = {
      student: "instructor",
      instructor: "admin",
      admin: "student",
    };
    const nextRole = roleCycle[currentUser.role] || "student";
    const matchingUser = allUsers.find((u) => u.role === nextRole);
    if (matchingUser) {
      setCurrentUser(matchingUser);
    } else {
      const defaults = {
        student: { user_id: 3, full_name: "Roshan Kumar", email: "roshan@student.edu" },
        instructor: { user_id: 1, full_name: "Dr. Alan Turing", email: "turing@aitutor.edu" },
        admin: { user_id: 6, full_name: "Ada Lovelace", email: "admin@aitutor.edu" },
      };
      setCurrentUser({
        ...defaults[nextRole],
        role: nextRole,
      });
    }
  };

  const handleSelectTopicForTutor = (topicId: number) => {
    setSelectedTopicIdForTutor(topicId);
    setActiveTab("tutor");
  };

  const handleSubjectCreated = async (newSubject: Subject) => {
    setSubjects((prev) => {
      const exists = prev.find((s) => s.subject_id === newSubject.subject_id);
      if (exists) return prev;
      return [...prev, newSubject];
    });
    setSelectedSubjectId(newSubject.subject_id);
    setHasDocument(true);
    try {
      const fresh = await api.getSubjects();
      if (fresh.length > 0) {
        setSubjects(fresh);
      }
    } catch (e) {
      console.error("Could not sync fresh subjects:", e);
    }
  };

  const handleDeleteSubject = (deletedSubjectId: number) => {
    setSubjects((prev) => {
      const remaining = prev.filter((s) => s.subject_id !== deletedSubjectId);
      const indexed = remaining.filter((s) => s.is_indexed);
      if (indexed.length === 0) {
        setHasDocument(false);
        setSelectedSubjectId(0);
        setActiveTab("upload");
      } else if (selectedSubjectId === deletedSubjectId) {
        setSelectedSubjectId(indexed[0].subject_id);
      }
      return remaining;
    });
  };

  const handleCoursesPurged = async () => {
    try {
      const fresh = await api.getSubjects();
      setSubjects(fresh);
      const indexed = fresh.filter((s) => s.is_indexed);
      if (indexed.length === 0) {
        setHasDocument(false);
        setSelectedSubjectId(0);
        setActiveTab("upload");
      } else {
        setSelectedSubjectId(indexed[0].subject_id);
      }
    } catch {
      setSubjects([]);
      setHasDocument(false);
      setSelectedSubjectId(0);
      setActiveTab("upload");
    }
  };

  const activeSubject = subjects.find((s) => s.subject_id === selectedSubjectId) || subjects[0] || {
    subject_id: 0,
    subject_key: "",
    subject_name: "No Course Selected",
    description: "Upload a course document to build your knowledge base.",
    is_indexed: false,
    total_topics: 0,
    total_textbooks: 0,
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col">
      {/* Streamlined Minimalist Navbar */}
      <Navbar
        currentUser={currentUser}
        onSwitchRole={handle1ClickSwitchRole}
        onOpenUserModal={() => setIsRoleModalOpen(true)}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        selectedSubjectName={activeSubject.subject_name}
        hasDocument={hasDocument}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-8 py-3 sm:py-4">
        {loading ? (
          <div className="flex h-96 flex-col items-center justify-center gap-3 text-zinc-500">
            <RefreshCw className="h-5 w-5 animate-spin text-orange-400" />
            <p className="font-mono text-xs text-zinc-400">
              Connecting to MySQL 8.0 & ChromaDB...
            </p>
          </div>
        ) : (
          <>
            {/* TAB 1: DOCUMENT INGESTION (FOCUSED FIRST STEP) */}
            {activeTab === "upload" && (
              <DocumentUpload
                subjects={subjects}
                activeSubjectId={selectedSubjectId}
                onSubjectChange={setSelectedSubjectId}
                onSubjectCreated={handleSubjectCreated}
                onProceedToSkillTree={() => setActiveTab("skilltree")}
                onProceedToTutor={() => setActiveTab("tutor")}
                hasDocument={hasDocument}
                setHasDocument={setHasDocument}
                currentUser={currentUser}
                onDeleteSubject={handleDeleteSubject}
              />
            )}

            {/* TAB 2: SKILL TREE (DAG) - UNLOCKED AFTER INGESTION */}
            {activeTab === "skilltree" && (
              <SkillTreeDag
                subject={activeSubject}
                subjects={subjects}
                currentUser={currentUser}
                completedTopicIds={completedTopicIds}
                onSelectTopicForTutor={handleSelectTopicForTutor}
              />
            )}

            {/* TAB 3: AI TUTOR CHAT - UNLOCKED AFTER INGESTION */}
            {activeTab === "tutor" && (
              <TutorChat
                subjects={subjects}
                activeSubjectId={selectedSubjectId}
                initialTopicId={selectedTopicIdForTutor}
                onSubjectChange={setSelectedSubjectId}
                currentUser={currentUser}
                completedTopicIds={completedTopicIds}
                onTopicCompleted={handleTopicCompleted}
              />
            )}

            {/* TAB 5: VECTOR KNOWLEDGE BASE (RUD) - ADMIN ONLY */}
            {activeTab === "vectors" && (
              <VectorStoreManager
                currentUser={currentUser}
                onCoursesUpdated={handleCoursesPurged}
                onSwitchToAdmin={() => {
                  const adminUser = allUsers.find((u) => u.role === "admin");
                  if (adminUser) {
                    setCurrentUser(adminUser);
                  } else {
                    setCurrentUser({
                      user_id: 6,
                      full_name: "Ada Lovelace",
                      email: "admin@aitutor.edu",
                      role: "admin",
                    });
                  }
                }}
              />
            )}
          </>
        )}
      </main>

      {/* Role Switcher Modal */}
      <RoleSwitcherModal
        isOpen={isRoleModalOpen}
        onClose={() => setIsRoleModalOpen(false)}
        currentUser={currentUser}
        onSelectUser={(u) => {
          setCurrentUser(u);
          setIsRoleModalOpen(false);
        }}
        allUsers={allUsers}
        rolesData={rolesData}
      />
    </div>
  );
}
