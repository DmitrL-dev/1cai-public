import { BehaviorSubject, Observable } from 'rxjs';
import { MobileDetectionService } from './mobile-detection-service';
import { TouchInteractionService } from './touch-interaction-service';

export interface NavigationItem {
  id: string;
  label: string;
  icon?: string;
  path: string;
  badge?: number | string;
  disabled?: boolean;
  separator?: boolean;
  children?: NavigationItem[];
  permissions?: string[];
  onSelect?: (item: NavigationItem) => void;
}

export interface NavigationConfig {
  enabled: boolean;
  style: 'bottom-tabs' | 'side-drawer' | 'floating' | 'hybrid';
  showLabels: boolean;
  compactMode: boolean;
  autoHide: boolean;
  hideOnScroll: boolean;
  gestureNavigation: boolean;
  maxItems: number;
  animation: {
    enabled: boolean;
    duration: number;
    easing: string;
  };
}

export interface NavigationState {
  isVisible: boolean;
  isMinimized: boolean;
  currentRoute: string;
  activeItem: string | null;
  drawerOpen: boolean;
  tabIndex: number;
}

export class MobileNavigationService {
  private config: NavigationConfig = {
    enabled: true,
    style: 'bottom-tabs',
    showLabels: true,
    compactMode: false,
    autoHide: false,
    hideOnScroll: true,
    gestureNavigation: true,
    maxItems: 5,
    animation: {
      enabled: true,
      duration: 300,
      easing: 'ease-in-out'
    }
  };

  private navigationItems: NavigationItem[] = [];
  private currentState: NavigationState = {
    isVisible: true,
    isMinimized: false,
    currentRoute: '/',
    activeItem: null,
    drawerOpen: false,
    tabIndex: 0
  };

  // Subjects
  private stateSubject = new BehaviorSubject<NavigationState | null>(null);
  private activeItemSubject = new BehaviorSubject<string | null>(null);
  private drawerStateSubject = new BehaviorSubject<boolean>(false);
  private visibilitySubject = new BehaviorSubject<boolean>(true);
  
  // Observables
  public state$ = this.stateSubject.asObservable();
  public activeItem$ = this.activeItemSubject.asObservable();
  public drawerState$ = this.drawerStateSubject.asObservable();
  public visibility$ = this.visibilitySubject.asObservable();

  private scrollPosition = 0;
  private lastScrollPosition = 0;
  private hideTimer: NodeJS.Timeout | null = null;

  constructor(
    private mobileDetection: MobileDetectionService,
    private touchInteraction: TouchInteractionService
  ) {
    this.initializeService();
  }

  private initializeService(): void {
    // Подписка на изменения устройства
    this.mobileDetection.deviceInfo$.subscribe(device => {
      if (device) {
        this.adaptToDevice(device.type);
      }
    });

    // Подписка на изменения ориентации
    this.mobileDetection.orientation$.subscribe(orientation => {
      this.handleOrientationChange(orientation);
    });

    // Подписка на gesture события
    this.touchInteraction.gesture$.subscribe(gesture => {
      if (gesture && this.config.gestureNavigation) {
        this.handleGesture(gesture);
      }
    });

    // Подписка на прокрутку страницы
    if (typeof window !== 'undefined') {
      window.addEventListener('scroll', this.handleScroll.bind(this), { passive: true });
    }

    // Инициализация навигации
    this.initializeDefaultNavigation();
    this.updateState();
  }

  private adaptToDevice(deviceType: string): void {
    switch (deviceType) {
      case 'mobile':
        this.config.style = 'bottom-tabs';
        this.config.showLabels = true;
        this.config.compactMode = true;
        this.config.maxItems = 5;
        break;
      case 'tablet':
        this.config.style = 'side-drawer';
        this.config.showLabels = true;
        this.config.compactMode = false;
        this.config.maxItems = 8;
        break;
      case 'desktop':
        this.config.style = 'side-drawer';
        this.config.showLabels = true;
        this.config.compactMode = false;
        this.config.maxItems = 12;
        break;
    }
    
    this.updateState();
  }

