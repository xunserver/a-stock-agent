import { useEffect, useMemo, useState, type FormEvent } from "react"
import { CheckCircle2Icon, CircleAlertIcon, InfoIcon } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldGroup,
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
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import {
  querySettingsCatalog,
  updateSettingsSection,
  type JsonSchema,
  type JsonSchemaOption,
  type SettingsCatalog,
  type SettingsModule,
  type SettingsSection,
} from "@/lib/api"

function isVisible(spec: JsonSchema, values: Record<string, unknown>) {
  const rules = spec["x-visibleWhen"]
  if (!rules) {
    return true
  }
  return Object.entries(rules).every(([key, allowed]) =>
    allowed.includes(String(values[key] ?? ""))
  )
}

function propertyEntries(schema: JsonSchema) {
  return Object.entries(schema.properties ?? {})
}

function optionsFor(spec: JsonSchema): JsonSchemaOption[] {
  if (spec["x-options"]?.length) {
    return spec["x-options"]
  }
  if (Array.isArray(spec.enum)) {
    return spec.enum.map((item) => ({
      value: String(item),
      label: String(item),
    }))
  }
  if (Array.isArray(spec.items?.enum)) {
    return spec.items.enum.map((item) => ({
      value: String(item),
      label: String(item),
    }))
  }
  return []
}

function displayEnum(spec: JsonSchema, value: unknown) {
  const token = spec["x-emptyToken"]
  if (token && (value === "" || value == null)) {
    return token
  }
  return String(value ?? "")
}

function storeEnum(spec: JsonSchema, value: string) {
  const token = spec["x-emptyToken"]
  if (token && value === token) {
    return ""
  }
  return value
}

function secretKey(name: string) {
  return `${name}_set`
}

