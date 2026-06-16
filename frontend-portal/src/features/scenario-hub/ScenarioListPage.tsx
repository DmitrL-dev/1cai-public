import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Scenario, scenarioHubService } from "../../services/scenario-hub-service";

export const ScenarioListPage: React.FC = () => {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadScenarios();
  }, []);

  const loadScenarios = async () => {
    try {
      const data = await scenarioHubService.getScenarios();
      setScenarios(data);
    } catch (error) {
      console.error("Failed to load scenarios:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="p-8">Loading...</div>;

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Scenario Hub</h1>
        <button className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
          Create Scenario
        </button>
      </div>

      <div className="grid gap-4">
        {scenarios.map((scenario) => (
          <div key={scenario.id} className="border p-4 rounded shadow hover:shadow-md transition">
            <div className="flex justify-between items-start">
              <div>
                <h2 className="text-xl font-semibold">{scenario.name}</h2>
                <p className="text-gray-600">{scenario.description}</p>
                <div className="mt-2 text-sm text-gray-500">
                  Steps: {scenario.steps.length} | Created: {new Date(scenario.created_at).toLocaleDateString()}
                </div>
              </div>
              <div className="flex gap-2">
                <button 
                  onClick={() => scenarioHubService.executeScenario(scenario.id)}
                  className="bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700 text-sm"
                >
                  Run
                </button>
                <Link 
                  to={`/scenarios/${scenario.id}`}
                  className="bg-gray-200 text-gray-800 px-3 py-1 rounded hover:bg-gray-300 text-sm"
                >
                  Edit
                </Link>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
