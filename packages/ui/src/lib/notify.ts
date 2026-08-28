import { toast } from "sonner"

type NotifyOptions = {
  description?: string
  coreHint?: boolean
}

function withCoreHint(message: string, coreHint: boolean | undefined): string {
  if (coreHint === false) {
    return message
  }
  if (message.includes("core")) {
    return message
  }
  return `${message}。确认 core 已启动。`
}

export const notify = {
  error(title: string, options?: NotifyOptions) {
    const description = options?.description
      ? withCoreHint(options.description, options.coreHint)
      : undefined
    toast.error(title, { description })
  },
  success(title: string, options?: Pick<NotifyOptions, "description">) {
    toast.success(title, { description: options?.description })
  },
  message(title: string, options?: Pick<NotifyOptions, "description">) {
    toast.message(title, { description: options?.description })
  },
}
