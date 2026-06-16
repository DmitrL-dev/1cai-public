import { BehaviorSubject, Observable } from 'rxjs';

export interface DeviceInfo {
  type: 'mobile' | 'tablet' | 'desktop';
  os: 'ios' | 'android' | 'windows' | 'macos' | 'linux' | 'unknown';
  browser: 'chrome' | 'safari' | 'firefox' | 'edge' | 'opera' | 'unknown';
  isTouchDevice: boolean;
  isLandscape: boolean;
  orientation: 'portrait' | 'landscape';
  screenSize: {
    width: number;
    height: number;
    devicePixelRatio: number;
  };
  viewportSize: {
    width: number;
    height: number;
  };
  capabilities: {
    hasCamera: boolean;
    hasMicrophone: boolean;
    hasGeolocation: boolean;
    hasVibration: boolean;
    hasNotification: boolean;
    hasServiceWorker: boolean;
    supportsWebRTC: boolean;
  };
  performance: {
    connectionSpeed: 'slow' | 'medium' | 'fast';
    memory: number; // in MB
    cores: number;
  };
}

export interface BreakpointConfig {
  xs: number; // < 576px
  sm: number; // >= 576px
  md: number; // >= 768px
  lg: number; // >= 992px
  xl: number; // >= 1200px
  xxl: number; // >= 1400px
}

export interface MobilePreferences {
  theme: 'light' | 'dark' | 'auto';
  compactMode: boolean;
  gestureNavigation: boolean;
  voiceCommands: boolean;
  notificationSettings: {
    enabled: boolean;
    sound: boolean;
    vibration: boolean;
    priority: 'low' | 'medium' | 'high';
  };
  accessibility: {
    fontSize: 'small' | 'medium' | 'large' | 'extra-large';
    highContrast: boolean;
    reducedMotion: boolean;
    screenReader: boolean;
  };
}

export class MobileDetectionService {
  private deviceInfo: DeviceInfo;
  private breakpoints: BreakpointConfig = {
    xs: 576,
    sm: 576,
    md: 768,
    lg: 992,
    xl: 1200,
    xxl: 1400
  };
  
  // Subjects для отслеживания изменений
  private deviceInfoSubject = new BehaviorSubject<DeviceInfo | null>(null);
  private orientationSubject = new BehaviorSubject<'portrait' | 'landscape'>('portrait');
  private viewportSubject = new BehaviorSubject<{ width: number; height: number } | null>(null);
  private capabilitiesSubject = new BehaviorSubject<DeviceInfo['capabilities'] | null>(null);
  
  // Observables
  public deviceInfo$ = this.deviceInfoSubject.asObservable();
  public orientation$ = this.orientationSubject.asObservable();
  public viewport$ = this.viewportSubject.asObservable();
  public capabilities$ = this.capabilitiesSubject.asObservable();

  // Предпочтения пользователя
  private preferences: MobilePreferences = {
    theme: 'auto',
    compactMode: false,
    gestureNavigation: true,
    voiceCommands: true,
    notificationSettings: {
      enabled: true,
      sound: true,
      vibration: true,
      priority: 'medium'
    },
    accessibility: {
      fontSize: 'medium',
      highContrast: false,
      reducedMotion: false,
      screenReader: false
    }
  };

  private preferencesSubject = new BehaviorSubject<MobilePreferences | null>(null);
  public preferences$ = this.preferencesSubject.asObservable();

  constructor() {
    this.deviceInfo = this.detectDevice();
    this.initializeDetection();
    this.loadPreferences();
  }

  private detectDevice(): DeviceInfo {
    const userAgent = navigator.userAgent.toLowerCase();
    const screen = window.screen;
    const viewport = {
      width: window.innerWidth,
      height: window.innerHeight
    };

    // Определение типа устройства
    const type = this.determineDeviceType(viewport.width, viewport.height);
    
    // Определение ОС
    const os = this.detectOS(userAgent);
    
    // Определение браузера
    const browser = this.detectBrowser(userAgent);
    
    // Определение возможностей
    const capabilities = this.detectCapabilities();
    
    // Определение производительности
    const performance = this.detectPerformance();

    return {
      type,
      os,
      browser,
      isTouchDevice: this.isTouchDevice(),
      isLandscape: this.isLandscape(),
      orientation: this.isLandscape() ? 'landscape' : 'portrait',
      screenSize: {
        width: screen.width,
        height: screen.height,
        devicePixelRatio: window.devicePixelRatio || 1
      },
      viewportSize: viewport,
      capabilities,
      performance
    };
  }

  private determineDeviceType(width: number, height: number): DeviceInfo['type'] {
    const maxDimension = Math.max(width, height);
    
    if (maxDimension < 768) {
      return 'mobile';
    } else if (maxDimension < 1024) {
      return 'tablet';
    } else {
      return 'desktop';
    }
  }

