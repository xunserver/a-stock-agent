import type { ReactNode } from "react"

import {
  Field,
  FieldContent,
  FieldDescription,
  FieldLabel,
  FieldSet,
  FieldTitle,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { JsonSchema, JsonSchemaOption } from "@/lib/api"

import { displayEnum, storeEnum } from "./schema-helpers"

type SchemaChoiceFieldProps = {
  name: string
  spec: JsonSchema
  values: Record<string, unknown>
  onChange: (name: string, value: unknown) => void
  id: string
  title: string
  types: string[]
  options: JsonSchemaOption[]
  readOnly: boolean
}

function FieldDetails({
  id,
  title,
  description,
}: {
  id: string
  title: string
  description?: string
}) {
  return (
    <FieldContent>
      <FieldLabel htmlFor={id}>{title}</FieldLabel>
      {description ? <FieldDescription>{description}</FieldDescription> : null}
    </FieldContent>
  )
}

function HorizontalField({ children }: { children: ReactNode }) {
  return <Field orientation="horizontal">{children}</Field>
}

export function isChoiceField(
  spec: JsonSchema,
  types: string[],
  options: JsonSchemaOption[]
) {
  return Boolean(
    spec["x-secret"] ||
    spec["x-widget"] === "switch" ||
    (types.includes("boolean") && spec["x-widget"] !== "toggle-group") ||
    (spec["x-widget"] === "switch-set" && types.includes("array")) ||
    ((spec["x-widget"] === "toggle-group" ||
      (options.length >= 2 && options.length <= 4 && !spec["x-widget"])) &&
      options.length) ||
    spec["x-widget"] === "select" ||
    (options.length > 4 && types.includes("string")) ||
    spec["x-widget"] === "time"
  )
}

export function SchemaChoiceField({
  name,
  spec,
  values,
  onChange,
  id,
  title,
  types,
  options,
  readOnly,
}: SchemaChoiceFieldProps) {
  const details = (
    <FieldDetails id={id} title={title} description={spec.description} />
  )
  if (spec["x-secret"]) {
    const configured = Boolean(values[`${name}_set`])
    return (
      <HorizontalField>
        {details}
        <Input
          id={id}
          name={name}
          type="password"
          autoComplete="new-password"
          value={String(values[name] ?? "")}
          placeholder={configured ? "已配置，留空则不修改" : "未配置"}
          className="max-w-xs"
          disabled={readOnly}
          onChange={(event) => onChange(name, event.target.value)}
        />
      </HorizontalField>
    )
  }
  if (
    spec["x-widget"] === "switch" ||
    (types.includes("boolean") && spec["x-widget"] !== "toggle-group")
  ) {
    return (
      <HorizontalField>
        {details}
        <Switch
          id={id}
          checked={Boolean(values[name])}
          disabled={readOnly}
          onCheckedChange={(checked) => onChange(name, checked)}
        />
      </HorizontalField>
    )
  }
  if (spec["x-widget"] === "switch-set" && types.includes("array")) {
    const selected = Array.isArray(values[name])
      ? (values[name] as unknown[]).map(String)
      : []
    return (
      <FieldSet>
        <FieldTitle>{title}</FieldTitle>
        {options.map((item) => (
          <HorizontalField key={item.value}>
            <FieldContent>
              <FieldLabel htmlFor={`${id}-${item.value}`}>
                {item.label}
              </FieldLabel>
              {item.description ? (
                <FieldDescription>{item.description}</FieldDescription>
              ) : null}
            </FieldContent>
            <Switch
              id={`${id}-${item.value}`}
              checked={selected.includes(item.value)}
              disabled={readOnly}
              onCheckedChange={(checked) =>
                onChange(
                  name,
                  checked
                    ? selected.includes(item.value)
                      ? selected
                      : [...selected, item.value]
                    : selected.filter((entry) => entry !== item.value)
                )
              }
            />
          </HorizontalField>
        ))}
      </FieldSet>
    )
  }
  if (
    (spec["x-widget"] === "toggle-group" ||
      (options.length >= 2 && options.length <= 4 && !spec["x-widget"])) &&
    options.length
  ) {
    return (
      <HorizontalField>
        <FieldTitle id={id}>{title}</FieldTitle>
        <ToggleGroup
          aria-labelledby={id}
          value={[displayEnum(spec, values[name])]}
          disabled={readOnly}
          onValueChange={(next) => {
            const key = next[0]
            if (typeof key === "string") onChange(name, storeEnum(spec, key))
          }}
          variant="outline"
          spacing={0}
        >
          {options.map((item) => {
            const value =
              item.value === "" ? spec["x-emptyToken"] || "empty" : item.value
            return (
              <ToggleGroupItem key={value} value={value}>
                {item.label}
              </ToggleGroupItem>
            )
          })}
        </ToggleGroup>
      </HorizontalField>
    )
  }
  if (
    spec["x-widget"] === "select" ||
    (options.length > 4 && types.includes("string"))
  ) {
    return (
      <HorizontalField>
        {details}
        <Select
          items={options}
          value={String(values[name] ?? "")}
          disabled={readOnly}
          onValueChange={(value) => {
            if (typeof value === "string") onChange(name, value)
          }}
        >
          <SelectTrigger id={id} className="min-w-56">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {options.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </HorizontalField>
    )
  }
  return (
    <HorizontalField>
      {details}
      <Input
        id={id}
        name={name}
        type="time"
        value={String(values[name] ?? "")}
        className="max-w-40"
        disabled={readOnly}
        onChange={(event) => onChange(name, event.target.value)}
      />
    </HorizontalField>
  )
}
