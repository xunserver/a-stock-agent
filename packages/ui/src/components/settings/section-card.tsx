import { useEffect, useState, type FormEvent } from "react"
import { CheckCircle2Icon, CircleAlertIcon } from "lucide-react"

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
import { FieldGroup } from "@/components/ui/field"
import { Spinner } from "@/components/ui/spinner"
import {
  updateSettingsSection,
  type SettingsModule,
  type SettingsSection,
} from "@/lib/api"

import { SchemaField } from "./schema-field"
import {
  patchFromForm,
  propertyEntries,
  sectionFormValues,
} from "./schema-helpers"

type SectionCardProps = {
  moduleId: string
  section: SettingsSection
  onSaved: (next: SettingsSection) => void
}

export function SectionCard({ moduleId, section, onSaved }: SectionCardProps) {
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
    if (section.read_only) return
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
              {saving ? <Spinner data-icon="inline-start" /> : null}保存{" "}
              {section.title}
            </Button>
          </CardFooter>
        )}
      </Card>
    </form>
  )
}

type ModuleSectionsProps = {
  module: SettingsModule
  onSectionSaved: (sectionId: string, next: SettingsSection) => void
}

export function ModuleSections({
  module,
  onSectionSaved,
}: ModuleSectionsProps) {
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
