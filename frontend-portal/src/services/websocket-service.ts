import { BehaviorSubject, Observable } from 'rxjs';
import React, { useState, useEffect, useCallback, useRef } from 'react';

// Интерфейсы для WebSocket сервиса

export interface User {
  id: string;
  name: string;
  email?: string;
  avatar?: string;
  role: 'admin' | 'user' | 'guest';
  isOnline: boolean;
  lastSeen?: Date;
}

export interface ChatMessage {
  id: string;
  userId: string;
  username: string;
  content: string;
  timestamp: Date;
  type: 'text' | 'file' | 'image' | 'system';
  replyTo?: string | null;
  metadata?: Record<string, any> | null;
}

export interface SessionState {
  id: string;
  users: User[];
  messages: ChatMessage[];
  isActive: boolean;
  createdAt: Date;
  updatedAt: Date;
  metadata?: Record<string, any> | null;
}

export interface WebSocketMessage {
  type: string;
  payload: any;
  timestamp: Date;
  userId?: string | null;
  sessionId?: string | null;
}

export class WebSocketService {
  private socket: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectInterval = 1000;
  
  // State management
  private connectionStateSubject = new BehaviorSubject<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  private currentUserSubject = new BehaviorSubject<User | null>(null);
  private sessionStateSubject = new BehaviorSubject<SessionState | null>(null);
  private messagesSubject = new BehaviorSubject<ChatMessage[]>([]);
  private usersSubject = new BehaviorSubject<User[]>([]);
  
  // Public observables
  public connectionState$ = this.connectionStateSubject.asObservable();
  public currentUser$ = this.currentUserSubject.asObservable();
  public sessionState$ = this.sessionStateSubject.asObservable();
  public messages$ = this.messagesSubject.asObservable();
  public users$ = this.usersSubject.asObservable();

  constructor(private wsUrl: string) {
    // Инициализация WebSocket сервиса
  }

  /**
   * Подключение к WebSocket серверу
   */
  connect(userId: string, username: string): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.connectionStateSubject.next('connecting');
        
        this.socket = new WebSocket(this.wsUrl);
        
        this.socket.onopen = () => {
          this.connectionStateSubject.next('connected');
          this.reconnectAttempts = 0;
          
          // Отправляем приветственное сообщение
          this.sendMessage({
            type: 'user_join',
            payload: { userId, username },
            timestamp: new Date()
          });
          
          resolve();
        };
        
        this.socket.onmessage = (event) => {
          this.handleMessage(JSON.parse(event.data));
        };
        
        this.socket.onclose = () => {
          this.connectionStateSubject.next('disconnected');
          this.attemptReconnect(userId, username);
        };
        
