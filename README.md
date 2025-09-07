# Production MCP Server with Cequence Integration

## Overview

This production-ready MCP (Model Context Protocol) server provides secure, OAuth-protected workplace search capabilities for AI agents. It integrates with the Cequence AI Gateway for comprehensive observability and security.

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   AI Agents     │    │  Cequence MCP    │    │   MCP Server    │
│ (Claude/Crew.ai)│◄──►│     Proxy        │◄──►│ (Workplace      │
│                 │    │                  │    │  Search)        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                         │
                                ▼                         ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │ Cequence Gateway │    │  OAuth Providers│
                       │  (Observability) │    │ (Descope/Google)│
                       └──────────────────┘    └─────────────────┘
```

## Features

- **Security**: OAuth2 + JWT authentication with Descope integration
- **Permissions**: Granular scope-based access control
- **Observability**: Full request/response logging via Cequence Gateway
- **Tools**: Workplace search across Google Drive, Notion, SharePoint
- **Compatibility**: Works with Claude Desktop, LangChain, Crew.ai
- **Production-Ready**: Docker deployment with HTTPS, rate limiting, monitoring

## Quick Start

### 1. Environment Setup

```bash
# Clone and setup
git clone <your-repo>
cd mcp-server

# Copy environment template
cp .env.example .env

# Edit .env with your credentials
vim .env
```

### 2. Required Environment Variables

```env
# Descope OAuth
DESCOPE_PROJECT_ID=P2xxxxxxxxxxxxx
JWT_SECRET_KEY=your-256-bit-secret-key

# Cequence AI Gateway
CEQUENCE_GATEWAY_URL=https://your-gateway.cequence.ai
CEQUENCE_API_KEY=ceq_xxxxxxxxxxxxxxxx

# OAuth Provider Credentials
GOOGLE_CLIENT_ID=xxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPXxxxxxxxxxxxx
NOTION_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
NOTION_CLIENT_SECRET=secret_xxxxxxxxxxxxxxxx
```

### 3. Deploy with Docker

```bash
# Build and deploy
docker-compose up -d

# Check status
docker-compose ps
curl -k https://localhost/health
```

### 4. SSL Certificate Setup

```bash
# Generate self-signed cert for development
openssl req -x509 -newkey rsa:4096 -keyout ssl/private.key -out ssl/certificate.crt -days 365 -nodes

# For production, use Let's Encrypt
certbot certonly --webroot -w /var/www/html -d your-domain.com
```

## API Documentation

### Authentication

All endpoints require Bearer token authentication:

```http
Authorization: Bearer <jwt_token>
```

### Available Tools

#### Workplace Search

**Endpoint**: `POST /mcp/tools/workplace_search/call`

**Required Scopes**: 
- `workplace:read:google_drive` (for Google Drive access)
- `workplace:read:notion` (for Notion access)

**Request**:
```json
{
  "name": "workplace_search",
  "arguments": {
    "query": "quarterly budget reports",
    "sources": ["google_drive", "notion"],
    "max_results": 10,
    "include_content": true
  }
}
```

**Response**:
```json
{
  "content": [
    {
      "type": "text",
      "text": "Found 5 results for 'quarterly budget reports'"
    },
    {
      "type": "resource",
      "resource": {
        "uri": "workplace://search/quarterly%20budget%20reports",
        "name": "Search Results",
        "mimeType": "application/json",
        "text": "{\"results\": [...], \"total_count\": 5}"
      }
    }
  ],
  "isError": false
}
```

## Client Integration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "workplace-search": {
      "command": "python",
      "args": ["-m", "mcp_client"],
      "env": {
        "MCP_SERVER_URL": "https://your-domain.com",
        "MCP_SERVER_TOKEN": "your_bearer_token_here"
      }
    }
  }
}
```

### LangChain Integration

```python
from mcp_langchain import WorkplaceSearchTool

tool = WorkplaceSearchTool(
    server_url="https://your-domain.com",
    auth_token="your_bearer_token"
)

# Use in LangChain chains
from langchain.agents import initialize_agent
agent = initialize_agent([tool], llm, agent_type="zero-shot-react-description")
result = agent.run("Find documents about Q4 planning")
```

### Crew.ai Integration

```python
from mcp_crewai import WorkplaceSearchTool

research_agent = Agent(
    role="Research Analyst",
    tools=[WorkplaceSearchTool(
        server_url="https://your-domain.com",
        auth_token="your_bearer_token"
    )]
)
```

## Cequence Configuration

### 1. Deploy MCP Proxy

```bash
# Deploy Cequence MCP Proxy
kubectl apply -f cequence-mcp-proxy.yaml

# Verify deployment
kubectl get pods -n mcp-system
kubectl logs -f deployment/cequence-mcp-proxy -n mcp-system
```

### 2. Configure Observability

The Cequence MCP Proxy provides:

- **Request/Response Logging**: All MCP tool calls logged
- **Performance Metrics**: Latency, throughput, error rates
- **Security Monitoring**: Auth failures, rate limiting, anomalies
- **Compliance**: Audit trails for regulatory requirements

### 3. Dashboard Setup

Access Cequence dashboard at: `https://your-cequence-instance.com`

