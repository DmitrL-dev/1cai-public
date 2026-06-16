  // EventEmitter polyfill for browser compatibility

export interface OAuthProvider {
  id: string;
  name: string;
  authUrl: string;
  tokenUrl: string;
  clientId: string;
  scopes: string[];
  redirectUri: string;
  responseType: 'code' | 'token';
  stateRequired: boolean;
  additionalParams?: Record<string, string>;
}

export interface OAuthToken {
  accessToken: string;
  refreshToken?: string;
  tokenType: string;
  expiresIn: number;
  expiresAt: Date;
  scope?: string;
  userId?: string;
  userEmail?: string;
}

export interface OAuthConfig {
  provider: string;
  redirectUri: string;
  scopes: string[];
  state?: string;
  nonce?: string;
  prompt?: 'none' | 'consent' | 'select_account';
  accessType?: 'online' | 'offline';
  includeGrantedScopes?: boolean;
  loginHint?: string;
}

export interface OAuthSession {
  id: string;
  provider: string;
  userId?: string;
  createdAt: Date;
  lastUsed: Date;
  expiresAt: Date;
  token: OAuthToken;
  refreshAttempts: number;
  isActive: boolean;
}

export class OAuthService extends EventEmitter {
  private providers: Map<string, OAuthProvider> = new Map();
  private sessions: Map<string, OAuthSession> = new Map();
  private tokenStore: Map<string, OAuthToken> = new Map();

  constructor() {
    super();
    this.initializeDefaultProviders();
    this.loadStoredTokens();
  }

  /**
   * Регистрирует OAuth провайдера
   */
  registerProvider(provider: OAuthProvider): void {
    if (this.providers.has(provider.id)) {
      throw new Error(`Provider '${provider.id}' already registered`);
    }

    this.providers.set(provider.id, provider);
    this.emit('provider-registered', { providerId: provider.id, provider });
  }

  /**
   * Инициализирует OAuth авторизацию
   */
  initiateOAuth(config: OAuthConfig): string {
    const provider = this.providers.get(config.provider);
    if (!provider) {
      throw new Error(`OAuth provider '${config.provider}' not found`);
    }

    // Генерируем state если требуется
    let state = config.state;
    if (provider.stateRequired && !state) {
      state = this.generateState();
    }

    // Генерируем nonce если требуется
    let nonce = config.nonce || this.generateNonce();

    // Строим URL авторизации
    const authUrl = new URL(provider.authUrl);
    authUrl.searchParams.set('client_id', provider.clientId);
    authUrl.searchParams.set('response_type', provider.responseType);
    authUrl.searchParams.set('redirect_uri', config.redirectUri);
    authUrl.searchParams.set('scope', config.scopes.join(' '));
    
    if (state) authUrl.searchParams.set('state', state);
    if (nonce) authUrl.searchParams.set('nonce', nonce);
    if (config.prompt) authUrl.searchParams.set('prompt', config.prompt);
    if (config.accessType) authUrl.searchParams.set('access_type', config.accessType);
    if (config.includeGrantedScopes !== undefined) {
      authUrl.searchParams.set('include_granted_scopes', config.includeGrantedScopes.toString());
    }
    if (config.loginHint) authUrl.searchParams.set('login_hint', config.loginHint);
    
    // Дополнительные параметры провайдера
    if (provider.additionalParams) {
      Object.entries(provider.additionalParams).forEach(([key, value]) => {
        authUrl.searchParams.set(key, value);
      });
    }

    this.emit('oauth-initiated', { 
      provider: config.provider, 
      state, 
      nonce,
      authUrl: authUrl.toString()
    });

    return authUrl.toString();
  }

