import {
  Field,
  FieldContent,
  FieldDescription,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import type { JsonSchema } from "@/lib/api"

import { isChoiceField, SchemaChoiceField } from "./schema-field-controls"
import { isVisible, optionsFor } from "./schema-helpers"

type SchemaFieldProps = {
  name: string
  spec: JsonSchema
  values: Record<string, unknown>
  onChange: (name: string, value: unknown) => void
  disabled?: boolean
}

export function SchemaField({
  name,
  spec,
  values,
  onChange,
  disabled,
}: SchemaFieldProps) {
  if (!isVisible(spec, values)) return null
  const id = `settings-${name}`
  const title = spec.title ?? name
  const readOnly = Boolean(spec.readOnly || disabled)
  const types = Array.isArray(spec.type)
    ? spec.type
    : spec.type
      ? [spec.type]
      : []
  const options = optionsFor(spec)
  if (isChoiceField(spec, types, options))
    return (
      <SchemaChoiceField
        name={name}
        spec={spec}
        values={values}
        onChange={onChange}
        id={id}
        title={title}
        types={types}
        options={options}
        readOnly={readOnly}
      />
    )
  if (
    spec["x-widget"] === "json" ||
    types.includes("object") ||
    (types.includes("array") && !options.length)
  ) {
    const raw = values[name]
    const text =
      typeof raw === "string"
        ? raw
        : JSON.stringify(raw ?? (types.includes("array") ? [] : {}), null, 2)
    return (
      <Field>
        <FieldContent>
          <FieldLabel htmlFor={id}>{title}</FieldLabel>
          {spec.description ? (
            <FieldDescription>{spec.description}</FieldDescription>
          ) : null}
        </FieldContent>
        <Textarea
          id={id}
          name={name}
          value={text}
          disabled={readOnly}
          readOnly={readOnly}
          className="min-h-36 font-mono text-sm"
          onChange={(event) => {
            try {
              onChange(name, JSON.parse(event.target.value))
            } catch {
              onChange(name, event.target.value)
            }
          }}
        />
      </Field>
    )
  }
  if (
    types.includes("integer") ||
    types.includes("number") ||
    types.includes("null")
  ) {
    const raw = values[name]
    return (
      <Field orientation="horizontal">
        <FieldContent>
          <FieldLabel htmlFor={id}>{title}</FieldLabel>
          {spec.description ? (
            <FieldDescription>{spec.description}</FieldDescription>
          ) : null}
        </FieldContent>
        <Input
          id={id}
          name={name}
          type="number"
          min={spec.minimum}
          max={spec.maximum}
          step={types.includes("integer") ? "1" : "any"}
          value={raw == null ? "" : String(raw)}
          className="max-w-32"
          disabled={readOnly}
          onChange={(event) => {
            const value = event.target.value
            onChange(
              name,
              value === ""
                ? types.includes("null")
                  ? null
                  : value
                : Number(value)
            )
          }}
        />
      </Field>
    )
  }
  return (
    <Field orientation="horizontal" data-disabled={readOnly || undefined}>
      <FieldContent>
        <FieldLabel htmlFor={id}>{title}</FieldLabel>
        {spec.description ? (
          <FieldDescription>{spec.description}</FieldDescription>
        ) : null}
      </FieldContent>
      <Input
        id={id}
        name={name}
        value={String(values[name] ?? "")}
        disabled={readOnly}
        readOnly={readOnly}
        className={readOnly ? "font-mono" : "max-w-md"}
        onChange={(event) => onChange(name, event.target.value)}
      />
    </Field>
  )
}
