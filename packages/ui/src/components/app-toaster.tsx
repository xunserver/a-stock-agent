import { Toaster } from "sonner"

export function AppToaster() {
  return (
    <Toaster
      closeButton
      position="top-center"
      toastOptions={{
        classNames: {
          toast:
            "group toast bg-popover text-popover-foreground border-border shadow-lg",
          title: "text-sm font-medium",
          description: "text-sm text-muted-foreground",
          actionButton: "bg-primary text-primary-foreground",
          cancelButton: "bg-muted text-muted-foreground",
        },
      }}
    />
  )
}
