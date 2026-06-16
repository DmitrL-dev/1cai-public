# 1C AI Assistant EDT Plugin

Eclipse plugin for 1C:Enterprise Development Tools with AI capabilities.

## Features

### 4 Views:

1. **AI Assistant** - Chat interface with AI about your 1C configuration
2. **Metadata Graph** - Visualize metadata graph from Neo4j
3. **Semantic Search** - Search code by meaning using vector search
4. **Code Optimizer** - AI-powered code optimization

### Context Menu Actions:

Right-click on any BSL function:
- **Analyze with AI** - Get AI analysis of function
- **Optimize Function** - Get AI optimization suggestions
- **Find Similar Code** - Find semantically similar functions
- **Show Call Graph** - Visualize function dependencies

## Building

### Prerequisites:

- Java 17+
- Maven 3.8+
- Eclipse/EDT SDK

### Build:

```bash
cd edt-plugin
mvn clean package
```

Output: `target/com.1cai.edt-1.0.0-SNAPSHOT.jar`

## Installation

### Method 1: From Update Site (after build)

1. In EDT: **Help → Install New Software**
2. Click **Add → Local**
3. Browse to: `edt-plugin/target/repository`
4. Select **1C AI Assistant**
5. Click **Next → Finish**
6. Restart EDT

### Method 2: Direct JAR (for development)

1. Build plugin
2. Copy JAR to: `<EDT_HOME>/plugins/`
3. Restart EDT with `-clean` flag

## Configuration

### 1. Set Backend URLs

**Window → Preferences → 1C AI Assistant → Connection Settings**

- MCP Server URL: `http://localhost:6001`
- Graph API URL: `http://localhost:8080`
- Click **Test Connection**

### 2. Enable Features

**Window → Preferences → 1C AI Assistant**

- ✓ Enable AI Assistant
- ✓ Auto-suggest (optional)

## Usage

### Open Views:

**Window → Show View → Other... → 1C AI Assistant**

Select view:
- AI Assistant
- Metadata Graph
- Semantic Search
- Code Optimizer

### Use Context Menu:

1. Open BSL module
2. Right-click on function
3. Select action from **1C AI Assistant** submenu

## Backend Requirements

Plugin requires running backend services:

```bash
# Start all services
docker-compose -f docker-compose.yml -f docker-compose.stage1.yml up -d

# Start API servers
python -m uvicorn src.api.graph_api:app --port 8080
python -m uvicorn src.ai.mcp_server:app --port 6001
```

## Development

### Project Structure:

```
edt-plugin/
├── plugin.xml           # Plugin configuration
├── META-INF/
│   └── MANIFEST.MF     # OSGi manifest
├── pom.xml             # Maven build
├── build.properties
└── src/com/1cai/edt/
    ├── Activator.java  # Plugin activator
    ├── views/          # View classes
    │   ├── AIAssistantView.java
    │   ├── MetadataGraphView.java
    │   ├── SemanticSearchView.java
    │   └── CodeOptimizerView.java
    ├── actions/        # Context menu actions
    │   ├── AnalyzeFunctionAction.java
    │   ├── OptimizeFunctionAction.java
    │   ├── FindSimilarCodeAction.java
    │   └── ShowCallGraphAction.java
    ├── services/       # Backend integration
    │   └── BackendConnector.java
    └── preferences/    # Preference pages
        ├── MainPreferencePage.java
        └── ConnectionPreferencePage.java
```

### Dependencies:

- Eclipse Platform
- 1C EDT API (`com._1c.g5.v8.dt.*`)
- Apache HttpClient
- Gson (JSON)

## Troubleshooting

### Plugin doesn't appear in EDT

1. Check EDT version (must be 2023.3.6+)
2. Check Java version (must be 17+)
3. Restart EDT with `-clean` flag
4. Check Error Log view

### Backend connection failed

1. Verify services running: `docker-compose ps`
2. Test URLs manually:
   - http://localhost:8080/health
   - http://localhost:6001/mcp
3. Check firewall settings

### Views don't show data

1. Check backend connection in Preferences
2. Verify data migrated to databases
3. Check backend logs

## License

MIT License

## Support

See main project documentation:
- [START_HERE.md](../../01-getting-started/README.md)
- [DEPLOYMENT_INSTRUCTIONS.md](../../01-getting-started/DEPLOYMENT_INSTRUCTIONS.md)

