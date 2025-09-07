"""
Production-Ready MCP Server with Cequence AI Gateway Integration
================================================================

This MCP server provides secure, OAuth-protected workplace search capabilities
for AI agents with full observability through Cequence AI Gateway.

Requirements:
- fastapi
- uvicorn
- python-jose[cryptography]
- requests
- python-multipart
- aiofiles
- httpx
- pydantic
- python-dotenv
"""

import os
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Depends, Security, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from jose import JWTError, jwt
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
class Config:
    # Descope OAuth Configuration
    DESCOPE_PROJECT_ID = os.getenv("DESCOPE_PROJECT_ID", "your_project_id")
    DESCOPE_DOMAIN = f"https://api.descope.com/v1/projects/{DESCOPE_PROJECT_ID}"
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = 24
    
    # Cequence AI Gateway Configuration
    CEQUENCE_GATEWAY_URL = os.getenv("CEQUENCE_GATEWAY_URL", "https://your-gateway.cequence.ai")
    CEQUENCE_API_KEY = os.getenv("CEQUENCE_API_KEY", "your_cequence_api_key")
    
    # MCP Server Configuration
    MCP_SERVER_NAME = "workplace-search"
    MCP_SERVER_VERSION = "1.0.0"
    
    # Security
    ALLOWED_ORIGINS = ["https://claude.ai", "https://desktop.claude.ai", "http://localhost:3000"]
    TRUSTED_HOSTS = ["*.cequence.ai", "localhost", "127.0.0.1"]

config = Config()

# Pydantic Models
class MCPTool(BaseModel):
    """MCP Tool Definition"""
    name: str
    description: str
    inputSchema: Dict[str, Any]

class MCPToolCall(BaseModel):
    """MCP Tool Call Request"""
    name: str
    arguments: Dict[str, Any]

class MCPResponse(BaseModel):
    """MCP Response"""
    content: List[Dict[str, Any]]
    isError: bool = False

class WorkplaceSearchRequest(BaseModel):
    """Workplace Search Request"""
    query: str = Field(..., description="Search query")
    sources: List[str] = Field(default=["google_drive", "notion"], description="Sources to search")
    max_results: int = Field(default=10, ge=1, le=50, description="Maximum number of results")
    include_content: bool = Field(default=True, description="Include document content in results")

class SearchResult(BaseModel):
    """Search Result"""
    title: str
    source: str
    url: str
    snippet: str
    score: float
    last_modified: Optional[datetime] = None
    content: Optional[str] = None

class WorkplaceSearchResponse(BaseModel):
    """Workplace Search Response"""
    results: List[SearchResult]
    total_count: int
    query: str
    sources: List[str]
    execution_time_ms: int

class UserClaims(BaseModel):
    """JWT User Claims"""
    user_id: str
    email: str
    scopes: List[str]
    exp: int

# Security
security = HTTPBearer()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# FastAPI App
app = FastAPI(
    title="MCP Workplace Search Server",
    description="Production-ready MCP server with Cequence AI Gateway integration",
    version=config.MCP_SERVER_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=config.TRUSTED_HOSTS
)

