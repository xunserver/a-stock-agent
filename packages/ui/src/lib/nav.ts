import type { LucideIcon } from "lucide-react"
import {
  BrainIcon,
  LayersIcon,
  LandmarkIcon,
  ListTodoIcon,
  SparklesIcon,
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
      { title: "多智能体分析", url: "/analyze", icon: BrainIcon },
      { title: "Qlib 候选", url: "/qlib", icon: SparklesIcon },
    ],
  },
  {
    title: "运行",
    items: [{ title: "任务", url: "/jobs", icon: ListTodoIcon }],
  },
]
