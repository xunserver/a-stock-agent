import type { FormEvent } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"

export function PoolCreateDialog({
  open,
  busy,
  id,
  name,
  onOpenChange,
  onIdChange,
  onNameChange,
  onSubmit,
}: {
  open: boolean
  busy: boolean
  id: string
  name: string
  onOpenChange: (open: boolean) => void
  onIdChange: (value: string) => void
  onNameChange: (value: string) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form className="flex flex-col gap-4" onSubmit={onSubmit}>
          <DialogHeader>
            <DialogTitle>新建股票池</DialogTitle>
            <DialogDescription>
              id 给命令用，名称显示在列表里。不会改系统设置里的默认池。
            </DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="new-pool-id">id</FieldLabel>
              <Input
                id="new-pool-id"
                name="pool_id"
                required
                value={id}
                placeholder="hs300"
                onChange={(event) => onIdChange(event.target.value)}
              />
              <FieldDescription>
                字母、数字、下划线或短横线，最长 32 位。
              </FieldDescription>
            </Field>
            <Field>
              <FieldLabel htmlFor="new-pool-name">名称</FieldLabel>
              <Input
                id="new-pool-name"
                name="name"
                value={name}
                placeholder="沪深300样本"
                onChange={(event) => onNameChange(event.target.value)}
              />
            </Field>
          </FieldGroup>
          <DialogFooter>
            <Button type="submit" disabled={busy}>
              {busy ? <Spinner data-icon="inline-start" /> : null}创建
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
