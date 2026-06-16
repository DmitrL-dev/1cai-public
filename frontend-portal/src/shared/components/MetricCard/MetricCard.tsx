/**
 * Metric Card Component
 * For displaying KPIs with trends
 */

import React from 'react';
import { clsx } from 'clsx';
import { ArrowUp, ArrowDown, Minus } from 'lucide-react';
import Card from '../Card/Card';

export interface MetricCardProps {
  title: string;
  value: string | number;
  change?: number;
  trend?: 'up' | 'down' | 'stable';
  status?: 'good' | 'warning' | 'critical';
  subtitle?: string;
  icon?: React.ReactNode;
  format?: 'number' | 'currency' | 'percentage';
  loading?: boolean;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  change,
  trend = 'stable',
  status = 'good',
  subtitle,
  icon,
  format = 'number',
  loading = false,
}) => {
  const formatValue = (val: string | number): string => {
    if (typeof val === 'string') return val;
    
    switch (format) {
      case 'currency':
        return new Intl.NumberFormat('de-DE', {
          style: 'currency',
          currency: 'EUR',
          minimumFractionDigits: 0,
          maximumFractionDigits: 2,
        }).format(val);
      
      case 'percentage':
        return `${val}%`;
      
      default:
        return new Intl.NumberFormat('de-DE').format(val);
    }
  };
  
  const statusColors = {
    good: 'text-success-500',
    warning: 'text-warning-500',
    critical: 'text-error-500',
  };
  
  const trendIcons = {
    up: <ArrowUp className="w-4 h-4" />,
    down: <ArrowDown className="w-4 h-4" />,
    stable: <Minus className="w-4 h-4" />,
  };
  
  const trendColors = {
    up: 'text-success-600 bg-success-50',
    down: 'text-error-600 bg-error-50',
    stable: 'text-gray-600 bg-gray-50',
  };
  
  if (loading) {
    return (
      <Card className="animate-pulse">
        <div className="h-32 bg-gray-200 dark:bg-gray-700 rounded" />
      </Card>
    );
  }
  
  return (
    <Card hover className="min-h-[160px]">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            {icon && (
              <div className={clsx('text-2xl', statusColors[status])}>
                {icon}
              </div>
            )}
            <h4 className="text-sm font-medium text-gray-600 dark:text-gray-400">
              {title}
            </h4>
          </div>
          
          <div className={clsx('text-3xl font-bold mb-2', statusColors[status])}>
            {formatValue(value)}
          </div>
          
          {subtitle && (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {subtitle}
            </p>
          )}
        </div>
      </div>
      
      {change !== undefined && (
        <div className={clsx(
          'inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium mt-3',
          trendColors[trend]
        )}>
          {trendIcons[trend]}
          <span>
            {change > 0 && '+'}{change}%
          </span>
          <span className="text-gray-600">vs last period</span>
        </div>
      )}
    </Card>
  );
};

export default MetricCard;


