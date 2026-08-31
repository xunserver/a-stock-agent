import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

export type SlotProps = { className?: string; children?: ReactNode }

export function PanelTitle({ className, children }: SlotProps) {
  return (
    <h2
      className={cn(
        "font-heading text-base leading-none font-medium",
        className
      )}
    >
      {children}
    </h2>
  )
}

export function PanelDescription({ className, children }: SlotProps) {
  return (
    <p className={cn("text-sm text-muted-foreground", className)}>{children}</p>
  )
}
