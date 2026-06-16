import { BehaviorSubject, Observable, combineLatest } from 'rxjs';
import { map, filter } from 'rxjs/operators';
import { SpeechRecognitionService, SpeechCommand } from './speech-recognition-service';
import { TextToSpeechService } from './text-to-speech-service';
import { VoiceCommandProcessorService, ProcessedCommand, CommandExecutionContext } from './voice-command-processor-service';

export interface VoiceIntegrationConfig {
  enableSpeechRecognition: boolean;
  enableTextToSpeech: boolean;
  autoExecuteCommands: boolean;
  confirmCriticalCommands: boolean;
  defaultLanguage: string;
  voiceFeedback: boolean;
  wakeWordDetection: boolean;
  continuousListening: boolean;
}

export interface AgentVoiceSettings {
  agentType: string;
  enabled: boolean;
  customCommands: string[];
  voiceProfile: string;
  autoResponse: boolean;
}

export interface VoiceSession {
  id: string;
  agentType: string;
  userId: string;
  sessionId: string;
  startTime: Date;
  isActive: boolean;
  commandsProcessed: number;
  lastCommand: Date | null;
}

export interface VoiceEvent {
  type: 'session_started' | 'session_ended' | 'command_received' | 'command_executed' | 'error' | 'speech_recognized' | 'tts_started' | 'tts_completed';
  sessionId: string;
  agentType?: string;
  data?: any;
  timestamp: Date;
}

export class VoiceIntegrationService {
  private speechRecognition: SpeechRecognitionService;
  private textToSpeech: TextToSpeechService;
  private commandProcessor: VoiceCommandProcessorService;
  
  private config: VoiceIntegrationConfig = {
    enableSpeechRecognition: true,
    enableTextToSpeech: true,
    autoExecuteCommands: false,
    confirmCriticalCommands: true,
    defaultLanguage: 'ru-RU',
    voiceFeedback: true,
    wakeWordDetection: false,
    continuousListening: true
  };

  private agentSettings = new Map<string, AgentVoiceSettings>();
  private activeSessions = new Map<string, VoiceSession>();
  private currentSession: VoiceSession | null = null;
  
  // Subjects
  private voiceEventSubject = new BehaviorSubject<VoiceEvent | null>(null);
  private sessionSubject = new BehaviorSubject<VoiceSession | null>(null);
  private activeAgentsSubject = new BehaviorSubject<string[]>([]);
  private configSubject = new BehaviorSubject<VoiceIntegrationConfig>(this.config);
  
  // Observables
  public voiceEvent$: Observable<VoiceEvent | null> = this.voiceEventSubject.asObservable();
  public session$: Observable<VoiceSession | null> = this.sessionSubject.asObservable();
  public activeAgents$: Observable<string[]> = this.activeAgentsSubject.asObservable();
  public config$: Observable<VoiceIntegrationConfig> = this.configSubject.asObservable();
  
  // Комбинированные streams (инициализируются после commandProcessor)
  public commandsProcessed$!: Observable<any>;
  public commandsExecuted$!: Observable<any>;

  constructor() {
    this.speechRecognition = new SpeechRecognitionService();
    this.textToSpeech = new TextToSpeechService();
    this.commandProcessor = new VoiceCommandProcessorService();
    
    // Инициализируем streams после создания commandProcessor
    this.commandsProcessed$ = this.commandProcessor?.commandProcessed$.pipe(
      filter(cmd => cmd !== null) as any
    );
    
    this.commandsExecuted$ = this.commandProcessor?.commandExecuted$.pipe(
      filter(cmd => cmd !== null) as any
    );
    
    this.initializeServices();
    this.setupEventHandlers();
  }

  private initializeServices(): void {
    // Инициализация агентов по умолчанию
    const defaultAgents = ['architect', 'developer', 'pm', 'ba', 'data_analyst'];
    defaultAgents.forEach(agentType => {
      this.agentSettings.set(agentType, {
        agentType,
        enabled: true,
        customCommands: [],
        voiceProfile: 'default',
        autoResponse: true
      });
    });

    // Обновляем активные агенты
    this.updateActiveAgents();
  }

