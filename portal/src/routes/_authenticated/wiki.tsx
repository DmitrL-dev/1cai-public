import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_authenticated/wiki")({
  beforeLoad: () => {
    throw redirect({ to: "/evidence-bundle" })
  },
  component: LegacyWikiRedirect,
})

function LegacyWikiRedirect() {
  return null
}
