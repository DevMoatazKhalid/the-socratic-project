import { lazy, Suspense, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { ChevronRight, Plus } from "lucide-react"
import { AppShell } from "@/components/layout/AppShell"
import { MetricCard } from "@/components/socratiq/MetricCard"
import { MasteryBadge } from "@/components/socratiq/MasteryBadge"
import { AttentionList } from "@/components/socratiq/AttentionList"
import { ActivityFeed, type ActivityFeedEntry } from "@/components/socratiq/ActivityFeed"
import { AssignmentRow } from "@/components/socratiq/ListRow"
import { ChartCard } from "@/components/charts/ChartCard"
import { Badge } from "@/components/ui/Badge"
import { ButtonLink } from "@/components/ui/Button"
import { SectionHeading } from "@/components/ui/SectionHeading"
import { EmptyState, QueryState } from "@/components/ui/States"
import { useCourses, useDashboard, useTeacherCourse } from "@/lib/queries"
import { cn } from "@/lib/utils"

// recharts is the heaviest dependency; load it only when a teacher opens the dashboard.
const TeacherAnalytics = lazy(() => import("@/components/socratiq/TeacherAnalytics"))

const lifecycleText = { DRAFT: "Draft", PUBLISHED: "Published", ARCHIVED: "Archived" } as const
const lifecycleTone = { DRAFT: "neutral", PUBLISHED: "success", ARCHIVED: "slate" } as const

/** Thin proportion bar next to a percentage: makes a column of numbers scannable. */
function Meter({ value, tone = "teal-dark" }: { value: number; tone?: "teal-dark" | "clay" }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="w-10 shrink-0 tabular-nums text-[var(--color-ink)]">{value}%</span>
      <div className="hidden h-1.5 w-20 overflow-hidden rounded-full bg-[var(--color-surface-muted)] md:block" aria-hidden="true">
        <div className="h-full rounded-full" style={{ width: `${Math.min(Math.max(value, 0), 100)}%`, background: `var(--color-${tone})` }} />
      </div>
    </div>
  )
}

function AnalyticsFallback() {
  return (
    <div className="grid gap-4 lg:grid-cols-2" aria-busy="true">
      {["Assignments by state", "Submissions per assignment", "Mastery across students", "Recent learning activity"].map((t) => (
        <ChartCard key={t} title={t} description="Loading…" state="loading">{null}</ChartCard>
      ))}
    </div>
  )
}