  private setupEventHandlers(): void {
    // Обработка команд распознавания речи
    this.speechRecognition.command$.subscribe(command => {
      if (command) {
        this.handleSpeechCommand(command);
      }
    });

    // Обработка событий распознавания речи
    this.speechRecognition.speechEvent$.subscribe(event => {
      if (event) {
        this.emitVoiceEvent({
          type: 'speech_recognized',
          sessionId: this.currentSession?.id || 'default',
          agentType: this.currentSession?.agentType,
          data: event,
          timestamp: new Date()
        });
      }
    });

    // Обработка событий TTS
    this.textToSpeech.ttsEvent$.subscribe(event => {
      if (event) {
        if (event.type === 'start') {
          this.emitVoiceEvent({
            type: 'tts_started',
            sessionId: this.currentSession?.id || 'default',
            agentType: this.currentSession?.agentType,
            timestamp: new Date()
          });
        } else if (event.type === 'end') {
          this.emitVoiceEvent({
            type: 'tts_completed',
            sessionId: this.currentSession?.id || 'default',
            agentType: this.currentSession?.agentType,
            timestamp: new Date()
          });
        }
      }
    });

    // Обработка выполненных команд
    this.commandProcessor?.commandExecuted$?.subscribe(command => {
      if (command) {
        this.emitVoiceEvent({
          type: 'command_executed',
          sessionId: this.currentSession?.id || 'default',
          agentType: this.currentSession?.agentType,
          data: command,
          timestamp: new Date()
        });

        // Озвучиваем результат если включено
        if (this.config.voiceFeedback && command.result?.message) {
          this.speakAgentResponse(command.result.message, this.currentSession?.agentType);
        }
      }
    });

    // Обработка неудачных команд
    this.commandProcessor?.commandFailed$?.subscribe(command => {
      if (command) {
        this.emitVoiceEvent({
          type: 'error',
          sessionId: this.currentSession?.id || 'default',
          agentType: this.currentSession?.agentType,
          data: command,
          timestamp: new Date()
        });

        if (this.config.voiceFeedback) {
          this.speakAgentResponse('Произошла ошибка при выполнении команды', this.currentSession?.agentType);
        }
      }
    });
  }

  private async handleSpeechCommand(command: SpeechCommand): Promise<void> {
    if (!this.currentSession) {
      console.warn('Нет активной сессии для обработки команды');
      return;
    }

    this.emitVoiceEvent({
      type: 'command_received',
      sessionId: this.currentSession.id,
      agentType: this.currentSession.agentType,
      data: command,
      timestamp: new Date()
    });

    try {
      // Создаем контекст выполнения
      const executionContext: CommandExecutionContext = {
        agentType: this.currentSession.agentType,
        sessionId: this.currentSession.sessionId,
        userId: this.currentSession.userId,
        environment: 'development'
      };

      // Обрабатываем команду
      const processedCommand = this.commandProcessor?.processSpeechText(command.text, executionContext);
      
      if (!processedCommand) {
        if (this.config.voiceFeedback) {
          await this.speakAgentResponse('Команда не распознана', this.currentSession.agentType);
        }
        return;
      }

      // Обновляем статистику сессии
      this.updateSessionStats();

      // Выполняем команду если настроено автоматически
      if (this.config.autoExecuteCommands) {
        await this.executeCommand(processedCommand, executionContext);
      } else if (this.config.voiceFeedback) {
        await this.speakAgentResponse(`Команда: ${processedCommand.command}`, this.currentSession.agentType);
      }

    } catch (error) {
      console.error('Ошибка обработки голосовой команды:', error);
      
      if (this.config.voiceFeedback) {
        await this.speakAgentResponse('Произошла ошибка при обработке команды', this.currentSession.agentType);
      }
    }
  }

  private emitVoiceEvent(event: VoiceEvent): void {
    this.voiceEventSubject.next(event);
  }