# Authentication Functions
async def verify_descope_token(token: str) -> UserClaims:
    """Verify Descope JWT token"""
    try:
        # In production, get Descope public key and verify signature
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{config.DESCOPE_DOMAIN}/keys",
                headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid token")
        
        # Decode JWT (simplified - in production, verify with Descope public key)
        payload = jwt.decode(
            token, 
            config.JWT_SECRET_KEY, 
            algorithms=[config.JWT_ALGORITHM]
        )
        
        return UserClaims(
            user_id=payload.get("sub"),
            email=payload.get("email"),
            scopes=payload.get("permissions", []),
            exp=payload.get("exp")
        )
    except JWTError as e:
        logger.error(f"JWT verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> UserClaims:
    """Get current authenticated user"""
    try:
        return await verify_descope_token(credentials.credentials)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")

async def check_scope(required_scope: str, user: UserClaims = Depends(get_current_user)) -> UserClaims:
    """Check if user has required scope"""
    if required_scope not in user.scopes:
        raise HTTPException(
            status_code=403, 
            detail=f"Insufficient permissions. Required scope: {required_scope}"
        )
    return user

# Cequence AI Gateway Integration
class CequenceClient:
    """Cequence AI Gateway Client"""
    
    def __init__(self):
        self.base_url = config.CEQUENCE_GATEWAY_URL
        self.api_key = config.CEQUENCE_API_KEY
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def log_request(self, user_id: str, tool_name: str, request_data: Dict[str, Any]):
        """Log request to Cequence for observability"""
        try:
            await self.client.post(
                f"{self.base_url}/api/v1/mcp/requests",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "timestamp": datetime.utcnow().isoformat(),
                    "user_id": user_id,
                    "tool_name": tool_name,
                    "request_data": request_data,
                    "server_name": config.MCP_SERVER_NAME,
                    "server_version": config.MCP_SERVER_VERSION
                }
            )
        except Exception as e:
            logger.error(f"Failed to log request to Cequence: {e}")
    
    async def log_response(self, user_id: str, tool_name: str, response_data: Dict[str, Any], 
                          execution_time_ms: int, success: bool):
        """Log response to Cequence for observability"""
        try:
            await self.client.post(
                f"{self.base_url}/api/v1/mcp/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "timestamp": datetime.utcnow().isoformat(),
                    "user_id": user_id,
                    "tool_name": tool_name,
                    "response_data": response_data,
                    "execution_time_ms": execution_time_ms,
                    "success": success,
                    "server_name": config.MCP_SERVER_NAME,
                    "server_version": config.MCP_SERVER_VERSION
                }
            )
        except Exception as e:
            logger.error(f"Failed to log response to Cequence: {e}")

cequence_client = CequenceClient()

# Mock Workplace Search Implementation
class WorkplaceSearchService:
    """Mock Workplace Search Service - Replace with real integrations"""
    
    async def search_google_drive(self, query: str, user_token: str, max_results: int) -> List[SearchResult]:
        """Mock Google Drive search"""
        # In production: Use Google Drive API with user's OAuth token
        mock_results = [
            SearchResult(
                title=f"Document about {query}",
                source="google_drive",
                url=f"https://drive.google.com/doc/mock",
                snippet=f"This document contains information about {query}...",
                score=0.95,
                last_modified=datetime.utcnow() - timedelta(days=1),
                content=f"Full content about {query} would be here..."
            )
        ]
        return mock_results[:max_results]
    
    async def search_notion(self, query: str, user_token: str, max_results: int) -> List[SearchResult]:
        """Mock Notion search"""
        # In production: Use Notion API with user's OAuth token
        mock_results = [
            SearchResult(
                title=f"Notion page: {query}",
                source="notion",
                url=f"https://notion.so/mock-page",
                snippet=f"Notion content about {query}...",
                score=0.88,
                last_modified=datetime.utcnow() - timedelta(days=2),
                content=f"Full Notion content about {query}..."
            )
        ]
        return mock_results[:max_results]
    
    async def search(self, request: WorkplaceSearchRequest, user: UserClaims) -> WorkplaceSearchResponse:
        """Perform workplace search across multiple sources"""
        start_time = datetime.utcnow()
        all_results = []
        
        # Mock user OAuth tokens - in production, retrieve from secure storage
        user_tokens = {
            "google_drive": "mock_google_token",
            "notion": "mock_notion_token"
        }
        
        for source in request.sources:
            try:
                if source == "google_drive" and "workplace:read:google_drive" in user.scopes:
                    results = await self.search_google_drive(
                        request.query, 
                        user_tokens.get("google_drive"), 
                        request.max_results
                    )
                    all_results.extend(results)
                
                elif source == "notion" and "workplace:read:notion" in user.scopes:
                    results = await self.search_notion(
                        request.query, 
                        user_tokens.get("notion"), 
                        request.max_results
                    )
                    all_results.extend(results)
                    
            except Exception as e:
                logger.error(f"Error searching {source}: {e}")
        
        # Sort by score and limit results
        all_results.sort(key=lambda x: x.score, reverse=True)
        final_results = all_results[:request.max_results]
        
        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return WorkplaceSearchResponse(
            results=final_results,
            total_count=len(final_results),
            query=request.query,
            sources=request.sources,
            execution_time_ms=int(execution_time)
        )

workplace_search = WorkplaceSearchService()

# MCP Tool Definitions
MCP_TOOLS = [
    MCPTool(
        name="workplace_search",
        description="Search across workplace documents (Google Drive, Notion) with permission controls",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to find relevant documents"
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["google_drive", "notion"]},
                    "description": "Sources to search in",
                    "default": ["google_drive", "notion"]
                },
                "max_results": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 10,
                    "description": "Maximum number of results to return"
                },
                "include_content": {
                    "type": "boolean",
                    "default": True,
                    "description": "Whether to include document content in results"
                }
            },
            "required": ["query"]
        }
    )
]