        this.socket.onerror = (error) => {
          this.connectionStateSubject.next('error');
          reject(error);
        };
        
      } catch (error) {
        this.connectionStateSubject.next('error');
        reject(error);
      }
    });
  }

  /**
   * Отключение от WebSocket сервера
   */
  disconnect(): void {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    
    this.connectionStateSubject.next('disconnected');
    this.currentUserSubject.next(null);
    this.sessionStateSubject.next(null);
    this.messagesSubject.next([]);
    this.usersSubject.next([]);
  }

  /**
   * Отправка сообщения
   */
  sendMessage(message: WebSocketMessage): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected');
    }
  }

  /**
   * Отправка текстового сообщения в чат
   */
  sendChatMessage(content: string, type: 'text' | 'file' | 'image' = 'text', replyTo: string | null = undefined): void {
    const currentUser = this.currentUserSubject.value;
    if (!currentUser) {
      console.warn('No current user found');
      return;
    }

    const message: ChatMessage = {
      id: this.generateMessageId(),
      userId: currentUser.id,
      username: currentUser.name,
      content,
      timestamp: new Date(),
      type,
      replyTo: replyTo || undefined
    };

    this.sendMessage({
      type: 'chat_message',
      payload: message,
      timestamp: new Date(),
      userId: currentUser.id
    });

    // Локально добавляем сообщение
    this.addMessageToState(message);
  }

  /**
   * Обработка входящих сообщений
   */
  private handleMessage(message: WebSocketMessage): void {
    switch (message.type) {
      case 'user_joined':
        this.handleUserJoined(message.payload);
        break;
      case 'user_left':
        this.handleUserLeft(message.payload);
        break;
      case 'chat_message':
        this.handleChatMessage(message.payload);
        break;
      case 'session_update':
        this.handleSessionUpdate(message.payload);
        break;
      case 'typing_indicator':
        this.handleTypingIndicator(message.payload);
        break;
      default:
        console.log('Unknown message type:', message.type);
    }
  }

  private handleUserJoined(userData: any): void {
    const user: User = {
      id: userData.id,
      name: userData.name,
      email: userData.email || undefined,
      avatar: userData.avatar || undefined,
      isOnline: true,
      role: userData.role || 'user',
      lastSeen: userData.lastSeen ? new Date(userData.lastSeen) : undefined
    };

    const currentUsers = this.usersSubject.value;
    const updatedUsers = [...currentUsers.filter(u => u.id !== user.id), user];
    this.usersSubject.next(updatedUsers);

    // Добавляем системное сообщение
    this.addSystemMessage(`${user.name} присоединился к сессии`);
  }

  private handleUserLeft(userData: any): void {
    if (!userData?.id || !userData?.name) {
      console.warn('Invalid user data for left event:', userData);
      return;
    }

    const currentUsers = this.usersSubject.value;
    const updatedUsers = currentUsers.map(u => 
      u.id === userData.id ? { ...u, isOnline: false } : u
    );
    this.usersSubject.next(updatedUsers);

    // Добавляем системное сообщение
    this.addSystemMessage(`${userData.name} покинул сессию`);
  }

  private handleChatMessage(message: ChatMessage): void {
    this.addMessageToState(message);
  }

  private handleSessionUpdate(sessionData: any): void {
    // Проверяем, что все обязательные поля присутствуют
    if (!sessionData.id || !sessionData.createdAt || !sessionData.updatedAt) {
      console.error('Invalid session data:', sessionData);
      return;
    }

    const session: SessionState = {
      id: sessionData.id,
      users: Array.isArray(sessionData.users) ? sessionData.users : [],
      messages: Array.isArray(sessionData.messages) ? sessionData.messages : [],
      isActive: Boolean(sessionData.isActive),
      createdAt: new Date(sessionData.createdAt),
      updatedAt: new Date(sessionData.updatedAt),
      metadata: sessionData.metadata || undefined
    };

    this.sessionStateSubject.next(session);
    
    if (sessionData.messages) {
      this.messagesSubject.next(sessionData.messages);
    }
    
    if (sessionData.users) {
      this.usersSubject.next(sessionData.users);
    }
  }

  private handleTypingIndicator(payload: any): void {
    // Обработка индикатора набора текста
    // В реальном приложении здесь можно показать визуальный индикатор
  }

  private addMessageToState(message: ChatMessage | null): void {
    if (!message) return;
    
    const currentMessages = this.messagesSubject.value;
    this.messagesSubject.next([...currentMessages, message]);
  }

  private addSystemMessage(content: string | null): void {
    if (!content) return;
    
    const systemMessage: ChatMessage = {
      id: this.generateMessageId(),
      userId: 'system',
      username: 'Система',
      content,
      timestamp: new Date(),
      type: 'system'
    };

    this.addMessageToState(systemMessage);
  }

  private generateMessageId(): string {
    return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private attemptReconnect(userId: string, username: string): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      setTimeout(() => {
        this.reconnectAttempts++;
        this.connect(userId, username).catch(() => {
          // Рекурсивная попытка переподключения
          this.attemptReconnect(userId, username);
        });
      }, this.reconnectInterval * Math.pow(2, this.reconnectAttempts));
    }
  }

  /**
   * Создание новой сессии
   */
  createSession(): Promise<string | null> {
    return new Promise((resolve, reject) => {
      this.sendMessage({
        type: 'create_session',
        payload: {},
        timestamp: new Date()
      });

      // В реальном приложении здесь был бы обработчик ответа
      const sessionId = this.generateSessionId();
      resolve(sessionId);
    });
  }

  /**
   * Присоединение к существующей сессии
   */
  joinSession(sessionId: string | null): Promise<void> {
    if (!sessionId) {
      return Promise.reject(new Error('Session ID is required'));
    }
    
    return new Promise((resolve, reject) => {
      this.sendMessage({
        type: 'join_session',
        payload: { sessionId },
        timestamp: new Date()
      });

      resolve();
    });
  }

  private generateSessionId(): string {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Установка текущего пользователя
   */
  setCurrentUser(user: User): void {
    this.currentUserSubject.next(user);
  }

  /**
   * Получение состояния подключения
   */
  isConnected(): boolean {
    return this.connectionStateSubject.value === 'connected';
  }

  /**
   * Очистка ресурсов
   */
  cleanup(): void {
    this.disconnect();
    this.connectionStateSubject.complete();
    this.currentUserSubject.complete();
    this.sessionStateSubject.complete();
    this.messagesSubject.complete();
    this.usersSubject.complete();
  }
}

