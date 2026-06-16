<?php

/**
 * Health Check Middleware для PHP приложений
 * Предоставляет эндпоинты для мониторинга состояния сервисов
 */

class HealthCheckMiddleware
{
    private $config;
    private $database;
    private $redis;

    public function __construct($config = [])
    {
        $this->config = array_merge([
            'health_check_path' => '/health',
            'ready_check_path' => '/ready',
            'live_check_path' => '/live',
            'detailed_checks' => true,
            'timeout' => 5
        ], $config);
    }

    /**
     * Основной health check endpoint
     */
    public function health()
    {
        $checks = $this->performHealthChecks();
        
        $status = $this->determineOverallStatus($checks);
        $httpStatus = $status === 'healthy' ? 200 : 503;
        
        $response = [
            'status' => $status,
            'timestamp' => date('c'),
            'version' => $this->getApplicationVersion(),
            'checks' => $this->config['detailed_checks'] ? $checks : null
        ];

        $this->sendJsonResponse($response, $httpStatus);
    }

    /**
     * Ready check endpoint (Kubernetes)
     */
    public function ready()
    {
        $ready = $this->checkReadiness();
        
        $response = [
            'ready' => $ready,
            'timestamp' => date('c'),
            'checks' => [
                'database' => $this->checkDatabaseConnection(),
                'redis' => $this->checkRedisConnection(),
                'external_apis' => $this->checkExternalAPIs()
            ]
        ];

        $this->sendJsonResponse($response, $ready ? 200 : 503);
    }

    /**
     * Live check endpoint (Kubernetes)
     */
    public function live()
    {
        $response = [
            'live' => true,
            'timestamp' => date('c'),
            'uptime' => $this->getUptime()
        ];

        $this->sendJsonResponse($response, 200);
    }

    /**
     * Метрики для Prometheus
     */
    public function metrics()
    {
        $metrics = $this->generatePrometheusMetrics();
        header('Content-Type: text/plain');
        echo $metrics;
    }

    /**
     * Выполнение всех проверок состояния
     */
    private function performHealthChecks()
    {
        $checks = [];

        // Системные проверки
        $checks['system'] = $this->checkSystem();
        
        // База данных
        $checks['database'] = $this->checkDatabaseConnection();
        
        // Redis
        $checks['redis'] = $this->checkRedisConnection();
        
        // Внешние API
        $checks['external_apis'] = $this->checkExternalAPIs();
        
        // Память
        $checks['memory'] = $this->checkMemoryUsage();
        
        // Дисковое пространство
        $checks['disk_space'] = $this->checkDiskSpace();

        return $checks;
    }

    /**
     * Проверка готовности сервиса
     */
    private function checkReadiness()
    {
        // Основные зависимости должны быть доступны
        $dbOk = $this->checkDatabaseConnection();
        $redisOk = $this->checkRedisConnection();
        
        return $dbOk['status'] && $redisOk['status'];
    }

    /**
     * Проверка системных ресурсов
     */
    private function checkSystem()
    {
        $load = sys_getloadavg();
        $cpuUsage = $this->getCpuUsage();
        $memoryUsage = $this->getMemoryUsage();
        
        $healthy = (
            $load[0] < 2.0 && // CPU load average (1 min)
            $cpuUsage < 80 && // CPU usage %
            $memoryUsage < 85 // Memory usage %
        );

        return [
            'status' => $healthy,
            'data' => [
                'load_average' => $load,
                'cpu_usage_percent' => $cpuUsage,
                'memory_usage_percent' => $memoryUsage
            ]
        ];
    }

    /**
     * Проверка подключения к базе данных
     */
    private function checkDatabaseConnection()
    {
        try {
            if (!$this->database) {
                return ['status' => false, 'error' => 'Database not configured'];
            }
            
            $start = microtime(true);
            $stmt = $this->database->query("SELECT 1");
            $duration = microtime(true) - $start;
            
            $healthy = $duration < 1.0; // Response time should be < 1 second
            
            return [
                'status' => $healthy,
                'duration' => round($duration, 3),
                'connection_pool' => $this->getConnectionPoolInfo()
            ];
        } catch (Exception $e) {
            return [
                'status' => false,
                'error' => $e->getMessage()
            ];
        }
    }