  private updateSessionStats(): void {
    if (this.currentSession) {
      this.currentSession.commandsProcessed++;
      this.currentSession.lastCommand = new Date();
      
      this.sessionSubject.next(this.currentSession);
    }
  }

  public async startVoiceSession(agentType: string, userId: string): Promise<string> {
    if (!this.agentSettings.get(agentType)?.enabled) {
      throw new Error(`Голосовое управление для агента ${agentType} отключено`);
    }

    const sessionId = this.generateId();
    const session: VoiceSession = {
      id: sessionId,
      agentType,
      userId,
      sessionId,
      startTime: new Date(),
      isActive: true,
      commandsProcessed: 0,
      lastCommand: null
    };

    this.activeSessions.set(sessionId, session);
    this.currentSession = session;

    this.emitVoiceEvent({
      type: 'session_started',
      sessionId,
      agentType,
      timestamp: new Date()
    });

    // Запускаем распознавание речи если включено
    if (this.config.enableSpeechRecognition && this.config.continuousListening) {
      await this.speechRecognition.startListening();
    }

    this.updateActiveAgents();
    this.sessionSubject.next(session);

    // Приветственное сообщение
    if (this.config.voiceFeedback) {
      await this.speakAgentResponse(`Голосовое управление для ${this.getAgentDisplayName(agentType)} активировано`, agentType);
    }

    return sessionId;
  }

  public async endVoiceSession(sessionId: string): Promise<void> {
    const session = this.activeSessions.get(sessionId);
    if (!session) {
      throw new Error(`Сессия ${sessionId} не найдена`);
    }

    session.isActive = false;

    // Останавливаем распознавание речи
    if (this.speechRecognition.getListeningState()) {
      this.speechRecognition.stopListening();
    }

    this.activeSessions.delete(sessionId);

    // Если это была текущая сессия, очищаем ее
    if (this.currentSession?.id === sessionId) {
      this.currentSession = null;
    }

    this.emitVoiceEvent({
      type: 'session_ended',
      sessionId,
      agentType: session.agentType,
      timestamp: new Date()
    });

    this.updateActiveAgents();
    this.sessionSubject.next(null);

    // Прощальное сообщение
    if (this.config.voiceFeedback) {
      await this.speakAgentResponse('Голосовое управление отключено', session.agentType);
    }
  }

  public async executeCommand(command: ProcessedCommand, context: CommandExecutionContext): Promise<ProcessedCommand> {
    try {
      const executedCommand = await this.commandProcessor?.executeCommand(command, context);
      
      if (this.config.voiceFeedback && executedCommand.result?.message) {
        await this.speakAgentResponse(executedCommand.result.message, context.agentType);
      }

      return executedCommand;
    } catch (error) {
      if (this.config.voiceFeedback) {
        await this.speakAgentResponse(`Ошибка выполнения команды: ${error}`, context.agentType);
      }
      throw error;
    }
  }

  public async speakAgentResponse(text: string, agentType?: string): Promise<void> {
    if (!this.config.enableTextToSpeech) {
      return;
    }

    try {
      await this.textToSpeech.speakAIResponse(text, agentType);
    } catch (error) {
      console.error('Ошибка синтеза речи:', error);
    }
  }

  public getAgentSettings(agentType: string): AgentVoiceSettings | undefined {
    return this.agentSettings.get(agentType);
  }

  public updateAgentSettings(agentType: string, settings: Partial<AgentVoiceSettings>): void {
    const current = this.agentSettings.get(agentType);
    if (current) {
      const updated = { ...current, ...settings };
      this.agentSettings.set(agentType, updated);
      this.updateActiveAgents();
    }
  }

  public updateConfig(updates: Partial<VoiceIntegrationConfig>): void {
    this.config = { ...this.config, ...updates };
    this.configSubject.next(this.config);

    // Применяем изменения к сервисам
    if (updates.defaultLanguage) {
      this.speechRecognition.updateConfig({ language: updates.defaultLanguage });
      this.textToSpeech.updateConfig({ lang: updates.defaultLanguage });
    }
  }

  public getActiveSessions(): VoiceSession[] {
    return Array.from(this.activeSessions.values()).filter(s => s.isActive);
  }

