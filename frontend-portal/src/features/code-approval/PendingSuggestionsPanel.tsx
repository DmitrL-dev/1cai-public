/**
 * Pending Suggestions Panel - показывает все ожидающие approval
 */

import { api } from "@/lib/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import React from "react";
import { CodeApprovalModal } from "./CodeApprovalModal";

export const PendingSuggestionsPanel: React.FC<{
  userId: string;
}> = ({ userId }) => {
  const [selectedToken, setSelectedToken] = React.useState<string | null>(null);
  const [showModal, setShowModal] = React.useState(false);
  const queryClient = useQueryClient();

  // Загрузка pending suggestions
  const { data, isLoading } = useQuery({
    queryKey: ["pending-suggestions", userId],
    queryFn: async () => {
      const response = await api.get(
        `/code-approval/pending?user_id=${userId}`
      );
      return response.data;
    },
    refetchInterval: 30000, // Обновление каждые 30 секунд
  });

  // Загрузка полного preview
  const { data: preview } = useQuery({
    queryKey: ["code-preview", selectedToken],
    queryFn: async () => {
      if (!selectedToken) return null;
      const response = await api.get(`/code-approval/preview/${selectedToken}`);
      return response.data;
    },
    enabled: !!selectedToken,
  });

  // Bulk approve mutation
  const bulkApproveMutation = useMutation({
    mutationFn: async (tokens: string[]) => {
      const response = await api.post("/code-approval/approve-all", {
        tokens,
        approved_by_user: userId,
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pending-suggestions"] });
    },
  });

  const handleBulkApprove = () => {
    // Только безопасные suggestions (score > 0.95)
    const safeTokens = data.suggestions
      .filter((s: any) => s.can_auto_apply)
      .map((s: any) => s.token);

    if (safeTokens.length > 0) {
      bulkApproveMutation.mutate(safeTokens);
    }
  };

  const handleReviewClick = (token: string) => {
    setSelectedToken(token);
    setShowModal(true);
  };

  if (isLoading) {
    return <div className="p-4">Loading suggestions...</div>;
  }

  const pendingCount = data?.pending || 0;
  const safeCount =
    data?.suggestions?.filter((s: any) => s.can_auto_apply).length || 0;

  return (
    <div className="bg-white rounded-lg shadow p-6">
      {/* Header */}
      <div className="flex justify-between items-center mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            Pending AI Suggestions
          </h3>
          <p className="text-sm text-gray-600">
            {pendingCount} suggestion{pendingCount !== 1 ? "s" : ""} waiting for
            your review
          </p>
        </div>

        {safeCount > 0 && (
          <button
            onClick={handleBulkApprove}
            disabled={bulkApproveMutation.isPending}
            className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 font-medium flex items-center gap-2"
          >
            ✅ Apply All Safe ({safeCount})
          </button>
        )}
      </div>

      {/* List */}
      {pendingCount === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <div className="text-4xl mb-2">✨</div>
          <p>No pending suggestions</p>
          <p className="text-sm">All caught up!</p>
        </div>
      ) : (
        <div className="space-y-3">
          {data.suggestions.map((suggestion: any) => (
            <div
              key={suggestion.token}
              className="border rounded-lg p-4 hover:border-blue-500 transition cursor-pointer"
              onClick={() => handleReviewClick(suggestion.token)}
            >
              <div className="flex justify-between items-start mb-2">
                <div className="flex-1">
                  <p className="font-medium text-gray-900">
                    {suggestion.prompt}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {new Date(suggestion.created_at).toLocaleString()}
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  {/* Safety Badge */}
                  <div
                    className={`px-3 py-1 rounded-full text-xs font-semibold ${
                      suggestion.safety_score >= 0.95
                        ? "bg-green-100 text-green-800"
                        : suggestion.safety_score >= 0.8
                        ? "bg-yellow-100 text-yellow-800"
                        : "bg-red-100 text-red-800"
                    }`}
                  >
                    {(suggestion.safety_score * 100).toFixed(0)}% Safe
                  </div>

                  {suggestion.can_auto_apply && (
                    <div className="px-3 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">
                      ⚡ Auto-approvable
                    </div>
                  )}
                </div>
              </div>

              <div className="text-sm text-blue-600 hover:text-blue-800 font-medium">
                Click to review →
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal */}
      {showModal && preview && (
        <CodeApprovalModal
          suggestion={preview.suggestion}
          originalPrompt={preview.prompt}
          token={selectedToken!}
          safety={preview.safety}
          onApprove={() => {
            setShowModal(false);
            setSelectedToken(null);
          }}
          onReject={() => {
            setShowModal(false);
            setSelectedToken(null);
          }}
          onClose={() => {
            setShowModal(false);
            setSelectedToken(null);
          }}
        />
      )}
    </div>
  );
};
