import {
  Subject,
  Topic,
  PrerequisiteItem,
  UnlockedTopicItem,
  SubjectGraph,
  User,
  RolesPermissions,
  CollectionItem,
  CollectionStats,
  VectorSearchResult,
  VectorChunk,
  TutorQueryRequest,
  TutorQueryResponse,
} from "./types";

// Same-origin requests use Next.js rewrites and HttpOnly session cookies.
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const res = await fetch(url, {
    credentials: "include",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
  });

  if (!res.ok) {
    let errorDetail = "Request failed";
    try {
      const errJson = await res.json();
      errorDetail = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail || errJson);
    } catch {
      errorDetail = `${res.status} ${res.statusText}`;
    }
    if (res.status === 401 && typeof window !== "undefined") window.dispatchEvent(new Event("auth-expired"));
    throw new Error(errorDetail);
  }

  return res.json();
}

export const api = {
  me: () => request<User>("/api/auth/me"),
  logout: () => request("/api/auth/logout", { method: "POST" }),
  health: () => request<{status: string; database: string}>("/api/health"),
  startSession: (userId: number, subjectId: number, topicId?: number) => request<{session_id: string}>("/api/sessions/start", {method: "POST", body: JSON.stringify({user_id: userId, subject_id: subjectId, current_topic_id: topicId})}),
  getSessions: (userId: number, subjectId: number) => request<Array<{session_id: string}>>(`/api/sessions/user/${userId}?subject_id=${subjectId}`),
  getSession: (id: string) => request<{current_topic_id: number; messages: Array<{log_id: number; role: "user" | "assistant"; content: string; created_at: string}>}>(`/api/sessions/${id}`),
  assess: (sessionId: string, topicId: number, mcq: number, check: number, verdict: string) => request<{mastery_status: string; next_stage: string}>("/api/sessions/quiz-attempt", {method: "POST", body: JSON.stringify({session_id: sessionId, topic_id: topicId, mcq_score: mcq, check_score: check, verdict})}),
  mastery: (userId: number, subjectId: number) => request<{mastery_percentage: number; topics: Array<{topic_id: number; topic_name: string; mastery_status: string; total_attempts: number}>}>(`/api/sessions/mastery/${userId}/${subjectId}`),
  recommendation: (userId: number, subjectId: number) => request<{recommended_topic_id: number | null; recommendation_reason: string; topic: Topic | null}>(`/api/sessions/recommend/${userId}/${subjectId}`),

  getRoles: () => request<RolesPermissions>("/api/auth/roles"),
  getUsers: () => request<User[]>("/api/auth/users"),
  login: (email: string, password: string) =>
    request<User>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  getSubjects: () => request<Subject[]>("/api/curriculum/subjects"),
  getTopics: (subjectId: number) =>
    request<Topic[]>(`/api/curriculum/topics/${subjectId}`),
  getPrerequisites: (topicId: number) =>
    request<PrerequisiteItem[]>(`/api/curriculum/prerequisites/${topicId}`),
  getUnlockedTopics: (topicId: number) =>
    request<UnlockedTopicItem[]>(`/api/curriculum/unlocked/${topicId}`),
  getSubjectGraph: (subjectId: number) =>
    request<SubjectGraph>(`/api/curriculum/graph/${subjectId}`),
  getTopicVisual: (topicId: number) =>
    request<Topic>(`/api/curriculum/visual/${topicId}`),
  getVisualConfig: (topicId: number) =>
    request<Topic>(`/api/curriculum/visual/${topicId}`),
  getTopicPrerequisites: (topicId: number) =>
    request<PrerequisiteItem[]>(`/api/curriculum/prerequisites/${topicId}`),

  getCollections: () => request<CollectionItem[]>("/api/vector/collections"),
  getCollectionStats: (subjectKey: string) =>
    request<CollectionStats>(`/api/vector/stats/${subjectKey}`),
  getChunks: (subjectKey: string) =>
    request<VectorChunk[]>(`/api/vector/chunks/${subjectKey}`),
  searchVectors: (subjectKey: string, query: string, topK: number = 4) =>
    request<{ subject: string; query: string; total_results: number; results: VectorSearchResult[] }>(
      "/api/vector/search",
      {
        method: "POST",
        body: JSON.stringify({ subject_key: subjectKey, query, top_k: topK }),
      }
    ),
  addChunk: (subjectKey: string, chunkId: string, text: string, metadata?: Record<string, any>) =>
    request<{ status: string; message: string; chunk_id: string }>("/api/vector/chunk", {
      method: "POST",
      body: JSON.stringify({ subject_key: subjectKey, chunk_id: chunkId, text, metadata }),
    }),
  updateChunk: (subjectKey: string, chunkId: string, newText: string, newMetadata?: Record<string, any>) =>
    request<{ status: string; message: string }>("/api/vector/update", {
      method: "PUT",
      body: JSON.stringify({
        subject_key: subjectKey,
        chunk_id: chunkId,
        new_text: newText,
        new_metadata: newMetadata,
      }),
    }),
  deleteChunks: (subjectKey: string, chunkIds: string[]) =>
    request<{ status: string; deleted_count: number; message: string }>("/api/vector/delete", {
      method: "DELETE",
      body: JSON.stringify({ subject_key: subjectKey, chunk_ids: chunkIds }),
    }),
  clearCollection: (subjectKey: string, role?: string, userId?: number) =>
    request<{ status: string; deleted_count: number; message: string }>("/api/vector/clear-collection", {
      method: "POST",
      body: JSON.stringify({ subject_key: subjectKey }),
    }),
  clearAllVectors: (role?: string, userId?: number) =>
    request<{ status: string; total_chunks_deleted: number; collections_cleared: string[]; message: string }>(
      "/api/vector/clear-all",
      {
        method: "POST",
        body: JSON.stringify({ confirm: true }),
      }
    ),
  deleteCourse: (subjectId: number, role?: string, userId?: number) =>
    request<{ status: string; deleted_subject_id: number; deleted_subject_name: string; message: string }>(
      `/api/vector/course/${subjectId}`,
      { method: "DELETE" }
    ),
  uploadPdf: async (formData: FormData) => {
    const res = await fetch(`${API_BASE}/api/vector/upload`, {
      method: "POST",
      body: formData,
      credentials: "include",
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Upload failed" }));
      throw new Error(err.detail || "PDF upload failed");
    }
    return res.json();
  },
  uploadDocument: async (formData: FormData) => {
    const res = await fetch(`${API_BASE}/api/vector/upload`, {
      method: "POST",
      body: formData,
      credentials: "include",
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Upload failed" }));
      throw new Error(err.detail || "Document upload failed");
    }
    return res.json();
  },
  queryTutor: (payload: TutorQueryRequest) =>
    request<TutorQueryResponse>("/api/tutor/query", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
