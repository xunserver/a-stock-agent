import { cn } from "@/lib/utils"

export type ChangeTone = "gain" | "loss" | "flat"

export function changeTone(value: number | null | undefined): ChangeTone {
  if (value == null || !Number.isFinite(value) || value === 0) {
    return "flat"
  }
  return value > 0 ? "gain" : "loss"
}

export function changeTextClass(value: number | null | undefined): string {
  const tone = changeTone(value)
  return cn(
    tone === "gain" && "text-gain",
    tone === "loss" && "text-loss",
    tone === "flat" && "text-muted-foreground"
  )
}

export function changeFillClass(value: number | null | undefined): string {
  const tone = changeTone(value)
  return cn(
    tone === "gain" && "fill-gain",
    tone === "loss" && "fill-loss",
    tone === "flat" && "fill-foreground"
  )
}

export function changeFillForegroundClass(value: number | null | undefined): string {
  const tone = changeTone(value)
  return cn(
    tone === "gain" && "fill-gain-foreground",
    tone === "loss" && "fill-loss-foreground",
    tone === "flat" && "fill-background"
  )
}
