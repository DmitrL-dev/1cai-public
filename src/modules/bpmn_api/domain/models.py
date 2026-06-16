from pydantic import BaseModel


class BPMNDiagram(BaseModel):
    id: str
    name: str
    description: str
    xml: str
    project_id: str | None = None


class SaveDiagramRequest(BaseModel):
    name: str
    description: str
    xml: str
    project_id: str | None = None
