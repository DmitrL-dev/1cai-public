import { createFileRoute, redirect } from "@tanstack/react-router"

export const Route = createFileRoute("/_authenticated/bpmn")({
  beforeLoad: () => {
    throw redirect({ to: "/architecture" })
  },
  component: LegacyBpmnRedirect,
})

function LegacyBpmnRedirect() {
  return null
}
