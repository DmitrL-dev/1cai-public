import { BehaviorSubject, Observable } from 'rxjs';

// Namespace для кастомных touch событий, чтобы избежать конфликта с DOM TouchEvent
export namespace AppTouchEvent {
  export interface TouchEvent {
    type: 'touchstart' | 'touchmove' | 'touchend' | 'touchcancel' | 'tap' | 'swipe' | 'pinch' | 'rotate' | 'longpress';
    id: string;
    timestamp: number;
    touches: TouchPoint[];
    center?: TouchPoint;
    delta?: TouchDelta;
    scale?: number;
    rotation?: number;
    velocity?: number;
    direction?: 'left' | 'right' | 'up' | 'down';
  }

  export interface TouchPoint {
    id: number;
    x: number;
    y: number;
    force?: number;
    radiusX?: number;
    radiusY?: number;
    rotationAngle?: number;
  }

  export interface TouchDelta {
    x: number;
    y: number;
    distance: number;
    angle: number;
  }

  export interface GestureConfig {
    tapThreshold: number; // ms
    doubleTapThreshold: number; // ms
    longPressThreshold: number; // ms
    swipeThreshold: number; // pixels
    pinchThreshold: number;
    rotationThreshold: number; // degrees
    maxTapDistance: number; // pixels
    maxLongPressDistance: number; // pixels
    preventDefaultOnMove: boolean;
    passive: boolean;
  }

  export interface TouchAction {
    type: 'scroll' | 'zoom' | 'none';
    preventDefault: boolean;
    stopPropagation: boolean;
  }
}

export class TouchInteractionService {
  private config: AppTouchEvent.GestureConfig = {
    tapThreshold: 200,
    doubleTapThreshold: 300,
    longPressThreshold: 500,
    swipeThreshold: 50,
    pinchThreshold: 0.1,
    rotationThreshold: 15,
    maxTapDistance: 10,
    maxLongPressDistance: 10,
    preventDefaultOnMove: true,
    passive: false
  };

  private activeTouches = new Map<number, AppTouchEvent.TouchPoint>();
  private gestureHistory: AppTouchEvent.TouchEvent[] = [];
  private touchStartTime = 0;
  private touchStartPosition: { x: number; y: number } | null = null;
  private lastTapTime = 0;
  private lastTapPosition: { x: number; y: number } | null = null;
  private longPressTimer: NodeJS.Timeout | null = null;
  
  // Multi-touch tracking
  private pinchStartDistance = 0;
  private pinchStartScale = 1;
  private rotationStartAngle = 0;
  private isPinching = false;
  private isRotating = false;

  // Subjects
  private touchEventSubject = new BehaviorSubject<AppTouchEvent.TouchEvent | null>(null);
  private gestureSubject = new BehaviorSubject<AppTouchEvent.TouchEvent | null>(null);
  private touchActionSubject = new BehaviorSubject<AppTouchEvent.TouchAction | null>(null);
  
  // Observables
  public touchEvent$ = this.touchEventSubject.asObservable();
  public gesture$ = this.gestureSubject.asObservable();
  public touchAction$ = this.touchActionSubject.asObservable();

  // Event listeners
  private touchStartHandler: EventListener;
  private touchMoveHandler: EventListener;
  private touchEndHandler: EventListener;
  private touchCancelHandler: EventListener;

  constructor() {
    this.touchStartHandler = this.handleTouchStart.bind(this);
    this.touchMoveHandler = this.handleTouchMove.bind(this);
    this.touchEndHandler = this.handleTouchEnd.bind(this);
    this.touchCancelHandler = this.handleTouchCancel.bind(this);
    
    this.initializeTouchEvents();
  }

  private initializeTouchEvents(): void {
    if (typeof window !== 'undefined') {
      // Добавляем глобальные обработчики
      document.addEventListener('touchstart', this.touchStartHandler, { passive: this.config.passive });
      document.addEventListener('touchmove', this.touchMoveHandler, { passive: this.config.passive });
      document.addEventListener('touchend', this.touchEndHandler, { passive: this.config.passive });
      document.addEventListener('touchcancel', this.touchCancelHandler, { passive: this.config.passive });
    }
  }

