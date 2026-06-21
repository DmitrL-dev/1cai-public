import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react-swc"
import { tanstackRouter } from "@tanstack/router-plugin/vite"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [
    tanstackRouter({
      quoteStyle: "double",
      autoCodeSplitting: true,
      codeSplittingOptions: {
        defaultBehavior: [["component"], ["pendingComponent"], ["errorComponent"], ["notFoundComponent"]],
      },
    }),
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: true,
    port: 3000,
    strictPort: true,
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: process.env.VITE_WS_PROXY_TARGET || "ws://localhost:8000",
        ws: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          const normalized = id.replace(/\\/g, "/")

          if (normalized.includes("/node_modules/")) {
            if (normalized.includes("/@tanstack/")) return "tanstack"
            if (normalized.includes("/lucide-react/")) return "icons"
            return "vendor"
          }

          if (normalized.includes("/src/routes/_authenticated/")) {
            if (/(killer-demo|launch-room|board-pack|outcome-ledger|buyer-concierge|commercial-offer-studio|demo-command-center|pilot-launchpad|scenario-hub|guided-demo|business-case|vendor-portfolio|value-packs)/.test(normalized)) {
              return "routes-deal"
            }
            if (/(approvals|audit|enterprise-trust-center|productization|offline-readiness|operations|lock-radar|extension-safety|rights-rls|platform-doctor)/.test(normalized)) {
              return "routes-trust"
            }
            if (/(configurations|quality|change|safe-autopilot|testing|release-readiness|architecture|metadata|requirements|team-governance|edt-mcp|workbench)/.test(normalized)) {
              return "routes-engineering"
            }
            return "routes-other"
          }
        },
      },
    },
  },
})
