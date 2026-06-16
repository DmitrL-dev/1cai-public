import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Send,
  Loader2,
  CheckCircle,
  AlertCircle,
  Download
} from 'lucide-react';
import { getEdgeFunctionUrl, SUPABASE_ANON_KEY, isSupabaseConfigured } from '@/lib/supabase';

interface DemoResult {
  message?: string;
  diagram?: string;
  code?: string;
  components?: Record<string, any>;
  [key: string]: any;
}

interface StepResult {
  progress: number;
  message: string;
  result?: DemoResult;
}

interface CustomQuerySectionProps {
  role: string;
  roleTitle: string;
  placeholder: string;
  onQueryComplete?: (result: DemoResult) => void;
}

const CustomQuerySection: React.FC<CustomQuerySectionProps> = ({
  role,
  roleTitle,
  placeholder,
  onQueryComplete
}) => {
  const [query, setQuery] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [result, setResult] = useState<DemoResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isValidQuery = query.trim().length >= 10;

  const handleSubmit = async () => {
    if (!isValidQuery || isProcessing) return;

    setIsProcessing(true);
    setError(null);
    setResult(null);
    setProgress(0);
    setCurrentStep(null);

    try {
      // Проверяем конфигурацию Supabase
      if (!isSupabaseConfigured()) {
        throw new Error('Supabase не настроен. Функция недоступна в режиме демо.');
      }

      const functionUrl = getEdgeFunctionUrl(`${role}-demo`);
      
      const response = await fetch(functionUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${SUPABASE_ANON_KEY}`
        },
        body: JSON.stringify({ 
          demoType: 'custom',
          userQuery: query.trim()
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      
      if (data.error) {
        throw new Error(data.error.message || 'Ошибка выполнения запроса');
      }

      // Обрабатываем шаги прогресса
      if (data.data?.steps) {
        for (const step of data.data.steps) {
          setProgress(step.progress);
          setCurrentStep(step.message);
          await new Promise(r => setTimeout(r, 300));
        }
      }

      // Устанавливаем результат
      if (data.data?.finalResult) {
        setResult(data.data.finalResult);
        onQueryComplete?.(data.data.finalResult);
      }

    } catch (err) {
      console.error('Custom query error:', err);
      setError(err instanceof Error ? err.message : 'Неизвестная ошибка');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDownload = () => {
    if (!result) return;

    const content = JSON.stringify(result, null, 2);
    const blob = new Blob([content], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${role}-custom-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <Card className="border-dashed border-2 bg-gradient-to-br from-slate-50 to-white">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <Send className="w-5 h-5" />
          Пользовательский запрос
        </CardTitle>
        <CardDescription>
          Задайте свой вопрос или опишите задачу для {roleTitle}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Textarea
            placeholder={placeholder}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={isProcessing}
            className="min-h-[100px] resize-none"
            maxLength={2000}
          />
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>
              {query.trim().length < 10 && query.trim().length > 0 
                ? `Минимум 10 символов (осталось ${10 - query.trim().length})` 
                : query.trim().length >= 10 
                ? 'Готово к отправке' 
                : 'Введите минимум 10 символов'}
            </span>
            <span>{query.length} / 2000</span>
          </div>
        </div>

        <Button 
          onClick={handleSubmit}
          disabled={!isValidQuery || isProcessing}
          className="w-full"
          size="lg"
        >
          {isProcessing ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Обработка запроса...
            </>
          ) : (
            <>
              <Send className="w-4 h-4 mr-2" />
              Выполнить запрос
            </>
          )}
        </Button>

        {/* Прогресс выполнения */}
        {isProcessing && (
          <div className="space-y-2">
            <Progress value={progress} className="h-2" />
            {currentStep && (
              <p className="text-sm text-slate-600 flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                {currentStep}
              </p>
            )}
          </div>
        )}

        {/* Ошибка */}
        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Результат */}
        {result && !isProcessing && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Badge variant="default" className="flex items-center gap-1">
                <CheckCircle className="w-3 h-3" />
                Запрос выполнен - Результат ниже
              </Badge>
              <Button
                variant="outline"
                size="sm"
                onClick={handleDownload}
              >
                <Download className="w-4 h-4 mr-2" />
                Скачать
              </Button>
            </div>

            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="w-5 h-5 text-green-600" />
                <span className="font-medium text-green-800">Результат готов к скачиванию!</span>
              </div>
              <div className="text-sm text-green-700 mb-3">
                Результат также сохранен в общем списке справа и доступен для скачивания.
              </div>
              <Card className="bg-white">
                <CardContent className="p-4">
                  <div className="space-y-2">
                    {result.message && (
                      <p className="text-sm text-slate-700">{result.message}</p>
                    )}
                    
                    {result.code && (
                      <pre className="text-xs bg-slate-900 text-slate-100 p-3 rounded overflow-x-auto">
                        <code>{result.code}</code>
                      </pre>
                    )}
                    
                    {result.diagram && (
                      <div className="text-xs bg-white p-3 rounded border">
                        <code className="text-slate-600">{result.diagram}</code>
                      </div>
                    )}
                    
                    {Object.keys(result).filter(k => !['message', 'code', 'diagram'].includes(k)).length > 0 && (
                      <details className="text-xs">
                        <summary className="cursor-pointer text-slate-600 hover:text-slate-900">
                          Подробная информация
                        </summary>
                        <pre className="mt-2 bg-white p-2 rounded border overflow-x-auto">
                          {JSON.stringify(
                            Object.fromEntries(
                              Object.entries(result).filter(([k]) => !['message', 'code', 'diagram'].includes(k))
                            ),
                            null,
                            2
                          )}
                        </pre>
                      </details>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default CustomQuerySection;
