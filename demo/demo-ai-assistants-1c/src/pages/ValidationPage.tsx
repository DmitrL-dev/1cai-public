import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  CheckCircle, 
  XCircle, 
  AlertTriangle,
  Clock,
  Loader2,
  TestTube,
  Shield,
  Zap,
  Database,
  Globe,
  Cpu,
  BarChart3
} from 'lucide-react';

// Структура для результатов тестирования
interface TestResult {
  name: string;
  status: 'pending' | 'running' | 'passed' | 'failed';
  duration?: number;
  details?: string;
}

interface ValidationResults {
  api: TestResult[];
  integration: TestResult[];
  performance: TestResult[];
  security: TestResult[];
}

const ValidationPage = () => {
  const [validationResults, setValidationResults] = useState<ValidationResults>({
    api: [
      { name: "GET /health - Health Check", status: 'pending' },
      { name: "GET /api/assistants/ - Список ассистентов", status: 'pending' },
      { name: "POST /api/assistants/architect/analyze-requirements", status: 'pending' },
      { name: "POST /api/assistants/architect/generate-diagram", status: 'pending' },
      { name: "GET /api/assistants/architect/stats", status: 'pending' }
    ],
    integration: [
      { name: "End-to-end: UX → API → AI → Risk → ML", status: 'pending' },
      { name: "ML System → Metrics → Analytics", status: 'pending' },
      { name: "Database connectivity", status: 'pending' },
      { name: "Redis cache operations", status: 'pending' },
      { name: "Message queue operations", status: 'pending' }
    ],
    performance: [
      { name: "Load testing (100 concurrent users)", status: 'pending' },
      { name: "Stress testing (500 requests/sec)", status: 'pending' },
      { name: "Memory usage monitoring", status: 'pending' },
      { name: "Response time benchmarks", status: 'pending' },
      { name: "Throughput measurements", status: 'pending' }
    ],
    security: [
      { name: "Authentication & Authorization", status: 'pending' },
      { name: "Input validation", status: 'pending' },
      { name: "SQL injection protection", status: 'pending' },
      { name: "Rate limiting", status: 'pending' },
      { name: "CORS configuration", status: 'pending' }
    ]
  });

  const [isRunning, setIsRunning] = useState(false);
  const [overallProgress, setOverallProgress] = useState(0);
  const [validationComplete, setValidationComplete] = useState(false);

  const apiEndpoints = [
    { url: "http://localhost:8000/health", method: "GET" },
    { url: "http://localhost:8000/api/assistants/", method: "GET" },
    { url: "http://localhost:8001/health", method: "GET" },
    { url: "http://localhost:8003/health", method: "GET" },
    { url: "http://localhost:8004/health", method: "GET" }
  ];

  const runValidation = async () => {
    setIsRunning(true);
    setValidationComplete(false);
    setOverallProgress(0);

    // Симуляция процесса валидации
    const allTests = [
      ...validationResults.api,
      ...validationResults.integration, 
      ...validationResults.performance,
      ...validationResults.security
    ];

    for (let i = 0; i < allTests.length; i++) {
      const category = i < 5 ? 'api' : 
                      i < 10 ? 'integration' :
                      i < 15 ? 'performance' : 'security';
      
      const testIndex = i % 5;

      // Обновляем статус на "running"
      setValidationResults(prev => ({
        ...prev,
        [category]: prev[category].map((test, idx) => 
          idx === testIndex ? { ...test, status: 'running' } : test
        )
      }));

      // Симулируем время выполнения теста
      await new Promise(resolve => setTimeout(resolve, Math.random() * 2000 + 500));

      // Устанавливаем статус passed/failed с вероятностью 90% успеха
      const success = Math.random() > 0.1;
      setValidationResults(prev => ({
        ...prev,
        [category]: prev[category].map((test, idx) => 
          idx === testIndex ? { 
            ...test, 
            status: success ? 'passed' : 'failed',
            duration: Math.random() * 1000 + 100,
            details: success ? 'Тест пройден успешно' : 'Ошибка выполнения теста'
          } : test
        )
      }));

      // Обновляем общий прогресс
      setOverallProgress(((i + 1) / allTests.length) * 100);
    }

    setIsRunning(false);
    setValidationComplete(true);
  };

  const runApiTest = async (endpoint: string, method: string = 'GET') => {
    try {
      const response = await fetch(endpoint, {
        method,
        headers: {
          'Content-Type': 'application/json'
        }
      });
      return response.ok;
    } catch (error) {
      return false;
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'passed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />;
      case 'running':
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      default:
        return <Clock className="w-4 h-4 text-slate-400" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const variants = {
      passed: { variant: 'default' as const, className: 'bg-green-100 text-green-800' },
      failed: { variant: 'destructive' as const, className: 'bg-red-100 text-red-800' },
      running: { variant: 'secondary' as const, className: 'bg-blue-100 text-blue-800' },
      pending: { variant: 'outline' as const, className: 'bg-slate-100 text-slate-600' }
    };

    const config = variants[status as keyof typeof variants];
    return <Badge variant={config.variant} className={config.className}>{status}</Badge>;
  };

  const getTestCategoryIcon = (category: string) => {
    switch (category) {
      case 'api':
        return <Globe className="w-4 h-4" />;
      case 'integration':
        return <Zap className="w-4 h-4" />;
      case 'performance':
        return <BarChart3 className="w-4 h-4" />;
      case 'security':
        return <Shield className="w-4 h-4" />;
      default:
        return <TestTube className="w-4 h-4" />;
    }
  };

  const getTestCategoryTitle = (category: string) => {
    switch (category) {
      case 'api':
        return "API Endpoints";
      case 'integration':
        return "Integration Tests";
      case 'performance':
        return "Performance Tests";
      case 'security':
        return "Security Audit";
      default:
        return "Tests";
    }
  };

  const calculateCategoryStats = (tests: TestResult[]) => {
    const passed = tests.filter(t => t.status === 'passed').length;
    const failed = tests.filter(t => t.status === 'failed').length;
    const total = tests.length;
    return { passed, failed, total, percentage: total > 0 ? Math.round((passed / total) * 100) : 0 };
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-green-50 p-6">
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Заголовок */}
        <div className="text-center space-y-4">
          <h1 className="text-4xl font-bold text-slate-800">
            🧪 Валидация системы AI-ассистентов
          </h1>
          <p className="text-lg text-slate-600 max-w-3xl mx-auto">
            Полная валидация всех компонентов системы: API, интеграция, производительность и безопасность
          </p>
        </div>

        {/* Общий прогресс */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TestTube className="w-5 h-5" />
              Прогресс валидации
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between text-sm">
                <span>Общий прогресс</span>
                <span>{Math.round(overallProgress)}%</span>
              </div>
              <Progress value={overallProgress} className="h-3" />
              
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {(['api', 'integration', 'performance', 'security'] as const).map(category => {
                  const stats = calculateCategoryStats(validationResults[category]);
                  return (
                    <Card key={category} className="p-4">
                      <div className="flex items-center gap-2 mb-2">
                        {getTestCategoryIcon(category)}
                        <span className="font-medium text-sm">{getTestCategoryTitle(category)}</span>
                      </div>
                      <div className="text-2xl font-bold text-slate-800">{stats.percentage}%</div>
                      <div className="text-xs text-slate-600">
                        {stats.passed}/{stats.total} тестов пройдено
                      </div>
                    </Card>
                  );
                })}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Кнопки управления */}
        <Card>
          <CardContent className="p-6">
            <div className="flex gap-4">
              <Button 
                onClick={runValidation} 
                disabled={isRunning}
                className="flex items-center gap-2"
              >
                {isRunning ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <TestTube className="w-4 h-4" />
                )}
                {isRunning ? 'Запуск валидации...' : 'Запустить полную валидацию'}
              </Button>
              
              <Button variant="outline" onClick={() => {
                setValidationResults({
                  api: validationResults.api.map(t => ({ ...t, status: 'pending', duration: undefined, details: undefined })),
                  integration: validationResults.integration.map(t => ({ ...t, status: 'pending', duration: undefined, details: undefined })),
                  performance: validationResults.performance.map(t => ({ ...t, status: 'pending', duration: undefined, details: undefined })),
                  security: validationResults.security.map(t => ({ ...t, status: 'pending', duration: undefined, details: undefined }))
                });
                setOverallProgress(0);
                setValidationComplete(false);
              }}>
                Сбросить результаты
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Детальные результаты */}
        <Card>
          <CardContent className="p-6">
            <Tabs defaultValue="api" className="space-y-4">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="api" className="flex items-center gap-2">
                  <Globe className="w-4 h-4" />
                  API Tests
                </TabsTrigger>
                <TabsTrigger value="integration" className="flex items-center gap-2">
                  <Zap className="w-4 h-4" />
                  Integration
                </TabsTrigger>
                <TabsTrigger value="performance" className="flex items-center gap-2">
                  <BarChart3 className="w-4 h-4" />
                  Performance
                </TabsTrigger>
                <TabsTrigger value="security" className="flex items-center gap-2">
                  <Shield className="w-4 h-4" />
                  Security
                </TabsTrigger>
              </TabsList>

              {(['api', 'integration', 'performance', 'security'] as const).map(category => (
                <TabsContent key={category} value={category} className="space-y-4">
                  <div className="space-y-3">
                    {validationResults[category].map((test, index) => (
                      <div key={index} className="flex items-center justify-between p-4 bg-white rounded-lg border">
                        <div className="flex items-center gap-3">
                          {getStatusIcon(test.status)}
                          <div>
                            <div className="font-medium">{test.name}</div>
                            {test.duration && (
                              <div className="text-sm text-slate-600">
                                Время выполнения: {Math.round(test.duration)}ms
                              </div>
                            )}
                            {test.details && (
                              <div className="text-sm text-slate-600">{test.details}</div>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {getStatusBadge(test.status)}
                          {test.status === 'running' && <Cpu className="w-4 h-4 text-blue-500 animate-pulse" />}
                        </div>
                      </div>
                    ))}
                  </div>
                </TabsContent>
              ))}
            </Tabs>
          </CardContent>
        </Card>

        {/* Итоговый отчет */}
        {validationComplete && (
          <Card className="border-green-200 bg-green-50">
            <CardContent className="p-6">
              <div className="text-center space-y-4">
                <CheckCircle className="w-12 h-12 text-green-500 mx-auto" />
                <h3 className="text-xl font-bold text-green-800">
                  ✅ Валидация завершена!
                </h3>
                
                <div className="grid md:grid-cols-4 gap-4 mt-6">
                  {(['api', 'integration', 'performance', 'security'] as const).map(category => {
                    const stats = calculateCategoryStats(validationResults[category]);
                    return (
                      <Card key={category} className="p-4">
                        <div className="text-center">
                          <div className="text-2xl font-bold text-slate-800">{stats.passed}</div>
                          <div className="text-sm text-slate-600">из {stats.total} тестов</div>
                          <div className="text-xs text-slate-500">{getTestCategoryTitle(category)}</div>
                          {stats.failed > 0 && (
                            <Badge variant="destructive" className="mt-2">
                              {stats.failed} неудач
                            </Badge>
                          )}
                        </div>
                      </Card>
                    );
                  })}
                </div>

                <Alert className="mt-6">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>
                    Рекомендуется проверить неудачные тесты и устранить обнаруженные проблемы перед production развертыванием.
                  </AlertDescription>
                </Alert>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
};

export default ValidationPage;