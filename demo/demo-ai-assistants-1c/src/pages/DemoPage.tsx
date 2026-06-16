import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { 
  Brain, 
  Code, 
  TestTube, 
  UserCheck, 
  Users, 
  Target,
  CheckCircle,
  AlertTriangle,
  Clock,
  TrendingUp,
  Zap,
  Shield,
  BookOpen,
  Settings,
  Activity,
  BarChart3
} from 'lucide-react';

// Демо данные для каждой роли
const demoData = {
  architect: {
    title: "Архитектор AI",
    icon: Brain,
    description: "Анализ требований и проектирование архитектуры",
    color: "bg-blue-500",
    examples: [
      "Анализ требований к системе управления складом",
      "Генерация архитектурной диаграммы",
      "Комплексный анализ проекта",
      "Оценка архитектурных рисков"
    ],
    metrics: {
      projects: 47,
      diagrams: 156,
      risks_identified: 23,
      avg_analysis_time: "2.3 сек"
    }
  },
  developer: {
    title: "Разработчик AI", 
    icon: Code,
    description: "Генерация кода и техническая поддержка",
    color: "bg-green-500",
    examples: [
      "Генерация модуля справочника товаров",
      "Оптимизация запросов к БД",
      "Создание обработчика событий",
      "Code review с выявлением проблем"
    ],
    metrics: {
      modules_generated: 89,
      queries_optimized: 134,
      bugs_fixed: 67,
      code_quality: "94%"
    }
  },
  tester: {
    title: "Тестировщик AI",
    icon: TestTube,
    description: "Создание тестов и обеспечение качества", 
    color: "bg-purple-500",
    examples: [
      "Создание тестового сценария приемки",
      "Генерация тестовых данных",
      "Анализ покрытия тестами",
      "Автоматизация тестирования"
    ],
    metrics: {
      test_cases: 234,
      coverage: "87%",
      automation_rate: "78%",
      bugs_found: 156
    }
  },
  pm: {
    title: "Менеджер проектов AI",
    icon: Users,
    description: "Планирование и управление проектами",
    color: "bg-orange-500", 
    examples: [
      "Планирование этапов внедрения 1С",
      "Оценка временных затрат",
      "Управление рисками проекта",
      "Координация команды"
    ],
    metrics: {
      projects: 32,
      on_time: "91%",
      budget_alignment: "88%",
      team_satisfaction: "4.7/5"
    }
  },
  ba: {
    title: "Бизнес-аналитик AI",
    icon: UserCheck,
    description: "Анализ требований и процессов",
    color: "bg-teal-500",
    examples: [
      "Извлечение требований из документов",
      "Моделирование бизнес-процессов",
      "Создание пользовательских историй",
      "Анализ функциональных требований"
    ],
    metrics: {
      requirements: 567,
      stories: 234,
      processes: 89,
      stakeholder_satisfaction: "4.8/5"
    }
  }
};

