/**
 * Shared types for all Edge Functions
 * Eliminates code duplication and ensures consistency
 */

export interface BaseRequest {
  demoType: string;
  userQuery?: string;
}

export interface ProgressStep {
  progress: number;
  message: string;
  result?: any;
}

export interface DemoResponse {
  data: {
    steps: ProgressStep[];
    finalResult: any;
  };
}

export interface ErrorResponse {
  error: {
    code: string;
    message: string;
    timestamp?: string;
    requestId?: string;
    service?: string;
    version?: string;
    [key: string]: any;
  };
}

export interface ValidationResult {
  isValid: boolean;
  errors: string[];
}

export interface ServiceMetadata {
  service: string;
  version: string;
  timestamp: string;
  processingTime: string;
  supportedLanguages: string[];
  capabilities: string[];
}