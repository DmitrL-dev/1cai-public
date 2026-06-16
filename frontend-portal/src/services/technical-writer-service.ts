import { axiosInstance as apiClient } from "../lib/api-client";

export interface DocRequest {
  source_code: string;
  doc_type: "api" | "user_guide" | "architecture";
  language: "python" | "javascript" | "typescript" | "bsl";
}

export interface DocResult {
  content: string;
  format: "markdown" | "html";
  generated_at: string;
}

export const technicalWriterService = {
  async generateDocs(request: DocRequest): Promise<DocResult> {
    const response = await apiClient.post(
      "/api/v1/technical_writer/generate",
      request
    );
    return response.data;
  },
};
