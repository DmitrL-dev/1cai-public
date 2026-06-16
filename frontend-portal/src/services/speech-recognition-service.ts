import { BehaviorSubject, Observable } from 'rxjs';

export interface SpeechRecognitionConfig {
  language: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  grammars?: SpeechGrammarList;
}

export interface SpeechRecognitionEvent {
  type: 'start' | 'end' | 'error' | 'result' | 'nomatch';
  transcript?: string;
  confidence?: number;
  error?: string;
  timestamp: Date;
}

export interface SpeechCommand {
  text: string;
  confidence: number;
  timestamp: Date;
  agent?: string;
  command?: string;
  parameters?: Record<string, any>;
}

export class SpeechRecognitionService {
  private recognition: SpeechRecognition | null = null;
  private isListening = false;
  private currentConfig: SpeechRecognitionConfig;
  private commandPatterns: Map<string, RegExp> = new Map();
  
  // Subjects для событий
  private speechEventSubject = new BehaviorSubject<SpeechRecognitionEvent | null>(null);
  private commandSubject = new BehaviorSubject<SpeechCommand | null>(null);
  private listeningStateSubject = new BehaviorSubject<boolean>(false);
  
  // Observables
  public speechEvent$: Observable<SpeechRecognitionEvent | null> = this.speechEventSubject.asObservable();
  public command$: Observable<SpeechCommand | null> = this.commandSubject.asObservable();
  public listeningState$: Observable<boolean> = this.listeningStateSubject.asObservable();

  constructor(config?: Partial<SpeechRecognitionConfig>) {
    this.currentConfig = {
      language: 'ru-RU',
      continuous: true,
      interimResults: true,
      maxAlternatives: 3,
      ...config
    };
    
    this.initializeRecognition();
    this.setupCommandPatterns();
  }

  private initializeRecognition(): void {
    // Проверка поддержки Web Speech API
    const SpeechRecognition = window.SpeechRecognition || (window as any).webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
      console.error('Speech Recognition API не поддерживается в этом браузере');
      return;
    }

