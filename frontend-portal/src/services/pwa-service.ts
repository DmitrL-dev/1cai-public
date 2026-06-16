/**
 * PWA (Progressive Web App) сервис
 * Обеспечивает функционал для установки приложения как PWA,
 * офлайн работу, push-уведомления и другие возможности
 */

import { useState, useEffect, useCallback } from 'react';

// Типы для PWA функционала
export interface PWAInstallPrompt {
  prompt(): Promise<void>;
  userChoice: Promise<{
    outcome: 'accepted' | 'dismissed';
    platform: string;
  }>;
}

export interface PWAManifest {
  name: string;
  short_name: string;
  description: string;
  start_url: string;
  display: 'standalone' | 'minimal-ui' | 'fullscreen' | 'browser';
  orientation: 'portrait' | 'landscape' | 'any';
  theme_color: string;
  background_color: string;
  scope: string;
  icons: PWAIcon[];
  screenshots?: PWAScreenshot[];
  categories?: string[];
  lang?: string;
  dir?: 'ltr' | 'rtl';
  shortcuts?: PWAShortcut[];
  related_applications?: PWAApp[];
  prefer_related_applications?: boolean;
}

export interface PWAIcon {
  src: string;
  sizes: string;
  type: string;
  purpose?: 'any' | 'maskable' | 'monochrome';
  platform?: string;
}

export interface PWAScreenshot {
  src: string;
  sizes: string;
  type: string;
  platform?: string;
  label?: string;
  form_factor?: 'narrow' | 'wide';
}

export interface PWAShortcut {
  name: string;
  short_name?: string;
  description?: string;
  url: string;
  icons?: PWAIcon[];
}

export interface PWAApp {
  platform: string;
  url: string;
  id?: string;
}

export interface PWAInstallStatus {
  isInstallable: boolean;
  isInstalled: boolean;
  isStandalone: boolean;
  isInStandaloneMode: boolean;
  canInstall: boolean;
  installPrompt?: PWAInstallPrompt;
  platform: string;
}

export interface PWAUpdateInfo {
  hasUpdate: boolean;
  newWorker?: ServiceWorkerRegistration;
  waitingWorker?: ServiceWorker;
  needRefresh: boolean;
  offlineReady: boolean;
  isOnline: boolean;
}

export interface PWAPushSubscription {
  endpoint: string;
  keys: {
    p256dh: string;
    auth: string;
  };
}

export interface PWAStorageEstimate {
  quota: number;
  usage: number;
  usageDetails: {
    [type: string]: number;
  };
}

export interface PWAFileSystemHandle {
  name: string;
  kind: 'file' | 'directory';
  queryPermission(descriptor?: { mode?: 'read' | 'readwrite' }): Promise<PermissionState>;
  requestPermission(descriptor?: { mode?: 'read' | 'readwrite' }): Promise<PermissionState>;
}

export interface PWANotificationOptions {
  title: string;
  body?: string;
  icon?: string;
  badge?: string;
  image?: string;
  vibrate?: number | number[];
  sound?: string;
  silent?: boolean;
  requireInteraction?: boolean;
  tag?: string;
  renotify?: boolean;
  data?: any;
  actions?: PWANotificationAction[];
  timestamp?: number;
  dir?: 'auto' | 'ltr' | 'rtl';
  lang?: string;
}

export interface PWANotificationAction {
  action: string;
  title: string;
  icon?: string;
  description?: string;
}

