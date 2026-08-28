import type { LucideIcon } from "lucide-react"
import {
  BrainIcon,
  LayersIcon,
  LandmarkIcon,
  ListTodoIcon,
  SparklesIcon,
  WorkflowIcon,
} from "lucide-react"

export type NavItem = {
  title: string
  url: string
  icon: LucideIcon
}

export type NavGroup = {
  title: string
  items: NavItem[]
}

export const navGroups: NavGroup[] = [
  {
    title: "股票管理",
    items: [
      { title: "股票", url: "/stocks", icon: LandmarkIcon },
      { title: "股票池", url: "/pools", icon: LayersIcon },
      { title: "量化选股", url: "/qlib", icon: SparklesIcon },
      { title: "AI分析", url: "/analyze", icon: BrainIcon },
    ],
  },
  {
    title: "运行",
    items: [
      { title: "自动任务", url: "/automations", icon: WorkflowIcon },
      { title: "任务", url: "/jobs", icon: ListTodoIcon },
    ],
  },
]
