/**
 * Main App Component
 * Wrapped with Error Boundary
 */

import {
  Navigate,
  Route,
  BrowserRouter as Router,
  Routes,
} from "react-router-dom";
import OAuthCallback from "../components/OAuthCallback";
import { LoginPage } from "../features/auth/LoginPage";
import { DeveloperConsole } from "../features/developer/DeveloperConsole";
import { ExecutiveDashboard } from "../features/executive/ExecutiveDashboard";
import { PMDashboard } from "../features/pm/PMDashboard";
import { OwnerDashboardConnected } from "../features/simple-owner/OwnerDashboardConnected";
import IntegrationsPage from "../pages/IntegrationsPage";
import { ErrorBoundary } from "../shared/components/ErrorBoundary/ErrorBoundary";

function App() {
  return (
    <ErrorBoundary>
      <Router>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/owner" element={<OwnerDashboardConnected />} />
          <Route path="/executive" element={<ExecutiveDashboard />} />
          <Route path="/pm" element={<PMDashboard />} />
          <Route path="/developer" element={<DeveloperConsole />} />
          <Route path="/" element={<Navigate to="/owner" replace />} />

          {/* OAuth callback route */}
          <Route path="/oauth/callback/:provider" element={<OAuthCallback />} />

          {/* Integrations page */}
          <Route path="/integrations" element={<IntegrationsPage />} />

          {/* New Agent Routes */}
          <Route path="/scenarios" element={<ScenarioListPage />} />
          <Route path="/scenarios/:id" element={<ScenarioDetailPage />} />
          <Route path="/technical-writer" element={<DocGenerationPage />} />
          <Route path="/security" element={<SecurityScanPage />} />

          {/* Placeholder routes (will be implemented) */}
          <Route
            path="/customers"
            element={
              <div className="p-8">
                <h1 className="text-4xl">Customers (Coming Soon)</h1>
              </div>
            }
          />
          <Route
            path="/reports"
            element={
              <div className="p-8">
                <h1 className="text-4xl">Reports (Coming Soon)</h1>
              </div>
            }
          />
          <Route
            path="/billing"
            element={
              <div className="p-8">
                <h1 className="text-4xl">Billing (Coming Soon)</h1>
              </div>
            }
          />
          <Route
            path="/support"
            element={
              <div className="p-8">
                <h1 className="text-4xl">Support (Coming Soon)</h1>
              </div>
            }
          />
          <Route
            path="/help"
            element={
              <div className="p-8">
                <h1 className="text-4xl">Help (Coming Soon)</h1>
              </div>
            }
          />
        </Routes>
      </Router>
    </ErrorBoundary>
  );
}

export default App;