Key metrics to monitor:
- Tool usage by user/agent
- Success/failure rates
- Response times
- Permission violations
- Rate limit hits

## Security Best Practices

### 1. OAuth Scopes

Define minimal required scopes:

```python
WORKPLACE_SCOPES = [
    "workplace:read:google_drive",    # Read Google Drive documents
    "workplace:read:notion",          # Read Notion pages
    "workplace:write:comments",       # Add comments to documents
]
```

### 2. Rate Limiting

Configure per-user and global limits:

```yaml
# In nginx.conf
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req zone=api_limit burst=20 nodelay;
```

### 3. Input Validation

All inputs are validated using Pydantic models:

```python
class WorkplaceSearchRequest(BaseModel):
    query: str = Field(..., max_length=500)  # Prevent long queries
    sources: List[str] = Field(default=["google_drive"], max_items=5)
    max_results: int = Field(default=10, ge=1, le=50)
```

### 4. Secrets Management

Use external secret management:

```yaml
# Kubernetes secret
apiVersion: v1
kind: Secret
metadata:
  name: mcp-server-secrets
type: Opaque
data:
  descope-client-secret: <base64-encoded>
  jwt-secret: <base64-encoded>
  cequence-api-key: <base64-encoded>
```

## Testing

### 1. Run Test Suite

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest test_mcp_server.py -v

# Run specific test categories
pytest test_mcp_server.py::TestSecurity -v
pytest test_mcp_server.py::TestMCPServer::test_workplace_search_tool_call -v
```

### 2. Load Testing

```bash
# Install artillery
npm install -g artillery

# Run load test
artillery run load-test.yaml
```

### 3. MCP Client Testing

Use the official MCP test client:

```bash
# Install MCP SDK
pip install mcp

# Test server
python -m mcp test-server https://your-domain.com \
  --header "Authorization: Bearer your_token"
```

## Monitoring & Alerting

### 1. Health Checks

```bash
# Basic health check
curl -f https://your-domain.com/health

# Detailed health with auth
curl -H "Authorization: Bearer $TOKEN" https://your-domain.com/mcp/tools
```

### 2. Metrics Collection

Key metrics to track:

- **Request Rate**: Requests per second
- **Error Rate**: 4xx/5xx responses percentage
- **Latency**: p50, p95, p99 response times
- **Tool Usage**: Which tools are used most
- **User Activity**: Active users, usage patterns

### 3. Alerting Rules

```yaml
# Prometheus alerting rules
groups:
- name: mcp-server
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
    for: 2m
    annotations:
      summary: "High error rate on MCP server"
  
  - alert: HighLatency
    expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
    for: 5m
    annotations:
      summary: "High latency on MCP server"
```

## Production Deployment

### 1. Infrastructure Requirements

- **CPU**: 2+ cores
- **Memory**: 4GB+ RAM  
- **Storage**: 20GB+ SSD
- **Network**: HTTPS with valid SSL certificate
- **Database**: Redis for session/cache storage

### 2. Scaling Considerations

- Deploy multiple server instances behind load balancer
- Use Redis for shared state/caching
- Configure horizontal pod autoscaler in Kubernetes
- Monitor resource usage and scale proactively

### 3. Backup & Recovery

```bash
# Backup configuration
kubectl create backup mcp-server-config --include-resources configmap,secret

# Database backup (if using persistent storage)
kubectl exec redis-0 -- redis-cli BGSAVE
```

## Troubleshooting

### Common Issues

1. **401 Unauthorized**
   - Check JWT token validity and expiration
   - Verify Descope project ID and configuration
   - Ensure proper Authorization header format

2. **403 Forbidden** 
   - Check user scopes/permissions
   - Verify OAuth provider grants required permissions
   - Review Cequence policy configuration

3. **Rate Limited**
   - Check rate limiting configuration
   - Monitor usage patterns
   - Consider increasing limits or optimizing requests

4. **Tool Execution Timeout**
   - Check external API performance (Google Drive, Notion)
   - Increase timeout values if needed
   - Monitor network connectivity

### Debug Commands

```bash
# Check server logs
docker-compose logs -f mcp-server

# Test authentication
curl -H "Authorization: Bearer $TOKEN" https://your-domain.com/mcp/tools

# Verify SSL certificate
openssl s_client -connect your-domain.com:443 -servername your-domain.com

# Test tool execution
curl -X POST https://your-domain.com/mcp/tools/workplace_search/call \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "workplace_search", "arguments": {"query": "test"}}'
```

## Next Steps

1. **Add More Tools**: Implement additional workplace tools (calendar, email, CRM)
2. **Enhanced Security**: Add IP allowlisting, advanced threat detection
3. **Performance Optimization**: Implement caching, database optimization
4. **Advanced Analytics**: Custom dashboards, usage analytics
5. **Multi-tenant Support**: Support multiple organizations/workspaces

## Support

- **Documentation**: [Internal Wiki](https://wiki.company.com/mcp)
- **Issues**: Create GitHub issues for bugs/feature requests  
- **Security**: Contact security@company.com for security issues
- **Cequence Support**: [Cequence Documentation](https://docs.cequence.ai)