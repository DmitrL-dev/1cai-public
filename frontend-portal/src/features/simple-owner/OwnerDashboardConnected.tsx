/**
 * CONNECTED Owner Dashboard
 * Loads REAL data from API!
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../lib/api-client';
import { DashboardSkeleton } from '../../shared/components/Loading/LoadingSkeleton';

interface DashboardData {
  revenue: {
    this_month: number;
    last_month: number;
    change_percent: number;
    trend: 'up' | 'down' | 'stable';
  };
  customers: {
    total: number;
    new_this_month: number;
  };
  growth_percent: number;
  system_status: 'healthy' | 'unhealthy';
  recent_activities: Array<{
    type: string;
    description: string;
    actor: string;
    timestamp: string;
  }>;
}

export const OwnerDashboardConnected: React.FC = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDashboard();
    
    // Refresh every 30 seconds
    const interval = setInterval(loadDashboard, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadDashboard = async () => {
    try {
      setError(null);
      const response = await api.dashboard.owner();
      setData(response.data);
    } catch (err: any) {
      console.error('Failed to load dashboard:', err);
      setError(err.response?.data?.detail || 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <DashboardSkeleton />;
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50 p-8">
        <div className="bg-white rounded-2xl p-8 shadow-lg max-w-md text-center">
          <div className="text-6xl mb-4">⚠️</div>
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Oops!</h2>
          <p className="text-gray-600 mb-6">{error}</p>
          <button
            onClick={loadDashboard}
            className="bg-blue-500 hover:bg-blue-600 text-white px-8 py-3 rounded-xl text-lg font-semibold"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="p-8 bg-gray-50 min-h-screen">
      {/* Greeting */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-gray-900">
          Good Morning, Boss! 👋
        </h1>
        <p className="text-xl text-gray-600 mt-2">
          Here's your business in 30 seconds
        </p>
        <button
          onClick={loadDashboard}
          className="mt-2 text-blue-600 hover:underline text-sm"
        >
          🔄 Refresh
        </button>
      </div>
      
      {/* THE MOST IMPORTANT NUMBER */}
      <div className={`bg-gradient-to-r ${
        data.revenue.trend === 'up' ? 'from-green-400 to-green-600' : 
        data.revenue.trend === 'down' ? 'from-red-400 to-red-600' :
        'from-gray-400 to-gray-600'
      } rounded-3xl p-12 mb-8 text-white shadow-2xl`}>
        <p className="text-2xl mb-2">💰 You Made This Month:</p>
        <p className="text-7xl font-bold mb-4">
          €{data.revenue.this_month.toLocaleString()}
        </p>
        {data.revenue.change_percent !== 0 && (
          <p className="text-2xl">
            {data.revenue.trend === 'up' ? '↗️' : '↘️'} That's{' '}
            <span className="font-bold">
              {data.revenue.trend === 'up' ? '+' : ''}
              €{Math.abs(data.revenue.this_month - data.revenue.last_month).toLocaleString()}
              {' '}({data.revenue.change_percent > 0 ? '+' : ''}
              {data.revenue.change_percent}%)
            </span>{' '}
            {data.revenue.trend === 'up' ? 'more' : 'less'} than last month!
          </p>
        )}
      </div>
      
      {/* SIMPLE STATUS */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        {/* System Status */}
        <div className="bg-white rounded-2xl p-8 shadow-lg text-center">
          <div className="text-6xl mb-4">
            {data.system_status === 'healthy' ? '🟢' : '🔴'}
          </div>
          <p className="text-2xl font-bold text-gray-900 mb-2">
            {data.system_status === 'healthy' ? 'Everything is OK' : 'System Issue'}
          </p>
          <p className="text-gray-600">
            {data.system_status === 'healthy' ? 'All systems working fine' : 'Check system status'}
          </p>
        </div>
        
        {/* Customers */}
        <div className="bg-white rounded-2xl p-8 shadow-lg text-center">
          <div className="text-6xl mb-4">👥</div>
          <p className="text-5xl font-bold text-gray-900 mb-2">{data.customers.total}</p>
          <p className="text-gray-600">Happy customers</p>
          {data.customers.new_this_month > 0 && (
            <p className="text-green-600 font-semibold mt-2">
              +{data.customers.new_this_month} this month!
            </p>
          )}
        </div>
        
        {/* Growth */}
        <div className="bg-white rounded-2xl p-8 shadow-lg text-center">
          <div className="text-6xl mb-4">📈</div>
          <p className="text-5xl font-bold text-gray-900 mb-2">
            +{data.growth_percent}%
          </p>
          <p className="text-gray-600">Business growth</p>
          <p className="text-green-600 font-semibold mt-2">You're growing!</p>
        </div>
      </div>
      
      {/* WHAT HAPPENED RECENTLY */}
      <div className="bg-white rounded-2xl p-8 shadow-lg mb-8">
        <h2 className="text-2xl font-bold mb-6">📋 Recent Activity</h2>
        
        <div className="space-y-4">
          {data.recent_activities.map((activity, index) => (
            <div key={index} className="flex items-center gap-4 p-4 bg-gray-50 rounded-xl">
              <div className="text-3xl">
                {activity.type === 'new_customer' ? '✅' :
                 activity.type === 'support' ? '💬' :
                 activity.type === 'task_completed' ? '🎉' :
                 'ℹ️'}
              </div>
              <div className="flex-1">
                <p className="font-semibold">{activity.description}</p>
                <p className="text-gray-600 text-sm">
                  by {activity.actor} • {new Date(activity.timestamp).toLocaleString()}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
      
      {/* ONE-CLICK ACTIONS */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <button
          onClick={() => navigate('/reports')}
          className="bg-blue-500 hover:bg-blue-600 text-white rounded-2xl p-8 text-left shadow-lg transition-all hover:scale-105"
        >
          <div className="text-4xl mb-3">📊</div>
          <p className="text-2xl font-bold mb-2">See Full Report</p>
          <p className="text-blue-100">Revenue, customers, everything →</p>
        </button>
        
        <button
          onClick={() => navigate('/customers')}
          className="bg-purple-500 hover:bg-purple-600 text-white rounded-2xl p-8 text-left shadow-lg transition-all hover:scale-105"
        >
          <div className="text-4xl mb-3">👥</div>
          <p className="text-2xl font-bold mb-2">My Customers</p>
          <p className="text-purple-100">See who's using your product →</p>
        </button>
        
        <button
          onClick={() => navigate('/billing')}
          className="bg-green-500 hover:bg-green-600 text-white rounded-2xl p-8 text-left shadow-lg transition-all hover:scale-105"
        >
          <div className="text-4xl mb-3">💳</div>
          <p className="text-2xl font-bold mb-2">Get Paid</p>
          <p className="text-green-100">Invoices, payments, money →</p>
        </button>
        
        <button
          onClick={() => navigate('/support')}
          className="bg-orange-500 hover:bg-orange-600 text-white rounded-2xl p-8 text-left shadow-lg transition-all hover:scale-105"
        >
          <div className="text-4xl mb-3">📞</div>
          <p className="text-2xl font-bold mb-2">Customer Support</p>
          <p className="text-orange-100">Answer customer questions →</p>
        </button>
      </div>
      
      {/* HELP BUTTON (always visible) */}
      <button
        onClick={() => navigate('/help')}
        className="fixed bottom-8 right-8 bg-yellow-400 hover:bg-yellow-500 text-gray-900 rounded-full p-6 shadow-2xl text-2xl font-bold transition-all hover:scale-110"
      >
        ❓ HELP
      </button>
    </div>
  );
};

export default OwnerDashboardConnected;

