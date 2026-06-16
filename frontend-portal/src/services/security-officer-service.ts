import { axiosInstance as apiClient } from "../lib/api-client";

export interface ScanRequest {
  target_path: string;
  scan_type: "full" | "quick" | "secrets";
}

export interface Vulnerability {
  id: string;
  severity: "critical" | "high" | "medium" | "low";
  description: string;
  file_path: string;
  line_number: number;
}

export interface ScanResult {
  id: string;
  status: "completed" | "failed";
  vulnerabilities: Vulnerability[];
  scanned_files_count: number;
  scan_duration_ms: number;
}

export const securityOfficerService = {
  async runScan(request: ScanRequest): Promise<ScanResult> {
    const response = await apiClient.post("/api/v1/security/scan", request);
    return response.data;
  },
};
