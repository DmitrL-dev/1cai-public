import { BehaviorSubject } from "rxjs";
import { MobileDetectionService } from "./mobile-detection-service";

export interface ResponsiveConfig {
  enabled: boolean;
  breakpoints: {
    xs: number;
    sm: number;
    md: number;
    lg: number;
    xl: number;
    xxl: number;
  };
  animations: {
    enabled: boolean;
    duration: number;
    easing: string;
    reducedMotion: boolean;
  };
  touch: {
    minTapSize: number;
    touchTargetSize: number;
    swipeThreshold: number;
  };
  performance: {
    lazyLoading: boolean;
    virtualScrolling: boolean;
    imageOptimization: boolean;
  };
}

export interface LayoutConfig {
  columns: number;
  gap: number;
  padding: number;
  margin: number;
  typography: {
    fontSize: number;
    lineHeight: number;
    fontWeight: number;
  };
  spacing: {
    xs: number;
    sm: number;
    md: number;
    lg: number;
    xl: number;
  };
}

export interface ComponentVariant {
  id: string;
  name: string;
  breakpoint: "xs" | "sm" | "md" | "lg" | "xl" | "xxl";
  props: Record<string, any>;
  priority: number;
}

// Тип для совместимости с экспортами
// Тип для совместимости с экспортами

export interface ResponsiveComponent {
  id: string;
  variants: ComponentVariant[];
  defaultVariant: string;
}

export class ResponsiveUIService {
  private config: ResponsiveConfig = {
    enabled: true,
    breakpoints: {
      xs: 0,
      sm: 576,
      md: 768,
      lg: 992,
      xl: 1200,
      xxl: 1400,
    },
    animations: {
      enabled: true,
      duration: 300,
      easing: "ease-in-out",
      reducedMotion: false,
    },
    touch: {
      minTapSize: 44,
      touchTargetSize: 48,
      swipeThreshold: 50,
    },
    performance: {
      lazyLoading: true,
      virtualScrolling: true,
      imageOptimization: true,
    },
  };

  private responsiveComponents = new Map<string, ResponsiveComponent>();
  private layoutCache = new Map<string, LayoutConfig>();

  // State subjects
  private currentBreakpointSubject = new BehaviorSubject<string>("md");
  private layoutConfigSubject = new BehaviorSubject<LayoutConfig | null>(null);
  private touchEnabledSubject = new BehaviorSubject<boolean>(false);

  // Observables
  public currentBreakpoint$ = this.currentBreakpointSubject.asObservable();
  public layoutConfig$ = this.layoutConfigSubject.asObservable();
  public touchEnabled$ = this.touchEnabledSubject.asObservable();

  constructor(private mobileDetection: MobileDetectionService) {
    this.initializeService();
  }

  private initializeService(): void {
    // Подписка на изменения устройства
    this.mobileDetection.deviceInfo$.subscribe((device) => {
      if (device) {
        this.handleDeviceChange(device);
      }
    });

    // Подписка на изменения ориентации
    this.mobileDetection.orientation$.subscribe((orientation) => {
      this.handleOrientationChange(orientation);
    });

    // Подписка на изменения viewport
    this.mobileDetection.viewport$.subscribe((viewport) => {
      if (viewport) {
        this.handleViewportChange(viewport);
      }
    });

    // Подписка на предпочтения доступности
    this.mobileDetection.preferences$.subscribe((preferences) => {
      if (preferences) {
        this.handleAccessibilityPreferences(preferences.accessibility);
      }
    });

    // Первоначальная настройка
    this.updateCurrentBreakpoint();
    this.updateLayoutConfig();
    this.updateTouchSettings();
  }

  private handleDeviceChange(device: any): void {
    // Обновление конфигурации на основе устройства
    this.updateBreakpointConfigForDevice(device.type);
    this.updateTouchSettings();
  }

  private handleOrientationChange(orientation: "portrait" | "landscape"): void {
    // Пересчет layout при изменении ориентации
    this.updateLayoutConfig();
  }

  private handleViewportChange(viewport: {
    width: number;
    height: number;
  }): void {
    // Обновление breakpoint при изменении viewport
    this.updateCurrentBreakpoint();
    this.updateLayoutConfig();
  }