  /**
   * Обрабатывает callback после авторизации
   */
  async handleOAuthCallback(
    callbackUrl: string,
    state: string,
    expectedProvider: string
  ): Promise<OAuthSession> {
    try {
      const url = new URL(callbackUrl);
      const code = url.searchParams.get('code');
      const error = url.searchParams.get('error');

      if (error) {
        throw new Error(`OAuth error: ${error}`);
      }

      if (!code) {
        throw new Error('Authorization code not found in callback');
      }

      const provider = this.providers.get(expectedProvider);
      if (!provider) {
        throw new Error(`OAuth provider '${expectedProvider}' not found`);
      }

      // Обмениваем код на токен
      const token = await this.exchangeCodeForToken(provider, code, url.searchParams.get('redirect_uri') || '');
      
      // Создаем сессию
      const session = await this.createSession(expectedProvider, token, state);
      
      this.emit('oauth-success', { 
        provider: expectedProvider, 
        sessionId: session.id,
        token 
      });

      return session;

    } catch (error) {
      this.emit('oauth-error', { 
        provider: expectedProvider, 
        error: error as Error 
      });
      throw error;
    }
  }

  /**
   * Получает действительный токен для провайдера
   */
  async getValidToken(providerId: string, userId?: string): Promise<OAuthToken | null> {
    const session = this.findActiveSession(providerId, userId);
    if (!session) return null;

    // Проверяем, не истек ли токен
    if (new Date() >= session.expiresAt) {
      // Пытаемся обновить токен
      try {
        const updatedToken = await this.refreshToken(session);
        session.token = updatedToken;
        session.expiresAt = updatedToken.expiresAt;
        session.lastUsed = new Date();
        session.refreshAttempts = 0;

        this.saveSession(session);
        this.emit('token-refreshed', { 
          provider: providerId, 
          sessionId: session.id,
          token: updatedToken 
        });

        return updatedToken;

      } catch (error) {
        // Токен не удалось обновить, сессия больше не действительна
        session.isActive = false;
        this.saveSession(session);
        this.emit('token-expired', { 
          provider: providerId, 
          sessionId: session.id,
          error: error as Error 
        });
        return null;
      }
    }

    session.lastUsed = new Date();
    this.saveSession(session);
    return session.token;
  }

  /**
   * Обновляет токен
   */
  async refreshToken(session: OAuthSession): Promise<OAuthToken> {
    if (!session.token.refreshToken) {
      throw new Error('No refresh token available');
    }

    const provider = this.providers.get(session.provider);
    if (!provider) {
      throw new Error(`Provider '${session.provider}' not found`);
    }

    // Увеличиваем счетчик попыток обновления
    session.refreshAttempts++;
    if (session.refreshAttempts > 5) {
      throw new Error('Maximum refresh attempts exceeded');
    }

    try {
      const token = await this.makeTokenRequest(provider, {
        grant_type: 'refresh_token',
        refresh_token: session.token.refreshToken,
        client_id: provider.clientId
      });

      const oauthToken: OAuthToken = {
        accessToken: token.access_token,
        refreshToken: token.refresh_token || session.token.refreshToken,
        tokenType: token.token_type,
        expiresIn: token.expires_in,
        expiresAt: new Date(Date.now() + token.expires_in * 1000),
        scope: token.scope || session.token.scope,
        userId: session.token.userId,
        userEmail: session.token.userEmail
      };

      return oauthToken;

    } catch (error) {
      this.emit('token-refresh-failed', { 
        provider: session.provider, 
        sessionId: session.id,
        error: error as Error 
      });
      throw error;
    }
  }

  /**
   * Отзывает токен
   */
  async revokeToken(providerId: string, userId?: string): Promise<void> {
    const session = this.findActiveSession(providerId, userId);
    if (!session) return;

    const provider = this.providers.get(providerId);
    if (!provider) return;

    try {
      // Отзываем токен у провайдера
      await this.revokeTokenAtProvider(provider, session.token.accessToken);
      
      // Удаляем локальную сессию
      session.isActive = false;
      this.sessions.delete(session.id);
      this.tokenStore.delete(session.id);
      
      this.saveTokens();

      this.emit('token-revoked', { 
        provider: providerId, 
        sessionId: session.id 
      });

    } catch (error) {
      // Даже если отзыв у провайдера не удался, удаляем локальную сессию
      session.isActive = false;
      this.sessions.delete(session.id);
      this.tokenStore.delete(session.id);
      this.saveTokens();
      
      this.emit('token-revoke-error', { 
        provider: providerId, 
        sessionId: session.id,
        error: error as Error 
      });
    }
  }

