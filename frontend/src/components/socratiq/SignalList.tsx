import { Eye, TrendingUp } from "lucide-react"
import type { LearningSignal } from "@/types"
import { cn } from "@/lib/utils"

const toneStyles: Record<LearningSignal["tone"], string> = {
  watch: "border-[var(--color-warning-light)] bg-[var(--color-warning-light)]/50",
  positive: "border-[var(--color-success-light)] bg-[var(--color-success-light)]/50",
  neutral: "border-[var(--color-border)] bg-white",
}

const iconTone: Record<LearningSignal["tone"], string> = {
  watch: "text-[var(--color-warning-ink)]",
  positive: "text-[var(--color-success-ink)]",
  neutral: "text-[var(--color-ink-soft)]",
}

export function SignalList({ signals }: { signals: LearningSignal[] }) {
  if (signals.length === 0) {
    return (
      <p className="text-sm text-[var(--color-ink-soft)]">
        No notable learning signals for this student right now.
      </p>
    )
  }

  return (
    <div className="space-y-2.5">
      {signals.map((signal, i) => {
        const Icon = signal.tone === "watch" ? Eye : TrendingUp
        return (
          <div key={i} className={cn("rounded-[var(--radius-md)] border p-3.5", toneStyles[signal.tone])}>
            <div className="flex items-start gap-2.5">
              <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", iconTone[signal.tone])} />
              <div>
                <p className="text-sm font-medium text-[var(--color-ink)]">{signal.label}</p>
                <p className="mt-0.5 text-sm text-[var(--color-ink-soft)]">{signal.detail}</p>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
