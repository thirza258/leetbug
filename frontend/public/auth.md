# LeetBug auth.md

## Overview

LeetBug provides authentication and registration protocols for AI agents to interact with coding challenge debugging, test suite execution, and hint generation APIs.

- **Audience**: AI Agents, Code Assistants, and Automated Systems
- **Resource Identifier**: `https://leetbug.nevatal.id`
- **Authorization Server**: `https://leetbug.nevatal.id`
- **Registration Endpoint**: `https://leetbug.nevatal.id/api/agent/register`
- **Token Endpoint**: `https://leetbug.nevatal.id/api/auth/token`
- **Supported Methods**: Bearer Token (`Authorization: Bearer <token>`)
- **Supported Scopes**: `read`, `write`, `debug`, `mcp`

## Agent Registration Flow

Agents can register or provision an API token:

```http
POST /api/agent/register HTTP/1.1
Host: leetbug.nevatal.id
Content-Type: application/json

{
  "client_name": "MyDebuggingAgent",
  "client_uri": "https://example.com/agent"
}
```

Response:
```json
{
  "access_token": "leetbug_agent_token_sample",
  "token_type": "Bearer",
  "expires_in": 2592000,
  "scope": "read write debug mcp"
}
```

## Discovery Endpoints

- OAuth Authorization Server Metadata: [/.well-known/oauth-authorization-server](https://leetbug.nevatal.id/.well-known/oauth-authorization-server)
- OpenID Connect Configuration: [/.well-known/openid-configuration](https://leetbug.nevatal.id/.well-known/openid-configuration)
- OAuth Protected Resource Metadata: [/.well-known/oauth-protected-resource](https://leetbug.nevatal.id/.well-known/oauth-protected-resource)
- API Catalog: [/.well-known/api-catalog](https://leetbug.nevatal.id/.well-known/api-catalog)
- MCP Server Card: [/.well-known/mcp/server-card.json](https://leetbug.nevatal.id/.well-known/mcp/server-card.json)
- A2A Agent Card: [/.well-known/agent-card.json](https://leetbug.nevatal.id/.well-known/agent-card.json)
- Agent Skills Discovery: [/.well-known/agent-skills/index.json](https://leetbug.nevatal.id/.well-known/agent-skills/index.json)