  private handleTouchStart(event: globalThis.TouchEvent): void {
    event.preventDefault();
    
    this.touchStartTime = Date.now();
    this.activeTouches.clear();
    
    // Сохраняем все касания
    for (let i = 0; i < event.touches.length; i++) {
      const touch = event.touches[i];
      const point: AppTouchEvent.TouchPoint = {
        id: touch.identifier,
        x: touch.clientX,
        y: touch.clientY,
        force: touch.force,
        radiusX: touch.radiusX,
        radiusY: touch.radiusY,
        rotationAngle: touch.rotationAngle
      };
      this.activeTouches.set(touch.identifier, point);
    }

    // Сохраняем позицию для определения swipe
    if (event.touches.length > 0) {
      this.touchStartPosition = {
        x: event.touches[0].clientX,
        y: event.touches[0].clientY
      };
    }

    // Запуск long press timer для первого касания
    if (event.touches.length === 1) {
      this.startLongPressTimer();
    }

    // Инициализация для pinch и rotate
    if (event.touches.length === 2) {
      this.initializePinchAndRotate();
    }

    // Создание события touchstart
    this.emitTouchEvent('touchstart', event.touches);
  }

  private handleTouchMove(event: globalThis.TouchEvent): void {
    event.preventDefault();
    
    this.clearLongPressTimer();
    
    // Обновляем активные касания
    this.activeTouches.clear();
    for (let i = 0; i < event.touches.length; i++) {
      const touch = event.touches[i];
      const point: AppTouchEvent.TouchPoint = {
        id: touch.identifier,
        x: touch.clientX,
        y: touch.clientY,
        force: touch.force
      };
      this.activeTouches.set(touch.identifier, point);
    }

    // Обработка gesture событий
    if (this.activeTouches.size === 1) {
      this.handleSwipeGesture(event.touches[0]);
    } else if (this.activeTouches.size === 2) {
      this.handlePinchAndRotateGestures();
    }

    this.emitTouchEvent('touchmove', event.touches);
  }

  private handleTouchEnd(event: globalThis.TouchEvent): void {
    event.preventDefault();
    
    this.clearLongPressTimer();
    
    if (event.touches.length === 0) {
      // Все касания завершены
      this.processFinalGesture();
      this.activeTouches.clear();
      
      // Определение tap или swipe
      if (this.touchStartPosition) {
        const touch = event.changedTouches[0];
        const endPosition = { x: touch.clientX, y: touch.clientY };
        const distance = this.calculateDistance(this.touchStartPosition, endPosition);
        const duration = Date.now() - this.touchStartTime;
        
        if (distance < this.config.maxTapDistance && duration < this.config.tapThreshold) {
          this.processTapGesture(endPosition);
        } else if (distance >= this.config.swipeThreshold) {
          this.processSwipeGesture(touch);
        }
      }
    } else {
      // Некоторые касания продолжаются
      this.activeTouches.clear();
      for (let i = 0; i < event.touches.length; i++) {
        const touch = event.touches[i];
        this.activeTouches.set(touch.identifier, {
          id: touch.identifier,
          x: touch.clientX,
          y: touch.clientY
        });
      }
    }

    // Обновление для multi-touch
    if (event.touches.length < 2) {
      this.isPinching = false;
      this.isRotating = false;
    }

    this.emitTouchEvent('touchend', event.touches);
  }

  private handleTouchCancel(event: globalThis.TouchEvent): void {
    event.preventDefault();
    
    this.clearLongPressTimer();
    this.activeTouches.clear();
    this.isPinching = false;
    this.isRotating = false;
    
    this.emitTouchEvent('touchcancel', event.touches);
  }

  private startLongPressTimer(): void {
    this.clearLongPressTimer();
    this.longPressTimer = setTimeout(() => {
      this.processLongPressGesture();
    }, this.config.longPressThreshold);
  }

  private clearLongPressTimer(): void {
    if (this.longPressTimer) {
      clearTimeout(this.longPressTimer);
      this.longPressTimer = null;
    }
  }

  private processTapGesture(position: { x: number; y: number }): void {
    const now = Date.now();
    const isDoubleTap = 
      this.lastTapTime > 0 &&
      now - this.lastTapTime < this.config.doubleTapThreshold &&
      this.lastTapPosition &&
      this.calculateDistance(this.lastTapPosition, position) < this.config.maxTapDistance;

    const tapEvent: AppTouchEvent.TouchEvent = {
      type: 'tap',
      id: `tap_${now}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: now,
      touches: [{
        id: -1,
        x: position.x,
        y: position.y
      }]
    };

    this.gestureSubject.next(tapEvent);
    
    if (isDoubleTap) {
      this.lastTapTime = 0; // Сброс для предотвращения тройного tap
    } else {
      this.lastTapTime = now;
      this.lastTapPosition = position;
    }
  }

  private processLongPressGesture(): void {
    const longPressEvent: AppTouchEvent.TouchEvent = {
      type: 'longpress',
      id: `longpress_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: Date.now(),
      touches: this.touchStartPosition ? [{
        id: -1,
        x: this.touchStartPosition.x,
        y: this.touchStartPosition.y
      }] : []
    };

    this.gestureSubject.next(longPressEvent);
  }