  private detectOS(userAgent: string): DeviceInfo['os'] {
    if (userAgent.includes('iphone') || userAgent.includes('ipad') || userAgent.includes('ipod')) {
      return 'ios';
    } else if (userAgent.includes('android')) {
      return 'android';
    } else if (userAgent.includes('windows')) {
      return 'windows';
    } else if (userAgent.includes('mac')) {
      return 'macos';
    } else if (userAgent.includes('linux')) {
      return 'linux';
    }
    return 'unknown';
  }

  private detectBrowser(userAgent: string): DeviceInfo['browser'] {
    if (userAgent.includes('chrome') && !userAgent.includes('edg')) {
      return 'chrome';
    } else if (userAgent.includes('safari') && !userAgent.includes('chrome')) {
      return 'safari';
    } else if (userAgent.includes('firefox')) {
      return 'firefox';
    } else if (userAgent.includes('edg')) {
      return 'edge';
    } else if (userAgent.includes('opera')) {
      return 'opera';
    }
    return 'unknown';
  }

  private detectCapabilities(): DeviceInfo['capabilities'] {
    return {
      hasCamera: this.checkCapability('mediaDevices'),
      hasMicrophone: this.checkCapability('mediaDevices'),
      hasGeolocation: this.checkCapability('geolocation'),
      hasVibration: 'vibrate' in navigator,
      hasNotification: 'Notification' in window,
      hasServiceWorker: 'serviceWorker' in navigator,
      supportsWebRTC: this.checkCapability('mediaDevices') && 'RTCPeerConnection' in window
    };
  }

  private detectPerformance(): DeviceInfo['performance'] {
    // Определение скорости соединения
    const connection = (navigator as any).connection;
    let connectionSpeed: 'slow' | 'medium' | 'fast' = 'medium';
    
    if (connection) {
      const effectiveType = connection.effectiveType;
      if (effectiveType === 'slow-2g' || effectiveType === '2g') {
        connectionSpeed = 'slow';
      } else if (effectiveType === '4g') {
        connectionSpeed = 'fast';
      }
    }

    // Оценка памяти (если доступно)
    let memory = 0;
    if ((navigator as any).deviceMemory) {
      memory = (navigator as any).deviceMemory;
    }

    // Количество ядер процессора
    const cores = navigator.hardwareConcurrency || 4;

    return {
      connectionSpeed,
      memory,
      cores
    };
  }

  private checkCapability(feature: string): boolean {
    switch (feature) {
      case 'mediaDevices':
        return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
      case 'geolocation':
        return 'geolocation' in navigator;
      default:
        return false;
    }
  }

  private isTouchDevice(): boolean {
    return (
      'ontouchstart' in window ||
      navigator.maxTouchPoints > 0 ||
      (navigator as any).msMaxTouchPoints > 0
    );
  }

  private isLandscape(): boolean {
    return window.innerWidth > window.innerHeight;
  }

  private initializeDetection(): void {
    // Обновление при изменении размера окна
    this.addEventListener('resize', this.handleResize.bind(this));
    
    // Обновление при изменении ориентации
    this.addEventListener('orientationchange', this.handleOrientationChange.bind(this));
    
    // Первоначальная установка
    this.updateDeviceInfo();
    this.updateOrientation();
    this.updateViewport();
    this.updateCapabilities();
    this.updatePreferences();
  }

  private handleResize(): void {
    this.updateDeviceInfo();
    this.updateViewport();
  }

  private handleOrientationChange(): void {
    this.updateOrientation();
  }

  private updateDeviceInfo(): void {
    this.deviceInfo = this.detectDevice();
    this.deviceInfoSubject.next(this.deviceInfo);
  }

  private updateOrientation(): void {
    const orientation = this.isLandscape() ? 'landscape' : 'portrait';
    this.orientationSubject.next(orientation);
  }

  private updateViewport(): void {
    const viewport = {
      width: window.innerWidth,
      height: window.innerHeight
    };
    this.viewportSubject.next(viewport);
  }

  private updateCapabilities(): void {
    this.capabilitiesSubject.next(this.deviceInfo.capabilities);
  }

  private updatePreferences(): void {
    this.preferencesSubject.next({ ...this.preferences });
  }

  // Публичные методы
  public getDeviceInfo(): DeviceInfo {
    return { ...this.deviceInfo };
  }

  public getCurrentBreakpoint(): keyof BreakpointConfig {
    const width = this.deviceInfo.viewportSize.width;
    
    if (width < this.breakpoints.xs) return 'xs';
    if (width < this.breakpoints.md) return 'sm';
    if (width < this.breakpoints.lg) return 'md';
    if (width < this.breakpoints.xl) return 'lg';
    if (width < this.breakpoints.xxl) return 'xl';
    return 'xxl';
  }

