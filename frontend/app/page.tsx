 "use client";
import { useEffect, useState } from "react";
import { User, Subject } from "@/lib/types";
import { api } from "@/lib/api";
import { Navbar } from "@/components/Navbar";
import { Login } from "@/components/Login";
import { SkillTreeDag } from "@/components/SkillTreeDag";
import { TutorChat } from "@/components/TutorChat";
import { DocumentUpload } from "@/components/DocumentUpload";
import { VectorStoreManager } from "@/components/VectorStoreManager";
import { Plus, ArrowLeft, Trash2 } from "lucide-react";
import { ConfirmModal } from "@/components/ConfirmModal";

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [subjectId, setSubjectId] = useState(0);
  const [topicId, setTopicId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<"upload" | "skilltree" | "tutor" | "vectors">("upload");
  const [hasDocument, setHasDocument] = useState(false);
  const [showCourseUpload, setShowCourseUpload] = useState(false);
  const [deleteModal, setDeleteModal] = useState<{ isOpen: boolean; subjectId: number; subjectName: string }>({
    isOpen: false,
    subjectId: 0,
    subjectName: "",
  });
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    api.me().then(setUser).catch(() => {}).finally(() => setReady(true));
    const expired = () => setUser(null);
    window.addEventListener("auth-expired", expired);
    return () => window.removeEventListener("auth-expired", expired);
  }, []);

  const refresh = async () => {
    try {
      const rows = await api.getSubjects();
      setSubjects(rows);
      setHasDocument(rows.some(s => !!s.is_indexed));
      setSubjectId(id => rows.some(s => s.subject_id === id) ? id : (rows[0]?.subject_id || 0));
      setError("");
    } catch (e: any) {
      setError(e.message);
    }
  };

  useEffect(() => {
    if (user) {
      setActiveTab("upload");
      setTopicId(null);
      setShowCourseUpload(false);
      refresh();
    } else {
      setSubjects([]);
      setSubjectId(0);
    }
  }, [user]);

  const logout = async () => {
    try {
      await api.logout();
      setUser(null);
    } catch (e: any) {
      setError(e.message);
    }
  };

  if (!ready) {
    return <main className="min-h-screen bg-zinc-950 text-zinc-300 grid place-items-center">Loading...</main>;
  }

  if (!user) {
    return <Login onLogin={setUser} />;
  }

  const subject = subjects.find(s => s.subject_id === subjectId);

  return (
    <div className={`app-shell bg-zinc-950 text-zinc-100 ${activeTab === "tutor" ? "app-shell-chat" : ""}`}>
      <Navbar
        currentUser={user}
        onLogout={logout}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        hasDocument={hasDocument}
      />
      <main className="app-main">
        {error && <p role="alert" className="text-red-400">{error}</p>}
        {activeTab === "upload" && (
          (showCourseUpload || subjects.length === 0) ? (
            <div className="space-y-4">
              {subjects.length > 0 && (
                <button
                  onClick={() => setShowCourseUpload(false)}
                  className="inline-flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition"
                >
                  <ArrowLeft className="h-3.5 w-3.5" /> Back to your courses
                </button>
              )}
              <DocumentUpload
                subjects={subjects}
                activeSubjectId={subjectId}
                onSubjectChange={setSubjectId}
                onSubjectCreated={s => {
                  setSubjectId(s.subject_id);
                  refresh();
                  setShowCourseUpload(false);
                }}
                onProceedToSkillTree={() => setActiveTab("skilltree")}
                onProceedToTutor={() => setActiveTab("tutor")}
                hasDocument={hasDocument}
                setHasDocument={setHasDocument}
                currentUser={user}
                onDeleteSubject={() => refresh()}
              />
            </div>
          ) : (
            <section className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-2xl font-semibold">Your courses</h1>
                  <p className="text-sm text-zinc-400">Select a course to view its skill tree or upload your own course materials.</p>
                </div>
                <button
                  onClick={() => setShowCourseUpload(true)}
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-orange-600 hover:bg-orange-500 text-white font-medium text-xs transition shadow-sm shadow-orange-600/30 active:scale-95"
                >
                  <Plus className="h-4 w-4" />
                  <span>Upload Course</span>
                </button>
              </div>

              <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">
                {subjects.map(s => (
                  <div
                    key={s.subject_id}
                    className="relative group rounded-xl border border-zinc-800 bg-zinc-900 hover:border-zinc-700 transition flex items-center justify-between p-5"
                  >
                    <button
                      className="text-left flex-1 min-w-0 pr-2"
                      onClick={() => {
                        setSubjectId(s.subject_id);
                        setTopicId(null);
                        setActiveTab("skilltree");
                      }}
                    >
                      <span className="block font-semibold text-zinc-100 truncate">{s.subject_name}</span>
                      <span className="text-sm text-zinc-400 block mt-1">{s.total_topics} chapters · Open learning path</span>
                    </button>
                    {user.role === "admin" && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeleteModal({
                            isOpen: true,
                            subjectId: s.subject_id,
                            subjectName: s.subject_name,
                          });
                        }}
                        className="opacity-0 group-hover:opacity-100 text-zinc-500 hover:text-red-400 transition p-2 rounded-lg hover:bg-zinc-800"
                        title={`Delete course '${s.subject_name}'`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )
        )}
        {activeTab === "skilltree" && subject && (
          <SkillTreeDag
            key={subjectId}
            subject={subject}
            currentUser={user}
            onSelectTopicForTutor={id => {
              setTopicId(id);
              setActiveTab("tutor");
            }}
          />
        )}
        {activeTab === "tutor" && subject && (
          <TutorChat
            key={`${user.user_id}-${subjectId}`}
            currentUser={user}
            subjects={subjects}
            activeSubjectId={subjectId}
            initialTopicId={topicId}
            onSubjectChange={id => {
              setSubjectId(id);
              setTopicId(null);
            }}
            onNavigateToSkillTree={() => setActiveTab("skilltree")}
            onTopicCompleted={() => refresh()}
          />
        )}
        {activeTab === "vectors" && user.role === "admin" && (
          <VectorStoreManager subject={subject} />
        )}
        {/* Admin Delete Course Confirmation Modal */}
        <ConfirmModal
          isOpen={deleteModal.isOpen}
          onClose={() => setDeleteModal({ isOpen: false, subjectId: 0, subjectName: "" })}
          onConfirm={async () => {
            if (!deleteModal.subjectId) return;
            setDeleting(true);
            try {
              await api.deleteCourse(deleteModal.subjectId, user?.role, user?.user_id);
              refresh();
              setDeleteModal({ isOpen: false, subjectId: 0, subjectName: "" });
            } catch (err: any) {
              setError(err.message || "Failed to delete course.");
              setDeleteModal({ isOpen: false, subjectId: 0, subjectName: "" });
            } finally {
              setDeleting(false);
            }
          }}
          title={`Delete Course '${deleteModal.subjectName}'`}
          description={`Permanently delete '${deleteModal.subjectName}' and wipe all its indexed vectors, topics, and documents?`}
          confirmLabel="Delete Course"
          variant="danger"
          loading={deleting}
        />
      </main>
    </div>
  );
}
