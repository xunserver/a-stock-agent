import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

const uiSrc = path.resolve(import.meta.dirname, "../../../packages/ui/src")

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": uiSrc,
    },
  },
  server: {
    fs: {
      allow: [path.resolve(import.meta.dirname, "../../..")],
    },
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8787",
        changeOrigin: true,
      },
    },
  },
})
