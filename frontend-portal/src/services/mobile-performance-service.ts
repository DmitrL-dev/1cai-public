import { BehaviorSubject, Observable } from 'rxjs';

export interface PerformanceConfig {
  lazyLoading: {
    enabled: boolean;
    threshold: number; // pixels before viewport
    rootMargin: string; // margin for intersection observer
  };
  virtualScrolling: {
    enabled: boolean;
    itemHeight: number;
    overscan: number; // number of items to render outside viewport
    maxItems: number;
  };
  imageOptimization: {
    enabled: boolean;
    quality: number; // 0-1
    formats: string[]; // webp, avif, jpg
    responsiveSizes: number[];
    lazyLoad: boolean;
  };
  caching: {
    enabled: boolean;
    maxAge: number; // milliseconds
    maxEntries: number;
    compression: boolean;
  };
  animation: {
    enabled: boolean;
    preferReducedMotion: boolean;
    useGPUAcceleration: boolean;
    throttle: number; // frames per second
  };
  network: {
    prefetch: boolean;
    prefetchDelay: number;
    offlineSupport: boolean;
    compression: boolean;
  };
}

export interface PerformanceMetrics {
  memory: {
    used: number; // MB
    total: number; // MB
    percentage: number;
  };
  cpu: {
    usage: number; // percentage
    load: number;
  };
  network: {
    type: 'slow-2g' | '2g' | '3g' | '4g' | 'wifi' | 'unknown';
    effectiveType: string;
    downlink: number;
    rtt: number;
    saveData: boolean;
  };
  rendering: {
    fps: number;
    frameTime: number;
    paintTime: number;
    layoutTime: number;
  };
  storage: {
    used: number; // bytes
    available: number; // bytes
    percentage: number;
  };
}

export interface OptimizationStrategy {
  name: string;
  enabled: boolean;
  priority: number;
  conditions: {
    memoryThreshold?: number;
    cpuThreshold?: number;
    networkType?: string[];
    deviceType?: string[];
  };
  actions: string[];
}

export class MobilePerformanceService {
  private config: PerformanceConfig = {
    lazyLoading: {
      enabled: true,
      threshold: 100,
      rootMargin: '50px'
    },
    virtualScrolling: {
      enabled: true,
      itemHeight: 60,
      overscan: 5,
      maxItems: 1000
    },
    imageOptimization: {
      enabled: true,
      quality: 0.8,
      formats: ['webp', 'avif', 'jpg'],
      responsiveSizes: [320, 640, 768, 1024, 1440],
      lazyLoad: true
    },
    caching: {
      enabled: true,
      maxAge: 24 * 60 * 60 * 1000, // 24 hours
      maxEntries: 100,
      compression: true
    },
    animation: {
      enabled: true,
      preferReducedMotion: false,
      useGPUAcceleration: true,
      throttle: 60
    },
    network: {
      prefetch: true,
      prefetchDelay: 100,
      offlineSupport: true,
      compression: true
    }
  };

  private metrics: PerformanceMetrics = {
    memory: { used: 0, total: 0, percentage: 0 },
    cpu: { usage: 0, load: 0 },
    network: { 
      type: 'unknown',
      effectiveType: '4g',
      downlink: 10,
      rtt: 50,
      saveData: false
    },
    rendering: { fps: 60, frameTime: 16.67, paintTime: 8, layoutTime: 4 },
    storage: { used: 0, available: 0, percentage: 0 }
  };

  private strategies: OptimizationStrategy[] = [
    {
      name: 'memory_optimization',
      enabled: true,
      priority: 1,
      conditions: { memoryThreshold: 80 },
      actions: ['disable_animations', 'reduce_image_quality', 'enable_lazy_loading']
    },
    {
      name: 'low_bandwidth',
      enabled: true,
      priority: 2,
      conditions: { networkType: ['slow-2g', '2g'] },
      actions: ['reduce_image_quality', 'disable_videos', 'compress_data']
    },
    {
      name: 'low_performance_device',
      enabled: true,
      priority: 3,
      conditions: { deviceType: ['low-end'] },
      actions: ['disable_animations', 'reduce_fps', 'enable_basic_mode']
    }
  ];

  private isMonitoring = false;
  private monitoringInterval: NodeJS.Timeout | null = null;
  private observers: Map<string, IntersectionObserver> = new Map();
  private virtualScrollContainers: Map<string, any> = new Map();
  private imageCache: Map<string, string> = new Map();

  // Subjects
  private metricsSubject = new BehaviorSubject<PerformanceMetrics | null>(null);
  private optimizationSubject = new BehaviorSubject<string[]>([]);
  private strategySubject = new BehaviorSubject<OptimizationStrategy[]>([]);
  
