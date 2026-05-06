"""AMP configuration management."""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AMPSettings(BaseSettings):
    """AMP platform settings."""

    model_config = SettingsConfigDict(
        env_prefix="AMP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Core settings
    data_dir: Path = Field(default=Path.home() / ".amp" / "data")
    log_level: str = Field(default="INFO")
    max_concurrent_tunnels: int = Field(default=20)
    max_concurrent_shells: int = Field(default=50)

    # Tunnel settings
    tunnel_default_method: str = Field(default="chisel")
    tunnel_health_check_interval: int = Field(default=30)
    tunnel_auto_recovery: bool = Field(default=True)
    chisel_binary_path: Path = Field(default=Path("/usr/local/bin/chisel"))
    chisel_port_range_start: int = Field(default=10000)
    chisel_port_range_end: int = Field(default=20000)
    ligolo_binary_path: Path = Field(default=Path("/usr/local/bin/ligolo-ng"))
    ligolo_interface_name: str = Field(default="ligolo")

    # Shell settings
    tmux_socket_path: Path = Field(default=Path.home() / ".amp" / "tmux.sock")
    tmux_default_shell: str = Field(default="/bin/bash")
    shell_command_timeout: int = Field(default=30)
    shell_output_buffer_size: int = Field(default=10000)

    # Context engine settings
    context_vector_db: str = Field(default="chromadb")
    context_embedding_model: str = Field(default="text-embedding-3-small")
    context_max_tokens: int = Field(default=8000)
    context_compression_strategy: str = Field(default="dynamic")

    # MCP server settings
    mcp_host: str = Field(default="127.0.0.1")
    mcp_port: int = Field(default=8765)
    mcp_auth_token: Optional[str] = Field(default=None)

    # Security settings
    security_isolation_mode: str = Field(default="docker")
    security_audit_log: Path = Field(default=Path.home() / ".amp" / "audit.log")
    security_safe_mode: bool = Field(default=False)

    # Database settings
    db_url: str = Field(default="sqlite:///{data_dir}/amp.db")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # Expand db_url template
        self.db_url = self.db_url.format(data_dir=self.data_dir)


# Global settings instance
settings = AMPSettings()
