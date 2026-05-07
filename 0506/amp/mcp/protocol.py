"""MCP protocol models and schemas."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ParameterType(StrEnum):
    """Parameter type enumeration."""
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"


class ToolParameter(BaseModel):
    """Tool parameter definition."""
    model_config = ConfigDict(use_enum_values=True)

    name: str = Field(..., description="Parameter name")
    type: ParameterType = Field(..., description="Parameter type")
    description: str = Field(..., description="Parameter description")
    required: bool = Field(default=True, description="Whether parameter is required")
    default: Any = Field(default=None, description="Default value if not required")


class ToolDefinition(BaseModel):
    """Tool metadata definition."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "create_tunnel",
                "description": "Create a new network tunnel",
                "parameters": [
                    {
                        "name": "name",
                        "type": "string",
                        "description": "Tunnel name",
                        "required": True
                    },
                    {
                        "name": "tunnel_type",
                        "type": "string",
                        "description": "Tunnel type (chisel or ligolo)",
                        "required": True
                    }
                ]
            }
        }
    )

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    parameters: list[ToolParameter] = Field(
        default_factory=list,
        description="Tool parameters"
    )


class ToolRequest(BaseModel):
    """Tool execution request."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "parameters": {
                    "name": "dmz-tunnel",
                    "tunnel_type": "chisel",
                    "local_port": 8080,
                    "remote_host": "192.168.1.100",
                    "remote_port": 9090
                }
            }
        }
    )

    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Tool parameters"
    )


class ToolResponse(BaseModel):
    """Tool execution response."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "result": {
                    "tunnel_id": "abc123",
                    "status": "active"
                },
                "error": None
            }
        }
    )

    success: bool = Field(..., description="Whether execution succeeded")
    result: Any = Field(default=None, description="Execution result")
    error: str | None = Field(default=None, description="Error message if failed")


class ErrorResponse(BaseModel):
    """Error response."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "Tool not found",
                "details": {
                    "tool_name": "invalid_tool"
                }
            }
        }
    )

    error: str = Field(..., description="Error message")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Error details"
    )


class HealthResponse(BaseModel):
    """Health check response."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "version": "0.1.0",
                "timestamp": "2026-05-07T12:00:00Z"
            }
        }
    )

    status: str = Field(..., description="Health status")
    version: str = Field(..., description="Server version")
    timestamp: str = Field(..., description="Current timestamp")


class ToolListResponse(BaseModel):
    """Tool list response."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tools": [
                    {
                        "name": "create_tunnel",
                        "description": "Create a new network tunnel",
                        "parameters": []
                    }
                ],
                "count": 1
            }
        }
    )

    tools: list[ToolDefinition] = Field(..., description="Available tools")
    count: int = Field(..., description="Number of tools")