  private handleOrientationChange(orientation: 'portrait' | 'landscape'): void {
    // Адаптация навигации при изменении ориентации
    if (orientation === 'landscape' && this.mobileDetection.getDeviceInfo().type === 'mobile') {
      this.config.style = 'side-drawer';
      this.config.compactMode = true;
    } else if (orientation === 'portrait' && this.mobileDetection.getDeviceInfo().type === 'mobile') {
      this.config.style = 'bottom-tabs';
    }
    
    this.updateState();
  }

  private handleGesture(gesture: any): void {
    switch (gesture.type) {
      case 'swipe':
        this.handleSwipeGesture(gesture);
        break;
      case 'tap':
        this.handleTapGesture(gesture);
        break;
      case 'pinch':
        this.handlePinchGesture(gesture);
        break;
    }
  }

  private handleSwipeGesture(gesture: any): void {
    const { direction, touches } = gesture;
    
    // Swipe снизу для показа навигации на мобильных
    if (direction === 'up' && this.mobileDetection.isMobile()) {
      this.showNavigation();
    }
    
    // Swipe влево/вправо для переключения табов
    if (direction === 'left' || direction === 'right') {
      this.navigateBySwipe(direction);
    }
  }

  private handleTapGesture(gesture: any): void {
    const { touches } = gesture;
    if (touches.length === 1) {
      // Tap для переключения табов
      this.handleTabTap(touches[0]);
    }
  }

  private handlePinchGesture(gesture: any): void {
    // Pinch для показа/скрытия навигации
    if (gesture.scale < 0.8) {
      this.hideNavigation();
    } else if (gesture.scale > 1.2) {
      this.showNavigation();
    }
  }

  private handleScroll(): void {
    const currentScroll = window.scrollY;
    
    if (this.config.hideOnScroll) {
      if (currentScroll > this.lastScrollPosition && currentScroll > 100) {
        // Прокрутка вниз - скрываем навигацию
        this.hideNavigation();
      } else if (currentScroll < this.lastScrollPosition) {
        // Прокрутка вверх - показываем навигацию
        this.showNavigation();
      }
    }
    
    this.lastScrollPosition = currentScroll;
  }

  private handleTabTap(touch: any): void {
    // Определение таба по позиции касания
    if (this.config.style === 'bottom-tabs') {
      this.selectTabByPosition(touch.x);
    }
  }

  private selectTabByPosition(x: number): void {
    const tabWidth = window.innerWidth / this.config.maxItems;
    const tabIndex = Math.floor(x / tabWidth);
    
    if (tabIndex >= 0 && tabIndex < this.navigationItems.length) {
      this.selectNavigationItem(this.navigationItems[tabIndex].id);
    }
  }

  private navigateBySwipe(direction: 'left' | 'right'): void {
    if (this.config.style === 'bottom-tabs') {
      if (direction === 'left' && this.currentState.tabIndex < this.navigationItems.length - 1) {
        this.currentState.tabIndex++;
        this.selectNavigationItem(this.navigationItems[this.currentState.tabIndex].id);
      } else if (direction === 'right' && this.currentState.tabIndex > 0) {
        this.currentState.tabIndex--;
        this.selectNavigationItem(this.navigationItems[this.currentState.tabIndex].id);
      }
    }
  }

