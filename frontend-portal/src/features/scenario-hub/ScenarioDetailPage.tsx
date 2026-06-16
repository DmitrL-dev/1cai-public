import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Scenario, scenarioHubService } from "../../services/scenario-hub-service";

export const ScenarioDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (id) loadScenario(id);
  }, [id]);

  const loadScenario = async (scenarioId: string) => {
    try {
      const data = await scenarioHubService.getScenario(scenarioId);
      setScenario(data);
    } catch (error) {
      console.error("Failed to load scenario:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="p-8">Loading...</div>;
  if (!scenario) return <div className="p-8">Scenario not found</div>;

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-4">{scenario.name}</h1>
      <p className="text-gray-600 mb-8">{scenario.description}</p>

      <div className="bg-white rounded shadow overflow-hidden">
        <table className="min-w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Step</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Params</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Expected Result</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {scenario.steps.map((step, index) => (
              <tr key={step.id}>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{index + 1}</td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{step.action}</td>
                <td className="px-6 py-4 text-sm text-gray-500">
                  <pre className="text-xs">{JSON.stringify(step.params, null, 2)}</pre>
                </td>
                <td className="px-6 py-4 text-sm text-gray-500">{step.expected_result || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
