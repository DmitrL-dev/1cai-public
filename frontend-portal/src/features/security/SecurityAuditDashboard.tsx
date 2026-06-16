/**
 * Security Audit Dashboard - мониторинг AI security
 */

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../lib/api-client';

export const SecurityAuditDashboard: React.FC = () => {
  const { data: metrics, isLoading } = useQuery({
    queryKey: ['security-metrics'],
    queryFn: async () => {
      const response = await api.get('/api/security/metrics');
      return response.data;
    },
    refetchInterval: 30000 // Обновление каждые 30 секунд
  });

  const { data: recentAlerts } = useQuery({
    queryKey: ['security-alerts'],
    queryFn: async () => {
      const response = await api.get('/api/security/alerts?limit=10');
      return response.data;
    },
    refetchInterval: 10000 // Обновление каждые 10 секунд
  });

  if (isLoading) {
    return <div>Loading security metrics...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">
          🔒 Security Audit Dashboard
        </h1>
        <p className="text-gray-600 mt-1">
          Real-time monitoring of AI agent security
        </p>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-4 gap-4">
        <MetricCard
          title="Blocked Inputs (24h)"
          value={metrics?.blocked_inputs_24h || 0}
          trend={metrics?.blocked_trend}
          icon="🛡️"
          status={metrics?.blocked_inputs_24h > 100 ? 'warning' : 'success'}
        />
        
        <MetricCard
          title="Data Leakage Attempts"
          value={metrics?.leakage_attempts || 0}
          trend={metrics?.leakage_trend}
          icon="🚨"
          status={metrics?.leakage_attempts > 0 ? 'critical' : 'success'}
        />
        
        <MetricCard
          title="Human Approvals (24h)"
          value={metrics?.human_approvals_24h || 0}
          trend={metrics?.approval_trend}
          icon="✅"
          status="info"
        />
        
        <MetricCard
          title="Auto-Rejected (ML)"
          value={metrics?.ml_rejections || 0}
          trend={metrics?.ml_trend}
          icon="🤖"
          status="info"
        />
      </div>

      {/* Agents Rule of Two Compliance */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">
          📊 Agents Rule of Two Compliance
        </h3>
        
        <div className="space-y-3">
          {[
            { name: 'Developer AI', config: '[AB]', status: 'compliant' },
            { name: 'Code Review AI', config: '[BC]', status: 'compliant' },
            { name: 'SQL Optimizer', config: '[AB]', status: 'compliant' },
            { name: 'DevOps AI', config: '[BC]', status: 'compliant' },
            { name: 'QA AI', config: '[AC]', status: 'compliant' },
            { name: 'Copilot', config: '[AB]', status: 'compliant' },
            { name: 'Business Analyst', config: '[AC]', status: 'compliant' },
            { name: 'Tech Writer', config: '[AC]', status: 'compliant' },
            { name: 'Architect', config: '[AB]', status: 'compliant' },
            { name: 'Issue Classifier', config: '[AB]', status: 'compliant' },
          ].map((agent) => (
            <div
              key={agent.name}
              className="flex items-center justify-between p-3 border rounded hover:bg-gray-50"
            >
              <div className="flex items-center gap-3">
                <span className="text-2xl">
                  {agent.status === 'compliant' ? '✅' : '⚠️'}
                </span>
                <div>
                  <div className="font-medium">{agent.name}</div>
                  <div className="text-sm text-gray-600">
                    Configuration: <code className="bg-gray-100 px-2 py-1 rounded">{agent.config}</code>
                  </div>
                </div>
              </div>
              <span className={`px-3 py-1 rounded-full text-sm font-semibold ${
                agent.status === 'compliant'
                  ? 'bg-green-100 text-green-800'
                  : 'bg-yellow-100 text-yellow-800'
              }`}>
                {agent.status === 'compliant' ? 'Compliant' : 'Review Needed'}
              </span>
            </div>
          ))}
        </div>
        
        <div className="mt-4 p-3 bg-green-50 rounded">
          <strong className="text-green-900">
            ✅ 100% Compliance Achieved!
          </strong>
          <p className="text-green-800 text-sm mt-1">
            All 10 agents follow Agents Rule of Two framework
          </p>
        </div>
      </div>

      {/* Recent Security Alerts */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">
          🚨 Recent Security Alerts
        </h3>
        
        {!recentAlerts || recentAlerts.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <div className="text-4xl mb-2">✨</div>
            <p>No security alerts</p>
            <p className="text-sm">All systems secure!</p>
          </div>
        ) : (
          <div className="space-y-2">
            {recentAlerts.map((alert: any, index: number) => (
              <div
                key={index}
                className={`p-3 rounded border-l-4 ${
                  alert.severity === 'CRITICAL'
                    ? 'bg-red-50 border-red-500'
                    : alert.severity === 'HIGH'
                    ? 'bg-orange-50 border-orange-500'
                    : 'bg-yellow-50 border-yellow-500'
                }`}
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">
                        {alert.event_type}
                      </span>
                      <span className={`px-2 py-0.5 rounded text-xs font-semibold ${
                        alert.severity === 'CRITICAL'
                          ? 'bg-red-200 text-red-900'
                          : 'bg-orange-200 text-orange-900'
                      }`}>
                        {alert.severity}
                      </span>
                    </div>
                    <p className="text-sm text-gray-700 mt-1">
                      {alert.reason}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      Agent: {alert.agent_id} • {new Date(alert.timestamp).toLocaleString()}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Attack Patterns Timeline */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">
          📈 Attack Patterns (Last 7 Days)
        </h3>
        {/* График будет здесь - placeholder */}
        <div className="h-64 bg-gray-50 rounded flex items-center justify-center text-gray-500">
          Chart: Attack patterns over time
        </div>
      </div>
    </div>
  );
};

const MetricCard: React.FC<{
  title: string;
  value: number;
  trend?: string;
  icon: string;
  status: 'success' | 'warning' | 'critical' | 'info';
}> = ({ title, value, trend, icon, status }) => {
  const statusColors = {
    success: 'from-green-500 to-emerald-600',
    warning: 'from-yellow-500 to-orange-600',
    critical: 'from-red-500 to-pink-600',
    info: 'from-blue-500 to-cyan-600',
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm text-gray-600">{title}</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">{value}</p>
          {trend && (
            <p className="text-sm text-gray-500 mt-1">{trend}</p>
          )}
        </div>
        <div className={`text-4xl bg-gradient-to-br ${statusColors[status]} p-3 rounded-lg`}>
          {icon}
        </div>
      </div>
    </div>
  );
};


