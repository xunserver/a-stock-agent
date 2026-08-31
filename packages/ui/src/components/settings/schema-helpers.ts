import type { JsonSchema, JsonSchemaOption, SettingsSection } from "@/lib/api"

export function isVisible(spec: JsonSchema, values: Record<string, unknown>) {
  const rules = spec["x-visibleWhen"]
  return (
    !rules ||
    Object.entries(rules).every(([key, allowed]) =>
      allowed.includes(String(values[key] ?? ""))
    )
  )
}

export function propertyEntries(schema: JsonSchema) {
  return Object.entries(schema.properties ?? {})
}

export function optionsFor(spec: JsonSchema): JsonSchemaOption[] {
  if (spec["x-options"]?.length) return spec["x-options"]
  const values = Array.isArray(spec.enum)
    ? spec.enum
    : Array.isArray(spec.items?.enum)
      ? spec.items.enum
      : []
  return values.map((item) => ({ value: String(item), label: String(item) }))
}

export function displayEnum(spec: JsonSchema, value: unknown) {
  const token = spec["x-emptyToken"]
  return token && (value === "" || value == null) ? token : String(value ?? "")
}

export function storeEnum(spec: JsonSchema, value: string) {
  return spec["x-emptyToken"] === value ? "" : value
}

export function sectionFormValues(section: SettingsSection) {
  const values: Record<string, unknown> = { ...section.values }
  for (const [name, spec] of propertyEntries(section.schema)) {
    if (spec["x-secret"] && values[name] === undefined) values[name] = ""
  }
  return values
}

export function patchFromForm(
  section: SettingsSection,
  values: Record<string, unknown>
) {
  const patch: Record<string, unknown> = {}
  for (const [name, spec] of propertyEntries(section.schema)) {
    if (spec.readOnly || !isVisible(spec, values)) continue
    if (spec["x-secret"]) {
      const typed = String(values[name] ?? "").trim()
      if (typed) patch[name] = typed
      continue
    }
    const types = Array.isArray(spec.type)
      ? spec.type
      : spec.type
        ? [spec.type]
        : []
    const value = values[name]
    if (
      (spec["x-widget"] === "json" ||
        types.includes("object") ||
        types.includes("array")) &&
      typeof value === "string"
    ) {
      throw new Error(`${spec.title ?? name} 需要合法 JSON`)
    }
    patch[name] = value
  }
  return patch
}
