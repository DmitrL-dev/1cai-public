import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  Activity,
  CheckCircle,
  XCircle,
  Clock,
  Wifi,
  WifiOff,
  RefreshCw,
  AlertTriangle
} from 'lucide-react';

interface APIStatus {
  name: string;
  endpoint: string;
  status: 'online' | 'offline' | 'testing' | 'error';
  lastCheck: Date | null;
  responseTime: number | null;
  errorMessage?: string;
  healthy?: boolean;
}

interface LiveAPIStatusProps {
  onStatusChange?: (isHealthy: boolean) => void;
}

const LiveAPIStatus: React.FC<LiveAPIStatusProps> = ({ onStatusChange }) => {
  const [apis, setAPIs] = useState<APIStatus[]>([
    {
      name: 'Архитектор AI',
      endpoint: 'architect-demo',
      status: 'offline',
      lastCheck: null,
      responseTime: null,
      healthy: false
    },
    {
      name: 'Разработчик AI',
      endpoint: 'developer-demo',
      status: 'offline',
      lastCheck: null,
      responseTime: null,
      healthy: false
    },
    {
      name: 'Тестировщик AI',
      endpoint: 'tester-demo',
      status: 'offline',
      lastCheck: null,
      responseTime: null,
      healthy: false
    },
    {
      name: 'Менеджер проектов AI',
      endpoint: 'pm-demo',
      status: 'offline',
      lastCheck: null,
      responseTime: null,
      healthy: false
    },
    {
      name: 'Бизнес-аналитик AI',
      endpoint: 'ba-demo',
      status: 'offline',
      lastCheck: null,
      responseTime: null
    }
  ]);
  
  const [isChecking, setIsChecking] = useState(false);
  const [overallStatus, setOverallStatus] = useState<'healthy' | 'degraded' | 'down'>('down');

  const checkAPI = async (api: APIStatus) => {
    const startTime = Date.now();
    
    setAPIs(prev => prev.map(a => 
      a.endpoint === api.endpoint 
        ? { ...a, status: 'testing' }
        : a
    ));

    try {
      const { getEdgeFunctionUrl, isSupabaseConfigured, SUPABASE_ANON_KEY } = await import('@/lib/supabase');
      
      // Проверяем конфигурацию Supabase перед вызовом
      if (!isSupabaseConfigured()) {
        throw new Error('Supabase не настроен');
      }
      
      const url = getEdgeFunctionUrl(api.endpoint);
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${SUPABASE_ANON_KEY}`
        },
        body: JSON.stringify({ demoType: 'health-check' })
      });

      const responseTime = Date.now() - startTime;

      if (response.ok) {
        setAPIs(prev => prev.map(a => 
          a.endpoint === api.endpoint 
            ? { 
                ...a, 
                status: 'online' as const, 
                lastCheck: new Date(),
                responseTime
              }
            : a
        ));
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch (error) {
      setAPIs(prev => prev.map(a => 
        a.endpoint === api.endpoint 
          ? { 
              ...a, 
              status: 'error' as const,
              lastCheck: new Date(),
              responseTime: Date.now() - startTime,
              errorMessage: error instanceof Error ? error.message : 'Unknown error'
            }
          : a
      ));
    }
  };

  const checkAllAPIs = async () => {
    setIsChecking(true);
    await Promise.all(apis.map(checkAPI));
    setIsChecking(false);
  };

  useEffect(() => {
    checkAllAPIs();
    
    // Автоматическая проверка каждые 30 секунд
    const interval = setInterval(checkAllAPIs, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const onlineAPIs = apis.filter(api => api.status === 'online').length;
    const totalAPIs = apis.length;
    
    let newStatus: 'healthy' | 'degraded' | 'down';
    if (onlineAPIs === totalAPIs) {
      newStatus = 'healthy';
    } else if (onlineAPIs > 0) {
      newStatus = 'degraded';
    } else {
      newStatus = 'down';
    }
    
    setOverallStatus(newStatus);
    onStatusChange?.(newStatus === 'healthy');
  }, [apis, onStatusChange]);

  const getStatusIcon = (status: APIStatus['status']) => {
    switch (status) {
      case 'online':
        return <CheckCircle className="w-4 h-4 text-green-600" />;
      case 'offline':
        return <XCircle className="w-4 h-4 text-red-600" />;
      case 'testing':
        return <RefreshCw className="w-4 h-4 text-blue-600 animate-spin" />;
      case 'error':
        return <AlertTriangle className="w-4 h-4 text-orange-600" />;
      default:
        return <Clock className="w-4 h-4 text-gray-600" />;
    }
  };

  const getStatusColor = (status: APIStatus['status']) => {
    switch (status) {
      case 'online':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'offline':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'testing':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'error':
        return 'bg-orange-100 text-orange-800 border-orange-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getOverallColor = (status: typeof overallStatus) => {
    switch (status) {
      case 'healthy':
        return 'border-green-500 bg-green-50';
      case 'degraded':
        return 'border-orange-500 bg-orange-50';
      case 'down':
        return 'border-red-500 bg-red-50';
    }
  };

  const onlineAPIs = apis.filter(api => api.status === 'online').length;
  const totalAPIs = apis.length;

  return (
    <Card className={`${getOverallColor(overallStatus)} transition-all duration-300`}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {overallStatus === 'healthy' ? (
              <Wifi className="w-5 h-5 text-green-600" />
            ) : (
              <WifiOff className="w-5 h-5 text-red-600" />
            )}
            <CardTitle className="text-lg">Статус Live API</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={overallStatus === 'healthy' ? 'default' : 'destructive'}>
              {onlineAPIs}/{totalAPIs} онлайн
            </Badge>
            <Button 
              size="sm" 
              variant="outline" 
              onClick={checkAllAPIs}
              disabled={isChecking}
            >
              <RefreshCw className={`w-4 h-4 ${isChecking ? 'animate-spin' : ''}`} />
              Обновить
            </Button>
          </div>
        </div>
        <CardDescription>
          Мониторинг статуса всех AI-ассистентов в реальном времени
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {/* Общий прогресс */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span>Общий статус системы</span>
              <span className="font-medium">
                {overallStatus === 'healthy' ? 'Здоровый' : 
                 overallStatus === 'degraded' ? 'Частично доступен' : 'Недоступен'}
              </span>
            </div>
            <Progress 
              value={(onlineAPIs / totalAPIs) * 100} 
              className="h-2"
            />
          </div>

          {/* Детальный статус каждого API */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {apis.map((api) => (
              <Card key={api.endpoint} className="border">
                <CardContent className="p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 flex-1">
                      {getStatusIcon(api.status)}
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium truncate">
                          {api.name}
                        </div>
                        <div className="text-xs text-slate-600">
                          {api.responseTime ? `${api.responseTime}ms` : '---'}
                        </div>
                      </div>
                    </div>
                    <Badge 
                      variant="outline" 
                      className={`text-xs ${getStatusColor(api.status)}`}
                    >
                      {api.status === 'online' ? 'Онлайн' : 
                       api.status === 'offline' ? 'Оффлайн' :
                       api.status === 'testing' ? 'Проверка' : 'Ошибка'}
                    </Badge>
                  </div>
                  
                  {api.errorMessage && (
                    <div className="mt-2 text-xs text-red-600 bg-red-50 p-2 rounded">
                      {api.errorMessage}
                    </div>
                  )}
                  
                  {api.lastCheck && (
                    <div className="mt-1 text-xs text-slate-500">
                      Последняя проверка: {api.lastCheck.toLocaleTimeString('ru-RU')}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Действия при проблемах */}
          {overallStatus !== 'healthy' && (
            <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
              <div className="flex items-start gap-2">
                <AlertTriangle className="w-5 h-5 text-orange-600 flex-shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <div className="font-medium text-orange-900">
                    Обнаружены проблемы с API
                  </div>
                  <div className="text-sm text-orange-800">
                    Некоторые AI-ассистенты недоступны. Демо будет работать в fallback режиме.
                    Проверьте подключение к Supabase и убедитесь, что Edge Functions развернуты.
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default LiveAPIStatus;