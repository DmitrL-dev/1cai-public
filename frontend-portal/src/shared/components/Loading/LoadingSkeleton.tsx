/**
 * Loading Skeletons
 * Show layout while loading (better than spinner!)
 */

import React from 'react';

export const DashboardSkeleton: React.FC = () => {
  return (
    <div className="p-8 bg-gray-50 min-h-screen animate-pulse">
      {/* Header */}
      <div className="mb-8">
        <div className="h-10 w-64 bg-gray-200 rounded mb-2"></div>
        <div className="h-6 w-48 bg-gray-200 rounded"></div>
      </div>
      
      {/* Big revenue card */}
      <div className="bg-gray-200 rounded-3xl h-64 mb-8"></div>
      
      {/* Three cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-gray-200 rounded-2xl h-48"></div>
        <div className="bg-gray-200 rounded-2xl h-48"></div>
        <div className="bg-gray-200 rounded-2xl h-48"></div>
      </div>
      
      {/* Activity card */}
      <div className="bg-gray-200 rounded-2xl h-64 mb-8"></div>
      
      {/* Action buttons */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-gray-200 rounded-2xl h-32"></div>
        <div className="bg-gray-200 rounded-2xl h-32"></div>
        <div className="bg-gray-200 rounded-2xl h-32"></div>
        <div className="bg-gray-200 rounded-2xl h-32"></div>
      </div>
    </div>
  );
};

export const CardSkeleton: React.FC = () => {
  return (
    <div className="bg-white rounded-2xl p-6 shadow-lg animate-pulse">
      <div className="h-6 w-3/4 bg-gray-200 rounded mb-4"></div>
      <div className="h-4 w-1/2 bg-gray-200 rounded mb-2"></div>
      <div className="h-4 w-2/3 bg-gray-200 rounded"></div>
    </div>
  );
};

export const TableSkeleton: React.FC<{ rows?: number }> = ({ rows = 5 }) => {
  return (
    <div className="bg-white rounded-2xl p-6 shadow-lg">
      <div className="h-8 w-48 bg-gray-200 rounded mb-6 animate-pulse"></div>
      
      <div className="space-y-4">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center gap-4 animate-pulse">
            <div className="h-12 w-12 bg-gray-200 rounded-full"></div>
            <div className="flex-1">
              <div className="h-4 w-3/4 bg-gray-200 rounded mb-2"></div>
              <div className="h-3 w-1/2 bg-gray-200 rounded"></div>
            </div>
            <div className="h-10 w-24 bg-gray-200 rounded"></div>
          </div>
        ))}
      </div>
    </div>
  );
};

export const MetricSkeleton: React.FC = () => {
  return (
    <div className="bg-white rounded-2xl p-8 shadow-lg text-center animate-pulse">
      <div className="h-16 w-16 bg-gray-200 rounded-full mx-auto mb-4"></div>
      <div className="h-8 w-24 bg-gray-200 rounded mx-auto mb-2"></div>
      <div className="h-4 w-32 bg-gray-200 rounded mx-auto"></div>
    </div>
  );
};

export const LoadingSkeleton: React.FC<{ type?: 'dashboard' | 'card' | 'table' | 'metric' }> = ({ 
  type = 'dashboard' 
}) => {
  switch (type) {
    case 'dashboard':
      return <DashboardSkeleton />;
    case 'card':
      return <CardSkeleton />;
    case 'table':
      return <TableSkeleton />;
    case 'metric':
      return <MetricSkeleton />;
    default:
      return <DashboardSkeleton />;
  }
};

export default LoadingSkeleton;


