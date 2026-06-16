import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { LiveAPIStatus, LiveDemoButton, CustomQuerySection } from '@/components/demo';
import {
  Brain,
  Code,
  TestTube,
  Users,
  FileText,
  Play,
  Sparkles,
  Zap,
  ImageIcon,
  Search,
  Globe,
  MapPin,
  TrendingUp,
  CheckCircle,
  Clock,
  Activity,
  Wifi
} from 'lucide-react';

interface Role {
  id: string;
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
  color: string;
  demos: Demo[];
}

interface Demo {
  id: string;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  demoType: string;
}

const LiveDemoPage = () => {
  const [activeRole, setActiveRole] = useState<string>('architect');
  const [isHealthy, setIsHealthy] = useState(false);
interface DemoResult {
  message?: string;
  diagram?: string;
  code?: string;
  components?: Record<string, any>;
  totalRisks?: number;
  criticalCount?: number;
  highCount?: number;
  mediumCount?: number;
  [key: string]: any;
}

  const [demoResults, setDemoResults] = useState<Record<string, DemoResult>>({});

  // Получить placeholder для пользовательского запроса в зависимости от роли
  const getPlaceholderForRole = (roleId: string): string => {
    const placeholders: Record<string, string> = {
      architect: 'Опишите архитектуру для системы управления складом с интеграцией с внешними API...',
      developer: 'Напишите функцию для расчета остатков товаров на складе с учетом резервов...',
      tester: 'Создайте тест-кейсы для проверки функции загрузки товаров из Excel файла...',
      pm: 'Составьте план проекта по внедрению системы управления складом на 3 месяца...',
      ba: 'Проанализируйте требования для автоматизации процесса инвентаризации склада...'
    };
    return placeholders[roleId] || 'Опишите вашу задачу или вопрос...';
  };

  const roles: Role[] = [
    {
      id: 'architect',
      title: 'Архитектор AI',
      icon: Brain,
      description: 'Проектирование архитектуры, создание схем, анализ требований',
      color: 'bg-blue-500',
      demos: [
        {
          id: 'arch-design',
          title: 'Проектирование архитектуры складской системы',
          description: 'Анализ требований и создание архитектурной схемы',
          icon: Brain,
          demoType: 'design'
        },
        {
          id: 'arch-diagram',
          title: 'Генерация архитектурных диаграмм',
          description: 'Автоматическое создание визуальных схем системы',
          icon: ImageIcon,
          demoType: 'diagram'
        },
        {
          id: 'arch-analysis',
          title: 'Анализ архитектурных рисков',
          description: 'Выявление потенциальных проблем и узких мест',
          icon: Search,
          demoType: 'analysis'
        }
      ]
    },
    {
      id: 'developer',
      title: 'Разработчик AI',
      icon: Code,
      description: 'Генерация кода 1С, оптимизация, интеграции',
      color: 'bg-green-500',
      demos: [
        {
          id: 'dev-generate',
          title: 'Генерация модуля справочника товаров',
          description: 'Автоматическое создание кода 1С с best practices',
          icon: Code,
          demoType: 'generate'
        },
        {
          id: 'dev-optimize',
          title: 'Оптимизация SQL запросов',
          description: 'Анализ и улучшение производительности запросов',
          icon: Zap,
          demoType: 'optimize'
        },
        {
          id: 'dev-api',
          title: 'Создание API интеграции',
          description: 'Генерация кода для работы с внешними API',
          icon: Globe,
          demoType: 'api'
        }
      ]
    },
    {
      id: 'tester',
      title: 'Тестировщик AI',
      icon: TestTube,
      description: 'Создание тестов, анализ покрытия, автоматизация',
      color: 'bg-purple-500',
      demos: [
        {
          id: 'test-generate',
          title: 'Генерация тест-кейсов',
          description: 'Автоматическое создание сценариев тестирования',
          icon: TestTube,
          demoType: 'generate'
        },
        {
          id: 'test-data',
          title: 'Создание тестовых данных',
          description: 'Генерация реалистичных тестовых наборов',
          icon: Sparkles,
          demoType: 'data'
        },
        {
          id: 'test-coverage',
          title: 'Анализ покрытия тестами',
          description: 'Оценка качества тестирования и поиск пробелов',
          icon: TrendingUp,
          demoType: 'coverage'
        }
      ]
    },
    {
      id: 'pm',
      title: 'Менеджер проектов AI',
      icon: Users,
      description: 'Планирование, управление рисками, координация',
      color: 'bg-orange-500',
      demos: [
        {
          id: 'pm-plan',
          title: 'Планирование проекта внедрения 1С',
          description: 'Создание детального плана с оценками и этапами',
          icon: FileText,
          demoType: 'plan'
        },
        {
          id: 'pm-risks',
          title: 'Анализ рисков проекта',
          description: 'Выявление и оценка потенциальных рисков',
          icon: Search,
          demoType: 'risks'
        },
        {
          id: 'pm-resources',
          title: 'Распределение ресурсов',
          description: 'Оптимальное распределение команды по задачам',
          icon: Users,
          demoType: 'resources'
        }
      ]
    },
    {
      id: 'ba',
      title: 'Бизнес-аналитик AI',
      icon: FileText,
      description: 'Анализ требований, моделирование процессов',
      color: 'bg-teal-500',
      demos: [
        {
          id: 'ba-requirements',
          title: 'Извлечение требований из документов',
          description: 'Автоматический анализ бизнес-документации',
          icon: FileText,
          demoType: 'requirements'
        },
        {
          id: 'ba-process',
          title: 'Моделирование бизнес-процессов',
          description: 'Создание визуальных схем процессов',
          icon: MapPin,
          demoType: 'process'
        },
        {
          id: 'ba-stories',
          title: 'Генерация пользовательских историй',
          description: 'Создание User Stories из требований',
          icon: Sparkles,
          demoType: 'stories'
        }
      ]
    }
  ];

  const getCurrentRole = () => roles.find(r => r.id === activeRole) || roles[0];

  const handleDemoComplete = (demoId: string, result: DemoResult) => {
    setDemoResults(prev => ({
      ...prev,
      [demoId]: result
    }));
  };



  const currentRole = getCurrentRole();
  const RoleIcon = currentRole.icon;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 p-6">
      <div className="max-w-7xl mx-auto space-y-8">
        
        {/* Заголовок */}
        <div className="text-center space-y-4">
          <div className="flex items-center justify-center gap-3">
            <Wifi className="w-10 h-10 text-blue-600 animate-pulse" />
            <h1 className="text-4xl font-bold text-slate-800">
              Live API Демонстрация AI-экосистемы для 1С
            </h1>
          </div>
          <p className="text-lg text-slate-600 max-w-3xl mx-auto">
            Реальная генерация контента через Live API с возможностью скачивания результатов
          </p>
          <div className="flex justify-center gap-2">
            <Badge variant={isHealthy ? 'default' : 'destructive'} className="text-sm">
              {isHealthy ? '✅ Live API активен' : '⚠️ Fallback режим'}
            </Badge>
            <Badge variant="outline" className="text-sm">
              🎯 Реальные результаты
            </Badge>
          </div>
        </div>

        {/* Мониторинг статуса API */}
        <LiveAPIStatus onStatusChange={setIsHealthy} />

        {/* Выбор роли */}
        <Card>
          <CardHeader>
            <CardTitle>Выберите роль для демонстрации</CardTitle>
            <CardDescription>
              Каждый AI-ассистент специализирован на задачах своей роли
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
              {roles.map((role) => {
                const Icon = role.icon;
                return (
                  <Button
                    key={role.id}
                    variant={activeRole === role.id ? "default" : "outline"}
                    className={`h-auto p-4 flex flex-col items-center gap-2 whitespace-normal min-h-[100px] ${
                      activeRole === role.id ? role.color + " text-white hover:opacity-90" : ""
                    }`}
                    onClick={() => setActiveRole(role.id)}
                  >
                    <Icon className="w-6 h-6 flex-shrink-0" />
                    <span className="text-xs sm:text-sm font-medium text-center leading-tight">{role.title}</span>
                  </Button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Live демонстрации */}
        <div className="grid md:grid-cols-2 gap-6">
          {/* Левая панель - Выбор демо */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <RoleIcon className="w-6 h-6" />
                {currentRole.title}
              </CardTitle>
              <CardDescription>{currentRole.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {currentRole.demos.map((demo) => (
                  <LiveDemoButton
                    key={demo.id}
                    role={activeRole}
                    demoType={demo.demoType}
                    title={demo.title}
                    description={demo.description}
                    icon={demo.icon}
                    disabled={!isHealthy && !demoResults[demo.id]}
                    onDemoComplete={(result) => handleDemoComplete(demo.id, result)}
                  />
                ))}
                
                {/* Разделитель */}
                <div className="relative py-4">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-slate-200"></div>
                  </div>
                  <div className="relative flex justify-center text-xs uppercase">
                    <span className="bg-white px-2 text-slate-500">Или</span>
                  </div>
                </div>
                
                {/* Секция пользовательского запроса */}
                <CustomQuerySection
                  role={activeRole}
                  roleTitle={currentRole.title}
                  placeholder={getPlaceholderForRole(activeRole)}
                  onQueryComplete={(result) => handleDemoComplete(`custom-${Date.now()}`, result)}
                />
              </div>
            </CardContent>
          </Card>

          {/* Правая панель - Обзор результатов */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="w-6 h-6" />
                Результаты выполнения
              </CardTitle>
              <CardDescription>
                История выполненных демонстраций и скачивание файлов
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {/* Статистика */}
                <div className="grid grid-cols-3 gap-2">
                  <Card>
                    <CardContent className="p-3 text-center">
                      <div className="text-lg font-bold text-green-600">
                        {Object.keys(demoResults).length}
                      </div>
                      <div className="text-xs text-slate-600">Выполнено</div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="p-3 text-center">
                      <div className="text-lg font-bold text-blue-600">
                        {isHealthy ? 'Live' : 'Local'}
                      </div>
                      <div className="text-xs text-slate-600">Режим</div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="p-3 text-center">
                      <div className="text-lg font-bold text-purple-600">
                        {currentRole.demos.length}
                      </div>
                      <div className="text-xs text-slate-600">Всего демо</div>
                    </CardContent>
                  </Card>
                </div>

                {/* Список результатов */}
                <ScrollArea className="h-[400px]">
                  <div className="space-y-2">
                    {Object.keys(demoResults).length === 0 ? (
                      <div className="text-center py-8 text-slate-500">
                        <FileText className="w-12 h-12 mx-auto mb-2 opacity-50" />
                        <p>Запустите демонстрацию или введите запрос для просмотра результатов</p>
                      </div>
                    ) : (
                      Object.entries(demoResults).map(([demoId, result]) => {
                        // Проверяем, является ли это пользовательским запросом
                        const isCustomQuery = demoId.startsWith('custom-');
                        let title, description;
                        
                        if (isCustomQuery) {
                          title = 'Пользовательский запрос';
                          description = 'Ваш индивидуальный запрос к AI';
                        } else {
                          const demo = currentRole.demos.find(d => d.id === demoId);
                          if (!demo) return null;
                          title = demo.title;
                          description = demo.description;
                        }
                        
                        return (
                          <Card key={demoId} className="border-l-4 border-l-green-500">
                            <CardContent className="p-3">
                              <div className="flex items-start justify-between gap-2">
                                <div className="flex items-start gap-2 flex-1">
                                  <CheckCircle className="w-4 h-4 text-green-600 mt-0.5 flex-shrink-0" />
                                  <div className="space-y-1 flex-1 min-w-0">
                                    <div className="text-sm font-medium truncate">
                                      {title}
                                    </div>
                                    <div className="text-xs text-slate-600">
                                      {description}
                                    </div>
                                    {result?.message && (
                                      <div className="text-xs text-green-700 bg-green-50 px-2 py-1 rounded">
                                        {result.message}
                                      </div>
                                    )}
                                  </div>
                                </div>
                                <Badge variant="outline" className="text-xs bg-green-50">
                                  Готово
                                </Badge>
                              </div>
                            </CardContent>
                          </Card>
                        );
                      })
                    )}
                  </div>
                </ScrollArea>

                {/* Инструкции */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-start gap-2">
                    <Activity className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                    <div className="space-y-1">
                      <div className="font-medium text-blue-900">
                        Как использовать Live Demo
                      </div>
                      <div className="text-sm text-blue-800 space-y-1">
                        <div>1. Нажмите "Live Demo" для запуска</div>
                        <div>2. Дождитесь завершения генерации</div>
                        <div>3. Нажмите "Скачать" для получения результата</div>
                        <div>4. Файлы содержат реальные данные или код</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Информация о системе */}
        <Card className={`${isHealthy ? 'border-green-200 bg-green-50' : 'border-orange-200 bg-orange-50'}`}>
          <CardContent className="p-6">
            <div className="flex items-start gap-4">
              <CheckCircle className={`w-8 h-8 ${isHealthy ? 'text-green-600' : 'text-orange-600'} flex-shrink-0`} />
              <div className="space-y-2">
                <h3 className={`font-bold ${isHealthy ? 'text-green-900' : 'text-orange-900'}`}>
                  {isHealthy 
                    ? 'Live API система работает в полном режиме'
                    : 'Система работает в fallback режиме'
                  }
                </h3>
                <p className={`text-sm ${isHealthy ? 'text-green-800' : 'text-orange-800'}`}>
                  {isHealthy 
                    ? 'AI-ассистенты генерируют реальный контент через Live API. Все результаты доступны для скачивания в различных форматах.'
                    : 'Live API недоступен. Демонстрации работают в fallback режиме. Для полной функциональности проверьте подключение к Supabase.'
                  }
                </p>
                <div className="flex gap-2 flex-wrap">
                  <Badge variant="outline" className="bg-white">
                    {isHealthy ? '✅ Live API' : '⚠️ Fallback'}
                  </Badge>
                  <Badge variant="outline" className="bg-white">
                    5 AI-ассистентов
                  </Badge>
                  <Badge variant="outline" className="bg-white">
                    15 демо-сценариев
                  </Badge>
                  <Badge variant="outline" className="bg-white">
                    {isHealthy ? '🎯 Реальные результаты' : '📝 Симуляция'}
                  </Badge>
                  <Badge variant="outline" className="bg-white">
                    💾 Скачивание файлов
                  </Badge>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default LiveDemoPage;