// React hook для удобного использования WebSocket в компонентах
export function useWebSocketCollaboration(wsUrl: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [currentUser, setCurrentUser] = useState<User | null>(null);

  const serviceRef = useRef<WebSocketService | null>(null);

  useEffect(() => {
    serviceRef.current = new WebSocketService(wsUrl);

    const service = serviceRef.current;
    const subscription = service.messages$.subscribe(setMessages);
    const usersSubscription = service.users$.subscribe(setUsers);
    const connectionSubscription = service.connectionState$.subscribe(state => {
      setIsConnected(state === 'connected');
    });
    const userSubscription = service.currentUser$.subscribe(setCurrentUser);

    return () => {
      subscription.unsubscribe();
      usersSubscription.unsubscribe();
      connectionSubscription.unsubscribe();
      userSubscription.unsubscribe();
      service.cleanup();
    };
  }, [wsUrl]);

  const connect = useCallback((userId: string, username: string) => {
    return serviceRef.current?.connect(userId, username);
  }, []);

  const disconnect = useCallback(() => {
    serviceRef.current?.disconnect();
  }, []);

  const sendMessage = useCallback((content: string, type: 'text' | 'file' | 'image' = 'text', replyTo: string | null = undefined) => {
    serviceRef.current?.sendChatMessage(content, type, replyTo || undefined);
  }, []);

  const createSession = useCallback(() => {
    return serviceRef.current?.createSession();
  }, []);

  const joinSession = useCallback((sessionId: string | null) => {
    return sessionId ? serviceRef.current?.joinSession(sessionId) : undefined;
  }, []);

  return {
    messages,
    users,
    isConnected,
    currentUser,
    connect,
    disconnect,
    sendMessage,
    createSession,
    joinSession
  };
}

// Вспомогательные функции
export const websocketUtils = {
  formatMessageTime: (date: Date | null): string => {
    if (!date) return '';
    return date.toLocaleTimeString('ru-RU', { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  },

  formatMessageDate: (date: Date | null): string => {
    if (!date) return '';
    const today = new Date();
    const messageDate = new Date(date);
    
    if (messageDate.toDateString() === today.toDateString()) {
      return 'Сегодня';
    }
    
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    
    if (messageDate.toDateString() === yesterday.toDateString()) {
      return 'Вчера';
    }
    
    return messageDate.toLocaleDateString('ru-RU');
  },

  getUserInitials: (name: string | null): string => {
    if (!name) return '';
    return name
      .split(' ')
      .map(word => word.charAt(0))
      .join('')
      .toUpperCase()
      .substring(0, 2);
  },

  generateAvatarColor: (userId: string | null): string => {
    if (!userId) return '#999999';
    const colors = [
      '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
      '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9'
    ];
    
    const hash = userId.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
    return colors[hash % colors.length];
  }
};

// Дефолтный экспорт экземпляра сервиса для глобального использования
export const defaultWebSocketService = new WebSocketService('ws://localhost:8080');