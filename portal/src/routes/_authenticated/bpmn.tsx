import { createFileRoute } from "@tanstack/react-router"
import { Plus, Pencil, Trash2, Workflow } from "lucide-react"

interface BpmnDiagram {
  id: string
  name: string
  lastModified: string
  author: string
}

const mockDiagrams: BpmnDiagram[] = [
  { id: "1", name: "Order Processing", lastModified: "2026-02-20", author: "ivanov.a" },
  { id: "2", name: "Invoice Approval", lastModified: "2026-02-18", author: "petrov.d" },
  { id: "3", name: "Employee Onboarding", lastModified: "2026-02-15", author: "kuznetsova.e" },
  { id: "4", name: "Return Handling", lastModified: "2026-02-12", author: "novikov.s" },
]

function BpmnPage() {
  return (
    <div className="space-y-8 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          BPMN Diagrams
        </h1>
        <button className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90">
          <Plus className="h-4 w-4" />
          New Diagram
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {mockDiagrams.map((diagram) => (
          <div
            key={diagram.id}
            className="overflow-hidden rounded-lg border bg-card"
          >
            {/* Preview placeholder */}
            <div className="flex h-40 items-center justify-center bg-muted/40">
              <Workflow className="h-12 w-12 text-muted-foreground/50" />
            </div>

            <div className="p-4">
              <h3 className="text-lg font-semibold text-foreground">
                {diagram.name}
              </h3>
              <div className="mt-1 flex items-center gap-3 text-sm text-muted-foreground">
                <span>Modified {diagram.lastModified}</span>
                <span>·</span>
                <span>{diagram.author}</span>
              </div>

              <div className="mt-4 flex gap-2">
                <button className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-3 py-1.5 text-sm font-medium text-foreground transition-colors hover:bg-muted">
                  <Pencil className="h-3.5 w-3.5" />
                  Edit
                </button>
                <button className="inline-flex items-center gap-1.5 rounded-md border border-destructive/30 bg-background px-3 py-1.5 text-sm font-medium text-destructive transition-colors hover:bg-destructive/10">
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export const Route = createFileRoute("/_authenticated/bpmn")({
  component: BpmnPage,
})
