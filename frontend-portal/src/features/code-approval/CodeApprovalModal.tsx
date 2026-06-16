/**
 * Code Approval Modal - Human-in-the-Loop для AI suggestions
 * Based on Agents Rule of Two [AB] configuration
 */

import { api } from "@/lib/api-client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import React, { useState } from "react";

interface CodeApprovalModalProps {
  suggestion: string;
  originalPrompt: string;
  token: string;
  safety: {
    score: number;
    concerns: Array<{
      severity: string;
      issue: string;
      suggestion?: string;
    }>;
    safe: boolean;
    auto_approvable: boolean;
  };
  onApprove: () => void;
  onReject: () => void;
  onClose: () => void;
}

export const CodeApprovalModal: React.FC<CodeApprovalModalProps> = ({
  suggestion,
  originalPrompt,
  token,
  safety,
  onApprove,
  onReject,
  onClose,
}) => {
  const [editedCode, setEditedCode] = useState(suggestion);
  const [isEditing, setIsEditing] = useState(false);
  const queryClient = useQueryClient();

  // Mutation для approval
  const approveMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post("/code-approval/approve", {
        token,
        approved_by_user: "current_user", // TODO: Get from auth
        changes_made: isEditing ? editedCode : null,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["code-suggestions"] });
      onApprove();
    },
  });

  // Mutation для reject
  const rejectMutation = useMutation({
    mutationFn: async () => {
      const response = await api.delete(`/code-approval/reject/${token}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["code-suggestions"] });
      onReject();
    },
  });

  const handleApprove = () => {
    approveMutation.mutate();
  };

  const handleReject = () => {
    rejectMutation.mutate();
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "CRITICAL":
        return "text-red-600 bg-red-50";
      case "HIGH":
        return "text-orange-600 bg-orange-50";
      case "MEDIUM":
        return "text-yellow-600 bg-yellow-50";
      default:
        return "text-gray-600 bg-gray-50";
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
        <div className="bg-gradient-to-r from-blue-600 to-purple-600 px-6 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-2xl font-bold text-white">
                🔍 Review AI Suggestion
              </h2>
              <p className="text-blue-100 text-sm mt-1">
                Requires your approval before applying
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-white hover:text-gray-200 text-2xl"
            >
              ×
            </button>
          </div>
        </div>

        <div className="p-6 overflow-y-auto max-h-[calc(90vh-200px)]">
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">
              Your Request:
            </h3>
            <div className="bg-gray-50 rounded p-3 text-gray-800">
              {originalPrompt}
            </div>
          </div>

          {safety.concerns.length > 0 && (
            <div className="mb-6">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">
                ⚠️ Security Concerns Detected:
              </h3>
              <div className="space-y-2">
                {safety.concerns.map((concern, index) => (
                  <div
                    key={index}
                    className={`p-3 rounded ${getSeverityColor(
                      concern.severity
                    )}`}
                  >
                    <div className="flex items-start">
                      <span className="font-semibold mr-2">
                        {concern.severity}:
                      </span>
                      <div className="flex-1">
                        <p>{concern.issue}</p>
                        {concern.suggestion && (
                          <p className="text-sm mt-1 italic">
                            💡 {concern.suggestion}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="mb-6">
            <h3 className="text-sm font-semibold text-gray-700 mb-2">
              Safety Score:
            </h3>
            <div className="flex items-center">
              <div className="flex-1 bg-gray-200 rounded-full h-4">
                <div
                  className={`h-4 rounded-full ${
                    safety.score >= 0.8
                      ? "bg-green-500"
                      : safety.score >= 0.5
                      ? "bg-yellow-500"
                      : "bg-red-500"
                  }`}
                  style={{ width: `${safety.score * 100}%` }}
                />
              </div>
              <span className="ml-3 font-semibold text-lg">
                {(safety.score * 100).toFixed(0)}%
              </span>
            </div>
            {safety.auto_approvable && (
              <p className="text-green-600 text-sm mt-2">
                ✅ This suggestion is safe to auto-apply in future
              </p>
            )}
          </div>

          <div className="mb-6">
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-sm font-semibold text-gray-700">
                Generated Code:
              </h3>
              <button
                onClick={() => setIsEditing(!isEditing)}
                className="text-blue-600 hover:text-blue-800 text-sm font-medium"
              >
                {isEditing ? "👁️ Preview" : "✏️ Edit"}
              </button>
            </div>

            {isEditing ? (
              <textarea
                value={editedCode}
                onChange={(e) => setEditedCode(e.target.value)}
                className="w-full h-64 font-mono text-sm border rounded p-3 focus:ring-2 focus:ring-blue-500"
                style={{ fontFamily: "JetBrains Mono, Consolas, monospace" }}
              />
            ) : (
              <pre className="bg-gray-900 text-gray-100 rounded p-4 overflow-x-auto">
                <code
                  className="text-sm"
                  style={{ fontFamily: "JetBrains Mono, Consolas, monospace" }}
                >
                  {editedCode}
                </code>
              </pre>
            )}
          </div>

          <div className="bg-blue-50 rounded p-3 text-sm text-blue-800">
            <strong>⌨️ Keyboard Shortcuts:</strong>
            <div className="mt-1 space-x-4">
              <span>
                <kbd className="px-2 py-1 bg-white rounded">Cmd+Enter</kbd>{" "}
                Apply
              </span>
              <span>
                <kbd className="px-2 py-1 bg-white rounded">Cmd+E</kbd> Edit
              </span>
              <span>
                <kbd className="px-2 py-1 bg-white rounded">Esc</kbd> Reject
              </span>
            </div>
          </div>
        </div>

        <div className="bg-gray-50 px-6 py-4 flex justify-between items-center border-t">
          <div className="text-sm text-gray-600">
            {isEditing && (
              <span className="text-orange-600">
                ⚠️ You've made changes - they will be applied
              </span>
            )}
          </div>

          <div className="flex gap-3">
            <button
              onClick={handleReject}
              disabled={rejectMutation.isPending}
              className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-100 font-medium"
            >
              ❌ Reject
            </button>

            {isEditing && (
              <button
                onClick={() => setIsEditing(false)}
                className="px-4 py-2 bg-gray-200 rounded hover:bg-gray-300 font-medium"
              >
                💾 Save Edit
              </button>
            )}

            <button
              onClick={handleApprove}
              disabled={approveMutation.isPending}
              className={`px-6 py-2 rounded font-medium text-white ${
                safety.score >= 0.8
                  ? "bg-green-600 hover:bg-green-700"
                  : safety.score >= 0.5
                  ? "bg-yellow-600 hover:bg-yellow-700"
                  : "bg-red-600 hover:bg-red-700"
              }`}
            >
              {approveMutation.isPending ? "⏳ Applying..." : "✅ Apply"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export const useCodeApprovalShortcuts = (
  onApprove: () => void,
  onReject: () => void,
  onEdit: () => void
) => {
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey) {
        if (e.key === "Enter") {
          e.preventDefault();
          onApprove();
        } else if (e.key === "e") {
          e.preventDefault();
          onEdit();
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        onReject();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onApprove, onReject, onEdit]);
};
