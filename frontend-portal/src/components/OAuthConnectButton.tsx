import React, { useEffect, useState } from "react";
import APIIntegrationService from "../services/api-integration-service";

interface OAuthConnectButtonProps {
  provider: "github" | "gitlab" | "jira";
  onConnect?: () => void;
  onDisconnect?: () => void;
}

/**
 * OAuth Connect Button Component
 * Кнопка для подключения/отключения OAuth провайдера
 */
const OAuthConnectButton: React.FC<OAuthConnectButtonProps> = ({
  provider,
  onConnect,
  onDisconnect,
}) => {
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);
  const apiService = new APIIntegrationService();

  // Проверить статус подключения при монтировании
  useEffect(() => {
    checkStatus();
  }, [provider]);

  const checkStatus = async () => {
    try {
      const status = await apiService.getOAuthStatus(provider);
      setConnected(status.connected);
      setExpiresAt(status.expires_at || null);
    } catch (error) {
      console.error("Failed to check OAuth status:", error);
    }
  };

  const handleConnect = async () => {
    try {
      setLoading(true);
      const authUrl = await apiService.connectOAuth(provider);

      // Redirect на страницу авторизации
      window.location.href = authUrl;

      if (onConnect) {
        onConnect();
      }
    } catch (error) {
      console.error("Failed to connect OAuth:", error);
      alert(`Ошибка подключения: ${(error as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    if (!confirm(`Отключить ${getProviderName(provider)}?`)) {
      return;
    }

    try {
      setLoading(true);
      await apiService.disconnectOAuth(provider);
      setConnected(false);
      setExpiresAt(null);

      if (onDisconnect) {
        onDisconnect();
      }
    } catch (error) {
      console.error("Failed to disconnect OAuth:", error);
      alert(`Ошибка отключения: ${(error as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const getProviderName = (provider: string): string => {
    const names: Record<string, string> = {
      github: "GitHub",
      gitlab: "GitLab",
      jira: "Jira",
    };
    return names[provider] || provider;
  };

  const getProviderIcon = (provider: string): string => {
    const icons: Record<string, string> = {
      github: "🐙",
      gitlab: "🦊",
      jira: "📋",
    };
    return icons[provider] || "🔗";
  };

  return (
    <div
      className="oauth-connect-button"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "10px",
        padding: "15px",
        border: "1px solid #e0e0e0",
        borderRadius: "8px",
        backgroundColor: "#fff",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{ fontSize: "24px" }}>{getProviderIcon(provider)}</span>
          <div>
            <h3 style={{ margin: 0, fontSize: "16px" }}>
              {getProviderName(provider)}
            </h3>
            {connected && expiresAt && (
              <p style={{ margin: 0, fontSize: "12px", color: "#666" }}>
                Истекает: {new Date(expiresAt).toLocaleDateString()}
              </p>
            )}
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {connected && (
            <span
              style={{
                padding: "4px 8px",
                backgroundColor: "#4caf50",
                color: "white",
                borderRadius: "4px",
                fontSize: "12px",
              }}
            >
              Подключено
            </span>
          )}

          <button
            onClick={connected ? handleDisconnect : handleConnect}
            disabled={loading}
            style={{
              padding: "8px 16px",
              backgroundColor: connected ? "#f44336" : "#3498db",
              color: "white",
              border: "none",
              borderRadius: "4px",
              cursor: loading ? "not-allowed" : "pointer",
              opacity: loading ? 0.6 : 1,
              fontSize: "14px",
              fontWeight: 500,
            }}
          >
            {loading ? "Загрузка..." : connected ? "Отключить" : "Подключить"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default OAuthConnectButton;