  private handleSwipeGesture(touch: globalThis.Touch): void {
    if (!this.touchStartPosition) return;
    
    const currentPosition = { x: touch.clientX, y: touch.clientY };
    const delta = {
      x: currentPosition.x - this.touchStartPosition.x,
      y: currentPosition.y - this.touchStartPosition.y
    };
    
    const distance = Math.sqrt(delta.x * delta.x + delta.y * delta.y);
    
    if (distance >= this.config.swipeThreshold) {
      const swipeEvent: AppTouchEvent.TouchEvent = {
        type: 'swipe',
        id: `swipe_${Date.now()}`,
        timestamp: Date.now(),
        touches: [{
          id: touch.identifier,
          x: currentPosition.x,
          y: currentPosition.y
        }],
        delta: {
          ...delta,
          distance,
          angle: Math.atan2(delta.y, delta.x) * 180 / Math.PI
        },
        direction: this.getSwipeDirection(delta),
        velocity: distance / (Date.now() - this.touchStartTime)
      };

      this.gestureSubject.next(swipeEvent);
      
      // Решение о том, разрешить ли scroll
      const touchAction = this.determineTouchAction(swipeEvent);
      this.touchActionSubject.next(touchAction);
    }
  }

  private handlePinchAndRotateGestures(): void {
    const touches = Array.from(this.activeTouches.values());
    if (touches.length !== 2) return;
    
    const [touch1, touch2] = touches;
    const distance = this.calculateDistance(touch1, touch2);
    const angle = Math.atan2(touch2.y - touch1.y, touch2.x - touch1.x);
    
    if (!this.isPinching && !this.isRotating) {
      // Инициализация pinch и rotate
      this.pinchStartDistance = distance;
      this.pinchStartScale = 1;
      this.rotationStartAngle = angle;
      this.isPinching = true;
      this.isRotating = true;
    }
    
    const scale = distance / this.pinchStartDistance;
    const rotation = angle - this.rotationStartAngle;
    
    if (Math.abs(scale - 1) > this.config.pinchThreshold) {
      const pinchEvent: AppTouchEvent.TouchEvent = {
        type: 'pinch',
        id: `pinch_${Date.now()}`,
        timestamp: Date.now(),
        touches,
        scale,
        center: {
          id: -1,
          x: (touch1.x + touch2.x) / 2,
          y: (touch1.y + touch2.y) / 2
        }
      };
      
      this.gestureSubject.next(pinchEvent);
    }
    
    if (Math.abs(rotation * 180 / Math.PI) > this.config.rotationThreshold) {
      const rotateEvent: AppTouchEvent.TouchEvent = {
        type: 'rotate',
        id: `rotate_${Date.now()}`,
        timestamp: Date.now(),
        touches,
        rotation: rotation * 180 / Math.PI,
        center: {
          id: -1,
          x: (touch1.x + touch2.x) / 2,
          y: (touch1.y + touch2.y) / 2
        }
      };
      
      this.gestureSubject.next(rotateEvent);
    }
  }

  private processFinalGesture(): void {
    if (this.isPinching || this.isRotating) {
      this.isPinching = false;
      this.isRotating = false;
    }
  }

  private getSwipeDirection(delta: { x: number; y: number }): 'left' | 'right' | 'up' | 'down' {
    const absX = Math.abs(delta.x);
    const absY = Math.abs(delta.y);
    
    if (absX > absY) {
      return delta.x > 0 ? 'right' : 'left';
    } else {
      return delta.y > 0 ? 'down' : 'up';
    }
  }

  private determineTouchAction(event: AppTouchEvent.TouchEvent): AppTouchEvent.TouchAction {
    switch (event.type) {
      case 'swipe':
        return {
          type: 'scroll',
          preventDefault: event.velocity! > 0.5,
          stopPropagation: false
        };
      case 'pinch':
      case 'rotate':
        return {
          type: 'zoom',
          preventDefault: true,
          stopPropagation: false
        };
      case 'tap':
        return {
          type: 'none',
          preventDefault: false,
          stopPropagation: false
        };
      default:
        return {
          type: 'scroll',
          preventDefault: false,
          stopPropagation: false
        };
    }
  }

