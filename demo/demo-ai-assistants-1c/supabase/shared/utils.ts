/**
 * Shared utilities for all Edge Functions
 * Provides common helper functions to eliminate code duplication
 */

export class TextAnalyzer {
  /**
   * Normalize text for analysis (lowercase, trim, remove extra spaces)
   */
  static normalize(text: string): string {
    return (text || '').toLowerCase().trim().replace(/\s+/g, ' ');
  }

  /**
   * Extract keywords from user query for matching
   */
  static extractKeywords(text: string): string[] {
    const normalized = this.normalize(text);
    // Remove common stop words and extract meaningful keywords
    const stopWords = new Set([
      'и', 'в', 'на', 'с', 'по', 'для', 'от', 'до', 'как', 'что', 'это', 'так',
      'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'
    ]);
    
    return normalized.split(' ')
      .filter(word => word.length > 2 && !stopWords.has(word));
  }

  /**
   * Check if query matches given patterns
   */
  static matchesPatterns(query: string, patterns: string[]): boolean {
    const normalizedQuery = this.normalize(query);
    return patterns.some(pattern => {
      const normalizedPattern = this.normalize(pattern);
      return normalizedQuery.includes(normalizedPattern);
    });
  }

  /**
   * Find the best matching category for a query
   */
  static categorizeQuery(query: string, categories: Record<string, string[]>): string {
    const normalizedQuery = this.normalize(query);
    let bestMatch = 'default';
    let maxScore = 0;

    for (const [category, keywords] of Object.entries(categories)) {
      const score = keywords.reduce((acc, keyword) => {
        const normalizedKeyword = this.normalize(keyword);
        return acc + (normalizedQuery.includes(normalizedKeyword) ? 1 : 0);
      }, 0);

      if (score > maxScore) {
        maxScore = score;
        bestMatch = category;
      }
    }

    return bestMatch;
  }
}

export class ResponseBuilder {
  /**
   * Build consistent response structure
   */
  static buildAnalysisResponse(
    userQuery: string, 
    analysis: any, 
    customMessage: string,
    metadata?: any
  ) {
    return {
      message: customMessage,
      analysis: analysis,
      userQuery: userQuery,
      timestamp: new Date().toISOString(),
      ...metadata
    };
  }

  /**
   * Build test cases response
   */
  static buildTestResponse(
    userQuery: string,
    testCases: any[],
    customMessage: string,
    additionalData?: any
  ) {
    return {
      message: customMessage,
      testCases: testCases,
      totalTests: testCases.length,
      userQuery: userQuery,
      ...additionalData
    };
  }

  /**
   * Build planning response
   */
  static buildPlanResponse(
    userQuery: string,
    plan: any,
    customMessage: string,
    additionalData?: any
  ) {
    return {
      message: customMessage,
      plan: plan,
      userQuery: userQuery,
      ...additionalData
    };
  }

  /**
   * Build development response
   */
  static buildCodeResponse(
    userQuery: string,
    codeResult: any,
    customMessage: string,
    metadata?: any
  ) {
    return {
      message: customMessage,
      codeResult: codeResult,
      userQuery: userQuery,
      timestamp: new Date().toISOString(),
      ...metadata
    };
  }
}

export class ValidationUtils {
  /**
   * Validate required fields in request
   */
  static validateRequiredFields(data: any, requiredFields: string[]): { isValid: boolean; errors: string[] } {
    const errors: string[] = [];

    for (const field of requiredFields) {
      if (!data[field]) {
        errors.push(`Поле "${field}" обязательно для заполнения`);
      }
    }

    return {
      isValid: errors.length === 0,
      errors
    };
  }

  /**
   * Validate demo type
   */
  static validateDemoType(demoType: string, supportedTypes: string[]): { isValid: boolean; error?: string } {
    if (!supportedTypes.includes(demoType)) {
      return {
        isValid: false,
        error: `Неподдерживаемый тип демо: ${demoType}. Поддерживаемые: ${supportedTypes.join(', ')}`
      };
    }
    return { isValid: true };
  }

  /**
   * Sanitize user input
   */
  static sanitizeInput(input: string): string {
    if (!input || typeof input !== 'string') {
      return '';
    }
    
    // Remove potentially harmful characters and normalize whitespace
    return input.trim().replace(/[\x00-\x1F\x7F]/g, '');
  }
}

export class TimeUtils {
  /**
   * Simulate processing time with progress updates
   */
  static async simulateProcessing(steps: Array<{message: string; duration: number}>): Promise<void> {
    for (const step of steps) {
      await new Promise(resolve => setTimeout(resolve, step.duration));
    }
  }

  /**
   * Format duration in human-readable format
   */
  static formatDuration(milliseconds: number): string {
    if (milliseconds < 1000) {
      return `${milliseconds}мс`;
    } else if (milliseconds < 60000) {
      return `${(milliseconds / 1000).toFixed(1)}с`;
    } else {
      return `${(milliseconds / 60000).toFixed(1)}мин`;
    }
  }

  /**
   * Get current timestamp in ISO format
   */
  static getTimestamp(): string {
    return new Date().toISOString();
  }
}

export class Constants {
  // Common demo types across all services
  static readonly DEMO_TYPES = {
    CUSTOM: 'custom',
    GENERATE: 'generate',
    ANALYSIS: 'analysis',
    DATA: 'data',
    COVERAGE: 'coverage'
  } as const;

  // Common response codes
  static readonly ERROR_CODES = {
    VALIDATION_ERROR: 'VALIDATION_ERROR',
    INVALID_REQUEST_FORMAT: 'INVALID_REQUEST_FORMAT',
    JSON_PARSE_ERROR: 'JSON_PARSE_ERROR',
    INTERNAL_ERROR: 'INTERNAL_ERROR',
    SERVICE_ERROR: 'SERVICE_ERROR'
  } as const;

  // Supported languages
  static readonly SUPPORTED_LANGUAGES = ['ru', 'en'];

  // Default progress increments
  static readonly PROGRESS_INCREMENTS = {
    START: 10,
    MIDDLE: 60,
    END: 90,
    COMPLETE: 100
  } as const;
}

export * from './types.ts';