    /**
     * Проверка подключения к Redis
     */
    private function checkRedisConnection()
    {
        try {
            if (!$this->redis) {
                return ['status' => false, 'error' => 'Redis not configured'];
            }
            
            $start = microtime(true);
            $this->redis->ping();
            $duration = microtime(true) - $start;
            
            $healthy = $duration < 0.5; // Response time should be < 0.5 seconds
            
            return [
                'status' => $healthy,
                'duration' => round($duration, 3),
                'info' => $this->redis->info()
            ];
        } catch (Exception $e) {
            return [
                'status' => false,
                'error' => $e->getMessage()
            ];
        }
    }

    /**
     * Проверка внешних API
     */
    private function checkExternalAPIs()
    {
        $apis = $this->config['external_apis'] ?? [];
        $results = [];

        foreach ($apis as $name => $config) {
            try {
                $start = microtime(true);
                $response = $this->makeApiRequest($config['url'], $config['timeout'] ?? 5);
                $duration = microtime(true) - $start;
                
                $healthy = ($response['status_code'] >= 200 && $response['status_code'] < 300);
                
                $results[$name] = [
                    'status' => $healthy,
                    'duration' => round($duration, 3),
                    'status_code' => $response['status_code']
                ];
            } catch (Exception $e) {
                $results[$name] = [
                    'status' => false,
                    'error' => $e->getMessage()
                ];
            }
        }

        $allHealthy = empty($results) || array_reduce($results, function($carry, $result) {
            return $carry && $result['status'];
        }, true);

        return [
            'status' => $allHealthy,
            'apis' => $results
        ];
    }

    /**
     * Проверка использования памяти
     */
    private function checkMemoryUsage()
    {
        $memoryLimit = ini_get('memory_limit');
        $memoryUsage = memory_get_usage(true);
        $memoryPeak = memory_get_peak_usage(true);
        
        $memoryLimitBytes = $this->convertToBytes($memoryLimit);
        $usagePercent = ($memoryUsage / $memoryLimitBytes) * 100;
        $peakPercent = ($memoryPeak / $memoryLimitBytes) * 100;
        
        $healthy = $usagePercent < 80;

        return [
            'status' => $healthy,
            'data' => [
                'usage_percent' => round($usagePercent, 2),
                'peak_percent' => round($peakPercent, 2),
                'usage_mb' => round($memoryUsage / 1024 / 1024, 2),
                'peak_mb' => round($memoryPeak / 1024 / 1024, 2),
                'limit' => $memoryLimit
            ]
        ];
    }

    /**
     * Проверка дискового пространства
     */
    private function checkDiskSpace()
    {
        $freeBytes = disk_free_space('/');
        $totalBytes = disk_total_space('/');
        $usagePercent = (($totalBytes - $freeBytes) / $totalBytes) * 100;
        
        $healthy = $usagePercent < 85;

        return [
            'status' => $healthy,
            'data' => [
                'usage_percent' => round($usagePercent, 2),
                'free_gb' => round($freeBytes / 1024 / 1024 / 1024, 2),
                'total_gb' => round($totalBytes / 1024 / 1024 / 1024, 2)
            ]
        ];
    }

    /**
     * Определение общего статуса системы
     */
    private function determineOverallStatus($checks)
    {
        // Если есть критические ошибки
        foreach ($checks as $check) {
            if (isset($check['status']) && !$check['status']) {
                return 'unhealthy';
            }
        }
        
        // Если есть предупреждения
        foreach ($checks as $check) {
            if (isset($check['status']) && $check['status'] === 'warning') {
                return 'degraded';
            }
        }
        
        return 'healthy';
    }

