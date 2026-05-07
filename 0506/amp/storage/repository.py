"""Repository pattern for data access."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from amp.exceptions import ShellNotFound, TunnelNotFound
from amp.storage.models import (
    NetworkSegmentModel,
    OperationModel,
    ShellModel,
    ShellStatus,
    TunnelModel,
    TunnelStatus,
)
from amp.storage.schema import NetworkSegment, Operation, Shell, Tunnel


class TunnelRepository:
    """Repository for tunnel operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, tunnel_data: dict) -> TunnelModel:
        """Create a new tunnel."""
        tunnel = Tunnel(
            id=str(uuid4()),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            **tunnel_data,
        )
        self.session.add(tunnel)
        self.session.flush()
        return self._to_model(tunnel)

    def get(self, tunnel_id: str) -> TunnelModel | None:
        """Get tunnel by ID."""
        tunnel = self.session.query(Tunnel).filter(Tunnel.id == tunnel_id).first()
        return self._to_model(tunnel) if tunnel else None

    def get_or_raise(self, tunnel_id: str) -> TunnelModel:
        """Get tunnel by ID or raise exception."""
        tunnel = self.get(tunnel_id)
        if not tunnel:
            raise TunnelNotFound(tunnel_id)
        return tunnel

    def list_active(self) -> list[TunnelModel]:
        """List all active tunnels."""
        tunnels = self.session.query(Tunnel).filter(
            Tunnel.status == TunnelStatus.ACTIVE.value
        ).all()
        return [self._to_model(t) for t in tunnels]

    def list_all(self) -> list[TunnelModel]:
        """List all tunnels."""
        tunnels = self.session.query(Tunnel).all()
        return [self._to_model(t) for t in tunnels]

    def update_status(self, tunnel_id: str, status: TunnelStatus) -> TunnelModel:
        """Update tunnel status."""
        tunnel = self.session.query(Tunnel).filter(Tunnel.id == tunnel_id).first()
        if not tunnel:
            raise TunnelNotFound(tunnel_id)
        tunnel.status = status.value
        tunnel.updated_at = datetime.utcnow()
        self.session.flush()
        return self._to_model(tunnel)

    def update_heartbeat(self, tunnel_id: str) -> TunnelModel:
        """Update tunnel heartbeat timestamp."""
        tunnel = self.session.query(Tunnel).filter(Tunnel.id == tunnel_id).first()
        if not tunnel:
            raise TunnelNotFound(tunnel_id)
        tunnel.last_heartbeat = datetime.utcnow()
        tunnel.updated_at = datetime.utcnow()
        self.session.flush()
        return self._to_model(tunnel)

    def delete(self, tunnel_id: str) -> None:
        """Delete tunnel."""
        tunnel = self.session.query(Tunnel).filter(Tunnel.id == tunnel_id).first()
        if tunnel:
            self.session.delete(tunnel)
            self.session.flush()

    def get_children(self, parent_id: str) -> list[TunnelModel]:
        """Get child tunnels."""
        tunnels = self.session.query(Tunnel).filter(
            Tunnel.parent_tunnel_id == parent_id
        ).all()
        return [self._to_model(t) for t in tunnels]

    @staticmethod
    def _to_model(tunnel: Tunnel) -> TunnelModel:
        """Convert ORM entity to Pydantic model."""
        return TunnelModel.model_validate(tunnel)


