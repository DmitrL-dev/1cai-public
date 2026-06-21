import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_authenticated/marketplace")({
  beforeLoad: () => {
    throw redirect({ to: "/value-packs" })
  },
  component: LegacyMarketplaceRedirect,
})

function LegacyMarketplaceRedirect() {
  return null
}
