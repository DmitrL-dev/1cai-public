/**
 * SQL Approval Modal - для approval SQL execution
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import React, { useState } from "react";

interface SQLApprovalModalProps {
  originalSQL: string;
  optimizedSQL: string;
  token: string;
  safety: {
    safe_for_auto_execute: boolean;
    has_dangerous_ops: boolean;
    is_read_only: boolean;
    operations: string[];
    requires_dba_approval: boolean;
    warning?: string;
  };
  performance: {
    original_estimated_time: number;
    optimized_estimated_time: number;
    speedup: number;
    explanation: string;
  };
  onExecute: () => void;
  onReject: () => void;
  onClose: () => void;
}

export const SQLApprovalModal: React.FC<SQLApprovalModalProps> = ({
  originalSQL,
  optimizedSQL,
  token,
  safety,
  performance,
  onExecute,
  onReject,
  onClose,
}) => {
  const [confirmationText, setConfirmationText] = useState("");
  const queryClient = useQueryClient();

  const executeMutation = useMutation({
    mutationFn: async () => {
      const response = await fetch("/api/sql-approval/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token,
          approved_by_user: "current_user",
          confirmation_text: confirmationText,
        }),
      });

      if (!response.ok) {
        throw new Error(await response.text());
      }

      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sql-suggestions"] });
      onExecute();
    },
  });

  const handleExecute = () => {
    if (safety.has_dangerous_ops && confirmationText !== "CONFIRM") {
      alert("Please type CONFIRM to execute dangerous operation");
      return;
    }

    executeMutation.mutate();
  };

  const needsConfirmation = safety.has_dangerous_ops;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-2xl max-w-5xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div
          className={`px-6 py-4 ${
            safety.has_dangerous_ops
              ? "bg-gradient-to-r from-red-600 to-orange-600"
              : "bg-gradient-to-r from-blue-600 to-green-600"
          }`}
        >
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-2xl font-bold text-white">
                {safety.has_dangerous_ops ? "⚠️" : "⚡"} SQL Optimization Review
              </h2>
              <p className="text-blue-100 text-sm mt-1">
                {safety.has_dangerous_ops
                  ? "DANGEROUS OPERATION - Requires confirmation"
                  : "Review optimized query before execution"}
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

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-200px)]">
          {/* Warning for dangerous ops */}
          {safety.has_dangerous_ops && (
            <div className="mb-6 p-4 bg-red-50 border-2 border-red-500 rounded-lg">
              <div className="flex items-start">
                <div className="text-4xl mr-4">🚨</div>
                <div className="flex-1">
                  <h4 className="text-lg font-bold text-red-900 mb-2">
                    CRITICAL WARNING
                  </h4>
                  <p className="text-red-800 mb-2">{safety.warning}</p>
                  <div className="bg-white rounded p-2 text-sm font-mono text-red-900">
                    Operations: {safety.operations.join(", ")}
                  </div>
                  {safety.requires_dba_approval && (
                    <p className="text-red-900 font-semibold mt-2">
                      ⚠️ This requires DBA approval!
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Performance Comparison */}
          <div className="mb-6 bg-gradient-to-r from-green-50 to-blue-50 rounded-lg p-4">
            <h3 className="font-semibold text-gray-900 mb-3">
              ⚡ Performance Improvement
            </h3>
            <div className="grid grid-cols-3 gap-4 text-center">
              <div>
                <div className="text-3xl font-bold text-red-600">
                  {performance.original_estimated_time.toFixed(1)}s
                </div>
                <div className="text-sm text-gray-600">Original</div>
              </div>
              <div className="flex items-center justify-center">
                <div className="text-2xl">→</div>
              </div>
              <div>
                <div className="text-3xl font-bold text-green-600">
                  {performance.optimized_estimated_time.toFixed(1)}s
                </div>
                <div className="text-sm text-gray-600">Optimized</div>
              </div>
            </div>
            <div className="mt-3 text-center">
              <span className="text-2xl font-bold text-purple-600">
                {performance.speedup.toFixed(1)}x faster!
              </span>
              <p className="text-sm text-gray-600 mt-1">
                {performance.explanation}
              </p>
            </div>
          </div>

          {/* SQL Comparison */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">
                Original Query (Slow):
              </h3>
              <pre className="bg-red-50 border border-red-200 text-gray-900 rounded p-4 overflow-x-auto text-sm font-mono">
                {originalSQL}
              </pre>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-2">
                Optimized Query (Fast):
              </h3>
              <pre className="bg-green-50 border border-green-200 text-gray-900 rounded p-4 overflow-x-auto text-sm font-mono">
                {optimizedSQL}
              </pre>
            </div>
          </div>

          {/* Confirmation for dangerous ops */}
          {needsConfirmation && (
            <div className="mb-6 p-4 bg-yellow-50 border-2 border-yellow-500 rounded">
              <h4 className="font-semibold text-yellow-900 mb-2">
                ⚠️ Confirmation Required
              </h4>
              <p className="text-yellow-800 mb-3">
                This operation is DANGEROUS and can cause data loss. Type{" "}
                <strong>CONFIRM</strong> to proceed:
              </p>
              <input
                type="text"
                value={confirmationText}
                onChange={(e) => setConfirmationText(e.target.value)}
                placeholder="Type CONFIRM"
                className="w-full px-4 py-2 border-2 border-yellow-500 rounded focus:ring-2 focus:ring-yellow-500 font-mono uppercase"
              />
              {confirmationText && confirmationText !== "CONFIRM" && (
                <p className="text-red-600 text-sm mt-2">
                  ❌ Must type exactly "CONFIRM" (all caps)
                </p>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="bg-gray-50 px-6 py-4 flex justify-between items-center border-t">
          <div className="text-sm text-gray-600">
            {safety.is_read_only ? (
              <span className="text-green-600 font-medium">
                ✅ Read-only query - Safe to execute
              </span>
            ) : (
              <span className="text-orange-600 font-medium">
                ⚠️ Will modify data - Review carefully
              </span>
            )}
          </div>

          <div className="flex gap-3">
            <button
              onClick={onReject}
              className="px-4 py-2 border border-gray-300 rounded hover:bg-gray-100 font-medium"
            >
              ❌ Cancel
            </button>

            <button
              onClick={() => {
                navigator.clipboard.writeText(optimizedSQL);
                alert("Copied to clipboard!");
              }}
              className="px-4 py-2 bg-gray-200 rounded hover:bg-gray-300 font-medium"
            >
              📋 Copy
            </button>

            <button
              onClick={handleExecute}
              disabled={
                executeMutation.isPending ||
                (needsConfirmation && confirmationText !== "CONFIRM")
              }
              className={`px-6 py-2 rounded font-medium text-white ${
                safety.has_dangerous_ops
                  ? "bg-red-600 hover:bg-red-700"
                  : "bg-green-600 hover:bg-green-700"
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              {executeMutation.isPending ? "⏳ Executing..." : "▶️ Execute"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