  // Observables
  public metrics$ = this.metricsSubject.asObservable();
  public optimization$ = this.optimizationSubject.asObservable();
  public strategies$ = this.strategySubject.asObservable();

  constructor() {
    this.initializeService();
  }

  private initializeService(): void {
    this.detectDeviceCapabilities();
    this.initializeNetworkMonitoring();
    this.initializeMemoryMonitoring();
    this.initializeRenderingMonitoring();
    this.setupAccessibilityPreferences();
    
    // Обновление стратегий
    this.updateStrategies();
  }

  private detectDeviceCapabilities(): void {
    // Определение возможностей устройства
    const capabilities = {
      memory: (navigator as any).deviceMemory || 4,
      cores: navigator.hardwareConcurrency || 4,
      connection: (navigator as any).connection
    };

    // Настройка конфигурации на основе возможностей
    if (capabilities.memory < 2) {
      this.config.lazyLoading.enabled = true;
      this.config.virtualScrolling.enabled = true;
      this.config.animation.enabled = false;
    }

    if (capabilities.cores < 2) {
      this.config.animation.throttle = 30;
    }

    this.updateStrategies();
  }

  private initializeNetworkMonitoring(): void {
    const connection = (navigator as any).connection;
    
    if (connection) {
      connection.addEventListener('change', () => {
        this.updateNetworkMetrics();
        this.applyNetworkOptimizations();
      });
    }

    this.updateNetworkMetrics();
  }

  private initializeMemoryMonitoring(): void {
    if ('memory' in performance) {
      setInterval(() => {
        this.updateMemoryMetrics();
      }, 5000);
    }
  }

  private initializeRenderingMonitoring(): void {
    let lastTime = performance.now();
    let frameCount = 0;

    const measureFPS = () => {
      const now = performance.now();
      frameCount++;

      if (now - lastTime >= 1000) {
        this.updateRenderingMetrics(frameCount, now - lastTime);
        frameCount = 0;
        lastTime = now;
      }

      requestAnimationFrame(measureFPS);
    };

    requestAnimationFrame(measureFPS);
  }

  private setupAccessibilityPreferences(): void {
    // Проверка prefers-reduced-motion
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      this.config.animation.preferReducedMotion = true;
      this.config.animation.enabled = false;
    }