    this.recognition = new SpeechRecognition();
    this.setupRecognitionEvents();
  }

  private setupRecognitionEvents(): void {
    if (!this.recognition) return;

    this.recognition.onstart = () => {
      this.listeningStateSubject.next(true);
      this.emitEvent({ type: 'start', timestamp: new Date() });
    };

    this.recognition.onend = () => {
      this.listeningStateSubject.next(false);
      this.emitEvent({ type: 'end', timestamp: new Date() });
    };

    this.recognition.onerror = (event) => {
      this.listeningStateSubject.next(false);
      const errorMessage = `Ошибка распознавания: ${event.error}`;
      this.emitEvent({ 
        type: 'error', 
        error: errorMessage,
        timestamp: new Date() 
      });
    };

    this.recognition.onnomatch = () => {
      this.emitEvent({ 
        type: 'nomatch', 
        timestamp: new Date() 
      });
    };

    this.recognition.onresult = (event) => {
      const result = event.results[event.resultIndex];
      const transcript = result[0].transcript;
      const confidence = result[0].confidence;

      // Эмитируем промежуточный результат если нужно
      if (result.isFinal) {
        this.emitEvent({ 
          type: 'result', 
          transcript, 
          confidence,
          timestamp: new Date() 
        });

        // Обрабатываем как команду
        this.processSpeechCommand(transcript, confidence);
      } else if (this.currentConfig.interimResults) {
        this.emitEvent({ 
          type: 'result', 
          transcript: `[промежуточный] ${transcript}`, 
          confidence,
          timestamp: new Date() 
        });
      }
    };
  }

  private setupCommandPatterns(): void {
    // Паттерны для разных типов команд
    this.commandPatterns.set('agent_switch', /^(?:переключи(?:ться|сь)?|перейти|открыть)\s+(?:на\s+)?(.+)/i);
    this.commandPatterns.set('create_task', /^(?:создай|добавь|сделай)\s+(?:задачу|задание|новую задачу)\s*(?:название|имя)?\s*(.+)?/i);
    this.commandPatterns.set('execute_command', /^(?:выполни|запусти|сделай)\s+(.+)/i);
    this.commandPatterns.set('search', /^(?:найди|поиск|ищи)\s+(.+)/i);
    this.commandPatterns.set('help', /^(?:помощь|что|как|справка)/i);
    this.commandPatterns.set('stop', /^(?:стоп|останови|закончить)/i);
    this.commandPatterns.set('save', /^(?:сохрани|запиши)/i);
    this.commandPatterns.set('export', /^(?:экспорт|выгрузи|скачать)/i);
  }

  public async startListening(): Promise<void> {
    if (!this.recognition) {
      throw new Error('Speech Recognition не инициализирован');
    }

    if (this.isListening) {
      console.warn('Распознавание речи уже активно');
      return;
    }

    try {
      // Настройка конфигурации
      this.recognition.lang = this.currentConfig.language;
      this.recognition.continuous = this.currentConfig.continuous;
      this.recognition.interimResults = this.currentConfig.interimResults;
      this.recognition.maxAlternatives = this.currentConfig.maxAlternatives;

      if (this.currentConfig.grammars) {
        this.recognition.grammars = this.currentConfig.grammars;
      }

      this.recognition.start();
      this.isListening = true;
    } catch (error) {
      this.emitEvent({ 
        type: 'error', 
        error: `Не удалось запустить распознавание: ${error}`,
        timestamp: new Date() 
      });
      throw error;
    }
  }

  public stopListening(): void {
    if (this.recognition && this.isListening) {
      this.recognition.stop();
      this.isListening = false;
    }
  }

  public updateConfig(config: Partial<SpeechRecognitionConfig>): void {
    this.currentConfig = { ...this.currentConfig, ...config };
    
    if (this.recognition) {
      this.recognition.lang = this.currentConfig.language;
    }
  }

  private processSpeechCommand(transcript: string, confidence: number): void {
    const command: SpeechCommand = {
      text: transcript.trim(),
      confidence,
      timestamp: new Date()
    };

    // Анализ команды
    const commandType = this.identifyCommandType(transcript);
    if (commandType) {
      command.command = commandType;
      command.agent = this.extractAgent(transcript);
      command.parameters = this.extractParameters(transcript, commandType);
    }

    this.commandSubject.next(command);
  }

  private identifyCommandType(text: string): string | null {
    for (const [type, pattern] of this.commandPatterns.entries()) {
      const match = text.match(pattern);
      if (match) {
        return type;
      }
    }
    return null;
  }

  private extractAgent(text: string): string | undefined {
    // Извлечение агента из команды
    const agents = ['архитектор', 'разработчик', 'менеджер проектов', 'бизнес-аналитик', 'аналитик данных'];
    
    for (const agent of agents) {
      if (text.toLowerCase().includes(agent)) {
        return agent;
      }
    }
    
    return undefined;
  }

  private extractParameters(text: string, commandType: string): Record<string, any> {
    const parameters: Record<string, any> = {};

    switch (commandType) {
      case 'create_task':
        const taskMatch = text.match(/создай\s+задачу\s*(?:название|имя)?\s*(.+)?/i);
        if (taskMatch && taskMatch[1]) {
          parameters.taskName = taskMatch[1].trim();
        }
        break;

      case 'search':
        const searchMatch = text.match(/найди\s+(.+)/i);
        if (searchMatch) {
          parameters.query = searchMatch[1].trim();
        }
        break;

      case 'execute_command':
        const execMatch = text.match(/выполни\s+(.+)/i);
        if (execMatch) {
          parameters.command = execMatch[1].trim();
        }
        break;
    }

    return parameters;
  }

  private emitEvent(event: SpeechRecognitionEvent): void {
    this.speechEventSubject.next(event);
  }

  public getSupportedLanguages(): string[] {
    return [
      'ru-RU',
      'en-US',
      'en-GB',
      'uk-UA',
      'be-BY',
      'kk-KZ'
    ];
  }

  public getListeningState(): boolean {
    return this.isListening;
  }

  public getCurrentConfig(): SpeechRecognitionConfig {
    return { ...this.currentConfig };
  }

  public cleanup(): void {
    if (this.recognition) {
      this.recognition.onstart = null;
      this.recognition.onend = null;
      this.recognition.onerror = null;
      this.recognition.onnomatch = null;
      this.recognition.onresult = null;
    }

    this.speechEventSubject.complete();
    this.commandSubject.complete();
    this.listeningStateSubject.complete();
  }
}

// Функции-помощники для работы с грамматикой
export function createGrammarRules(rules: Array<{ phrase: string; weight: number }>): SpeechGrammarList {
  const SpeechGrammarListClass = window.SpeechGrammarList || (window as any).webkitSpeechGrammarList;
  
  if (!SpeechGrammarListClass) {
    throw new Error('Speech Grammar List не поддерживается');
  }

  const grammarList = new SpeechGrammarListClass();
  
  rules.forEach(rule => {
    const grammar = `#JSGF V1.0; grammar ${rule.phrase}; public <phrase> = ${rule.phrase};`;
    grammarList.addFromString(grammar, rule.weight);
  });

  return grammarList;
}