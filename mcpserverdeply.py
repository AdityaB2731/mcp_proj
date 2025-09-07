# # docker-compose.yml - Production deployment with Cequence integration
# version: '3.8'

# services:
#   mcp-server:
#     build: 
#       context: .
#       dockerfile: Dockerfile
#     container_name: mcp-workplace-search
#     restart: unless-stopped
#     ports:
#       - "8000:8000"
#     environment:
#       # Descope OAuth Configuration
#       - DESCOPE_PROJECT_ID=${DESCOPE_PROJECT_ID}
#       - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      
#       # Cequence AI Gateway Configuration  
#       - CEQUENCE_GATEWAY_URL=${CEQUENCE_GATEWAY_URL}
#       - CEQUENCE_API_KEY=${CEQUENCE_API_KEY}
      
#       # Google Drive & Notion OAuth
#       - GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
#       - GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}
#       - NOTION_CLIENT_ID=${NOTION_CLIENT_ID}
#       - NOTION_CLIENT_SECRET=${NOTION_CLIENT_SECRET}
      
#     volumes:
#       - ./ssl:/app/ssl:ro
#       - ./logs:/app/logs
#     networks:
#       - mcp-network
#     depends_on:
#       - redis
      
#   redis:
#     image: redis:7-alpine
#     container_name: mcp-redis
#     restart: unless-stopped
#     ports:
#       - "6379:6379"
#     volumes:
#       - redis_data:/data
#     networks:
#       - mcp-network

#   nginx:
#     image: nginx:alpine
#     container_name: mcp-nginx
#     restart: unless-stopped
#     ports:
#       - "80:80"
#       - "443:443"
#     volumes:
#       - ./nginx.conf:/etc/nginx/nginx.conf:ro
#       - ./ssl:/etc/nginx/ssl:ro
#     depends_on:
#       - mcp-server
#     networks:
#       - mcp-network

# volumes:
#   redis_data:

# networks:
#   mcp-network:
#     driver: bridge

# ---
# # .env.example - Environment variables template
# DESCOPE_PROJECT_ID=your_descope_project_id
# JWT_SECRET_KEY=your_super_secret_jwt_key_256_bits_long

# # Cequence AI Gateway
# CEQUENCE_GATEWAY_URL=https://your-gateway.cequence.ai
# CEQUENCE_API_KEY=your_cequence_api_key

# # OAuth Providers
# GOOGLE_CLIENT_ID=your_google_oauth_client_id
# GOOGLE_CLIENT_SECRET=your_google_oauth_client_secret
# NOTION_CLIENT_ID=your_notion_oauth_client_id
# NOTION_CLIENT_SECRET=your_notion_oauth_client_secret

# ---
# # Dockerfile - Production container build
# FROM python:3.11-slim

# WORKDIR /app

# # Install system dependencies
# RUN apt-get update && apt-get install -y \
#     gcc \
#     && rm -rf /var/lib/apt/lists/*

# # Copy requirements and install Python dependencies
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# # Copy application code
# COPY . .

# # Create non-root user
# RUN useradd -m -u 1000 mcp && chown -R mcp:mcp /app
# USER mcp

# # Health check
# HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
#     CMD curl -f http://localhost:8000/health || exit 1

# EXPOSE 8000

# CMD ["python", "mcp_server.py"]

# ---
# # requirements.txt - Python dependencies
# fastapi==0.104.1
# uvicorn[standard]==0.24.0
# python-jose[cryptography]==3.3.0
# requests==2.31.0
# python-multipart==0.0.6
# aiofiles==23.2.1
# httpx==0.25.2
# pydantic==2.5.0
# python-dotenv==1.0.0
# redis==5.0.1
# google-api-python-client==2.108.0
# notion-client==2.2.1
# cryptography==41.0.7

# ---
# # nginx.conf - Reverse proxy configuration
# events {
#     worker_connections 1024;
# }

# http {
#     upstream mcp_server {
#         server mcp-server:8000;
#     }
    
#     # Rate limiting
#     limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    
#     server {
#         listen 80;
#         server_name your-domain.com;
#         return 301 https://$server_name$request_uri;
#     }
    
#     server {
#         listen 443 ssl http2;
#         server_name your-domain.com;
        
#         # SSL Configuration
#         ssl_certificate /etc/nginx/ssl/certificate.crt;
#         ssl_certificate_key /etc/nginx/ssl/private.key;
#         ssl_protocols TLSv1.2 TLSv1.3;
#         ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
#         ssl_prefer_server_ciphers off;
        
#         # Security headers
#         add_header X-Frame-Options DENY;
#         add_header X-Content-Type-Options nosniff;
#         add_header X-XSS-Protection "1; mode=block";
#         add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";
        
#         # Rate limiting
#         limit_req zone=api_limit burst=20 nodelay;
        
#         location / {
#             proxy_pass http://mcp_server;
#             proxy_set_header Host $host;
#             proxy_set_header X-Real-IP $remote_addr;
#             proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
#             proxy_set_header X-Forwarded-Proto $scheme;
            
#             # Timeout settings
#             proxy_connect_timeout 60s;
#             proxy_send_timeout 60s;
#             proxy_read_timeout 60s;
#         }
        
#         # Health check endpoint (no auth required)
#         location /health {
#             proxy_pass http://mcp_server/health;
#             access_log off;
#         }
#     }
# }