import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_authenticated/rentgen")({
  beforeLoad: () => {
    throw redirect({ to: "/" })
  },
  component: LegacyRentgenRedirect,
})

function LegacyRentgenRedirect() {
  return null
}
