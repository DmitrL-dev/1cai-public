import { BehaviorSubject, Observable } from 'rxjs';

export interface TTSConfig {
  voice?: string;
  rate: number;
  pitch: number;
  volume: number;
  lang: string;
}

export interface TTSEvent {
  type: 'start' | 'end' | 'error' | 'pause' | 'resume';
  utterance?: SpeechSynthesisUtterance;
  error?: string;
  timestamp: Date;
}

export interface TTSQueueItem {
  id: string;
  text: string;
  config: TTSConfig;
  priority: number;
  timestamp: Date;
  callback?: () => void;
}

export class TextToSpeechService {
  private synthesis: SpeechSynthesis;
  private voices: SpeechSynthesisVoice[] = [];
  private currentUtterance: SpeechSynthesisUtterance | null = null;
  private queue: TTSQueueItem[] = [];
  private isProcessing = false;
  
  private currentConfig: TTSConfig = {
    rate: 1.0,
    pitch: 1.0,
    volume: 1.0,
    lang: 'ru-RU'
  };
  
  // Subjects для событий
  private ttsEventSubject = new BehaviorSubject<TTSEvent | null>(null);
  private queueSizeSubject = new BehaviorSubject<number>(0);
  private processingStateSubject = new BehaviorSubject<boolean>(false);
  private voiceListSubject = new BehaviorSubject<SpeechSynthesisVoice[]>([]);
  
  // Observables
  public ttsEvent$: Observable<TTSEvent | null> = this.ttsEventSubject.asObservable();
  public queueSize$: Observable<number> = this.queueSizeSubject.asObservable();
  public processingState$: Observable<boolean> = this.processingStateSubject.asObservable();
  public voices$: Observable<SpeechSynthesisVoice[]> = this.voiceListSubject.asObservable();

  constructor() {
    this.synthesis = window.speechSynthesis;
    this.initializeVoices();
  }

  private initializeVoices(): void {
    // Загрузка голосов
    const loadVoices = () => {
      this.voices = this.synthesis.getVoices();
      this.voiceListSubject.next([...this.voices]);
    };

    // Голоса могут загружаться асинхронно
    if (this.synthesis.onvoiceschanged !== undefined) {
      this.synthesis.onvoiceschanged = loadVoices;
    }

    // Пытаемся загрузить сразу
    loadVoices();
  }

  public async speak(text: string, config?: Partial<TTSConfig>): Promise<string> {
    const utteranceId = this.generateId();
    const utteranceConfig = { ...this.currentConfig, ...config };
    
    const queueItem: TTSQueueItem = {
      id: utteranceId,
      text,
      config: utteranceConfig,
      priority: 1,
      timestamp: new Date()
    };

    return new Promise((resolve, reject) => {
      queueItem.callback = () => resolve(utteranceId);
      
      this.addToQueue(queueItem);
    });
  }

  public async speakWithPriority(text: string, priority: number = 10, config?: Partial<TTSConfig>): Promise<string> {
    const utteranceId = this.generateId();
    const utteranceConfig = { ...this.currentConfig, ...config };
    
    const queueItem: TTSQueueItem = {
      id: utteranceId,
      text,
      config: utteranceConfig,
      priority,
      timestamp: new Date()
    };

    return new Promise((resolve, reject) => {
      queueItem.callback = () => resolve(utteranceId);
      
      this.addToQueue(queueItem);
    });
  }

  private addToQueue(item: TTSQueueItem): void {
    // Проверяем, не превышает ли размер очереди лимит
    if (this.queue.length >= 100) {
      // Удаляем старые элементы с низким приоритетом
      this.queue.sort((a, b) => a.priority - b.priority);
      const removed = this.queue.splice(0, this.queue.length - 50);
      console.warn(`Удалено ${removed.length} элементов из очереди TTS`);
    }

    // Добавляем в очередь и сортируем по приоритету
    this.queue.push(item);
    this.queue.sort((a, b) => b.priority - a.priority);
    
    this.queueSizeSubject.next(this.queue.length);
    
    // Запускаем обработку если не активно
    if (!this.isProcessing) {
      this.processQueue();
    }
  }

  private async processQueue(): Promise<void> {
    if (this.isProcessing || this.queue.length === 0) {
      return;
    }

    this.isProcessing = true;
    this.processingStateSubject.next(true);

    try {
      while (this.queue.length > 0) {
        const item = this.queue.shift()!;
        await this.speakItem(item);
        
        // Небольшая пауза между элементами
        await this.delay(100);
      }
    } finally {
      this.isProcessing = false;
      this.processingStateSubject.next(false);
      this.queueSizeSubject.next(this.queue.length);
    }
  }