function SchemaField({
  name,
  spec,
  values,
  onChange,
  disabled,
}: {
  name: string
  spec: JsonSchema
  values: Record<string, unknown>
  onChange: (name: string, value: unknown) => void
  disabled?: boolean
}) {
  if (!isVisible(spec, values)) {
    return null
  }
  const id = `settings-${name}`
  const title = spec.title ?? name
  const description = spec.description
  const widget = spec["x-widget"]
  const readOnly = Boolean(spec.readOnly || disabled)
  const types = Array.isArray(spec.type) ? spec.type : spec.type ? [spec.type] : []
  const opts = optionsFor(spec)

  if (spec["x-secret"]) {
    const configured = Boolean(values[secretKey(name)])
    return (
      <Field orientation="horizontal">
        <FieldContent>
          <FieldLabel htmlFor={id}>{title}</FieldLabel>
          {description ? <FieldDescription>{description}</FieldDescription> : null}
        </FieldContent>
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
      </Field>
    )
  }

  if (widget === "switch" || (types.includes("boolean") && widget !== "toggle-group")) {
    return (
      <Field orientation="horizontal">
        <FieldContent>
          <FieldLabel htmlFor={id}>{title}</FieldLabel>
          {description ? <FieldDescription>{description}</FieldDescription> : null}
        </FieldContent>
        <Switch
          id={id}
          checked={Boolean(values[name])}
          disabled={readOnly}
          onCheckedChange={(checked) => onChange(name, checked)}
        />
      </Field>
    )
  }

  if (widget === "switch-set" && types.includes("array")) {
    const selected = Array.isArray(values[name])
      ? (values[name] as unknown[]).map((item) => String(item))
      : []
    return (
      <FieldSet>
        <FieldTitle>{title}</FieldTitle>
        {opts.map((item) => (
          <Field orientation="horizontal" key={item.value}>
            <FieldContent>
              <FieldLabel htmlFor={`${id}-${item.value}`}>{item.label}</FieldLabel>
              {item.description ? (
                <FieldDescription>{item.description}</FieldDescription>
              ) : null}
            </FieldContent>
            <Switch
              id={`${id}-${item.value}`}
              checked={selected.includes(item.value)}
              disabled={readOnly}
              onCheckedChange={(checked) => {
                const next = checked
                  ? selected.includes(item.value)
                    ? selected
                    : [...selected, item.value]
                  : selected.filter((entry) => entry !== item.value)
                onChange(name, next)
              }}
            />
          </Field>
        ))}
      </FieldSet>
    )
  }

  if ((widget === "toggle-group" || (opts.length >= 2 && opts.length <= 4 && !widget)) && opts.length) {
    return (
      <Field orientation="horizontal">
        <FieldTitle id={id}>{title}</FieldTitle>
        <ToggleGroup
          aria-labelledby={id}
          value={[displayEnum(spec, values[name])]}
          disabled={readOnly}
          onValueChange={(next) => {
            const key = next[0]
            if (typeof key === "string") {
              onChange(name, storeEnum(spec, key))
            }
          }}
          variant="outline"
          spacing={0}
        >
          {opts.map((item) => (
            <ToggleGroupItem
              key={item.value === "" ? spec["x-emptyToken"] || "empty" : item.value}
              value={item.value === "" ? spec["x-emptyToken"] || "empty" : item.value}
            >
              {item.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </Field>
    )
  }

  if (widget === "select" || (opts.length > 4 && types.includes("string"))) {
    const current = String(values[name] ?? "")
    return (
      <Field orientation="horizontal">
        <FieldLabel htmlFor={id}>{title}</FieldLabel>
        <Select
          items={opts}
          value={current}
          disabled={readOnly}
          onValueChange={(value) => {
            if (typeof value === "string") {
              onChange(name, value)
            }
          }}
        >
          <SelectTrigger id={id} className="min-w-56">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {opts.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </Field>
    )
  }

  if (widget === "time") {
    return (
      <Field orientation="horizontal">
        <FieldLabel htmlFor={id}>{title}</FieldLabel>
        <Input
          id={id}
          name={name}
          type="time"
          value={String(values[name] ?? "")}
          className="max-w-40"
          disabled={readOnly}
          onChange={(event) => onChange(name, event.target.value)}
        />
      </Field>
    )
  }

  if (types.includes("integer") || types.includes("number") || types.includes("null")) {
    const raw = values[name]
    const text = raw === null || raw === undefined ? "" : String(raw)
    return (
      <Field orientation="horizontal">
        <FieldContent>
          <FieldLabel htmlFor={id}>{title}</FieldLabel>
          {description ? <FieldDescription>{description}</FieldDescription> : null}
        </FieldContent>
        <Input
          id={id}
          name={name}
          type="number"
          min={spec.minimum}
          max={spec.maximum}
          step={types.includes("integer") ? "1" : "any"}
          value={text}
          className="max-w-32"
          disabled={readOnly}
          onChange={(event) => {
            const next = event.target.value
            if (next === "") {
              onChange(name, types.includes("null") ? null : next)
              return
            }
            onChange(name, types.includes("integer") ? Number(next) : Number(next))
          }}
        />
      </Field>
    )
  }

  return (
    <Field orientation="horizontal" data-disabled={readOnly || undefined}>
      <FieldContent>
        <FieldLabel htmlFor={id}>{title}</FieldLabel>
        {description ? <FieldDescription>{description}</FieldDescription> : null}
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

function sectionFormValues(section: SettingsSection) {
  const values: Record<string, unknown> = { ...section.values }
  for (const [name, spec] of propertyEntries(section.schema)) {
    if (spec["x-secret"] && values[name] === undefined) {
      values[name] = ""
    }
  }
  return values
}

function patchFromForm(section: SettingsSection, values: Record<string, unknown>) {
  const patch: Record<string, unknown> = {}
  for (const [name, spec] of propertyEntries(section.schema)) {
    if (spec.readOnly) {
      continue
    }
    if (spec["x-secret"]) {
      const typed = String(values[name] ?? "").trim()
      if (typed) {
        patch[name] = typed
      }
      continue
    }
    if (!isVisible(spec, values)) {
      continue
    }
    patch[name] = values[name]
  }
  return patch
}

function SectionCard({
  moduleId,
  section,
  onSaved,
}: {
  moduleId: string
  section: SettingsSection
  onSaved: (next: SettingsSection) => void
}) {
  const [values, setValues] = useState(() => sectionFormValues(section))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    setValues(sectionFormValues(section))
    setError(null)
    setSaved(false)
  }, [section])

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (section.read_only) {
      return
    }
    setSaving(true)
    setSaved(false)
    setError(null)
    try {
      const next = await updateSettingsSection(
        moduleId,
        section.id,
        patchFromForm(section, values)
      )
      onSaved({
        ...section,
        values: next.values,
        updated_at: next.updated_at,
        schema: next.schema,
      })
      setSaved(true)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "保存失败")
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={(event) => void onSubmit(event)}>
      <Card>
        <CardHeader>
          <CardTitle>{section.title}</CardTitle>
          <CardDescription>{section.description}</CardDescription>
        </CardHeader>
        <CardContent>
          {error ? (
            <Alert variant="destructive" className="mb-4">
              <CircleAlertIcon />
              <AlertTitle>无法保存 {section.title}</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
          {saved && !error ? (
            <Alert className="mb-4">
              <CheckCircle2Icon />
              <AlertTitle>已保存</AlertTitle>
              <AlertDescription>
                写入系统库的 {moduleId}.{section.id}。刷新后仍会读到这次的值。
              </AlertDescription>
            </Alert>
          ) : null}
          <FieldGroup>
            {propertyEntries(section.schema).map(([name, spec]) => (
              <SchemaField
                key={name}
                name={name}
                spec={spec}
                values={values}
                disabled={section.read_only}
                onChange={(field, value) =>
                  setValues((current) => ({ ...current, [field]: value }))
                }
              />
            ))}
          </FieldGroup>
        </CardContent>
        {section.read_only ? null : (
          <CardFooter>
            <Button type="submit" disabled={saving}>
              {saving ? <Spinner data-icon="inline-start" /> : null}
                    保存 {section.title}
            </Button>
          </CardFooter>
        )}
      </Card>
    </form>
  )
}

function ModuleSections({
  module,
  onSectionSaved,
}: {
  module: SettingsModule
  onSectionSaved: (sectionId: string, next: SettingsSection) => void
}) {
  return (
    <div className="flex flex-col gap-4">
      {module.sections.map((section) => (
        <SectionCard
          key={`${module.id}.${section.id}`}
          moduleId={module.id}
          section={section}
          onSaved={(next) => onSectionSaved(section.id, next)}
        />
      ))}
    </div>
  )
}

export function SettingsPage() {
  const [catalog, setCatalog] = useState<SettingsCatalog | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const defaultModule = catalog?.modules[0]?.id ?? "ingest"

  const modules = useMemo(() => catalog?.modules ?? [], [catalog])

  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const next = await querySettingsCatalog()
        if (!cancelled) {
          setCatalog(next)
          setError(null)
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "加载失败")
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="flex flex-col gap-4">
      <Alert>
        <InfoIcon />
        <AlertTitle>设置存在系统库</AlertTitle>
        <AlertDescription>
          schema 和取值都写在 data/system.db，和行情库 market.db 分开。按模块打开，每个小类单独保存。
        </AlertDescription>
      </Alert>
      {error ? (
        <Alert variant="destructive">
          <CircleAlertIcon />
          <AlertTitle>无法读写系统设置</AlertTitle>
          <AlertDescription>{error}。确认 core 已启动。</AlertDescription>
        </Alert>
      ) : null}

      {loading && catalog === null ? (
        <Card>
          <CardHeader>
            <CardTitle>系统设置</CardTitle>
            <CardDescription>正在从系统库读取模块和 schema。</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
            <Skeleton className="h-8 w-full" />
          </CardContent>
        </Card>
      ) : catalog ? (
        <Tabs defaultValue={defaultModule} orientation="vertical" className="items-start">
          <TabsList variant="line" className="w-44">
            {modules.map((module) => (
              <TabsTrigger key={module.id} value={module.id}>
                {module.title}
              </TabsTrigger>
            ))}
          </TabsList>
          {modules.map((module) => (
            <TabsContent key={module.id} value={module.id} className="min-w-0 w-full">
              <div className="flex flex-col gap-4">
                <div>
                  <h2 className="text-base font-medium">{module.title}</h2>
                  <p className="text-sm text-muted-foreground">{module.description}</p>
                </div>
                <ModuleSections
                  module={module}
                  onSectionSaved={(sectionId, next) =>
                    setCatalog((current) => {
                      if (!current) {
                        return current
                      }
                      return {
                        ...current,
                        modules: current.modules.map((item) =>
                          item.id === module.id
                            ? {
                                ...item,
                                sections: item.sections.map((section) =>
                                  section.id === sectionId ? next : section
                                ),
                              }
                            : item
                        ),
                      }
                    })
                  }
                />
              </div>
            </TabsContent>
          ))}
        </Tabs>
      ) : null}
    </div>
  )
}
