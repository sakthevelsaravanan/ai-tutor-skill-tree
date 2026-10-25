export type UserRole = "student" | "instructor" | "admin";

export interface User {
  user_id: number;
  full_name: string;
  email: string;
  role: UserRole;
  created_at?: string;
}

export interface RolesPermissions {
  roles: UserRole[];
  permissions: {
    student: string[];
    instructor: string[];
    admin: string[];
  };
}

export interface Subject {
  subject_id: number;
  subject_key: string;
  subject_name: string;
  description: string;
  is_indexed: number | boolean;
  total_topics: number;
  total_textbooks: number;
}

export interface Topic {
  topic_id: number;
  subject_id: number;
  topic_name: string;
  difficulty_level: number;
  visual_type: "iframe" | "p5js";
  embed_url: string;
}

export interface PrerequisiteItem {
  target_topic_id: number;
  prereq_topic_id: number;
  prereq_topic_name: string;
  prereq_difficulty: number;
  importance_weight: number;
  traversal_depth: number;
  learning_order_path: string;
}

export interface UnlockedTopicItem {
  unlocked_topic_id: number;
  unlocked_topic_name: string;
  difficulty_level: number;
  unlock_tier: number;
}

export interface GraphNode {
  id: number;
  label: string;
  difficulty_level: number;
  visual_type: "iframe" | "p5js";
}

export interface GraphEdge {
  source: number;
  target: number;
  weight: number;
}

export interface SubjectGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export type GraphData = SubjectGraph;
export type PrerequisiteNode = PrerequisiteItem;

export interface VectorSearchResult {
  id: string;
  document: string;
  metadata: Record<string, any>;
  distance: number;
  similarity: number;
}

export interface VectorChunk {
  id: string;
  document: string;
  metadata: Record<string, any>;
}

export interface CollectionStats {
  collection_name: string;
  total_chunks: number;
  metadata?: Record<string, any>;
}

export interface CollectionItem {
  name: string;
  count: number;
}

export interface TutorQueryRequest {
  query: string;
  subject_id: number;
  topic_id?: number;
  session_id?: string;
  user_id?: number;
  include_prereqs?: boolean;
}

export interface TutorQueryResponse {
  answer: string;
  target_topic?: Topic | null;
  prerequisites: PrerequisiteItem[];
  retrieved_chunks: VectorSearchResult[];
  session_id?: string;
  relational_filter_applied: boolean;
  reflection_question?: string | null;
  grounding_excerpt?: string | null;
  top_similarity?: number | null;
  top_source?: string | null;
}
