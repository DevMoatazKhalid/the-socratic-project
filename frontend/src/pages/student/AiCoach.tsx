import { useEffect, useRef, useState } from "react"
import { useParams } from "react-router-dom"
import { AppShell } from "@/components/layout/AppShell"
import { Button } from "@/components/ui/Button"
import { DueDate } from "@/components/socratiq/DueDate"
import { QueryState } from "@/components/ui/States"
import { useCoachHistory, useSendCoach, useStartAttempt, useStudentAssignment, useStudentCourse } from "@/lib/queries"
import { ApiError } from "@/lib/api"
import type { ChatMessage } from "@/types"
import { cn } from "@/lib/utils"
import { Send } from "lucide-react"

const thinkingStates = ["Reviewing your attempt…", "Looking at the relevant course material…", "Preparing a learning question…"]

type Local = ChatMessage & { sources?: { documentTitle?: string; pageNumber?: number }[] }

export default function AiCoach() {
  const { courseId = "", assignmentId = "" } = useParams()
  const course = useStudentCourse(courseId)
  const assignmentQ = useStudentAssignment(assignmentId)
  const history = useCoachHistory(assignmentId)
  const startAttempt = useStartAttempt()
  const send = useSendCoach()

  const [messages, setMessages] = useState<Local[]>([])
  const [draft, setDraft] = useState("")
  const [thinking, setThinking] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const loaded = useRef(false)
  const started = useRef(false)

  const closed = assignmentQ.data?.status === "submitted" || assignmentQ.data?.status === "verified"

  // the transcript is stored server-side; reloading the page restores it
  useEffect(() => {
    if (history.data && !loaded.current) {
      loaded.current = true
      setMessages(history.data)
    }
  }, [history.data])

  // The Coach works on an open attempt. Opening the chat starts one if needed (idempotent on the server).
  useEffect(() => {
    if (assignmentQ.data && !closed && !started.current) {
      started.current = true
      startAttempt.mutate(assignmentId)
    }
  }, [assignmentQ.data, closed, assignmentId, startAttempt])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [messages, thinking])

  async function handleSend() {
    const text = draft.trim()
    if (!text || send.isPending || closed) return
    setError(null)
    setMessages((m) => [...m, { id: crypto.randomUUID(), role: "student", content: text }])
    setDraft("")
    setThinking(thinkingStates[Math.floor(Math.random() * thinkingStates.length)])
    try {
      const r = await send.mutateAsync({ assignmentId, message: text })
      setMessages((m) => [...m, { ...r.message, sources: r.sources }])
    } catch (e) {
      const msg =
        e instanceof ApiError && e.code === "rate_limited" ? "You're sending messages quickly. Wait a moment, then send again."
        : e instanceof ApiError && e.code === "ai_unavailable" ? "SocratiQ AI is unavailable right now. Your message wasn't saved. Please send it again."
        : e instanceof ApiError ? e.message
        : "Your message couldn't be sent."
      setError(msg)
      setMessages((m) => m.slice(0, -1))                 // the server did not record this turn, so don't show it as sent
      setDraft(text)
    } finally {
      setThinking(null)
    }
  }

  return (
    <AppShell
      role="student"
      crumbs={[
        { label: "Courses", to: "/student/courses" },
        { label: course.data?.course.name ?? "Course", to: `/student/courses/${courseId}` },
        { label: assignmentQ.data?.title ?? "Assignment", to: `/student/courses/${courseId}/assignments/${assignmentId}` },
        { label: "SocratiQ AI" },
      ]}
    >
      <QueryState query={assignmentQ} what="Assignment">
        {(assignment) => (
          <div className="mx-auto flex h-[calc(100dvh-8.5rem)] min-h-[26rem] max-w-3xl flex-col overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white">
            <div className="border-b border-[var(--color-border)] px-5 py-3">
              <p className="text-xs font-semibold text-[var(--color-teal-dark)]">Learning coach</p>
              <h1 className="text-base font-semibold text-[var(--color-ink)]">{assignment.topic || assignment.title}</h1>
              <div className="mt-1.5">
                <DueDate dueDate={assignment.dueDate} done={closed} />
              </div>
            </div>

            <div ref={scrollRef} className="thin-scroll flex-1 space-y-3 overflow-y-auto px-5 py-5">
              {messages.length === 0 && !history.isPending && (
                <p className="text-center text-sm text-[var(--color-ink-muted)]">Tell SocratiQ where you're stuck, or paste what you've tried so far.</p>
              )}
              {messages.map((m) => (
                <Bubble key={m.id} message={m} />
              ))}
              {thinking && (
                <div className="flex justify-start">
                  <div className="flex items-center gap-2 rounded-[var(--radius-lg)] bg-[var(--color-surface-muted)] px-4 py-2.5 text-sm text-[var(--color-ink-faint)]">
                    <span className="flex gap-1">
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--color-ink-faint)]" />
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--color-ink-faint)] [animation-delay:150ms]" />
                      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--color-ink-faint)] [animation-delay:300ms]" />
                    </span>
                    {thinking}
                  </div>
                </div>
              )}
            </div>

            {error && (
              <p role="alert" className="border-t border-[var(--color-danger-light)] bg-[var(--color-danger-light)]/40 px-5 py-2 text-sm text-[var(--color-danger-ink)]">
                {error}
              </p>
            )}
            {closed && <p className="border-t border-[var(--color-border)] px-5 py-2 text-sm text-[var(--color-ink-soft)]">You've submitted this assignment, so the coaching chat is now read-only.</p>}

            <form
              className="flex items-center gap-2 border-t border-[var(--color-border)] p-3"
              onSubmit={(e) => {
                e.preventDefault()
                void handleSend()
              }}
            >
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                disabled={closed}
                maxLength={4000}
                placeholder="Start your chat here…"
                className="h-11 flex-1 rounded-full border border-[var(--color-border-strong)] bg-white px-4 text-sm placeholder:text-[var(--color-ink-faint)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-teal-dark)] disabled:opacity-60"
                aria-label="Message SocratiQ AI"
              />
              <Button type="submit" size="md" className="h-11 w-11 rounded-full p-0" aria-label="Send message" disabled={closed || send.isPending}>
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </div>
        )}
      </QueryState>
    </AppShell>
  )
}

function Bubble({ message }: { message: Local }) {
  const isStudent = message.role === "student"
  const cites = (message.sources ?? []).filter((s) => s.documentTitle)
  return (
    <div className={cn("flex", isStudent ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[88%] rounded-[var(--radius-lg)] sm:max-w-[75%] px-4 py-2.5 text-sm",
          isStudent ? "bg-[var(--color-teal-light)] text-[var(--color-ink)]" : "bg-[var(--color-surface-muted)] text-[var(--color-ink)]"
        )}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
        {cites.length > 0 && (
          <p className="mt-1.5 text-xs text-[var(--color-ink-faint)]">
            From course material: {cites.map((s) => `${s.documentTitle}${s.pageNumber ? ` (p. ${s.pageNumber})` : ""}`).join(", ")}
          </p>
        )}
      </div>
    </div>
  )
}