  private initializeDefaultNavigation(): void {
    this.navigationItems = [
      {
        id: 'home',
        label: 'Главная',
        icon: 'home',
        path: '/',
        permissions: ['read']
      },
      {
        id: 'agents',
        label: 'Агенты',
        icon: 'users',
        path: '/agents',
        permissions: ['read'],
        children: [
          {
            id: 'architect',
            label: 'Архитектор',
            icon: 'building',
            path: '/agents/architect'
          },
          {
            id: 'developer',
            label: 'Разработчик',
            icon: 'code',
            path: '/agents/developer'
          },
          {
            id: 'pm',
            label: 'Менеджер проектов',
            icon: 'clipboard',
            path: '/agents/pm'
          },
          {
            id: 'ba',
            label: 'Бизнес-аналитик',
            icon: 'trending-up',
            path: '/agents/ba'
          },
          {
            id: 'data_analyst',
            label: 'Аналитик данных',
            icon: 'bar-chart',
            path: '/agents/data-analyst'
          }
        ]
      },
      {
        id: 'tasks',
        label: 'Задачи',
        icon: 'check-square',
        path: '/tasks',
        badge: 3,
        permissions: ['read']
      },
      {
        id: 'projects',
        label: 'Проекты',
        icon: 'folder',
        path: '/projects',
        permissions: ['read']
      },
      {
        id: 'settings',
        label: 'Настройки',
        icon: 'settings',
        path: '/settings',
        permissions: ['admin']
      }
    ];
    
    this.updateState();
  }

  public setNavigationItems(items: NavigationItem[]): void {
    this.navigationItems = items;
    this.updateState();
  }

  public addNavigationItem(item: NavigationItem): void {
    this.navigationItems.push(item);
    this.updateState();
  }

  public removeNavigationItem(itemId: string): void {
    this.navigationItems = this.navigationItems.filter(item => item.id !== itemId);
    this.updateState();
  }

  public updateNavigationItem(itemId: string, updates: Partial<NavigationItem>): void {
    const index = this.navigationItems.findIndex(item => item.id === itemId);
    if (index >= 0) {
      this.navigationItems[index] = { ...this.navigationItems[index], ...updates };
      this.updateState();
    }
  }

  public selectNavigationItem(itemId: string): void {
    const item = this.findNavigationItem(itemId);
    if (item && !item.disabled) {
      this.currentState.activeItem = itemId;
      this.currentState.currentRoute = item.path;
      
      // Обновление индекса таба
      const tabIndex = this.navigationItems.findIndex(navItem => navItem.id === itemId);
      if (tabIndex >= 0) {
        this.currentState.tabIndex = tabIndex;
      }
      
      this.activeItemSubject.next(itemId);
      this.updateState();
      
      // Вызов callback если установлен
      if (item.onSelect) {
        item.onSelect(item);
      }
    }
  }

  public showNavigation(): void {
    this.currentState.isVisible = true;
    this.visibilitySubject.next(true);
    
    // Очистка таймера автоскрытия
    if (this.hideTimer) {
      clearTimeout(this.hideTimer);
      this.hideTimer = null;
    }
    
    this.updateState();
  }

  public hideNavigation(): void {
    this.currentState.isVisible = false;
    this.visibilitySubject.next(false);
    
    if (this.config.autoHide) {
      this.hideTimer = setTimeout(() => {
        this.currentState.isMinimized = true;
        this.updateState();
      }, this.config.animation.duration);
    }
    
    this.updateState();
  }

  public toggleNavigation(): void {
    if (this.currentState.isVisible) {
      this.hideNavigation();
    } else {
      this.showNavigation();
      this.currentState.isMinimized = false;
    }
  }

  public toggleDrawer(): void {
    this.currentState.drawerOpen = !this.currentState.drawerOpen;
    this.drawerStateSubject.next(this.currentState.drawerOpen);
    this.updateState();
  }

  public closeDrawer(): void {
    this.currentState.drawerOpen = false;
    this.drawerStateSubject.next(false);
    this.updateState();
  }

  public openDrawer(): void {
    this.currentState.drawerOpen = true;
    this.drawerStateSubject.next(true);
    this.updateState();
  }

  public minimizeNavigation(): void {
    this.currentState.isMinimized = true;
    this.updateState();
  }

  public maximizeNavigation(): void {
    this.currentState.isMinimized = false;
    this.updateState();
  }

  private findNavigationItem(itemId: string, items?: NavigationItem[]): NavigationItem | null {
    const searchItems = items || this.navigationItems;
    
    for (const item of searchItems) {
      if (item.id === itemId) {
        return item;
      }
      if (item.children) {
        const found = this.findNavigationItem(itemId, item.children);
        if (found) return found;
      }
    }
    
    return null;
  }

