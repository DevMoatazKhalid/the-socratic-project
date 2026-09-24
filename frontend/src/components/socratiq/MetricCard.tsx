import { Card } from "@/components/ui/Card"

export function MetricCard({ value, label, hint, percent, tone = "teal-dark" }: { value: string; label: string; hint?: string; percent?: number; tone?: "teal-dark" | "clay" }) {
  return (
    <Card className="p-5" title={hint}>
      <p className="text-2xl font-semibold text-[var(--color-ink)]">{value}</p>
      <p className="mt-1 text-sm text-[var(--color-ink-muted)]">{label}</p>
      {percent !== undefined && (
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[var(--color-surface-muted)]" aria-hidden="true">
          <div className="h-full rounded-full transition-[width] duration-700 motion-reduce:transition-none" style={{ width: `${Math.min(Math.max(percent, 0), 100)}%`, background: `var(--color-${tone})` }} />
        </div>
      )}
    </Card>
  )
}
