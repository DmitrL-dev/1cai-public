from pydantic import BaseModel, Field


class CompletionRequest(BaseModel):
    code: str = Field(..., max_length=50000)
    current_line: str = Field(..., max_length=1000)
    language: str = Field(default="bsl", max_length=50)
    max_suggestions: int = Field(default=3, ge=1, le=10)


class GenerationRequest(BaseModel):
    prompt: str = Field(..., max_length=5000)
    language: str = Field(default="bsl", max_length=50)
    type: str = Field(default="function", max_length=50)  # function, procedure, test


class OptimizationRequest(BaseModel):
    code: str = Field(..., max_length=50000)
    language: str = Field(default="bsl", max_length=50)
