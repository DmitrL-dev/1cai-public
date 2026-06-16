# Rename analytics
Move-Item -Path "src/analytics/revolutionary_analytics.py" -Destination "src/analytics/advanced_analytics.py" -Force

# Rename api
Move-Item -Path "src/api/graph_api_revolutionary.py" -Destination "src/api/advanced_graph_api.py" -Force

# Rename config
Move-Item -Path "src/config/revolutionary_config.py" -Destination "src/config/advanced_config.py" -Force

# Rename monitoring
Move-Item -Path "src/monitoring/revolutionary_metrics.py" -Destination "src/monitoring/advanced_metrics.py" -Force

# Rename security
Move-Item -Path "src/security/revolutionary_security.py" -Destination "src/security/advanced_security.py" -Force

Write-Host "All revolutionary components renamed to advanced."