    // Проверка prefers-color-scheme
    const darkMode = window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (darkMode) {
      // Адаптация для темной темы
      this.config.imageOptimization.quality = 0.9;
    }
  }

  private updateNetworkMetrics(): void {
    const connection = (navigator as any).connection;
    
    if (connection) {
      this.metrics.network = {
        type: connection.effectiveType,
        effectiveType: connection.effectiveType,
        downlink: connection.downlink || 10,
        rtt: connection.rtt || 50,
        saveData: connection.saveData || false
      };

      // Применение оптимизаций на основе типа сети
      this.applyNetworkOptimizations();
    }
  }

  private updateMemoryMetrics(): void {
    if ('memory' in performance) {
      const memInfo = (performance as any).memory;
      this.metrics.memory = {
        used: Math.round(memInfo.usedJSHeapSize / 1024 / 1024),
        total: Math.round(memInfo.totalJSHeapSize / 1024 / 1024),
        percentage: Math.round((memInfo.usedJSHeapSize / memInfo.totalJSHeapSize) * 100)
      };

      // Применение оптимизаций памяти
      this.applyMemoryOptimizations();
    }
  }

  private updateRenderingMetrics(frameCount: number, duration: number): void {
    const fps = Math.round((frameCount / duration) * 1000);
    this.metrics.rendering = {
      fps,
      frameTime: duration / frameCount,
      paintTime: 8, // Приблизительные значения
      layoutTime: 4
    };

    // Применение оптимизаций рендеринга
    this.applyRenderingOptimizations();
  }

  private applyNetworkOptimizations(): void {
    const optimizations: string[] = [];
    
    if (this.metrics.network.effectiveType === 'slow-2g' || this.metrics.network.effectiveType === '2g') {
      optimizations.push('reduce_image_quality', 'disable_videos', 'compress_data');
      this.config.imageOptimization.quality = 0.6;
    } else if (this.metrics.network.effectiveType === '3g') {
      optimizations.push('optimize_images', 'compress_data');
      this.config.imageOptimization.quality = 0.7;
    }

    if (this.metrics.network.saveData) {
      optimizations.push('skip_images', 'minimal_content');
      this.config.imageOptimization.enabled = false;
    }

    this.optimizationSubject.next(optimizations);
  }

  private applyMemoryOptimizations(): void {
    const optimizations: string[] = [];
    
    if (this.metrics.memory.percentage > 80) {
      optimizations.push('disable_animations', 'reduce_image_quality', 'enable_lazy_loading', 'clear_cache');
      this.config.animation.enabled = false;
    } else if (this.metrics.memory.percentage > 60) {
      optimizations.push('reduce_fps', 'compress_images');
      this.config.animation.throttle = 30;
    }

    this.optimizationSubject.next(optimizations);
  }

  private applyRenderingOptimizations(): void {
    const optimizations: string[] = [];
    
    if (this.metrics.rendering.fps < 30) {
      optimizations.push('reduce_fps', 'simplify_animations', 'skip_non_critical_updates');
      this.config.animation.throttle = 30;
    } else if (this.metrics.rendering.fps < 45) {
      optimizations.push('optimize_animations');
    }

    this.optimizationSubject.next(optimizations);
  }

  private updateStrategies(): void {
    this.strategySubject.next([...this.strategies]);
  }

  // Public methods for optimization
  public startMonitoring(interval: number = 5000): void {
    if (this.isMonitoring) return;
    
    this.isMonitoring = true;
    this.monitoringInterval = setInterval(() => {
      this.collectMetrics();
      this.applyOptimizations();
    }, interval);
  }

  public stopMonitoring(): void {
    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
      this.monitoringInterval = null;
    }
    this.isMonitoring = false;
  }

  private collectMetrics(): void {
    this.updateNetworkMetrics();
    this.updateMemoryMetrics();
    
    // Обновление метрик в subject
    this.metricsSubject.next({ ...this.metrics });
  }

  private applyOptimizations(): void {
    const appliedOptimizations: string[] = [];
    
    // Проверка и применение стратегий
    this.strategies.forEach(strategy => {
      if (this.shouldApplyStrategy(strategy)) {
        this.applyStrategy(strategy);
        appliedOptimizations.push(...strategy.actions);
      }
    });

    this.optimizationSubject.next(appliedOptimizations);
  }

  private shouldApplyStrategy(strategy: OptimizationStrategy): boolean {
    const { conditions } = strategy;
    
    if (conditions.memoryThreshold && this.metrics.memory.percentage < conditions.memoryThreshold) {
      return false;
    }
    
    if (conditions.cpuThreshold && this.metrics.cpu.usage < conditions.cpuThreshold) {
      return false;
    }
    
    if (conditions.networkType && !conditions.networkType.includes(this.metrics.network.effectiveType)) {
      return false;
    }
    
    return true;
  }

  private applyStrategy(strategy: OptimizationStrategy): void {
    console.log(`Applying optimization strategy: ${strategy.name}`);
    
    strategy.actions.forEach(action => {
      switch (action) {
        case 'disable_animations':
          this.config.animation.enabled = false;
          break;
        case 'reduce_image_quality':
          this.config.imageOptimization.quality = Math.max(0.5, this.config.imageOptimization.quality - 0.2);
          break;
        case 'enable_lazy_loading':
          this.config.lazyLoading.enabled = true;
          break;
        case 'reduce_fps':
          this.config.animation.throttle = Math.min(30, this.config.animation.throttle);
          break;
        case 'compress_data':
          this.config.network.compression = true;
          break;
        case 'optimize_images':
          this.config.imageOptimization.enabled = true;
          break;
        case 'clear_cache':
          this.clearImageCache();
          break;
      }
    });
  }

  // Lazy loading implementation
  public createLazyLoader(callback: (element: Element) => void): IntersectionObserver {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          callback(entry.target);
          observer.unobserve(entry.target);
        }
      });
    }, {
      rootMargin: this.config.lazyLoading.rootMargin,
      threshold: 0
    });

    return observer;
  }

  public observeElement(element: Element, callback: () => void): void {
    if (!this.config.lazyLoading.enabled) {
      callback();
      return;
    }

    const observer = this.createLazyLoader(() => callback());
    observer.observe(element);
    this.observers.set(element, observer);
  }

  // Virtual scrolling implementation
  public createVirtualScroller(
    container: HTMLElement,
    itemHeight: number,
    getItemCount: () => number,
    renderItem: (index: number) => HTMLElement
  ): void {
    if (!this.config.virtualScrolling.enabled) {
      // Render all items
      for (let i = 0; i < getItemCount(); i++) {
        container.appendChild(renderItem(i));
      }
      return;
    }

    const state = {
      scrollTop: 0,
      containerHeight: container.clientHeight,
      visibleStart: 0,
      visibleEnd: 0
    };

    const updateVisibleItems = () => {
      state.scrollTop = container.scrollTop;
      state.containerHeight = container.clientHeight;
      
      const startIndex = Math.floor(state.scrollTop / itemHeight);
      const endIndex = Math.min(
        startIndex + Math.ceil(state.containerHeight / itemHeight) + this.config.virtualScrolling.overscan,
        getItemCount() - 1
      );

      // Clear existing items
      container.innerHTML = '';
      
      // Render visible items
      for (let i = startIndex; i <= endIndex; i++) {
        const item = renderItem(i);
        item.style.position = 'absolute';
        item.style.top = `${i * itemHeight}px`;
        item.style.height = `${itemHeight}px`;
        container.appendChild(item);
      }

      // Set container height
      container.style.height = `${getItemCount() * itemHeight}px`;
    };

    container.addEventListener('scroll', () => {
      requestAnimationFrame(updateVisibleItems);
    });

    updateVisibleItems();
    this.virtualScrollContainers.set(container, { update: updateVisibleItems });
  }

  // Image optimization
  public optimizeImageUrl(url: string, width?: number, height?: number): string {
    if (!this.config.imageOptimization.enabled) {
      return url;
    }

    const params = new URLSearchParams();
    
    if (width) params.set('w', width.toString());
    if (height) params.set('h', height.toString());
    params.set('q', Math.round(this.config.imageOptimization.quality * 100).toString());
    params.set('f', 'webp'); // Prefer webp
    
    return `${url}?${params.toString()}`;
  }

  public loadOptimizedImage(src: string): Promise<string> {
    return new Promise((resolve, reject) => {
      // Check cache first
      if (this.imageCache.has(src)) {
        resolve(this.imageCache.get(src)!);
        return;
      }

      const img = new Image();
      img.onload = () => {
        const optimizedSrc = this.optimizeImageUrl(src, img.width, img.height);
        this.imageCache.set(src, optimizedSrc);
        resolve(optimizedSrc);
      };
      img.onerror = reject;
      img.src = src;
    });
  }

  public clearImageCache(): void {
    this.imageCache.clear();
  }

  // Animation optimization
  public getOptimizedAnimationConfig(): {
    enabled: boolean;
    duration: number;
    easing: string;
    fps: number;
  } {
    return {
      enabled: this.config.animation.enabled && !this.config.animation.preferReducedMotion,
      duration: 300,
      easing: 'ease-in-out',
      fps: this.config.animation.throttle
    };
  }

  public createOptimizedAnimation(element: HTMLElement, keyframes: Keyframe[], options: AnimationOptions): Animation | null {
    if (!this.config.animation.enabled || this.config.animation.preferReducedMotion) {
      return null;
    }

    // Use GPU acceleration hints
    element.style.willChange = 'transform';
    element.style.transform = 'translateZ(0)';

    const animation = element.animate(keyframes, {
      ...options,
      duration: options.duration || 300,
      easing: options.easing || 'ease-in-out'
    });

    // Clean up willChange after animation
    animation.onfinish = () => {
      element.style.willChange = 'auto';
    };

    return animation;
  }

  // Getters
  public getMetrics(): PerformanceMetrics {
    return { ...this.metrics };
  }

  public getConfig(): PerformanceConfig {
    return { ...this.config };
  }

  public getCurrentOptimizations(): string[] {
    let optimizations: string[] = [];
    
    if (this.config.lazyLoading.enabled) optimizations.push('lazy_loading');
    if (this.config.virtualScrolling.enabled) optimizations.push('virtual_scrolling');
    if (this.config.imageOptimization.enabled) optimizations.push('image_optimization');
    if (this.config.caching.enabled) optimizations.push('caching');
    if (this.config.animation.enabled) optimizations.push('animations');
    
    return optimizations;
  }

  public updateConfig(updates: Partial<PerformanceConfig>): void {
    this.config = { ...this.config, ...updates };
    this.applyOptimizations();
  }

  public addOptimizationStrategy(strategy: OptimizationStrategy): void {
    this.strategies.push(strategy);
    this.strategies.sort((a, b) => a.priority - b.priority);
    this.updateStrategies();
  }

  public removeOptimizationStrategy(name: string): void {
    this.strategies = this.strategies.filter(s => s.name !== name);
    this.updateStrategies();
  }

  // Cleanup
  public cleanup(): void {
    this.stopMonitoring();
    
    // Clean up observers
    this.observers.forEach(observer => observer.disconnect());
    this.observers.clear();
    
    // Clean up virtual scrollers
    this.virtualScrollContainers.clear();
    
    // Clean up image cache
    this.clearImageCache();
    
    this.metricsSubject.complete();
    this.optimizationSubject.complete();
    this.strategySubject.complete();
  }
}