import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_authenticated/ide")({
  beforeLoad: () => {
    throw redirect({ to: "/workbench" })
  },
  component: LegacyIdeRedirect,
})

function LegacyIdeRedirect() {
  return null
}
