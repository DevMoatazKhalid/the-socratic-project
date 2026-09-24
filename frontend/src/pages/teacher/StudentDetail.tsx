import { Link, useParams } from "react-router-dom"
import { AppShell } from "@/components/layout/AppShell"
import { Card, CardContent } from "@/components/ui/Card"
import { Badge } from "@/components/ui/Badge"
import { Avatar } from "@/components/ui/Avatar"
import { QueryState } from "@/components/ui/States"
import { MasteryBadge } from "@/components/socratiq/MasteryBadge"
import { SignalList } from "@/components/socratiq/SignalList"
import { ActivityFeed } from "@/components/socratiq/ActivityFeed"
import { useCourses, useTeacherStudent } from "@/lib/queries"

export default function StudentDetail() {
  const { studentId = "" } = useParams()
  const q = useTeacherStudent(studentId)
  const allCourses = useCourses("teacher").data ?? []

  return (
    <AppShell role="teacher" crumbs={[{ label: "Dashboard", to: "/teacher" }, { label: q.data?.name ?? "Student" }]}>
      <QueryState query={q} what="Student">
        {(student) => {
          const courses = student.courseIds.map((id) => allCourses.find((c) => c.id === id)).filter((c) => !!c)
          const primaryCourseId = student.courseIds[0]
          return (
            <>
      {/* Overview */}
      <Card>
        <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-4">
            <Avatar name={student.name} className="h-14 w-14 text-base" />
            <div>
              <h1 className="text-lg font-semibold text-[var(--color-ink)]">{student.name}</h1>
              <p className="text-sm text-[var(--color-ink-soft)]">{student.email}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {courses.map((c) => (
                  <Badge key={c.id} tone="slate">
                    {c.name}
                  </Badge>
                ))}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 sm:flex-col sm:items-end">
            <span className="text-xs font-medium text-[var(--color-ink-muted)]">
              Overall mastery
            </span>
            <MasteryBadge level={student.mastery} />
          </div>
        </CardContent>
      </Card>

      {/* Quick stats */}
      <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Stat value={`${student.taskSubmission}%`} label="Task submission" />
        <Stat value={`${student.socraticAiUsage}%`} label="Socratic AI usage" />
        <Stat value={`${student.observedSignalRate}%`} label="Review indicators" />
        <Stat value={String(student.attempts)} label="Attempts" />
        <Stat value={String(student.revisions)} label="Revisions" />
      </div>

      {student.strugglingTopics.length > 0 && (
        <div className="mt-5 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white p-4">
          <h2 className="text-sm font-semibold text-[var(--color-ink)]">Topics to reinforce</h2>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {student.strugglingTopics.map((topic) => (
              <Badge key={topic} tone="warning">
                {topic}
              </Badge>
            ))}
          </div>
        </div>
      )}

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div>
          <h2 className="mb-3 text-sm font-semibold text-[var(--color-ink-muted)]">
            Learning signals
          </h2>
          <p className="mb-3 -mt-1 text-xs text-[var(--color-ink-faint)]">
            Evidence and review indicators from the learning process — not a determination of intent.
          </p>
          <SignalList signals={student.signals} />
        </div>

        <div>
          <h2 className="mb-3 text-sm font-semibold text-[var(--color-ink-muted)]">
            Recent activity
          </h2>
          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white p-4">
            <ActivityFeed entries={student.activity} emptyLabel="No recorded activity yet." />
          </div>
        </div>
      </div>

      {primaryCourseId && (
        <div className="mt-6">
          <Link
            to={`/teacher/courses/${primaryCourseId}`}
            className="text-sm font-medium text-[var(--color-teal-dark)] hover:underline"
          >
            View {courses[0]?.name ?? "course"} →
          </Link>
        </div>
      )}
            </>
          )
        }}
      </QueryState>
    </AppShell>
  )
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white p-4">
      <p className="text-xl font-semibold text-[var(--color-ink)]">{value}</p>
      <p className="mt-1 text-xs text-[var(--color-ink-soft)]">{label}</p>
    </div>
  )
}