  private initializePinchAndRotate(): void {
    const touches = Array.from(this.activeTouches.values());
    if (touches.length === 2) {
      this.pinchStartDistance = this.calculateDistance(touches[0], touches[1]);
      this.rotationStartAngle = Math.atan2(
        touches[1].y - touches[0].y,
        touches[1].x - touches[0].x
      );
    }
  }

  private calculateDistance(point1: { x: number; y: number }, point2: { x: number; y: number }): number {
    const dx = point2.x - point1.x;
    const dy = point2.y - point1.y;
    return Math.sqrt(dx * dx + dy * dy);
  }

  private emitTouchEvent(type: AppTouchEvent.TouchEvent['type'], touches: TouchList): void {
    const touchPoints: AppTouchEvent.TouchPoint[] = [];
    for (let i = 0; i < touches.length; i++) {
      touchPoints.push({
        id: touches[i].identifier,
        x: touches[i].clientX,
        y: touches[i].clientY,
        force: touches[i].force
      });
    }

    const touchEvent: AppTouchEvent.TouchEvent = {
      type,
      id: `${type}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: Date.now(),
      touches: touchPoints
    };

    this.touchEventSubject.next(touchEvent);
    
    // Добавляем в историю
    this.gestureHistory.push(touchEvent);
    
    // Ограничиваем размер истории
    if (this.gestureHistory.length > 100) {
      this.gestureHistory = this.gestureHistory.slice(-100);
    }
  }

  // Публичные методы
  public getGestureHistory(): AppTouchEvent.TouchEvent[] {
    return [...this.gestureHistory];
  }

  public clearHistory(): void {
    this.gestureHistory = [];
  }

  public updateConfig(updates: Partial<AppTouchEvent.GestureConfig>): void {
    this.config = { ...this.config, ...updates };
  }

  public getConfig(): AppTouchEvent.GestureConfig {
    return { ...this.config };
  }

  public isTouchDevice(): boolean {
    return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
  }

  public enableTouchElement(element: HTMLElement): void {
    // Добавление специфичных обработчиков для элемента
    element.addEventListener('touchstart', this.handleTouchStart, { passive: this.config.passive });
    element.addEventListener('touchmove', this.handleTouchMove, { passive: this.config.passive });
    element.addEventListener('touchend', this.handleTouchEnd, { passive: this.config.passive });
    element.addEventListener('touchcancel', this.handleTouchCancel, { passive: this.config.passive });
  }

  public disableTouchElement(element: HTMLElement): void {
    // Удаление обработчиков с элемента
    element.removeEventListener('touchstart', this.handleTouchStart);
    element.removeEventListener('touchmove', this.handleTouchMove);
    element.removeEventListener('touchend', this.handleTouchEnd);
    element.removeEventListener('touchcancel', this.handleTouchCancel);
  }

  public getTouchStats(): {
    totalTouches: number;
    gestureCount: number;
    tapCount: number;
    swipeCount: number;
    pinchCount: number;
    rotateCount: number;
  } {
    const stats = {
      totalTouches: this.gestureHistory.length,
      gestureCount: this.gestureHistory.filter(e => ['tap', 'swipe', 'pinch', 'rotate'].includes(e.type)).length,
      tapCount: this.gestureHistory.filter(e => e.type === 'tap').length,
      swipeCount: this.gestureHistory.filter(e => e.type === 'swipe').length,
      pinchCount: this.gestureHistory.filter(e => e.type === 'pinch').length,
      rotateCount: this.gestureHistory.filter(e => e.type === 'rotate').length
    };

    return stats;
  }

  public cleanup(): void {
    this.clearLongPressTimer();
    
    if (typeof window !== 'undefined') {
      document.removeEventListener('touchstart', this.touchStartHandler);
      document.removeEventListener('touchmove', this.touchMoveHandler);
      document.removeEventListener('touchend', this.touchEndHandler);
      document.removeEventListener('touchcancel', this.touchCancelHandler);
    }

    this.touchEventSubject.complete();
    this.gestureSubject.complete();
    this.touchActionSubject.complete();
    this.gestureHistory = [];
  }
}