export default function TeacherDashboard() {
  const navigate = useNavigate()
  const courses = useCourses("teacher")
  const [picked, setPicked] = useState<string | null>(null)
  const activeId = picked ?? courses.data?.[0]?.id
  const dash = useDashboard(activeId)
  const detail = useTeacherCourse(activeId)
  const course = courses.data?.find((c) => c.id === activeId)

  return (
    <AppShell role="teacher" crumbs={[{ label: "Dashboard" }, ...(course ? [{ label: course.name }] : [])]}>
      <QueryState query={courses} what="Dashboard">
        {(list) =>
          list.length === 0 || !course ? (
            <EmptyState
              title="Create your first course"
              description="Your dashboard fills in as students join and work on assignments."
              action={{ label: "Create a course", onClick: () => navigate("/teacher/courses/new") }}
            />
          ) : (
            <>
              {list.length > 1 && (
                <div role="group" aria-label="Choose a course" className="mb-5 flex flex-wrap gap-2">
                  {list.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      aria-pressed={c.id === activeId}
                      onClick={() => setPicked(c.id)}
                      className={cn(
                        "rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors",
                        c.id === activeId
                          ? "border-[var(--color-plum)] bg-[var(--color-plum)] text-[var(--color-on-plum)]"
                          : "border-[var(--color-border-strong)] bg-white text-[var(--color-ink-muted)] hover:bg-[var(--color-surface-muted)] hover:text-[var(--color-ink)]"
                      )}
                    >
                      {c.name}
                    </button>
                  ))}
                </div>
              )}

              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h1 className="text-xl font-semibold text-[var(--color-ink)]">{course.name} overview</h1>
                  <p className="mt-1 text-sm text-[var(--color-ink-muted)]">
                    {course.studentCount ?? 0} students · {course.status}
                  </p>
                </div>
                <ButtonLink to={`/teacher/courses/${course.id}/assignments/new`} variant="secondary" className="gap-1.5">
                  <Plus className="h-4 w-4" aria-hidden="true" /> New assignment
                </ButtonLink>
              </div>

              <QueryState query={dash} what="Dashboard">
                {(d) => {
                  const nameOf = new Map(d.students.map((s) => [s.id, s.name]))
                  const feed = (d.activity as ActivityFeedEntry[]).map((e) => ({ ...e, studentName: e.studentName ?? (e.studentId ? nameOf.get(e.studentId) : undefined) }))
                  const assignments = detail.data?.assignments ?? []
                  return (
                    <>
                      {d.attention.length > 0 && (
                        <div className="mt-6">
                          <AttentionList items={d.attention} />
                        </div>
                      )}

                      <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
                        <MetricCard percent={d.metrics.assignmentCompletion} value={`${d.metrics.assignmentCompletion}%`} label="Assignment completion" hint="Average share of published assignments each student has submitted" />
                        <MetricCard percent={d.metrics.verificationRate} value={`${d.metrics.verificationRate}%`} label="Verified understanding" hint="Share of submitted assignments whose learning verification finished as pass or partial" />
                        <MetricCard percent={d.metrics.socraticAiUsage} value={`${d.metrics.socraticAiUsage}%`} label="Socratic AI usage" hint="Average share of assignments where the student used the Socratic AI Coach" />
                        <MetricCard percent={d.metrics.observedSignalRate} tone="clay" value={`${d.metrics.observedSignalRate}%`} label="Review indicators" hint="Share of assignments with at least one OBSERVED pattern worth a look. An observation, not a determination of intent or of any tool use." />
                      </div>

                      <SectionHeading right={<span className="text-xs text-[var(--color-ink-muted)]">Drawn from this course's live data</span>}>Class analytics</SectionHeading>
                      <Suspense fallback={<AnalyticsFallback />}>
                        <TeacherAnalytics dashboard={d} assignments={detail.data?.assignments} assignmentsState={detail.isError ? "error" : detail.isPending ? "loading" : "ready"} />
                      </Suspense>

                      <div className="mt-2 grid grid-cols-1 gap-x-6 lg:grid-cols-3">
                        <div className="lg:col-span-2">
                          <SectionHeading right={<Link to={`/teacher/courses/${course.id}`} className="text-sm font-medium text-[var(--color-teal-dark)] hover:underline">View all</Link>}>Assignments</SectionHeading>
                          <div className="space-y-2">
                            {detail.isPending && <p className="text-sm text-[var(--color-ink-muted)]">Loading assignments…</p>}
                            {!detail.isPending && assignments.length === 0 && <p className="text-sm text-[var(--color-ink-muted)]">No assignments yet.</p>}
                            {assignments.map((a) => (
                              <AssignmentRow
                                key={a.id}
                                to={`/teacher/courses/${course.id}/assignments/${a.id}`}
                                title={a.title}
                                topic={`${a.submittedCount}/${a.studentCount} submitted`}
                                dueDate={a.dueDate}
                                done={a.lifecycle === "ARCHIVED" || (a.studentCount > 0 && a.submittedCount >= a.studentCount)}
                                badge={<Badge tone={lifecycleTone[a.lifecycle ?? "DRAFT"]}>{lifecycleText[a.lifecycle ?? "DRAFT"]}</Badge>}
                              />
                            ))}
                          </div>
                        </div>

                        <div>
                          <SectionHeading>Recent learning evidence</SectionHeading>
                          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white p-4">
                            <ActivityFeed entries={feed.slice(0, 6)} emptyLabel="No recent student activity yet." />
                          </div>
                        </div>
                      </div>

                      <SectionHeading count={d.students.length}>Students</SectionHeading>
                      {d.students.length === 0 ? (
                        <EmptyState title="No students yet" description="Share the invite code from the course page. Students appear here once they join." />
                      ) : (
                        <div className="overflow-x-auto rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white">
                          <table className="w-full min-w-[680px] text-left text-sm">
                            <thead>
                              <tr className="bg-[var(--color-slate-light)] text-[var(--color-ink)]">
                                <Th>Student</Th>
                                <Th>Task submission</Th>
                                <Th>Socratic AI usage</Th>
                                <Th>Review indicators</Th>
                                <Th>Mastery</Th>
                                <Th><span className="sr-only">Open</span></Th>
                              </tr>
                            </thead>
                            <tbody>
                              {d.students.map((s) => (
                                <tr key={s.id} className="transition-colors hover:bg-[var(--color-surface-muted)]">
                                  <Td className="p-0 font-medium text-[var(--color-ink)]">
                                    <Link to={`/teacher/students/${s.id}`} className="block px-4 py-3 hover:text-[var(--color-teal-dark)] hover:underline">
                                      {s.name}
                                    </Link>
                                  </Td>
                                  <Td><Meter value={s.taskSubmission} /></Td>
                                  <Td><Meter value={s.socraticAiUsage} /></Td>
                                  <Td><Meter value={s.observedSignalRate} tone="clay" /></Td>
                                  <Td><MasteryBadge level={s.mastery} /></Td>
                                  <Td className="w-10">
                                    <Link to={`/teacher/students/${s.id}`} aria-label={`View ${s.name}`}>
                                      <ChevronRight className="h-4 w-4 text-[var(--color-ink-muted)]" aria-hidden="true" />
                                    </Link>
                                  </Td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </>
                  )
                }}
              </QueryState>
            </>
          )
        }
      </QueryState>
    </AppShell>
  )
}

function Th({ children, className }: { children?: React.ReactNode; className?: string }) {
  return <th scope="col" className={cn("px-4 py-3 text-xs font-semibold", className)}>{children}</th>
}
function Td({ children, className }: { children: React.ReactNode; className?: string }) {
  return <td className={cn("border-t border-[var(--color-border)] px-4 py-3", className)}>{children}</td>
}