# API Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/mcp/info")
async def mcp_info():
    """MCP Server Information"""
    return {
        "name": config.MCP_SERVER_NAME,
        "version": config.MCP_SERVER_VERSION,
        "description": "AI-powered Workplace Search with OAuth security",
        "capabilities": {
            "tools": True,
            "resources": False,
            "prompts": False
        }
    }

@app.get("/mcp/tools", response_model=List[MCPTool])
async def list_tools(user: UserClaims = Depends(get_current_user)):
    """List available MCP tools"""
    # Filter tools based on user permissions
    available_tools = []
    for tool in MCP_TOOLS:
        if tool.name == "workplace_search":
            # Check if user has any workplace read permissions
            if any(scope.startswith("workplace:read:") for scope in user.scopes):
                available_tools.append(tool)
    
    return available_tools

@app.post("/mcp/tools/{tool_name}/call", response_model=MCPResponse)
async def call_tool(
    tool_name: str,
    tool_call: MCPToolCall,
    request: Request,
    user: UserClaims = Depends(get_current_user)
):
    """Execute MCP tool call"""
    start_time = datetime.utcnow()
    
    try:
        # Log request to Cequence
        await cequence_client.log_request(
            user.user_id, 
            tool_name, 
            {"arguments": tool_call.arguments}
        )
        
        if tool_name == "workplace_search":
            # Validate user has required permissions
            required_scope = "workplace:read"
            if not any(scope.startswith(required_scope) for scope in user.scopes):
                raise HTTPException(
                    status_code=403, 
                    detail=f"Insufficient permissions. Required scope: {required_scope}:*"
                )
            
            # Execute workplace search
            search_request = WorkplaceSearchRequest(**tool_call.arguments)
            search_response = await workplace_search.search(search_request, user)
            
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Log successful response to Cequence
            await cequence_client.log_response(
                user.user_id, 
                tool_name, 
                search_response.dict(), 
                execution_time, 
                True
            )
            
            return MCPResponse(
                content=[{
                    "type": "text",
                    "text": f"Found {search_response.total_count} results for '{search_response.query}'"
                }, {
                    "type": "resource",
                    "resource": {
                        "uri": f"workplace://search/{search_response.query}",
                        "name": "Search Results",
                        "mimeType": "application/json",
                        "text": json.dumps(search_response.dict(), indent=2)
                    }
                }]
            )
        
        else:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    
    except HTTPException:
        execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        await cequence_client.log_response(user.user_id, tool_name, {}, execution_time, False)
        raise
    except Exception as e:
        execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        await cequence_client.log_response(user.user_id, tool_name, {}, execution_time, False)
        logger.error(f"Tool execution error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Direct API Endpoints (for non-MCP clients)

@app.post("/api/v1/workplace/search", response_model=WorkplaceSearchResponse)
async def workplace_search_endpoint(
    search_request: WorkplaceSearchRequest,
    user: UserClaims = Depends(lambda: check_scope("workplace:read"))
):
    """Direct workplace search API endpoint"""
    return await workplace_search.search(search_request, user)

# OAuth Integration Endpoints

@app.post("/auth/token/exchange")
async def exchange_descope_token(descope_token: str):
    """Exchange Descope token for internal JWT"""
    try:
        # Verify Descope token and create internal JWT
        user_claims = await verify_descope_token(descope_token)
        
        # Create internal JWT with additional claims
        jwt_payload = {
            "sub": user_claims.user_id,
            "email": user_claims.email,
            "permissions": user_claims.scopes,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=config.JWT_EXPIRATION_HOURS)
        }
        
        internal_token = jwt.encode(
            jwt_payload, 
            config.JWT_SECRET_KEY, 
            algorithm=config.JWT_ALGORITHM
        )
        
        return {
            "access_token": internal_token,
            "token_type": "bearer",
            "expires_in": config.JWT_EXPIRATION_HOURS * 3600
        }
        
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        raise HTTPException(status_code=401, detail="Token exchange failed")

if __name__ == "__main__":
    # Production deployment with proper SSL
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        ssl_keyfile="path/to/private.key",
        ssl_certfile="path/to/certificate.crt",
        log_level="info"
    )