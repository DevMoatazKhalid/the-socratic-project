export type Role = "student" | "teacher"

export interface User {
  id: string
  name: string
  email: string
  role: Role
}

export type Mastery = "Strong" | "Moderate" | "Weak"

export type FileStatus = "QUEUED" | "PROCESSING" | "READY" | "STORED_ONLY" | "FAILED"
export type IndexMode = "RAG" | "EXTRACT_ONLY" | "STORAGE_ONLY"

export interface FileInfo {
  fileId: string
  filename: string
  extension: string
  mimeType: string
  sizeBytes: number
  kind: "DOCUMENT" | "PRESENTATION" | "SPREADSHEET" | "TEXT" | "CODE" | "IMAGE"
  indexMode: IndexMode
  status: FileStatus
  note?: string | null
  error?: string | null
  pageCount?: number | null
  createdAt?: string
  attachmentId?: string
  role?: "PROMPT" | "SUPPORTING"
}

export interface Course {
  id: string
  code: string
  name: string
  description: string
  teacher: string
  status: "Active" | "Archived"
  color: "plum" | "slate" | "teal" | "clay"
  materialCount: number
  assignmentCount: number
  studentCount?: number
  classroomId?: string | null
  joinCode?: string
}

export interface Material {
  id: string
  courseId: string
  title: string
  summary: string
  kind: "reading" | "slides" | "video" | "dataset"
  file?: FileInfo | null
  createdAt?: string
}

export type AssignmentStatus = "not_started" | "in_progress" | "submitted" | "verified"

export type AiAssistMode = "guided" | "assisted" | "open"

export interface Assignment {
  id: string
  courseId: string
  title: string
  topic: string
  prompt: string
  /** Student progress. Present on student endpoints; instructors use `lifecycle` instead. */
  status?: AssignmentStatus
  dueDate: string | null
  aiMode?: AiAssistMode
  lifecycle?: "DRAFT" | "PUBLISHED" | "ARCHIVED"
  version?: number
  attachments?: FileInfo[]
}

export interface SubmissionRow {
  studentId: string
  studentName: string
  status: AssignmentStatus
  mastery: Mastery | null
  submittedAt?: string | null
}

export interface EvidenceEntry {
  label: string
  prompt: string
  answer: string
}

export interface ChatMessage {
  id: string
  role: "coach" | "student"
  content: string
  kind?: "hint" | "question" | "explanation" | null
}

export interface StudentRow {
  id: string
  name: string
  taskSubmission: number
  socraticAiUsage: number
  /** % of assignments with at least one OBSERVED review indicator. An observation, never a claim about what a student did. */
  observedSignalRate: number
  observedSignalCount?: number
  mastery: Mastery | null   // null = not enough verification evidence yet
}

export type SignalTone = "neutral" | "watch" | "positive"

export interface LearningSignal {
  label: string
  detail: string
  tone: SignalTone
}

export interface ActivityEntry {
  id: string
  date: string
  courseId: string
  assignmentId?: string
  assignmentTitle: string
  kind: "submission" | "revision" | "verification" | "coach_session"
  detail: string
}

export interface StudentDetailInfo {
  id: string
  name: string
  email: string
  courseIds: string[]
  mastery: Mastery | null
  taskSubmission: number
  socraticAiUsage: number
  observedSignalRate: number
  attempts: number
  revisions: number
  strugglingTopics: string[]
  signals: LearningSignal[]
  activity: ActivityEntry[]
}

export interface AttentionItem {
  id: string
  kind: "review" | "signal" | "deadline"
  title: string
  description: string
  to: string
  tone: "warning" | "danger" | "neutral"
}

export interface Capabilities {
  purpose: string
  extensions: string[]
  accept: string
  maxBytes: number
  formats: { extension: string; kind: string; label: string; mimeType: string; mode: IndexMode; maxBytes: number; note?: string | null }[]
}
