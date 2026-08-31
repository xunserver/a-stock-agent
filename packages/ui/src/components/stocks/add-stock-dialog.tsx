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
  FieldTitle,
} from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { INDEX_OPTIONS } from "@/lib/indexes"

type AddMode = "codes" | "index"
type AddStockDialogProps = {
  open: boolean
  busy: boolean
  mode: AddMode
  codes: string
  index: string
  onOpenChange: (open: boolean) => void
  onModeChange: (mode: AddMode) => void
  onCodesChange: (codes: string) => void
  onIndexChange: (index: string) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
}

export function AddStockDialog({
  open,
  busy,
  mode,
  codes,
  index,
  onOpenChange,
  onModeChange,
  onCodesChange,
  onIndexChange,
  onSubmit,
}: AddStockDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <form className="flex flex-col gap-4" onSubmit={onSubmit}>
          <DialogHeader>
            <DialogTitle>加入系统</DialogTitle>
            <DialogDescription>
              这里决定系统里有哪些股票的数据。加入股票池要到「股票池」页。指数拉取可能要几秒。
            </DialogDescription>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldTitle id="stock-add-mode-label">方式</FieldTitle>
              <ToggleGroup
                aria-labelledby="stock-add-mode-label"
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
                <FieldLabel htmlFor="stock-add-codes">股票代码</FieldLabel>
                <Textarea
                  id="stock-add-codes"
                  required
                  value={codes}
                  placeholder="000001.SZ, 600519.SS"
                  onChange={(event) => onCodesChange(event.target.value)}
                />
                <FieldDescription>
                  逗号或换行分隔。6 位代码或带交易所后缀，例如 000001.SZ。
                </FieldDescription>
              </Field>
            ) : (
              <Field>
                <FieldTitle id="stock-add-index-label">指数</FieldTitle>
                <ToggleGroup
                  aria-labelledby="stock-add-index-label"
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
            )}
          </FieldGroup>
          <DialogFooter>
            <Button type="submit" disabled={busy}>
              {busy ? <Spinner data-icon="inline-start" /> : null}
              {mode === "index" ? "拉取并加入" : "加入"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
