import type { ReactNode } from "react"
import { ChevronDownIcon } from "lucide-react"

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { Field, FieldDescription, FieldTitle } from "@/components/ui/field"
import { cn } from "@/lib/utils"

export function InfoSection({
  title,
  open,
  onOpenChange,
  children,
}: {
  title: string
  open: boolean
  onOpenChange: (open: boolean) => void
  children: ReactNode
}) {
  return (
    <Collapsible
      className="flex flex-col gap-1"
      open={open}
      onOpenChange={onOpenChange}
    >
      <CollapsibleTrigger className="group/info inline-flex w-fit items-center gap-1 rounded-md text-left font-heading text-sm font-medium tracking-tight text-foreground outline-none hover:opacity-80 focus-visible:ring-[3px] focus-visible:ring-ring/50">
        {title}
        <ChevronDownIcon className="size-4 shrink-0 text-muted-foreground transition-transform duration-200 group-aria-expanded/info:rotate-180" />
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="grid grid-cols-2 gap-x-3 gap-y-1 pt-1 sm:grid-cols-4 lg:grid-cols-8">
          {children}
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}

export function InfoField({
  title,
  value,
  className,
}: {
  title: string
  value: string
  className?: string
}) {
  return (
    <Field className="flex-row flex-wrap items-baseline gap-1 *:w-auto max-sm:flex-col max-sm:items-start">
      <FieldTitle className="text-[11px] font-normal text-muted-foreground">
        {title}
      </FieldTitle>
      <FieldDescription
        className={cn("mt-0 text-xs leading-4 text-foreground", className)}
      >
        {value}
      </FieldDescription>
    </Field>
  )
}