  private updateState(): void {
    this.stateSubject.next({ ...this.currentState });
  }

  // Геттеры
  public getNavigationItems(): NavigationItem[] {
    return [...this.navigationItems];
  }

  public getVisibleNavigationItems(): NavigationItem[] {
    return this.navigationItems.filter(item => !item.disabled);
  }

  public getActiveNavigationItem(): NavigationItem | null {
    return this.findNavigationItem(this.currentState.activeItem || '');
  }

  public getCurrentRoute(): string {
    return this.currentState.currentRoute;
  }

  public getCurrentState(): NavigationState {
    return { ...this.currentState };
  }

  public getConfig(): NavigationConfig {
    return { ...this.config };
  }

  public updateConfig(updates: Partial<NavigationConfig>): void {
    this.config = { ...this.config, ...updates };
    this.updateState();
  }

  // Утилиты для стилей и классов
  public getNavigationClasses(): Record<string, string> {
    const classes: Record<string, string> = {
      container: 'fixed bottom-0 left-0 right-0 z-50 bg-white border-t border-gray-200',
      drawer: 'fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-gray-200 transform transition-transform duration-300',
      floating: 'fixed bottom-4 right-4 z-50 bg-white rounded-full shadow-lg',
      hybrid: ''
    };

    // Добавление модификаторов видимости
    if (!this.currentState.isVisible) {
      classes.container += ' translate-y-full';
      classes.drawer += ' -translate-x-full';
    }

    if (this.currentState.isMinimized) {
      classes.container += ' transform scale-75';
    }

    // Адаптация под устройство
    if (this.mobileDetection.isMobile()) {
      classes.container += ' safe-area-bottom';
    }

    return classes;
  }

  public getTabClasses(index: number): Record<string, string> {
    const isActive = index === this.currentState.tabIndex;
    const isActiveItem = this.navigationItems[index]?.id === this.currentState.activeItem;
    
    return {
      tab: `flex flex-col items-center justify-center p-2 transition-colors duration-200 ${
        (isActive || isActiveItem) 
          ? 'text-primary bg-primary/10' 
          : 'text-gray-600 hover:text-gray-900'
      } ${this.config.compactMode ? 'py-1' : 'py-2'}`,
      icon: this.config.compactMode ? 'h-4 w-4' : 'h-5 w-5',
      label: this.config.showLabels 
        ? `${this.config.compactMode ? 'text-xs' : 'text-sm'} mt-1`
        : 'hidden'
    };
  }

  public shouldShowNavigation(): boolean {
    const device = this.mobileDetection.getDeviceInfo();
    
    // На десктопе всегда показываем боковую навигацию
    if (device.type === 'desktop') {
      return true;
    }
    
    // На мобильных - по конфигурации
    return this.config.enabled && this.currentState.isVisible;
  }

  public getBreadcrumb(): NavigationItem[] {
    const breadcrumbs: NavigationItem[] = [];
    let currentItem = this.getActiveNavigationItem();
    
    while (currentItem) {
      breadcrumbs.unshift(currentItem);
      
      // Поиск родительского элемента
      currentItem = this.findParentItem(currentItem.id);
    }
    
    return breadcrumbs;
  }

  private findParentItem(itemId: string, items?: NavigationItem[]): NavigationItem | null {
    const searchItems = items || this.navigationItems;
    
    for (const item of searchItems) {
      if (item.children) {
        if (item.children.some(child => child.id === itemId)) {
          return item;
        }
        const parent = this.findParentItem(itemId, item.children);
        if (parent) return parent;
      }
    }
    
    return null;
  }

  public cleanup(): void {
    if (this.hideTimer) {
      clearTimeout(this.hideTimer);
    }
    
    if (typeof window !== 'undefined') {
      window.removeEventListener('scroll', this.handleScroll.bind(this));
    }
    
    this.stateSubject.complete();
    this.activeItemSubject.complete();
    this.drawerStateSubject.complete();
    this.visibilitySubject.complete();
  }
}