  /**
   * Получает все активные сессии
   */
  getActiveSessions(providerId?: string): OAuthSession[] {
    let sessions = Array.from(this.sessions.values()).filter(s => s.isActive);
    
    if (providerId) {
      sessions = sessions.filter(s => s.provider === providerId);
    }
    
    return sessions;
  }

  /**
   * Получает информацию о провайдере
   */
  getProvider(providerId: string): OAuthProvider | null {
    return this.providers.get(providerId) || null;
  }

  /**
   * Получает список провайдеров
   */
  getProviders(): OAuthProvider[] {
    return Array.from(this.providers.values());
  }

  /**
   * Проверяет валидность state
   */
  validateState(state: string, expectedState: string): boolean {
    return state === expectedState;
  }

  /**
   * Экспортирует конфигурацию провайдеров
   */
  exportProvidersConfig(): string {
    const config = {
      providers: this.getProviders(),
      exportDate: new Date().toISOString()
    };
    return JSON.stringify(config, null, 2);
  }

  /**
   * Импортирует конфигурацию провайдеров
   */
  async importProvidersConfig(configJson: string): Promise<void> {
    try {
      const config = JSON.parse(configJson);
      
      if (!config.providers || !Array.isArray(config.providers)) {
        throw new Error('Invalid providers configuration format');
      }

      // Очищаем существующие провайдеры
      this.providers.clear();

      // Импортируем новые
      for (const provider of config.providers) {
        this.registerProvider(provider);
      }

      this.emit('providers-imported', { 
        importedProviders: config.providers.length 
      });

    } catch (error) {
      throw new Error(`Failed to import providers configuration: ${(error as Error).message}`);
    }
  }

  // Private methods

  private initializeDefaultProviders(): void {
    // Google OAuth2
    this.registerProvider({
      id: 'google',
      name: 'Google',
      authUrl: 'https://accounts.google.com/o/oauth2/v2/auth',
      tokenUrl: 'https://oauth2.googleapis.com/token',
      clientId: '',
      scopes: ['openid', 'email', 'profile'],
      redirectUri: '',
      responseType: 'code',
      stateRequired: true
    });

    // GitHub OAuth2
    this.registerProvider({
      id: 'github',
      name: 'GitHub',
      authUrl: 'https://github.com/login/oauth/authorize',
      tokenUrl: 'https://github.com/login/oauth/access_token',
      clientId: '',
      scopes: ['user:email', 'repo'],
      redirectUri: '',
      responseType: 'code',
      stateRequired: false,
      additionalParams: { allow_signup: 'true' }
    });

    // Microsoft OAuth2
    this.registerProvider({
      id: 'microsoft',
      name: 'Microsoft',
      authUrl: 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
      tokenUrl: 'https://login.microsoftonline.com/common/oauth2/v2.0/token',
      clientId: '',
      scopes: ['openid', 'email', 'profile', 'User.Read'],
      redirectUri: '',
      responseType: 'code',
      stateRequired: true
    });

    // Facebook OAuth2
    this.registerProvider({
      id: 'facebook',
      name: 'Facebook',
      authUrl: 'https://www.facebook.com/v18.0/dialog/oauth',
      tokenUrl: 'https://graph.facebook.com/v18.0/oauth/access_token',
      clientId: '',
      scopes: ['email', 'public_profile'],
      redirectUri: '',
      responseType: 'code',
      stateRequired: true
    });

    // LinkedIn OAuth2
    this.registerProvider({
      id: 'linkedin',
      name: 'LinkedIn',
      authUrl: 'https://www.linkedin.com/oauth/v2/authorization',
      tokenUrl: 'https://www.linkedin.com/oauth/v2/accessToken',
      clientId: '',
      scopes: ['r_liteprofile', 'r_emailaddress'],
      redirectUri: '',
      responseType: 'code',
      stateRequired: true
    });
  }

