"""Configuration management for AMP."""

from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseModel):
    """Database configuration."""
    url: str = Field(default="sqlite:///amp.db", description="Database URL")
    echo: bool = Field(default=False, description="Enable SQL logging")


class TunnelConfig(BaseModel):
    """Tunnel configuration."""
    max_tunnels: int = Field(default=20, description="Maximum concurrent tunnels")
    heartbeat_interval: int = Field(default=30, description="Heartbeat interval in seconds")
    reconnect_attempts: int = Field(default=3, description="Reconnection attempts")
    reconnect_delay: int = Field(default=5, description="Delay between reconnection attempts")
    chisel_binary: str = Field(default="chisel", description="Path to chisel binary")
    ligolo_binary: str = Field(default="ligolo-ng", description="Path to ligolo-ng binary")


class ShellConfig(BaseModel):
    """Shell configuration."""
    max_shells: int = Field(default=50, description="Maximum concurrent shells")
    default_timeout: int = Field(default=30, description="Default command timeout in seconds")
    tmux_socket: str | None = Field(default=None, description="Custom tmux socket path")
    zombie_check_interval: int = Field(default=60, description="Zombie process check interval")


class ContextConfig(BaseModel):
    """Context engine configuration."""
    max_tokens: int = Field(default=8000, description="Maximum context tokens")
    compression_threshold: float = Field(default=0.7, description="Compression threshold (0-1)")
    vector_db_path: str = Field(default="./chroma_db", description="ChromaDB path")
    embedding_model: str = Field(default="all-MiniLM-L6-v2", description="Embedding model")


class MCPConfig(BaseModel):
    """MCP server configuration."""
    host: str = Field(default="127.0.0.1", description="Server host")
    port: int = Field(default=8000, description="Server port")
    auth_token: str | None = Field(default=None, description="Authentication token")
    cors_origins: list[str] = Field(default_factory=lambda: ["*"], description="CORS origins")


class SecurityConfig(BaseModel):
    """Security configuration."""
    docker_isolation: bool = Field(default=True, description="Enable Docker isolation")
    network_isolation: bool = Field(default=True, description="Enable network isolation")
    log_commands: bool = Field(default=True, description="Log all commands")
    log_output: bool = Field(default=False, description="Log command output (may contain sensitive data)")


class Settings(BaseSettings):
    """Application settings."""

    # General
    app_name: str = Field(default="AMP", description="Application name")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    data_dir: Path = Field(default=Path("./data"), description="Data directory")

    # Module configs
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    tunnel: TunnelConfig = Field(default_factory=TunnelConfig)
    shell: ShellConfig = Field(default_factory=ShellConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"
        case_sensitive = False

    def ensure_directories(self):
        """Ensure required directories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        Path(self.context.vector_db_path).mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