  private async speakItem(item: TTSQueueItem): Promise<void> {
    return new Promise((resolve, reject) => {
      const utterance = new SpeechSynthesisUtterance(item.text);
      
      // Настройка голоса
      const voice = this.getVoiceByName(item.config.voice);
      if (voice) {
        utterance.voice = voice;
      }
      utterance.lang = item.config.lang;
      utterance.rate = item.config.rate;
      utterance.pitch = item.config.pitch;
      utterance.volume = item.config.volume;

      // Обработчики событий
      utterance.onstart = () => {
        this.currentUtterance = utterance;
        this.emitEvent({ type: 'start', utterance, timestamp: new Date() });
      };

      utterance.onend = () => {
        this.emitEvent({ type: 'end', utterance, timestamp: new Date() });
        if (item.callback) item.callback();
        resolve();
      };

      utterance.onerror = (event) => {
        const error = `Ошибка синтеза речи: ${event.error}`;
        this.emitEvent({ type: 'error', utterance, error, timestamp: new Date() });
        reject(new Error(error));
      };

      utterance.onpause = () => {
        this.emitEvent({ type: 'pause', utterance, timestamp: new Date() });
      };

      utterance.onresume = () => {
        this.emitEvent({ type: 'resume', utterance, timestamp: new Date() });
      };

      // Запуск синтеза
      this.synthesis.speak(utterance);
    });
  }

  public pause(): void {
    if (this.synthesis.speaking && !this.synthesis.paused) {
      this.synthesis.pause();
    }
  }

  public resume(): void {
    if (this.synthesis.paused) {
      this.synthesis.resume();
    }
  }

  public cancel(): void {
    this.synthesis.cancel();
    this.queue = [];
    this.currentUtterance = null;
    this.queueSizeSubject.next(0);
    this.emitEvent({ type: 'end', timestamp: new Date() });
  }

  public updateConfig(config: Partial<TTSConfig>): void {
    this.currentConfig = { ...this.currentConfig, ...config };
  }

  public getVoices(): SpeechSynthesisVoice[] {
    return [...this.voices];
  }

  public getVoiceByName(name: string): SpeechSynthesisVoice | undefined {
    return this.voices.find(voice => voice.name === name);
  }

  public getVoicesByLanguage(lang: string): SpeechSynthesisVoice[] {
    return this.voices.filter(voice => voice.lang === lang);
  }

  public getAvailableLanguages(): string[] {
    const languages = new Set<string>();
    this.voices.forEach(voice => languages.add(voice.lang));
    return Array.from(languages).sort();
  }

  private generateId(): string {
    return `tts_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private emitEvent(event: TTSEvent): void {
    this.ttsEventSubject.next(event);
  }

  // Утилиты для создания пресетов голосов
  public getVoicePresets(): Array<{ name: string; config: TTSConfig }> {
    return [
      {
        name: 'Мужской стандарт',
        config: { ...this.currentConfig, voice: this.voices.find(v => v.name.includes('Male'))?.name }
      },
      {
        name: 'Женский стандарт',
        config: { ...this.currentConfig, voice: this.voices.find(v => v.name.includes('Female'))?.name }
      },
      {
        name: 'Быстрая речь',
        config: { ...this.currentConfig, rate: 1.5, pitch: 1.2 }
      },
      {
        name: 'Медленная речь',
        config: { ...this.currentConfig, rate: 0.7, pitch: 0.8 }
      },
      {
        name: 'Шепот',
        config: { ...this.currentConfig, volume: 0.5, pitch: 0.6 }
      }
    ];
  }

  // Озвучивание для AI Assistant
  public speakAIResponse(text: string, agentType?: string): Promise<string> {
    const config = this.getAIResponseConfig(agentType);
    return this.speak(text, config);
  }

  private getAIResponseConfig(agentType?: string): Partial<TTSConfig> {
    switch (agentType) {
      case 'architect':
        return { rate: 0.9, pitch: 0.8, voice: this.voices.find(v => v.name.includes('Male'))?.name };
      case 'developer':
        return { rate: 1.1, pitch: 1.1, voice: this.voices.find(v => v.name.includes('Female'))?.name };
      case 'pm':
        return { rate: 0.95, pitch: 0.9, voice: this.voices.find(v => v.name.includes('Male'))?.name };
      case 'ba':
        return { rate: 0.85, pitch: 0.7, voice: this.voices.find(v => v.name.includes('Female'))?.name };
      case 'data_analyst':
        return { rate: 1.0, pitch: 1.0, voice: this.voices.find(v => v.name.includes('Neutral'))?.name };
      default:
        return { rate: 1.0, pitch: 1.0 };
    }
  }

  public getQueueSize(): number {
    return this.queue.length;
  }

  public isSpeaking(): boolean {
    return this.synthesis.speaking;
  }

  public isPaused(): boolean {
    return this.synthesis.paused;
  }

  public cleanup(): void {
    this.cancel();
    this.ttsEventSubject.complete();
    this.queueSizeSubject.complete();
    this.processingStateSubject.complete();
    this.voiceListSubject.complete();
  }
}