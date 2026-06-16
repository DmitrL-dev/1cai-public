import { axiosInstance as apiClient } from "../lib/api-client";

export interface Scenario {
  id: string;
  name: string;
  description: string;
  steps: ScenarioStep[];
  created_at: string;
  updated_at: string;
}

export interface ScenarioStep {
  id: string;
  action: string;
  params: Record<string, any>;
  expected_result?: string;
}

export interface ExecutionResult {
  scenario_id: string;
  status: "success" | "failure";
  logs: string[];
  duration_ms: number;
}

export const scenarioHubService = {
  async getScenarios(): Promise<Scenario[]> {
    const response = await apiClient.get("/api/v1/scenario_hub/scenarios");
    return response.data;
  },

  async getScenario(id: string): Promise<Scenario> {
    const response = await apiClient.get(
      `/api/v1/scenario_hub/scenarios/${id}`
    );
    return response.data;
  },

  async createScenario(
    scenario: Omit<Scenario, "id" | "created_at" | "updated_at">
  ): Promise<Scenario> {
    const response = await apiClient.post(
      "/api/v1/scenario_hub/scenarios",
      scenario
    );
    return response.data;
  },

  async executeScenario(id: string): Promise<ExecutionResult> {
    const response = await apiClient.post(
      `/api/v1/scenario_hub/scenarios/${id}/execute`
    );
    return response.data;
  },
};
