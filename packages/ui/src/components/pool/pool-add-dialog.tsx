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
  FieldContent,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldTitle,
} from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { INDEX_OPTIONS } from "@/lib/indexes"

type AddMode = "codes" | "index"

export function PoolAddDialog({
  open,
  busy,
  poolId,
  mode,
  codes,
  index,
  replaceIndex,
  onOpenChange,
  onModeChange,
  onCodesChange,
  onIndexChange,
  onReplaceIndexChange,
  onSubmit,
}: {
  open: boolean
  busy: boolean
  poolId: string | null
  mode: AddMode
  codes: string
  index: string
  replaceIndex: boolean
  onOpenChange: (open: boolean) => void
  onModeChange: (mode: AddMode) => void
  onCodesChange: (codes: string) => void
  onIndexChange: (index: string) => void
  onReplaceIndexChange: (checked: boolean) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form className="flex flex-col gap-4" onSubmit={onSubmit}>
          <DialogHeader>
            <DialogTitle>添加成员</DialogTitle>
            <DialogDescription>
              只能加入已经在「股票」里的代码。按指数加入时，只并入系统里已有的成分。指数拉取可能要几秒。
            </DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldTitle id="add-mode-label">方式</FieldTitle>
              <ToggleGroup
                aria-labelledby="add-mode-label"
                value={[mode]}
                onValueChange={(next) => {
                  const value = next[0]
                  if (value === "codes" || value === "index")
                    onModeChange(value)
                }}
                variant="outline"
                spacing={0}
              >
                <ToggleGroupItem value="codes">代码</ToggleGroupItem>
                <ToggleGroupItem value="index">指数</ToggleGroupItem>
              </ToggleGroup>
            </Field>
            {mode === "codes" ? (
              <Field>
                <FieldLabel htmlFor="add-codes">股票代码</FieldLabel>
                <Textarea
                  id="add-codes"
                  required
                  value={codes}
                  placeholder="000001, 600519"
                  onChange={(event) => onCodesChange(event.target.value)}
                />
                <FieldDescription>
                  逗号或换行分隔，6 位代码。不在系统里的代码会拒绝。
                </FieldDescription>
              </Field>
            ) : (
              <>
                <Field>
                  <FieldTitle id="add-index-label">指数</FieldTitle>
                  <ToggleGroup
                    aria-labelledby="add-index-label"
                    value={[index]}
                    onValueChange={(next) => {
                      if (next[0]) onIndexChange(next[0])
                    }}
                    variant="outline"
                    className="w-full max-w-full flex-wrap"
                  >
                    {INDEX_OPTIONS.map((option) => (
                      <ToggleGroupItem key={option.value} value={option.value}>
                        {option.label}
                      </ToggleGroupItem>
                    ))}
                  </ToggleGroup>
                </Field>
                <Field orientation="horizontal">
                  <FieldContent>
                    <FieldLabel htmlFor="replace-index">
                      覆盖当前成分
                    </FieldLabel>
                    <FieldDescription>
                      打开后，不在指数里的票会标为移除，行情仍保留。
                    </FieldDescription>
                  </FieldContent>
                  <Switch
                    id="replace-index"
                    checked={replaceIndex}
                    onCheckedChange={onReplaceIndexChange}
                  />
                </Field>
              </>
            )}
          </FieldGroup>
          <DialogFooter>
            <Button type="submit" disabled={busy || !poolId}>
              {busy ? <Spinner data-icon="inline-start" /> : null}
              {mode === "index" ? "拉取并加入" : "加入"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
