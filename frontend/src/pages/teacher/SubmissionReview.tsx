import { useParams } from "react-router-dom"
import { AppShell } from "@/components/layout/AppShell"
import { Card, CardContent } from "@/components/ui/Card"
import { Badge } from "@/components/ui/Badge"
import { Button } from "@/components/ui/Button"
import { QueryState } from "@/components/ui/States"
import { SignalList } from "@/components/socratiq/SignalList"
import { downloadFile, useSubmissionReview, useTeacherAssignment, useTeacherCourse } from "@/lib/queries"
import { formatBytes } from "@/lib/files"

export default function SubmissionReview() {
  const { courseId = "", assignmentId = "", studentId = "" } = useParams()
  const course = useTeacherCourse(courseId).data?.course
  const q = useSubmissionReview(assignmentId, studentId)
  const asg = useTeacherAssignment(assignmentId).data

  return (
    <AppShell
      role="teacher"
      crumbs={[
        { label: "Courses", to: "/teacher/courses" },
        { label: course?.name ?? "Course", to: `/teacher/courses/${courseId}` },
        { label: q.data?.assignment.title ?? "Assignment", to: `/teacher/courses/${courseId}/assignments/${assignmentId}` },
        { label: q.data?.student.name ?? "Student" },
      ]}
    >
      <QueryState query={q} what="Submission">
        {(r) => {
          const file = r.submission?.file
          const mastery = asg?.submissions.find((s) => s.studentId === studentId)?.mastery ?? null
          return (
            <Card className="mx-auto max-w-2xl">
              <CardContent>
                <p className="text-xs font-medium text-[var(--color-teal-dark)]">Learning evidence</p>
                <h1 className="mt-1 text-lg font-semibold text-[var(--color-ink)]">{r.student.name}</h1>
                <p className="mt-1 text-sm text-[var(--color-ink-faint)]">
                  {r.assignment.title}
                  {r.attempt && ` · attempt ${r.attempt.number} (assignment version ${r.attempt.assignmentVersion}${r.attempt.assignmentVersion !== r.assignment.version ? `, now v${r.assignment.version}` : ""})`}
                </p>

                {r.submission ? (
                  <div className="mt-5">
                    <h2 className="text-sm font-semibold text-[var(--color-ink)]">Submission</h2>
                    {file && (
                      <div className="mt-2 flex items-center justify-between gap-3 rounded-[var(--radius-md)] border border-[var(--color-border)] px-3 py-2 text-sm">
                        <span className="min-w-0 truncate">{file.filename} <span className="text-xs text-[var(--color-ink-faint)]">· {formatBytes(file.sizeBytes)}</span></span>
                        <Button size="sm" variant="outline" onClick={() => void downloadFile(file.fileId)}>Download</Button>
                      </div>
                    )}
                    {r.submission.textPreview ? (
                      <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-[var(--radius-md)] bg-[var(--color-surface-muted)] p-3 text-xs text-[var(--color-ink-soft)]">
                        {r.submission.textPreview}
                        {r.submission.textTruncated ? "\n…" : ""}
                      </pre>
                    ) : (
                      <p className="mt-2 text-sm text-[var(--color-ink-soft)]">No text could be read from this file, so only the original file is available.</p>
                    )}
                  </div>
                ) : (
                  <p className="mt-5 text-sm text-[var(--color-ink-soft)]">This student hasn't submitted yet.</p>
                )}

                <div className="mt-6 flex items-center justify-between">
                  <h2 className="text-sm font-semibold text-[var(--color-ink)]">Learning verification</h2>
                  {mastery && <Badge tone="teal">{mastery} mastery</Badge>}
                </div>
                <p className="mt-1 text-sm text-[var(--color-ink-soft)]">
                  Responses from the student's learning verification — a short conversation checking their reasoning behind what they submitted, not a re-test.
                </p>
                {!r.verification || r.verification.entries.length === 0 ? (
                  <p className="mt-3 text-sm text-[var(--color-ink-soft)]">No verification responses yet.</p>
                ) : (
                  <div className="mt-4 space-y-4">
                    {r.verification.entries.map((entry) => (
                      <div key={entry.label} className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-4">
                        <Badge tone="teal">{entry.label}</Badge>
                        <p className="mt-2 text-sm font-medium text-[var(--color-ink)]">{entry.prompt}</p>
                        {entry.answer ? <p className="mt-2 whitespace-pre-wrap text-sm text-[var(--color-ink-soft)]">{entry.answer}</p> : <p className="mt-2 text-sm text-[var(--color-ink-faint)]">Not answered yet.</p>}
                        {entry.feedback && <p className="mt-2 text-xs text-[var(--color-ink-faint)]">AI feedback shown to the student: {entry.feedback}</p>}
                      </div>
                    ))}
                  </div>
                )}

                {r.signals.length > 0 && (
                  <div className="mt-6">
                    <h2 className="text-sm font-semibold text-[var(--color-ink)]">Review indicators</h2>
                    <p className="mb-2 mt-1 text-xs text-[var(--color-ink-faint)]">{r.signalsNote}</p>
                    <SignalList signals={r.signals} />
                  </div>
                )}
                <p className="mt-5 text-xs text-[var(--color-ink-faint)]">{r.coachInteractions} Socratic AI conversation turn{r.coachInteractions === 1 ? "" : "s"} on this assignment.</p>
              </CardContent>
            </Card>
          )
        }}
      </QueryState>
    </AppShell>
  )
}