  public getSessionById(sessionId: string): VoiceSession | undefined {
    return this.activeSessions.get(sessionId);
  }

  private updateActiveAgents(): void {
    const activeAgents = Array.from(this.agentSettings.values())
      .filter(settings => settings.enabled)
      .map(settings => settings.agentType);
    
    this.activeAgentsSubject.next(activeAgents);
  }

  private getAgentDisplayName(agentType: string): string {
    const names = {
      'architect': 'Архитектора',
      'developer': 'Разработчика',
      'pm': 'Менеджера проектов',
      'ba': 'Бизнес-аналитика',
      'data_analyst': 'Аналитика данных'
    };
    return names[agentType as keyof typeof names] || agentType;
  }

  private generateId(): string {
    return `voice_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  // Утилиты для управления
  public async enableAgentVoice(agentType: string): Promise<void> {
    this.updateAgentSettings(agentType, { enabled: true });
    await this.speakAgentResponse(`Голосовое управление для ${this.getAgentDisplayName(agentType)} включено`, agentType);
  }

  public async disableAgentVoice(agentType: string): Promise<void> {
    this.updateAgentSettings(agentType, { enabled: false });
    
    // Завершаем активную сессию для этого агента
    const activeSession = Array.from(this.activeSessions.values())
      .find(s => s.agentType === agentType && s.isActive);
    
    if (activeSession) {
      await this.endVoiceSession(activeSession.id);
    }
  }

  public getVoiceStatistics(): {
    totalSessions: number;
    activeSessions: number;
    commandsExecuted: number;
    mostActiveAgent: string;
    averageSessionDuration: number;
  } {
    const sessions = this.getActiveSessions();
    const commandStats = this.commandProcessor?.getCommandStatistics();
    
    let mostActiveAgent = '';
    let maxCommands = 0;
    const agentCommandCounts = new Map<string, number>();
    
    commandStats.mostUsedCommands.forEach(cmd => {
      const agentCommands = this.commandHistory.filter(c => c.command === cmd.command);
      const agent = agentCommands[0]?.agent || 'unknown';
      agentCommandCounts.set(agent, (agentCommandCounts.get(agent) || 0) + cmd.count);
    });
    
    agentCommandCounts.forEach((count, agent) => {
      if (count > maxCommands) {
        maxCommands = count;
        mostActiveAgent = agent;
      }
    });

    const totalSessions = this.activeSessions.size + (this.commandHistory.length > 0 ? 1 : 0);
    const averageSessionDuration = totalSessions > 0 
      ? this.getActiveSessions().reduce((sum, s) => sum + (Date.now() - s.startTime.getTime()), 0) / totalSessions 
      : 0;

    return {
      totalSessions,
      activeSessions: sessions.length,
      commandsExecuted: commandStats.successfulCommands,
      mostActiveAgent,
      averageSessionDuration
    };
  }

  private get commandHistory(): any[] {
    // Получаем историю команд через commandProcessor
    return this.commandProcessor?.getCommandHistory() || [];
  }

  public getAvailableCommands(agentType?: string): Array<{ command: string; description: string; examples: string[] }> {
    const allCommands = this.commandProcessor?.getAvailableCommands() || [];
    
    if (agentType) {
      // Фильтруем команды для конкретного агента
      return allCommands.filter(cmd => {
        const rules = this.commandProcessor?.getRules() || [];
        return rules.some(rule => rule.command === cmd.command && 
          (!rule.agent || rule.agent === agentType));
      });
    }
    
    return allCommands;
  }

  public cleanup(): void {
    // Завершаем все активные сессии
    this.activeSessions.forEach(session => {
      this.endVoiceSession(session.id);
    });

    // Очищаем сервисы
    this.speechRecognition.cleanup();
    this.textToSpeech.cleanup();
    this.commandProcessor?.cleanup();

    // Завершаем subjects
    this.voiceEventSubject.complete();
    this.sessionSubject.complete();
    this.activeAgentsSubject.complete();
    this.configSubject.complete();
  }
}