// Hook для работы с PWA функционалом
export function usePWA() {
  const [installStatus, setInstallStatus] = useState<PWAInstallStatus>({
    isInstallable: false,
    isInstalled: false,
    isStandalone: false,
    isInStandaloneMode: false,
    canInstall: false,
    platform: 'web'
  });

  const [updateInfo, setUpdateInfo] = useState<PWAUpdateInfo>({
    hasUpdate: false,
    needRefresh: false,
    offlineReady: false,
    isOnline: navigator.onLine
  });

  const [pushSubscription, setPushSubscription] = useState<PWAPushSubscription | null>(null);
  const [storageEstimate, setStorageEstimate] = useState<PWAStorageEstimate | null>(null);
  const [permissionState, setPermissionState] = useState<Record<string, PermissionState>>({});

  /**
   * Проверка возможности установки PWA
   */
  const checkInstallability = useCallback(() => {
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches;
    const isInStandaloneMode = (window.navigator as any).standalone === true;
    const isInstallable = 'beforeinstallprompt' in window;
    const isInstalled = isStandalone || isInStandaloneMode;
    const platform = navigator.platform || navigator.userAgent;

    setInstallStatus(prev => ({
      ...prev,
      isInstallable,
      isInstalled,
      isStandalone,
      isInStandaloneMode,
      canInstall: isInstallable && !isInstalled,
      platform
    }));

    return { isInstallable, isInstalled, isStandalone, isInStandaloneMode, platform };
  }, []);

  /**
   * Установка PWA
   */
  const installPWA = useCallback(async (): Promise<boolean> => {
    if (!installStatus.canInstall || !installStatus.installPrompt) {
      return false;
    }

    try {
      await installStatus.installPrompt.prompt();
      const { outcome } = await installStatus.installPrompt.userChoice;
      
      if (outcome === 'accepted') {
        setInstallStatus(prev => ({ ...prev, canInstall: false }));
        return true;
      }
      return false;
    } catch (error) {
      console.error('Ошибка установки PWA:', error);
      return false;
    }
  }, [installStatus]);

  /**
   * Регистрация Service Worker
   */
  const registerServiceWorker = useCallback(async (swUrl: string = '/sw.js') => {
    if (!('serviceWorker' in navigator)) {
      console.warn('Service Worker не поддерживается');
      return null;
    }

    try {
      const registration = await navigator.serviceWorker.register(swUrl);
      
      // Обновление доступности
      registration.addEventListener('updatefound', () => {
        const newWorker = registration.installing;
        if (newWorker) {
          newWorker.addEventListener('statechange', () => {
            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
              setUpdateInfo(prev => ({ ...prev, hasUpdate: true, waitingWorker: newWorker }));
            }
          });
        }
      });

      // Слушаем активацию нового Service Worker
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        window.location.reload();
      });

      return registration;
    } catch (error) {
      console.error('Ошибка регистрации Service Worker:', error);
      return null;
    }
  }, []);

  /**
   * Обновление PWA
   */
  const updateApp = useCallback(async () => {
    if (updateInfo.waitingWorker) {
      updateInfo.waitingWorker.postMessage({ type: 'SKIP_WAITING' });
      setUpdateInfo(prev => ({ ...prev, needRefresh: true }));
    }
  }, [updateInfo.waitingWorker]);

  /**
   * Проверка онлайн статуса
   */
  const handleOnlineStatus = useCallback(() => {
    setUpdateInfo(prev => ({ ...prev, isOnline: navigator.onLine }));
  }, []);

  /**
   * Подписка на push-уведомления
   */
  const subscribeToPush = useCallback(async (vapidPublicKey: string): Promise<boolean> => {
    if (!('serviceWorker' in navigator)) {
      return false;
    }

    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
      });

      setPushSubscription({
        endpoint: subscription.endpoint,
        keys: {
          p256dh: arrayBufferToBase64(subscription.getKey('p256dh')!),
          auth: arrayBufferToBase64(subscription.getKey('auth')!)
        }
      });

      return true;
    } catch (error) {
      console.error('Ошибка подписки на push-уведомления:', error);
      return false;
    }
  }, []);

  /**
   * Отписка от push-уведомлений
   */
  const unsubscribeFromPush = useCallback(async (): Promise<boolean> => {
    if (!('serviceWorker' in navigator)) {
      return false;
    }

    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      
      if (subscription) {
        await subscription.unsubscribe();
        setPushSubscription(null);
        return true;
      }
      return false;
    } catch (error) {
      console.error('Ошибка отписки от push-уведомлений:', error);
      return false;
    }
  }, []);

  /**
   * Показать уведомление
   */
  const showNotification = useCallback(async (options: PWANotificationOptions): Promise<boolean> => {
    if (!('Notification' in window)) {
      return false;
    }

    if (Notification.permission === 'default') {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        return false;
      }
    }

    if (Notification.permission === 'granted') {
      const registration = await navigator.serviceWorker.ready;
      await registration.showNotification(options.title, {
        body: options.body,
        icon: options.icon,
        badge: options.badge,
        vibrate: options.vibrate,
        data: options.data,
        tag: options.tag,
        actions: options.actions,
        timestamp: options.timestamp
      });
      return true;
    }

    return false;
  }, []);

  /**
   * Проверка доступа к хранилищу
   */
  const checkStorageAccess = useCallback(async (): Promise<boolean> => {
    try {
      if ('storage' in navigator && 'estimate' in navigator.storage) {
        const estimate = await navigator.storage.estimate();
        setStorageEstimate({
          quota: estimate.quota || 0,
          usage: estimate.usage || 0,
          usageDetails: estimate.usageDetails || {}
        });
        return true;
      }
      return false;
    } catch (error) {
      console.error('Ошибка проверки доступа к хранилищу:', error);
      return false;
    }
  }, []);

  /**
   * Запрос разрешения
   */
  const requestPermission = useCallback(async (permission: string): Promise<PermissionState> => {
    if (!('permissions' in navigator)) {
      return 'denied';
    }

    try {
      const result = await navigator.permissions.query({ name: permission as PermissionName });
      setPermissionState(prev => ({ ...prev, [permission]: result.state }));
      return result.state;
    } catch (error) {
      console.error(`Ошибка запроса разрешения ${permission}:`, error);
      return 'denied';
    }
  }, []);

  /**
   * Получение доступа к файловой системе
   */
  const getFileSystemAccess = useCallback(async (): Promise<boolean> => {
    if (!('showOpenFilePicker' in window)) {
      return false;
    }

    try {
      // Запрашиваем разрешение на доступ к файловой системе
      const permission = await navigator.permissions.query({ name: 'file-system-handle' as PermissionName });
      return permission.state === 'granted';
    } catch (error) {
      console.error('Ошибка доступа к файловой системе:', error);
      return false;
    }
  }, []);

  /**
   * Сохранение данных офлайн
   */
  const saveOfflineData = useCallback(async (key: string, data: any): Promise<boolean> => {
    try {
      if ('caches' in window) {
        const cache = await caches.open('pwa-offline-data');
        await cache.put(new Request(`/offline/${key}`), new Response(JSON.stringify(data)));
        return true;
      }
      return false;
    } catch (error) {
      console.error('Ошибка сохранения офлайн данных:', error);
      return false;
    }
  }, []);

  /**
   * Получение офлайн данных
   */
  const getOfflineData = useCallback(async (key: string): Promise<any> => {
    try {
      if ('caches' in window) {
        const cache = await caches.open('pwa-offline-data');
        const response = await cache.match(`/offline/${key}`);
        if (response) {
          return await response.json();
        }
      }
      return null;
    } catch (error) {
      console.error('Ошибка получения офлайн данных:', error);
      return null;
    }
  }, []);

  /**
   * Очистка офлайн данных
   */
  const clearOfflineData = useCallback(async (key?: string): Promise<boolean> => {
    try {
      if ('caches' in window) {
        const cache = await caches.open('pwa-offline-data');
        if (key) {
          await cache.delete(`/offline/${key}`);
        } else {
          await cache.delete(new Request('/offline/'));
        }
        return true;
      }
      return false;
    } catch (error) {
      console.error('Ошибка очистки офлайн данных:', error);
      return false;
    }
  }, []);

  // Инициализация
  useEffect(() => {
    checkInstallability();
    checkStorageAccess();

    // Обработчики событий
    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      setInstallStatus(prev => ({
        ...prev,
        canInstall: true,
        installPrompt: e as PWAInstallPrompt
      }));
    };

    const handleAppInstalled = () => {
      setInstallStatus(prev => ({
        ...prev,
        canInstall: false,
        isInstalled: true,
        installPrompt: undefined
      }));
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    window.addEventListener('appinstalled', handleAppInstalled);
    window.addEventListener('online', handleOnlineStatus);
    window.addEventListener('offline', handleOnlineStatus);

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
      window.removeEventListener('appinstalled', handleAppInstalled);
      window.removeEventListener('online', handleOnlineStatus);
      window.removeEventListener('offline', handleOnlineStatus);
    };
  }, [checkInstallability, checkStorageAccess, handleOnlineStatus]);

  return {
    // Статус установки
    installStatus,
    installPWA,
    
    // Обновления
    updateInfo,
    registerServiceWorker,
    updateApp,
    
    // Push-уведомления
    pushSubscription,
    subscribeToPush,
    unsubscribeFromPush,
    showNotification,
    
    // Хранилище
    storageEstimate,
    saveOfflineData,
    getOfflineData,
    clearOfflineData,
    
    // Разрешения
    permissionState,
    requestPermission,
    
    // Файловая система
    getFileSystemAccess,
    
    // Утилиты
    checkInstallability,
    checkStorageAccess
  };
}

// Утилитарные функции
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return window.btoa(binary);
}