  private handleAccessibilityPreferences(accessibility: any): void {
    // Обновление анимаций для accessibility
    this.config.animations.reducedMotion = accessibility.reducedMotion;

    if (accessibility.highContrast) {
      this.applyHighContrastMode(true);
    }
  }

  private updateCurrentBreakpoint(): void {
    const breakpoint = this.getCurrentBreakpoint();
    this.currentBreakpointSubject.next(breakpoint);
  }

  private updateLayoutConfig(): void {
    const device = this.mobileDetection.getDeviceInfo();
    const breakpoint = this.getCurrentBreakpoint();

    const layoutConfig = this.generateLayoutConfig(device.type, breakpoint);
    this.layoutConfigSubject.next(layoutConfig);

    // Кэширование конфигурации
    const cacheKey = `${device.type}_${breakpoint}`;
    this.layoutCache.set(cacheKey, layoutConfig);
  }

  private updateTouchSettings(): void {
    const touchEnabled = this.mobileDetection.supportsTouch();
    this.touchEnabledSubject.next(touchEnabled);
  }

  private updateBreakpointConfigForDevice(deviceType: string): void {
    // Настройка breakpoints для мобильных устройств
    if (deviceType === "mobile") {
      this.config.breakpoints.sm = 480; // Меньший breakpoint для мобильных
      this.config.breakpoints.md = 768;
    } else if (deviceType === "tablet") {
      this.config.breakpoints.md = 768;
      this.config.breakpoints.lg = 1024;
    }
  }

  private generateLayoutConfig(
    deviceType: string,
    breakpoint: string
  ): LayoutConfig {
    const baseConfig = this.getBaseLayoutConfig();

    // Адаптация под тип устройства и breakpoint
    switch (deviceType) {
      case "mobile":
        return this.adaptLayoutForMobile(baseConfig, breakpoint);
      case "tablet":
        return this.adaptLayoutForTablet(baseConfig, breakpoint);
      case "desktop":
        return this.adaptLayoutForDesktop(baseConfig, breakpoint);
      default:
        return baseConfig;
    }
  }

  private getBaseLayoutConfig(): LayoutConfig {
    return {
      columns: 12,
      gap: 16,
      padding: 16,
      margin: 16,
      typography: {
        fontSize: 16,
        lineHeight: 1.5,
        fontWeight: 400,
      },
      spacing: {
        xs: 4,
        sm: 8,
        md: 16,
        lg: 24,
        xl: 32,
      },
    };
  }

  private adaptLayoutForMobile(
    config: LayoutConfig,
    breakpoint: string
  ): LayoutConfig {
    const multiplier = breakpoint === "xs" ? 0.8 : 1;

    return {
      ...config,
      columns: breakpoint === "xs" ? 4 : 6,
      gap: config.gap * multiplier,
      padding: config.padding * multiplier,
      margin: config.margin * multiplier,
      typography: {
        ...config.typography,
        fontSize: config.typography.fontSize * multiplier,
      },
      spacing: Object.fromEntries(
        Object.entries(config.spacing).map(([key, value]) => [
          key,
          Math.round(value * multiplier),
        ])
      ) as LayoutConfig["spacing"],
    };
  }

  private adaptLayoutForTablet(
    config: LayoutConfig,
    breakpoint: string
  ): LayoutConfig {
    return {
      ...config,
      columns: breakpoint === "md" ? 8 : 12,
      gap: config.gap * 1.1,
      padding: config.padding * 1.1,
    };
  }

  private adaptLayoutForDesktop(
    config: LayoutConfig,
    breakpoint: string
  ): LayoutConfig {
    return {
      ...config,
      columns: 12,
      gap: config.gap * 1.2,
      padding: config.padding * 1.2,
      typography: {
        ...config.typography,
        fontSize: config.typography.fontSize * 1.1,
      },
    };
  }

  private getCurrentBreakpoint(): string {
    const device = this.mobileDetection.getDeviceInfo();
    const width = device.viewportSize.width;

    if (width < this.config.breakpoints.sm) return "xs";
    if (width < this.config.breakpoints.md) return "sm";
    if (width < this.config.breakpoints.lg) return "md";
    if (width < this.config.breakpoints.xl) return "lg";
    if (width < this.config.breakpoints.xxl) return "xl";
    return "xxl";
  }