class ShellRepository:
    """Repository for shell operations."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, shell_data: dict) -> ShellModel:
        """Create a new shell."""
        shell = Shell(
            id=str(uuid4()),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            **shell_data,
        )
        self.session.add(shell)
        self.session.flush()
        return self._to_model(shell)

    def get(self, shell_id: str) -> ShellModel | None:
        """Get shell by ID."""
        shell = self.session.query(Shell).filter(Shell.id == shell_id).first()
        return self._to_model(shell) if shell else None

    def get_or_raise(self, shell_id: str) -> ShellModel:
        """Get shell by ID or raise exception."""
        shell = self.get(shell_id)
        if not shell:
            raise ShellNotFound(shell_id)
        return shell

    def list_active(self) -> list[ShellModel]:
        """List all active shells."""
        shells = self.session.query(Shell).filter(
            Shell.status == ShellStatus.ACTIVE.value
        ).all()
        return [self._to_model(s) for s in shells]

    def list_all(self) -> list[ShellModel]:
        """List all shells."""
        shells = self.session.query(Shell).all()
        return [self._to_model(s) for s in shells]

    def update_status(self, shell_id: str, status: ShellStatus) -> ShellModel:
        """Update shell status."""
        shell = self.session.query(Shell).filter(Shell.id == shell_id).first()
        if not shell:
            raise ShellNotFound(shell_id)
        shell.status = status.value
        shell.updated_at = datetime.utcnow()
        self.session.flush()
        return self._to_model(shell)

    def update_activity(self, shell_id: str) -> ShellModel:
        """Update shell last activity timestamp."""
        shell = self.session.query(Shell).filter(Shell.id == shell_id).first()
        if not shell:
            raise ShellNotFound(shell_id)
        shell.last_activity = datetime.utcnow()
        shell.updated_at = datetime.utcnow()
        self.session.flush()
        return self._to_model(shell)

    def update_working_directory(self, shell_id: str, working_directory: str) -> ShellModel:
        """Update shell working directory."""
        shell = self.session.query(Shell).filter(Shell.id == shell_id).first()
        if not shell:
            raise ShellNotFound(shell_id)
        shell.working_directory = working_directory
        shell.updated_at = datetime.utcnow()
        self.session.flush()
        return self._to_model(shell)

    def delete(self, shell_id: str) -> None:
        """Delete shell."""
        shell = self.session.query(Shell).filter(Shell.id == shell_id).first()
        if shell:
            self.session.delete(shell)
            self.session.flush()

    @staticmethod
    def _to_model(shell: Shell) -> ShellModel:
        """Convert ORM entity to Pydantic model."""
        return ShellModel.model_validate(shell)


class OperationRepository:
    """Repository for operation history."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, operation_data: dict) -> OperationModel:
        """Create a new operation record."""
        operation = Operation(
            id=str(uuid4()),
            created_at=datetime.utcnow(),
            **operation_data,
        )
        self.session.add(operation)
        self.session.flush()
        return self._to_model(operation)

    def get(self, operation_id: str) -> OperationModel | None:
        """Get operation by ID."""
        operation = self.session.query(Operation).filter(
            Operation.id == operation_id
        ).first()
        return self._to_model(operation) if operation else None

    def list_by_shell(self, shell_id: str, limit: int = 100) -> list[OperationModel]:
        """List operations for a shell."""
        operations = (
            self.session.query(Operation)
            .filter(Operation.shell_id == shell_id)
            .order_by(Operation.created_at.desc())
            .limit(limit)
            .all()
        )
        return [self._to_model(op) for op in operations]

    def list_recent(self, limit: int = 100) -> list[OperationModel]:
        """List recent operations."""
        operations = (
            self.session.query(Operation)
            .order_by(Operation.created_at.desc())
            .limit(limit)
            .all()
        )
        return [self._to_model(op) for op in operations]

    @staticmethod
    def _to_model(operation: Operation) -> OperationModel:
        """Convert ORM entity to Pydantic model."""
        return OperationModel.model_validate(operation)


class NetworkSegmentRepository:
    """Repository for network segments."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, segment_data: dict) -> NetworkSegmentModel:
        """Create a new network segment."""
        segment = NetworkSegment(
            id=str(uuid4()),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            **segment_data,
        )
        self.session.add(segment)
        self.session.flush()
        return self._to_model(segment)

    def get(self, segment_id: str) -> NetworkSegmentModel | None:
        """Get segment by ID."""
        segment = self.session.query(NetworkSegment).filter(
            NetworkSegment.id == segment_id
        ).first()
        return self._to_model(segment) if segment else None

    def list_all(self) -> list[NetworkSegmentModel]:
        """List all segments."""
        segments = self.session.query(NetworkSegment).all()
        return [self._to_model(s) for s in segments]

    def delete(self, segment_id: str) -> None:
        """Delete segment."""
        segment = self.session.query(NetworkSegment).filter(
            NetworkSegment.id == segment_id
        ).first()
        if segment:
            self.session.delete(segment)
            self.session.flush()

    @staticmethod
    def _to_model(segment: NetworkSegment) -> NetworkSegmentModel:
        """Convert ORM entity to Pydantic model."""
        return NetworkSegmentModel.model_validate(segment)