const DemoPage = () => {
  const [activeRole, setActiveRole] = useState<string>('architect');
  const [demoProgress, setDemoProgress] = useState(0);
  const [liveMetrics, setLiveMetrics] = useState({
    requests: 0,
    avgResponseTime: 0,
    successRate: 0,
    activeUsers: 0
  });

  useEffect(() => {
    // Симуляция live metrics
    const interval = setInterval(() => {
      setLiveMetrics(prev => ({
        requests: prev.requests + Math.floor(Math.random() * 5),
        avgResponseTime: 1.2 + Math.random() * 0.8,
        successRate: 94 + Math.random() * 5,
        activeUsers: 15 + Math.floor(Math.random() * 10)
      }));
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    // Симуляция прогресса демонстрации
    if (demoProgress < 100) {
      const timer = setTimeout(() => {
        setDemoProgress(prev => Math.min(prev + 1, 100));
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [demoProgress]);

  const currentDemo = demoData[activeRole as keyof typeof demoData];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 p-6">
      <div className="max-w-7xl mx-auto space-y-8">
        
        {/* Заголовок */}
        <div className="text-center space-y-4">
          <h1 className="text-4xl font-bold text-slate-800">
            🏗️ Демонстрация AI-экосистемы для 1С
          </h1>
          <p className="text-lg text-slate-600 max-w-3xl mx-auto">
            Комплексная демонстрация системы AI-ассистентов для автоматизации разработки на платформе 1С:Предприятие
          </p>
        </div>

        {/* Live метрики системы */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-blue-600">{liveMetrics.requests}</div>
              <div className="text-sm text-slate-600">Запросов сегодня</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-green-600">{liveMetrics.avgResponseTime.toFixed(1)}с</div>
              <div className="text-sm text-slate-600">Среднее время отклика</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-purple-600">{liveMetrics.successRate.toFixed(1)}%</div>
              <div className="text-sm text-slate-600">Успешность запросов</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-orange-600">{liveMetrics.activeUsers}</div>
              <div className="text-sm text-slate-600">Активные пользователи</div>
            </CardContent>
          </Card>
        </div>

        {/* Выбор роли */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Target className="w-5 h-5" />
              Выберите роль для демонстрации
            </CardTitle>
            <CardDescription>
              Каждый AI-ассистент специализирован на определенных задачах своей роли
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              {Object.entries(demoData).map(([key, role]) => {
                const IconComponent = role.icon;
                return (
                  <Button
                    key={key}
                    variant={activeRole === key ? "default" : "outline"}
                    className={`h-auto p-4 flex flex-col items-center gap-2 ${
                      activeRole === key ? role.color + " text-white" : ""
                    }`}
                    onClick={() => setActiveRole(key)}
                  >
                    <IconComponent className="w-6 h-6" />
                    <span className="text-sm font-medium">{role.title}</span>
                  </Button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Демонстрация активной роли */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <currentDemo.icon className="w-6 h-6" />
              {currentDemo.title}
            </CardTitle>
            <CardDescription>{currentDemo.description}</CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="examples" className="space-y-4">
              <TabsList>
                <TabsTrigger value="examples">Примеры использования</TabsTrigger>
                <TabsTrigger value="metrics">Метрики эффективности</TabsTrigger>
                <TabsTrigger value="workflow">Демо workflow</TabsTrigger>
                <TabsTrigger value="api">API демонстрация</TabsTrigger>
              </TabsList>

              <TabsContent value="examples" className="space-y-4">
                <div className="grid gap-4">
                  {currentDemo.examples.map((example, index) => (
                    <Card key={index} className="border-l-4 border-l-blue-500">
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <CheckCircle className="w-5 h-5 text-green-500" />
                            <span className="font-medium">{example}</span>
                          </div>
                          <Badge variant="secondary">Demo</Badge>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="metrics" className="space-y-4">
                <div className="grid md:grid-cols-2 gap-6">
                  {Object.entries(currentDemo.metrics).map(([key, value]) => (
                    <Card key={key}>
                      <CardContent className="p-6">
                        <div className="space-y-2">
                          <div className="text-2xl font-bold text-slate-800">{value}</div>
                          <div className="text-sm text-slate-600 capitalize">
                            {key.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                          </div>
                          <Progress value={Math.random() * 100} className="h-2" />
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="workflow" className="space-y-4">
                <div className="space-y-4">
                  <div className="text-sm text-slate-600 mb-4">
                    Прогресс демонстрации workflow:
                  </div>
                  <Progress value={demoProgress} className="h-3" />
                  
                  <div className="grid gap-3">
                    {[
                      { step: "Получение запроса от пользователя", status: "completed" },
                      { step: "Анализ контекста и требований", status: "completed" },
                      { step: "Обработка через AI модель", status: demoProgress > 50 ? "completed" : "active" },
                      { step: "Генерация результата", status: demoProgress > 80 ? "completed" : "pending" },
                      { step: "Валидация и отправка ответа", status: demoProgress > 95 ? "completed" : "pending" }
                    ].map((item, index) => (
                      <div key={index} className="flex items-center gap-3 p-3 rounded-lg bg-white border">
                        {item.status === "completed" && <CheckCircle className="w-5 h-5 text-green-500" />}
                        {item.status === "active" && <Clock className="w-5 h-5 text-blue-500 animate-pulse" />}
                        {item.status === "pending" && <Clock className="w-5 h-5 text-slate-400" />}
                        <span className={item.status === "pending" ? "text-slate-500" : ""}>
                          {item.step}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="api" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">API Endpoints</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div className="font-mono text-sm bg-slate-100 p-3 rounded">
                        <div className="text-green-600">POST</div>
                        <div>/api/assistants/{activeRole}/analyze-requirements</div>
                      </div>
                      <div className="font-mono text-sm bg-slate-100 p-3 rounded">
                        <div className="text-green-600">POST</div>
                        <div>/api/assistants/{activeRole}/generate-solution</div>
                      </div>
                      <div className="font-mono text-sm bg-slate-100 p-3 rounded">
                        <div className="text-blue-600">GET</div>
                        <div>/api/assistants/{activeRole}/stats</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        {/* Системная интеграция */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="w-5 h-5" />
              Интеграция с экосистемой
            </CardTitle>
            <CardDescription>
              Демонстрация взаимодействия между всеми компонентами системы
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid md:grid-cols-3 gap-6">
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Shield className="w-4 h-4" />
                    Risk Management
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <Badge variant="outline">Выявлено рисков: 23</Badge>
                    <Badge variant="outline">Критических: 3</Badge>
                    <Badge variant="outline">Митигировано: 20</Badge>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <TrendingUp className="w-4 h-4" />
                    ML System
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <Badge variant="outline">Активных моделей: 7</Badge>
                    <Badge variant="outline">Точность: 94.2%</Badge>
                    <Badge variant="outline">A/B тестов: 3</Badge>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <BarChart3 className="w-4 h-4" />
                    Analytics
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <Badge variant="outline">Запросов/день: 1,234</Badge>
                    <Badge variant="outline">Покрытие: 87%</Badge>
                    <Badge variant="outline">SLA: 99.8%</Badge>
                  </div>
                </CardContent>
              </Card>
            </div>
          </CardContent>
        </Card>

        {/* Production Ready */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-green-500" />
              Production Readiness Checklist
            </CardTitle>
            <CardDescription>
              Статус готовности системы к промышленному развертыванию
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid md:grid-cols-2 gap-6">
              <div className="space-y-3">
                {[
                  "✅ Все тесты пройдены (14/14)",
                  "✅ Docker контейнеризация",
                  "✅ Мониторинг настроен",
                  "✅ Безопасность реализована",
                  "✅ Масштабирование поддерживается",
                  "✅ API документация готова"
                ].map((item, index) => (
                  <div key={index} className="flex items-center gap-2 text-sm">
                    {item.includes("✅") ? (
                      <CheckCircle className="w-4 h-4 text-green-500" />
                    ) : (
                      <AlertTriangle className="w-4 h-4 text-yellow-500" />
                    )}
                    <span>{item.replace("✅", "").trim()}</span>
                  </div>
                ))}
              </div>
              <div className="space-y-3">
                {[
                  "✅ CI/CD настроен",
                  "✅ Backup стратегия",
                  "✅ Логирование реализовано", 
                  "✅ Rate limiting настроен",
                  "✅ Health checks работают",
                  "✅ Документация полная"
                ].map((item, index) => (
                  <div key={index} className="flex items-center gap-2 text-sm">
                    <CheckCircle className="w-4 h-4 text-green-500" />
                    <span>{item.replace("✅", "").trim()}</span>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Демо завершение */}
        <Card className="border-green-200 bg-green-50">
          <CardContent className="p-6 text-center">
            <Activity className="w-12 h-12 text-green-500 mx-auto mb-4" />
            <h3 className="text-xl font-bold text-green-800 mb-2">
              🎉 Демонстрация завершена успешно!
            </h3>
            <p className="text-green-700 mb-4">
              Система AI-ассистентов готова к промышленному использованию
            </p>
            <div className="flex justify-center gap-4">
              <Button variant="outline" size="sm">
                <BookOpen className="w-4 h-4 mr-2" />
                Документация
              </Button>
              <Button variant="outline" size="sm">
                <Settings className="w-4 h-4 mr-2" />
                Настройки
              </Button>
              <Button size="sm">
                <Zap className="w-4 h-4 mr-2" />
                Запустить в Production
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default DemoPage;