  // Публичные методы для работы с компонентами
  public registerResponsiveComponent(component: ResponsiveComponent): void {
    this.responsiveComponents.set(component.id, component);
  }

  public getComponentVariant(
    componentId: string,
    customBreakpoint?: string
  ): ComponentVariant | null {
    const component = this.responsiveComponents.get(componentId);
    if (!component) return null;

    const breakpoint = customBreakpoint || this.getCurrentBreakpoint();

    // Поиск точного match
    let variant = component.variants.find((v) => v.breakpoint === breakpoint);

    // Если нет точного match, ищем лучший fallback
    if (!variant) {
      const breakpointOrder: string[] = ["xxl", "xl", "lg", "md", "sm", "xs"];
      const currentIndex = breakpointOrder.indexOf(breakpoint);

      for (let i = currentIndex; i < breakpointOrder.length; i++) {
        const fallback = breakpointOrder[i];
        variant = component.variants.find((v) => v.breakpoint === fallback);
        if (variant) break;
      }
    }

    // Если ничего не найдено, возвращаем default
    if (!variant) {
      variant =
        component.variants.find((v) => v.id === component.defaultVariant) ||
        component.variants[0];
    }

    return variant || null;
  }

  public getLayoutClasses(
    breakpoint?: string,
    deviceType?: string
  ): Record<string, string> {
    const bp = breakpoint || this.getCurrentBreakpoint();
    const device = deviceType || this.mobileDetection.getDeviceInfo().type;

    const classes: Record<string, string> = {
      container: `container mx-auto px-${this.getSpacing("md")}`,
      grid: "grid gap-4",
      flex: "flex items-center",
    };

    // Генерация классов для разных breakpoints
    switch (bp) {
      case "xs":
        classes.columns = "grid-cols-2";
        classes.flexDirection = "flex-col";
        break;
      case "sm":
        classes.columns = device === "mobile" ? "grid-cols-3" : "grid-cols-4";
        classes.flexDirection = device === "mobile" ? "flex-col" : "flex-row";
        break;
      case "md":
        classes.columns = device === "tablet" ? "grid-cols-6" : "grid-cols-8";
        classes.flexDirection = "flex-row";
        break;
      case "lg":
      case "xl":
      case "xxl":
        classes.columns = "grid-cols-12";
        classes.flexDirection = "flex-row";
        break;
    }

    return classes;
  }

  public getSpacing(size: "xs" | "sm" | "md" | "lg" | "xl"): string {
    const layoutConfig = this.layoutCache.get(
      `${
        this.mobileDetection.getDeviceInfo().type
      }_${this.getCurrentBreakpoint()}`
    );
    const spacing = layoutConfig?.spacing[size] || 16;
    return `${spacing}px`;
  }

  public getFontSize(base: number = 16): number {
    const layoutConfig = this.layoutCache.get(
      `${
        this.mobileDetection.getDeviceInfo().type
      }_${this.getCurrentBreakpoint()}`
    );
    return layoutConfig
      ? Math.round((base * layoutConfig.typography.fontSize) / 16)
      : base;
  }

  public shouldUseCompactMode(): boolean {
    const device = this.mobileDetection.getDeviceInfo();
    const preferences = this.mobileDetection.getPreferences();

    return preferences.compactMode || device.type === "mobile";
  }

  public shouldOptimizeForTouch(): boolean {
    return this.mobileDetection.supportsTouch();
  }

  public getTouchTargetSize(): number {
    return this.config.touch.touchTargetSize;
  }

  public getMinTapSize(): number {
    return this.config.touch.minTapSize;
  }

  public shouldLazyLoad(): boolean {
    return this.config.performance.lazyLoading;
  }

  public shouldUseVirtualScrolling(): boolean {
    return this.config.performance.virtualScrolling;
  }

  public getAnimationConfig(): {
    enabled: boolean;
    duration: number;
    easing: string;
    reducedMotion: boolean;
  } {
    return this.config.animations;
  }

