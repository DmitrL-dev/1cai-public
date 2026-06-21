import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_authenticated/code-review")({
  beforeLoad: () => {
    throw redirect({ to: "/quality" })
  },
  component: LegacyCodeReviewRedirect,
})

function LegacyCodeReviewRedirect() {
  return null
}
