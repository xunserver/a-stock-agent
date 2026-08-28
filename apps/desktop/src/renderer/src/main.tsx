import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { HashRouter } from "react-router"

import { App } from "@astock/ui"
import "@astock/ui/styles.css"

import { UpdateBanner } from "./update-banner"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <HashRouter>
      <UpdateBanner />
      <App />
    </HashRouter>
  </StrictMode>
)
