import React, { useEffect, useState } from "react";
import OAuthConnectButton from "../components/OAuthConnectButton";
import APIIntegrationService from "../services/api-integration-service";

/**
 * Integrations Page
 * Страница управления интеграциями с внешними сервисами
 */
const IntegrationsPage: React.FC = () => {
  const [providers, setProviders] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const apiService = new APIIntegrationService();

  useEffect(() => {
    loadProviders();
  }, []);

  const loadProviders = async () => {
    try {
      const data = await apiService.getOAuthProviders();
      setProviders(data);
    } catch (error) {
      console.error("Failed to load OAuth providers:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="integrations-page"
      style={{
        padding: "40px",
        maxWidth: "1200px",
        margin: "0 auto",
      }}
    >
      <div style={{ marginBottom: "40px" }}>
        <h1
          style={{ fontSize: "32px", fontWeight: "bold", marginBottom: "10px" }}
        >
          Интеграции
        </h1>
        <p style={{ color: "#666", fontSize: "16px" }}>
          Подключите внешние сервисы для расширения функциональности
        </p>
      </div>

      {loading ? (
        <div style={{ textAlign: "center", padding: "40px" }}>
          <div
            style={{
              width: "40px",
              height: "40px",
              border: "4px solid #f3f3f3",
              borderTop: "4px solid #3498db",
              borderRadius: "50%",
              animation: "spin 1s linear infinite",
              margin: "0 auto",
            }}
          />
          <p style={{ marginTop: "20px", color: "#666" }}>Загрузка...</p>
        </div>
      ) : (
        <>
          <section style={{ marginBottom: "40px" }}>
            <h2
              style={{
                fontSize: "24px",
                fontWeight: "600",
                marginBottom: "20px",
              }}
            >
              Системы контроля версий
            </h2>
            <div
              style={{ display: "flex", flexDirection: "column", gap: "15px" }}
            >
              <OAuthConnectButton
                provider="github"
                onConnect={() => console.log("GitHub connected")}
                onDisconnect={() => console.log("GitHub disconnected")}
              />
              <OAuthConnectButton
                provider="gitlab"
                onConnect={() => console.log("GitLab connected")}
                onDisconnect={() => console.log("GitLab disconnected")}
              />
            </div>
          </section>

          <section style={{ marginBottom: "40px" }}>
            <h2
              style={{
                fontSize: "24px",
                fontWeight: "600",
                marginBottom: "20px",
              }}
            >
              Управление проектами
            </h2>
            <div
              style={{ display: "flex", flexDirection: "column", gap: "15px" }}
            >
              <OAuthConnectButton
                provider="jira"
                onConnect={() => console.log("Jira connected")}
                onDisconnect={() => console.log("Jira disconnected")}
              />
            </div>
          </section>

          {providers && (
            <section
              style={{
                marginTop: "40px",
                padding: "20px",
                backgroundColor: "#f8f9fa",
                borderRadius: "8px",
              }}
            >
              <h3
                style={{
                  fontSize: "18px",
                  fontWeight: "600",
                  marginBottom: "10px",
                }}
              >
                Информация о провайдерах
              </h3>
              <pre
                style={{
                  backgroundColor: "#fff",
                  padding: "15px",
                  borderRadius: "4px",
                  overflow: "auto",
                  fontSize: "12px",
                }}
              >
                {JSON.stringify(providers, null, 2)}
              </pre>
            </section>
          )}
        </>
      )}

      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default IntegrationsPage;