    /**
     * Генерация метрик в формате Prometheus
     */
    private function generatePrometheusMetrics()
    {
        $metrics = [];
        
        // Системные метрики
        $load = sys_getloadavg();
        $memoryUsage = $this->getMemoryUsage();
        $diskUsage = $this->checkDiskSpace();
        
        $metrics[] = "# HELP app_uptime_seconds Application uptime in seconds";
        $metrics[] = "# TYPE app_uptime_seconds counter";
        $metrics[] = "app_uptime_seconds " . $this->getUptime();
        
        $metrics[] = "# HELP system_load_average_1m System load average for 1 minute";
        $metrics[] = "# TYPE system_load_average_1m gauge";
        $metrics[] = "system_load_average_1m " . $load[0];
        
        $metrics[] = "# HELP system_load_average_5m System load average for 5 minutes";
        $metrics[] = "# TYPE system_load_average_5m gauge";
        $metrics[] = "system_load_average_5m " . $load[1];
        
        $metrics[] = "# HELP system_load_average_15m System load average for 15 minutes";
        $metrics[] = "# TYPE system_load_average_15m gauge";
        $metrics[] = "system_load_average_15m " . $load[2];
        
        $metrics[] = "# HELP system_memory_usage_percent System memory usage percentage";
        $metrics[] = "# TYPE system_memory_usage_percent gauge";
        $metrics[] = "system_memory_usage_percent " . $memoryUsage;
        
        $metrics[] = "# HELP system_disk_usage_percent System disk usage percentage";
        $metrics[] = "# TYPE system_disk_usage_percent gauge";
        $metrics[] = "system_disk_usage_percent " . $diskUsage['data']['usage_percent'];
        
        $metrics[] = "# HELP health_check_status Health check status (1=healthy, 0=unhealthy)";
        $metrics[] = "# TYPE health_check_status gauge";
        $metrics[] = "health_check_status " . ($this->checkReadiness() ? 1 : 0);
        
        return implode("\n", $metrics);
    }

    // Вспомогательные методы

    private function getCpuUsage()
    {
        $load = sys_getloadavg();
        return ($load[0] / $this->getCpuCount()) * 100;
    }

    private function getCpuCount()
    {
        return function_exists('shell_exec') ? intval(shell_exec("nproc")) : 4;
    }

    private function getMemoryUsage()
    {
        $memoryLimit = ini_get('memory_limit');
        $memoryUsage = memory_get_usage(true);
        $memoryLimitBytes = $this->convertToBytes($memoryLimit);
        
        return ($memoryUsage / $memoryLimitBytes) * 100;
    }

    private function convertToBytes($value)
    {
        $value = trim($value);
        $last = strtolower($value[strlen($value) - 1]);
        $value = (int) $value;
        
        switch($last) {
            case 'g':
                $value *= 1024;
            case 'm':
                $value *= 1024;
            case 'k':
                $value *= 1024;
        }
        
        return $value;
    }

    private function getUptime()
    {
        if (function_exists('shell_exec')) {
            $uptime = shell_exec('cat /proc/uptime | cut -d\' \' -f1');
            return intval(floatval(trim($uptime)));
        }
        return 0;
    }

    private function getConnectionPoolInfo()
    {
        try {
            return [
                'active_connections' => $this->database->query("SHOW STATUS LIKE 'Threads_connected'")->fetch(PDO::FETCH_ASSOC)['Value'],
                'max_connections' => $this->database->query("SHOW VARIABLES LIKE 'max_connections'")->fetch(PDO::FETCH_ASSOC)['Value']
            ];
        } catch (Exception $e) {
            return ['error' => $e->getMessage()];
        }
    }

    private function makeApiRequest($url, $timeout = 5)
    {
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, $timeout);
        curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
        $response = curl_exec($ch);
        $statusCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        
        return ['status_code' => $statusCode, 'response' => $response];
    }

    private function getApplicationVersion()
    {
        return defined('APP_VERSION') ? APP_VERSION : '1.0.0';
    }

    private function sendJsonResponse($data, $statusCode = 200)
    {
        http_response_code($statusCode);
        header('Content-Type: application/json');
        header('Cache-Control: no-cache, no-store, must-revalidate');
        header('Pragma: no-cache');
        header('Expires: 0');
        
        echo json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
    }
}

// Пример использования
if (basename($_SERVER['SCRIPT_NAME']) == 'health-check.php') {
    $healthCheck = new HealthCheckMiddleware([
        'external_apis' => [
            'payment_api' => ['url' => 'http://payment-service:8080/health'],
            'notification_api' => ['url' => 'http://notification-service:8080/health']
        ]
    ]);

    $path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
    
    switch ($path) {
        case '/health':
            $healthCheck->health();
            break;
        case '/ready':
            $healthCheck->ready();
            break;
        case '/live':
            $healthCheck->live();
            break;
        case '/metrics':
            $healthCheck->metrics();
            break;
        default:
            http_response_code(404);
            echo json_encode(['error' => 'Not found']);
    }
}
?>