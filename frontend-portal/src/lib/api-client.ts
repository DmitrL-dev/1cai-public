import axios, { AxiosInstance } from "axios";

// Get API base URL from environment or default to localhost
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Create axios instance with proper configuration
export const axiosInstance: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 seconds
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor for adding auth tokens
axiosInstance.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = localStorage.getItem("auth_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
axiosInstance.interceptors.response.use(
  (response) => response,
  (error) => {
    // Handle common errors
    if (error.response?.status === 401) {
      // Unauthorized - redirect to login
      localStorage.removeItem("auth_token");
      window.location.href = "/login";
    } else if (error.response?.status === 403) {
      // Forbidden
      console.error("Access denied");
    } else if (error.response?.status >= 500) {
      // Server error
      console.error("Server error:", error.response.data);
    }
    return Promise.reject(error);
  }
);

// Dashboard API endpoints
const dashboardAPI = {
  /**
   * Get owner dashboard data
   */
  owner: async () => {
    return axiosInstance.get("/api/dashboard/owner");
  },

  /**
   * Get executive dashboard data
   */
  executive: async () => {
    return axiosInstance.get("/api/dashboard/executive");
  },

  /**
   * Get project manager dashboard data
   */
  pm: async () => {
    return axiosInstance.get("/api/dashboard/pm");
  },

  /**
   * Get developer dashboard data
   */
  developer: async () => {
    return axiosInstance.get("/api/dashboard/developer");
  },
};

// AI Services API endpoints
const aiAPI = {
  /**
   * Query AI Orchestrator
   */
  query: async (query: string, context?: string) => {
    return axiosInstance.post("/api/ai/query", { query, context });
  },

  /**
   * Search code using Code Graph Service
   */
  searchCode: async (query: string, language?: string) => {
    return axiosInstance.post("/api/ai/code/search", { query, language });
  },

  /**
   * Get scenario recommendations
   */
  getScenarios: async (context: string) => {
    return axiosInstance.post("/api/ai/scenarios", { context });
  },

  /**
   * Analyze screenshot using VLM Server
   */
  analyzeScreenshot: async (imageData: File | Blob) => {
    const formData = new FormData();
    formData.append("file", imageData);

    return axiosInstance.post("/api/vlm/analyze", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
  },
};

// Export unified API client
export const api = {
  ...axiosInstance,
  dashboard: dashboardAPI,
  ai: aiAPI,
};

export const apiClient = api;

// Export types for better TypeScript support
export type APIClient = typeof api;
