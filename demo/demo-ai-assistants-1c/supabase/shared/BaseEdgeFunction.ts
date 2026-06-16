/**
 * Base Edge Function class
 * Provides common functionality to eliminate code duplication across all Edge Functions
 */

import { BaseRequest, ProgressStep, DemoResponse, ErrorResponse, ServiceMetadata } from './types.ts';

export abstract class BaseEdgeFunction {
  protected corsHeaders: Record<string, string>;
  protected serviceName: string;
  protected serviceVersion: string;

  constructor(serviceName: string, version: string = '1.0.0') {
    this.serviceName = serviceName;
    this.serviceVersion = version;
    
    // CORS headers - same across all functions (but will be configurable in secure version)
    this.corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
      'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
      'Access-Control-Max-Age': '86400',
      'Access-Control-Allow-Credentials': 'false'
    };
  }

  /**
   * Main request handler - enforces consistent structure across all functions
   */
  async handleRequest(req: Request): Promise<Response> {
    // Handle CORS preflight
    if (req.method === 'OPTIONS') {
      return new Response(null, { status: 200, headers: this.corsHeaders });
    }

    try {
      // Validate request
      const validation = await this.validateRequest(req);
      if (!validation.isValid) {
        return this.createErrorResponse('VALIDATION_ERROR', validation.errors.join(', '), 400);
      }

      // Parse and validate request data
      const requestData = await req.json();
      const baseRequest = this.parseRequest(requestData);
      
      // Execute the main logic
      const result = await this.executeDemo(baseRequest);
      
      return this.createSuccessResponse(result);
      
    } catch (error) {
      console.error(`${this.serviceName} demo error:`, error);
      return this.createErrorResponse('INTERNAL_ERROR', error.message);
    }
  }

  /**
   * Validate incoming request
   */
  protected async validateRequest(req: Request): Promise<{ isValid: boolean; errors: string[] }> {
    const errors: string[] = [];

    // Check method
    if (!['GET', 'POST', 'OPTIONS'].includes(req.method)) {
      errors.push(`Unsupported method: ${req.method}`);
    }

    // Check Content-Type for POST
    if (req.method === 'POST') {
      const contentType = req.headers.get('content-type');
      if (!contentType?.includes('application/json')) {
        errors.push('Content-Type must be application/json');
      }
    }

    return {
      isValid: errors.length === 0,
      errors
    };
  }

  /**
   * Parse and validate request data
   */
  protected parseRequest(requestData: any): BaseRequest {
    if (!requestData || typeof requestData !== 'object') {
      throw new Error('Неверный формат данных запроса');
    }

    const { demoType, userQuery } = requestData;

    if (!demoType) {
      throw new Error('Параметр demoType обязателен для указания');
    }

    return {
      demoType,
      userQuery
    };
  }

  /**
   * Create standardized progress steps
   */
  protected createProgressSteps(steps: Array<{message: string; delay: number}>): ProgressStep[] {
    const result: ProgressStep[] = [];
    let progress = 0;

    steps.forEach((step, index) => {
      progress = Math.min(90, (index + 1) * Math.floor(90 / steps.length));
      
      result.push({
        progress,
        message: step.message
      });

      // Add delay if specified
      if (step.delay > 0) {
        // Note: In actual implementation, this would be handled differently
        // For now, we just track the steps without actual delays
      }
    });

    return result;
  }

  /**
   * Create success response
   */
  protected createSuccessResponse(result: any): Response {
    const response: DemoResponse = {
      data: result
    };

    return new Response(JSON.stringify(response), {
      headers: {
        ...this.corsHeaders,
        'Content-Type': 'application/json'
      }
    });
  }

  /**
   * Create error response
   */
  protected createErrorResponse(
    code: string, 
    message: string, 
    statusCode: number = 500,
    additionalData: Record<string, any> = {}
  ): Response {
    const errorResponse: ErrorResponse = {
      error: {
        code,
        message,
        timestamp: new Date().toISOString(),
        requestId: crypto.randomUUID(),
        service: this.serviceName,
        version: this.serviceVersion,
        ...additionalData
      }
    };

    return new Response(JSON.stringify(errorResponse), {
      status: statusCode,
      headers: {
        ...this.corsHeaders,
        'Content-Type': 'application/json'
      }
    });
  }

  /**
   * Get service metadata
   */
  protected getMetadata(processingTime: string, capabilities: string[] = []): ServiceMetadata {
    return {
      service: this.serviceName,
      version: this.serviceVersion,
      timestamp: new Date().toISOString(),
      processingTime,
      supportedLanguages: ['ru', 'en'],
      capabilities
    };
  }

  /**
   * Abstract method to be implemented by each specific function
   */
  protected abstract executeDemo(request: BaseRequest): Promise<{
    steps: ProgressStep[];
    finalResult: any;
    metadata?: ServiceMetadata;
  }>;
}