/**
 * Developer Console
 * Code, debug, test with AI assistance
 */

import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Code2, GitPullRequest, Bug, Zap } from 'lucide-react';
import MetricCard from '@/shared/components/MetricCard/MetricCard';
import Card from '@/shared/components/Card/Card';
import { api } from '@/lib/api-client';
import type { DeveloperDashboard } from '@/lib/types';

export const DeveloperConsole: React.FC = () => {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard', 'developer'],
    queryFn: () => api.dashboard.developer().then(r => r.data as DeveloperDashboard),
  });
  
  if (isLoading || !data) {
    return <div>Loading...</div>;
  }
  
  const { assigned_tasks, code_reviews, build_status, code_quality } = data;
  
  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Developer Console</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            Your tasks, code reviews, and AI assistance
          </p>
        </div>
        
        <button className="px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 flex items-center gap-2">
          <Zap className="w-4 h-4" />
          Ask AI
        </button>
      </div>
      
      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Assigned Tasks"
          value={assigned_tasks.length}
          icon={<Code2 />}
          status="good"
        />
        
        <MetricCard
          title="Code Reviews"
          value={code_reviews.length}
          icon={<GitPullRequest />}
          status="good"
        />
        
        <MetricCard
          title="Code Coverage"
          value={code_quality.coverage}
          format="percentage"
          status={code_quality.coverage >= 80 ? 'good' : 'warning'}
        />
        
        <MetricCard
          title="Security Score"
          value={code_quality.security_score}
          format="number"
          status={code_quality.security_score >= 90 ? 'good' : 'warning'}
          icon={<Bug />}
        />
      </div>
      
      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Assigned Tasks */}
        <Card className="lg:col-span-2">
          <Card.Header>
            <h3 className="text-lg font-semibold">My Tasks</h3>
          </Card.Header>
          <Card.Body>
            <div className="space-y-3">
              {assigned_tasks.map((task) => (
                <div
                  key={task.id}
                  className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:border-primary-500 cursor-pointer transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h4 className="font-medium">{task.title}</h4>
                      <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                        {task.description}
                      </p>
                    </div>
                    
                    <span
                      className={`px-2 py-1 text-xs rounded-full ${
                        task.priority === 'critical' ? 'bg-error-100 text-error-700' :
                        task.priority === 'high' ? 'bg-warning-100 text-warning-700' :
                        'bg-gray-100 text-gray-700'
                      }`}
                    >
                      {task.priority}
                    </span>
                  </div>
                  
                  <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
                    <span>{task.status.replace('_', ' ')}</span>
                    {task.due_date && (
                      <span>Due: {new Date(task.due_date).toLocaleDateString()}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card.Body>
        </Card>
        
        {/* Code Reviews */}
        <Card>
          <Card.Header>
            <h3 className="text-lg font-semibold">Code Reviews</h3>
          </Card.Header>
          <Card.Body>
            <div className="space-y-3">
              {code_reviews.map((review) => (
                <div
                  key={review.id}
                  className="p-3 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer"
                >
                  <p className="font-medium text-sm">PR #{review.pr_number}</p>
                  <p className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                    {review.title}
                  </p>
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-xs text-gray-500">{review.author}</span>
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      review.status === 'approved' ? 'bg-success-100 text-success-700' :
                      review.status === 'changes_requested' ? 'bg-error-100 text-error-700' :
                      'bg-gray-100 text-gray-700'
                    }`}>
                      {review.status.replace('_', ' ')}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </Card.Body>
        </Card>
      </div>
      
      {/* Build Status */}
      <Card>
        <Card.Header>
          <h3 className="text-lg font-semibold">Latest Build</h3>
        </Card.Header>
        <Card.Body>
          <div className="flex items-center gap-6">
            <div className={`w-12 h-12 rounded-full flex items-center justify-center ${
              build_status.status === 'success' ? 'bg-success-100' :
              build_status.status === 'failed' ? 'bg-error-100' :
              'bg-warning-100'
            }`}>
              {build_status.status === 'success' ? '✓' :
               build_status.status === 'failed' ? '✗' : '⟳'}
            </div>
            
            <div className="flex-1">
              <p className="font-medium">
                Build {build_status.status}
              </p>
              <p className="text-sm text-gray-600">
                {build_status.tests_passed}/{build_status.tests_total} tests passed
              </p>
            </div>
            
            <div className="text-right">
              <p className="text-sm text-gray-600">Duration:</p>
              <p className="font-medium">{build_status.duration_seconds}s</p>
            </div>
          </div>
        </Card.Body>
      </Card>
    </div>
  );
};

export default DeveloperConsole;