  private async exchangeCodeForToken(
    provider: OAuthProvider,
    code: string,
    redirectUri: string
  ): Promise<OAuthToken> {
    const tokenData = await this.makeTokenRequest(provider, {
      grant_type: 'authorization_code',
      code,
      redirect_uri: redirectUri,
      client_id: provider.clientId
    });

    return {
      accessToken: tokenData.access_token,
      refreshToken: tokenData.refresh_token,
      tokenType: tokenData.token_type,
      expiresIn: tokenData.expires_in,
      expiresAt: new Date(Date.now() + tokenData.expires_in * 1000),
      scope: tokenData.scope,
      userId: tokenData.user_id,
      userEmail: tokenData.user_email
    };
  }

  private async makeTokenRequest(
    provider: OAuthProvider,
    params: Record<string, string>
  ): Promise<any> {
    const response = await fetch(provider.tokenUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
      },
      body: new URLSearchParams(params)
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Token request failed: ${response.status} ${errorText}`);
    }

    const data = await response.json();
    
    if (data.error) {
      throw new Error(`OAuth error: ${data.error}`);
    }

    return data;
  }

  private async createSession(
    provider: string,
    token: OAuthToken,
    state?: string
  ): Promise<OAuthSession> {
    const sessionId = this.generateSessionId();
    const expiresAt = new Date(Date.now() + token.expiresIn * 1000);

    const session: OAuthSession = {
      id: sessionId,
      provider,
      userId: token.userId,
      createdAt: new Date(),
      lastUsed: new Date(),
      expiresAt,
      token,
      refreshAttempts: 0,
      isActive: true
    };

    this.sessions.set(sessionId, session);
    this.tokenStore.set(sessionId, token);
    this.saveTokens();

    return session;
  }

  private findActiveSession(providerId: string, userId?: string): OAuthSession | null {
    for (const session of this.sessions.values()) {
      if (session.isActive && 
          session.provider === providerId &&
          (!userId || session.userId === userId)) {
        return session;
      }
    }
    return null;
  }

  private async revokeTokenAtProvider(provider: OAuthProvider, accessToken: string): Promise<void> {
    // Большинство провайдеров не поддерживают отзыв токена через стандартный endpoint
    // Здесь можно добавить специфичную логику для каждого провайдера
    console.warn(`Token revocation not implemented for provider: ${provider.id}`);
  }

  private saveSession(session: OAuthSession): void {
    this.sessions.set(session.id, session);
    this.tokenStore.set(session.id, session.token);
    this.saveTokens();
  }

  private saveTokens(): void {
    try {
      const tokensData = Array.from(this.tokenStore.entries()).map(([id, token]) => ({
        id,
        token
      }));
      localStorage.setItem('oauth_tokens', JSON.stringify(tokensData));
    } catch (error) {
      console.error('Failed to save OAuth tokens:', error);
    }
  }

  private loadStoredTokens(): void {
    try {
      const tokensData = localStorage.getItem('oauth_tokens');
      if (tokensData) {
        const tokens = JSON.parse(tokensData);
        for (const { id, token } of tokens) {
          // Проверяем, не истек ли токен
          if (new Date(token.expiresAt) > new Date()) {
            this.tokenStore.set(id, token);
          }
        }
      }
    } catch (error) {
      console.error('Failed to load OAuth tokens:', error);
    }
  }

  private generateState(): string {
    return this.generateRandomString(32);
  }

  private generateNonce(): string {
    return this.generateRandomString(16);
  }

  private generateSessionId(): string {
    return `session_${Date.now()}_${this.generateRandomString(16)}`;
  }

  private generateRandomString(length: number): string {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    for (let i = 0; i < length; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
  }
}

export default OAuthService;