  public isBreakpoint(breakpoint: keyof BreakpointConfig): boolean {
    return this.getCurrentBreakpoint() === breakpoint;
  }

  public isSmallerThan(breakpoint: keyof BreakpointConfig): boolean {
    const currentBreakpoint = this.getCurrentBreakpoint();
    const breakpointOrder: (keyof BreakpointConfig)[] = ['xs', 'sm', 'md', 'lg', 'xl', 'xxl'];
    const currentIndex = breakpointOrder.indexOf(currentBreakpoint);
    const targetIndex = breakpointOrder.indexOf(breakpoint);
    return currentIndex < targetIndex;
  }

  public isLargerThan(breakpoint: keyof BreakpointConfig): boolean {
    const currentBreakpoint = this.getCurrentBreakpoint();
    const breakpointOrder: (keyof BreakpointConfig)[] = ['xs', 'sm', 'md', 'lg', 'xl', 'xxl'];
    const currentIndex = breakpointOrder.indexOf(currentBreakpoint);
    const targetIndex = breakpointOrder.indexOf(breakpoint);
    return currentIndex > targetIndex;
  }

  public getPreferences(): MobilePreferences {
    return { ...this.preferences };
  }

  public updatePreferences(updates: Partial<MobilePreferences>): void {
    this.preferences = { ...this.preferences, ...updates };
    this.updatePreferences();
    this.savePreferences();
  }

  public isMobile(): boolean {
    return this.deviceInfo.type === 'mobile';
  }

  public isTablet(): boolean {
    return this.deviceInfo.type === 'tablet';
  }

  public isDesktop(): boolean {
    return this.deviceInfo.type === 'desktop';
  }

  public supportsTouch(): boolean {
    return this.deviceInfo.isTouchDevice;
  }

  public isLandscapeMode(): boolean {
    return this.deviceInfo.isLandscape;
  }

  public canUseCamera(): boolean {
    return this.deviceInfo.capabilities.hasCamera;
  }

  public canUseMicrophone(): boolean {
    return this.deviceInfo.capabilities.hasMicrophone;
  }

  public canUseGeolocation(): boolean {
    return this.deviceInfo.capabilities.hasGeolocation;
  }

  public canVibrate(): boolean {
    return this.deviceInfo.capabilities.hasVibration;
  }

  public canShowNotifications(): boolean {
    return this.deviceInfo.capabilities.hasNotification;
  }

  public canUseServiceWorker(): boolean {
    return this.deviceInfo.capabilities.hasServiceWorker;
  }

  public supportsWebRTC(): boolean {
    return this.deviceInfo.capabilities.supportsWebRTC;
  }

  // Сохранение и загрузка предпочтений
  private savePreferences(): void {
    try {
      localStorage.setItem('mobile-preferences', JSON.stringify(this.preferences));
    } catch (error) {
      console.warn('Failed to save mobile preferences:', error);
    }
  }

  private loadPreferences(): void {
    try {
      const saved = localStorage.getItem('mobile-preferences');
      if (saved) {
        this.preferences = { ...this.preferences, ...JSON.parse(saved) };
      }
    } catch (error) {
      console.warn('Failed to load mobile preferences:', error);
    }
  }

  // Утилиты для событий
  private addEventListener(type: string, handler: EventListener): void {
    if (typeof window !== 'undefined') {
      window.addEventListener(type, handler);
    }
  }

  public getConnectionInfo(): {
    speed: 'slow' | 'medium' | 'fast';
    effectiveType?: string;
    downlink?: number;
    rtt?: number;
  } {
    const connection = (navigator as any).connection;
    
    if (!connection) {
      return { speed: 'medium' };
    }

    return {
      speed: this.deviceInfo.performance.connectionSpeed,
      effectiveType: connection.effectiveType,
      downlink: connection.downlink,
      rtt: connection.rtt
    };
  }

  public getBatteryInfo(): Promise<{
    level: number;
    charging: boolean;
    chargingTime: number;
    dischargingTime: number;
  } | null> {
    return new Promise((resolve) => {
      if (!('getBattery' in navigator)) {
        resolve(null);
        return;
      }

      (navigator as any).getBattery().then((battery: any) => {
        resolve({
          level: battery.level,
          charging: battery.charging,
          chargingTime: battery.chargingTime,
          dischargingTime: battery.dischargingTime
        });
      }).catch(() => {
        resolve(null);
      });
    });
  }

  public cleanup(): void {
    this.deviceInfoSubject.complete();
    this.orientationSubject.complete();
    this.viewportSubject.complete();
    this.capabilitiesSubject.complete();
    this.preferencesSubject.complete();
  }
}