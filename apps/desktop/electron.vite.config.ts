import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "electron-vite"

const uiSrc = path.resolve(import.meta.dirname, "../../packages/ui/src")
const repoRoot = path.resolve(import.meta.dirname, "../..")

export default defineConfig({
  main: {},
  preload: {},
  renderer: {
    resolve: {
      alias: {
        "@": uiSrc,
      },
    },
    plugins: [react(), tailwindcss()],
    define: {
      "import.meta.env.VITE_API_BASE": JSON.stringify("http://127.0.0.1:8787"),
    },
    server: {
      port: 5174,
      strictPort: true,
      fs: {
        allow: [repoRoot],
      },
    },
  },
})