  // Утилиты для CSS-in-JS
  public getResponsiveStyles(
    styles: Record<string, any>,
    breakpoint?: string
  ): Record<string, any> {
    const bp = breakpoint || this.getCurrentBreakpoint();
    const responsiveStyles: Record<string, any> = {};

    // Базовые стили для мобильных
    Object.keys(styles).forEach((key) => {
      if (typeof styles[key] === "object" && styles[key] !== null) {
        // Сложные стили с адаптацией
        responsiveStyles[key] = this.resolveResponsiveValue(styles[key], bp);
      } else {
        // Простые стили
        responsiveStyles[key] = styles[key];
      }
    });

    return responsiveStyles;
  }

  private resolveResponsiveValue(value: any, breakpoint: string): any {
    if (typeof value === "object" && value !== null) {
      // Адаптивные значения
      const responsiveValue = value[breakpoint] || value.md || value.base;
      return responsiveValue;
    }
    return value;
  }

  public generateMediaQuery(
    breakpoint: string,
    styles: Record<string, any>
  ): string {
    const query = `@media (min-width: ${this.config.breakpoints[breakpoint]}px)`;
    const styleString = Object.entries(styles)
      .map(([property, value]) => `${property}: ${value};`)
      .join(" ");
    return `${query} { ${styleString} }`;
  }

  // Управление производительностью
  public optimizeForPerformance(): void {
    // Включение оптимизаций для слабых устройств
    const device = this.mobileDetection.getDeviceInfo();

    if (
      device.performance.connectionSpeed === "slow" ||
      device.performance.memory < 2
    ) {
      this.config.performance.lazyLoading = true;
      this.config.animations.enabled = false;
    }
  }

  public applyHighContrastMode(enabled: boolean): void {
    // Применение режима высокой контрастности
    document.documentElement.classList.toggle("high-contrast", enabled);
  }

  public updateConfig(updates: Partial<ResponsiveConfig>): void {
    this.config = { ...this.config, ...updates };

    // Пересчет конфигурации
    this.updateCurrentBreakpoint();
    this.updateLayoutConfig();
  }

  public getConfig(): ResponsiveConfig {
    return { ...this.config };
  }

  // Кэширование и оптимизация
  public getCachedLayoutConfig(
    deviceType: string,
    breakpoint: string
  ): LayoutConfig | null {
    const cacheKey = `${deviceType}_${breakpoint}`;
    return this.layoutCache.get(cacheKey) || null;
  }

  public clearCache(): void {
    this.layoutCache.clear();
    this.updateLayoutConfig();
  }

  public cleanup(): void {
    this.currentBreakpointSubject.complete();
    this.layoutConfigSubject.complete();
    this.touchEnabledSubject.complete();
    this.layoutCache.clear();
    this.responsiveComponents.clear();
  }
}

// Дополнительный класс BreakpointManager для обратной совместимости
export class BreakpointManager {
  private service: ResponsiveUIService;

  constructor(service: ResponsiveUIService) {
    this.service = service;
  }

  getCurrentBreakpoint(): string {
    const device = this.service["mobileDetection"].getDeviceInfo();
    const width = device.viewportSize.width;

    if (width < 576) return "xs";
    if (width < 768) return "sm";
    if (width < 992) return "md";
    if (width < 1200) return "lg";
    if (width < 1400) return "xl";
    return "xxl";
  }

  getBreakpointClasses(): Record<string, string> {
    return this.service.getLayoutClasses();
  }

  isBreakpointActive(breakpoint: string): boolean {
    return this.getCurrentBreakpoint() === breakpoint;
  }

  getSpacing(size: "xs" | "sm" | "md" | "lg" | "xl"): string {
    return this.service.getSpacing(size);
  }

  shouldUseCompactMode(): boolean {
    return this.service.shouldUseCompactMode();
  }

  shouldOptimizeForTouch(): boolean {
    return this.service.shouldOptimizeForTouch();
  }

  onBreakpointChange(callback: (breakpoint: string) => void): () => void {
    const subscription = this.service.currentBreakpoint$.subscribe(callback);
    return () => subscription.unsubscribe();
  }
}
