import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Download,
  Play,
  CheckCircle,
  Clock,
  Loader2,
  FileText,
  Code,
  Image as ImageIcon,
  Zap
} from 'lucide-react';
import { supabaseClient, getEdgeFunctionUrl, SUPABASE_ANON_KEY } from '@/lib/supabase';

interface DemoResult {
  message?: string;
  diagram?: string;
  code?: string;
  components?: Record<string, any>;
  [key: string]: any;
}

interface DemoStep {
  progress: number;
  message: string;
  result?: DemoResult;
}

interface StepResult {
  progress: number;
  message: string;
}

interface DemoData {
  steps: StepResult[];
  finalResult: DemoResult;
}

interface LiveDemoButtonProps {
  role: string;
  demoType: string;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  onDemoStart?: () => void;
  onDemoComplete?: (result: DemoResult) => void;
  disabled?: boolean;
}

interface DemoResultData {
  steps: StepResult[];
  finalResult: DemoResult;
}

const LiveDemoButton: React.FC<LiveDemoButtonProps> = ({
  role,
  demoType,
  title,
  description,
  icon: Icon,
  onDemoStart,
  onDemoComplete,
  disabled = false
}) => {
  const [isRunning, setIsRunning] = useState(false);
  const [currentStep, setCurrentStep] = useState<StepResult | null>(null);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<DemoResultData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runLiveDemo = async () => {
    if (isRunning) return;

    setIsRunning(true);
    setError(null);
    setResult(null);
    setCurrentStep(null);
    setProgress(0);
    onDemoStart?.();

    try {
      const functionUrl = getEdgeFunctionUrl(`${role}-demo`);
      
      // Запускаем демо
      const response = await fetch(functionUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${SUPABASE_ANON_KEY}`
        },
        body: JSON.stringify({ demoType })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      const demoData = data.data || data;

      // Имитируем пошаговое выполнение
      for (let i = 0; i < demoData.steps.length; i++) {
        const step = demoData.steps[i];
        setCurrentStep(step);
        setProgress(step.progress);
        
        // Небольшая задержка для плавности анимации
        await new Promise(resolve => setTimeout(resolve, 200));
      }

      setResult(demoData);
      onDemoComplete?.(demoData.finalResult);

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Неизвестная ошибка';
      setError(errorMessage);
      
      // Fallback к локальной симуляции
      await runFallbackDemo();
    } finally {
      setIsRunning(false);
      setCurrentStep(null);
    }
  };

  const runFallbackDemo = async () => {
    // Fallback симуляция если API недоступен
    const fallbackSteps: StepResult[] = [
      { progress: 20, message: 'Анализ требований...' },
      { progress: 50, message: 'Обработка данных...' },
      { progress: 80, message: 'Формирование результата...' },
      { progress: 100, message: 'Результат готов!' }
    ];

    for (const step of fallbackSteps) {
      setCurrentStep(step);
      setProgress(step.progress);
      await new Promise(resolve => setTimeout(resolve, 800));
    }

    // Создаем fallback результат
    const fallbackResult: DemoResultData = {
      steps: fallbackSteps,
      finalResult: {
        message: 'Демо выполнено в fallback режиме',
        note: 'Реальные результаты недоступны - проверьте подключение к API'
      }
    };

    setResult(fallbackResult);
    onDemoComplete?.(fallbackResult.finalResult);
  };

  const downloadResult = () => {
    if (!result) return;

    let content = '';
    let filename = `${role}-${demoType}-demo`;
    let mimeType = 'text/plain';

    // Форматируем результат в зависимости от типа
    if (result.finalResult?.diagram) {
      // Если есть диаграмма
      content = `# ${title}\n\n## Диаграмма\n\n\`\`\`mermaid\n${result.finalResult.diagram}\n\`\`\`\n\n## Метаданные\n\n- Роль: ${role}\n- Тип демо: ${demoType}\n- Время: ${new Date().toLocaleString('ru-RU')}\n`;
      filename += '.md';
    } else if (result.finalResult?.code) {
      // Если есть код
      content = `// ${title}\n// Сгенерировано: ${new Date().toLocaleString('ru-RU')}\n\n${result.finalResult.code}`;
      filename += '.1s';
    } else if (typeof result.finalResult === 'object') {
      // Объект данных
      content = JSON.stringify({
        title,
        role,
        demoType,
        timestamp: new Date().toISOString(),
        result: result.finalResult,
        steps: result.steps
      }, null, 2);
      filename += '.json';
    } else {
      // Текстовый результат
      content = `${title}\n\n${result.steps.map(step => step.message).join('\n')}\n\nВремя: ${new Date().toLocaleString('ru-RU')}`;
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const getResultIcon = () => {
    if (!result) return null;
    
    if (result.finalResult?.diagram) {
      return <ImageIcon className="w-4 h-4" />;
    } else if (result.finalResult?.code) {
      return <Code className="w-4 h-4" />;
    } else if (typeof result.finalResult === 'object') {
      return <FileText className="w-4 h-4" />;
    }
    return <FileText className="w-4 h-4" />;
  };

  const getResultType = () => {
    if (!result) return null;
    
    if (result.finalResult?.diagram) return 'Диаграмма';
    if (result.finalResult?.code) return 'Код';
    if (typeof result.finalResult === 'object') return 'Данные';
    return 'Результат';
  };

  return (
    <div className="space-y-3">
      {/* Кнопка запуска */}
      <Card className={`transition-all ${isRunning ? 'border-blue-300 bg-blue-50' : ''}`}>
        <CardContent className="p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-start gap-3 flex-1 min-w-0">
              <Icon className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
              <div className="space-y-1 flex-1 min-w-0">
                <h4 className="font-medium text-sm leading-tight">{title}</h4>
                <p className="text-xs text-slate-600 leading-tight">{description}</p>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              {result && !isRunning && (
                <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                  Готово
                </Badge>
              )}
              
              <Button
                size="sm"
                onClick={runLiveDemo}
                disabled={isRunning || disabled}
                className="flex-shrink-0"
              >
                {isRunning ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Запуск...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    Live Demo
                  </>
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Прогресс выполнения */}
      {isRunning && currentStep && (
        <Card className="border-blue-200 bg-blue-50">
          <CardContent className="p-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-blue-600" />
                  <span className="font-medium text-blue-900">Выполнение...</span>
                </div>
                <span className="font-bold text-blue-900">{progress}%</span>
              </div>
              
              <Progress value={progress} className="h-2" />
              
              <div className="text-sm text-blue-800">
                {currentStep.message}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Ошибка */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-4">
            <div className="text-sm text-red-800">
              <strong>Ошибка:</strong> {error}
              <br />
              <span className="text-red-600">Переключение на fallback режим...</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Результат */}
      {result && !isRunning && (
        <Card className="border-green-200 bg-green-50">
          <CardContent className="p-4">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <span className="font-medium text-green-900">Демо завершено</span>
                  {getResultType() && (
                    <Badge variant="outline" className="bg-white">
                      {getResultIcon()}
                      <span className="ml-1">{getResultType()}</span>
                    </Badge>
                  )}
                </div>
                
                <Button
                  size="sm"
                  variant="outline"
                  onClick={downloadResult}
                  className="bg-white hover:bg-green-100"
                >
                  <Download className="w-4 h-4 mr-1" />
                  Скачать
                </Button>
              </div>
              
              <div className="text-sm text-green-800 space-y-1">
                {result.finalResult?.message && (
                  <div>{result.finalResult.message}</div>
                )}
                
                {result.finalResult?.components && (
                  <div className="flex gap-4 text-xs">
                    {Object.entries(result.finalResult.components).map(([key, value]) => (
                      <span key={key} className="bg-green-100 px-2 py-1 rounded">
                        {key}: {String(value)}
                      </span>
                    ))}
                  </div>
                )}
                
                {result.finalResult?.totalRisks && (
                  <div className="flex gap-2 text-xs">
                    <span className="bg-red-100 px-2 py-1 rounded">
                      Критических: {result.finalResult.criticalCount || 0}
                    </span>
                    <span className="bg-orange-100 px-2 py-1 rounded">
                      Высоких: {result.finalResult.highCount || 0}
                    </span>
                    <span className="bg-yellow-100 px-2 py-1 rounded">
                      Средних: {result.finalResult.mediumCount || 0}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default LiveDemoButton;