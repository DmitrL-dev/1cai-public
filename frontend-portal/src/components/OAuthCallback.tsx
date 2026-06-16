import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import APIIntegrationService from "../services/api-integration-service";

/**
 * OAuth Callback Component
 * Обрабатывает redirect после OAuth авторизации
 */
const OAuthCallback: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<"processing" | "success" | "error">(
    "processing"
  );
  const [error, setError] = useState<string>("");

  useEffect(() => {
    const handleCallback = async () => {
      try {
        // Получить параметры из URL
        const code = searchParams.get("code");
        const state = searchParams.get("state");
        const provider = window.location.pathname.split("/").pop() as
          | "github"
          | "gitlab"
          | "jira";

        if (!code || !state) {
          throw new Error("Missing code or state parameter");
        }

        // Обработать callback
        const apiService = new APIIntegrationService();
        await apiService.handleOAuthCallback(provider, code, state);

        setStatus("success");

        // Redirect обратно на страницу интеграций через 2 секунды
        setTimeout(() => {
          navigate("/integrations");
        }, 2000);
      } catch (err) {
        console.error("OAuth callback error:", err);
        setError((err as Error).message);
        setStatus("error");
      }
    };

    handleCallback();
  }, [searchParams, navigate]);

  return (
    <div
      className="oauth-callback-container"
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        padding: "20px",
        textAlign: "center",
      }}
    >
      {status === "processing" && (
        <>
          <div
            className="spinner"
            style={{
              width: "50px",
              height: "50px",
              border: "4px solid #f3f3f3",
              borderTop: "4px solid #3498db",
              borderRadius: "50%",
              animation: "spin 1s linear infinite",
              marginBottom: "20px",
            }}
          />
          <h2>Подключение...</h2>
          <p>Обрабатываем OAuth авторизацию</p>
        </>
      )}

      {status === "success" && (
        <>
          <div
            style={{
              width: "60px",
              height: "60px",
              borderRadius: "50%",
              backgroundColor: "#4caf50",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: "20px",
            }}
          >
            <span style={{ color: "white", fontSize: "30px" }}>✓</span>
          </div>
          <h2>Успешно подключено!</h2>
          <p>Перенаправляем обратно...</p>
        </>
      )}

      {status === "error" && (
        <>
          <div
            style={{
              width: "60px",
              height: "60px",
              borderRadius: "50%",
              backgroundColor: "#f44336",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: "20px",
            }}
          >
            <span style={{ color: "white", fontSize: "30px" }}>✗</span>
          </div>
          <h2>Ошибка подключения</h2>
          <p style={{ color: "#f44336" }}>{error}</p>
          <button
            onClick={() => navigate("/integrations")}
            style={{
              marginTop: "20px",
              padding: "10px 20px",
              backgroundColor: "#3498db",
              color: "white",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer",
            }}
          >
            Вернуться к интеграциям
          </button>
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

export default OAuthCallback;
