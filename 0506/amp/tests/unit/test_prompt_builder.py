"""Unit tests for prompt builder."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from amp.core.context.formatter import PromptFormatter
from amp.core.context.prompt_builder import PromptBuilder
from amp.core.context.relevance import RelevanceScorer


class TestRelevanceScorer:
    """Test RelevanceScorer class."""

    def test_init(self):
        """Test RelevanceScorer initialization."""
        scorer = RelevanceScorer(
            similarity_weight=0.5,
            recency_weight=0.3,
            context_weight=0.2,
        )

        assert scorer.similarity_weight == 0.5
        assert scorer.recency_weight == 0.3
        assert scorer.context_weight == 0.2

    def test_init_normalizes_weights(self):
        """Test weights are normalized if they don't sum to 1.0."""
        scorer = RelevanceScorer(
            similarity_weight=0.6,
            recency_weight=0.6,
            context_weight=0.6,
        )

        # Weights should be normalized to sum to 1.0
        total = scorer.similarity_weight + scorer.recency_weight + scorer.context_weight
        assert abs(total - 1.0) < 0.01

    def test_calculate_similarity_score(self):
        """Test similarity score calculation."""
        scorer = RelevanceScorer()

        # Distance 0 = perfect match (similarity 1.0)
        op1 = {"distance": 0.0}
        assert scorer.calculate_similarity_score(op1, "query") == 1.0

        # Distance 1 = 50% similar
        op2 = {"distance": 1.0}
        assert scorer.calculate_similarity_score(op2, "query") == 0.5

        # Distance 2 = opposite (similarity 0.0)
        op3 = {"distance": 2.0}
        assert scorer.calculate_similarity_score(op3, "query") == 0.0

    def test_calculate_recency_score(self):
        """Test recency score calculation."""
        scorer = RelevanceScorer()
        now = datetime.utcnow()

        # Recent operation (1 hour ago)
        recent_op = {
            "metadata": {"timestamp": (now - timedelta(hours=1)).isoformat()}
        }
        recent_score = scorer.calculate_recency_score(recent_op)
        assert recent_score > 0.9  # Should be very high

        # Old operation (48 hours ago)
        old_op = {
            "metadata": {"timestamp": (now - timedelta(hours=48)).isoformat()}
        }
        old_score = scorer.calculate_recency_score(old_op)
        assert old_score < 0.5  # Should be lower

        # No timestamp
        no_timestamp_op = {"metadata": {}}
        assert scorer.calculate_recency_score(no_timestamp_op) == 0.1

    def test_calculate_context_score(self):
        """Test context match score calculation."""
        scorer = RelevanceScorer()

        # Exact shell_id match
        op1 = {"metadata": {"shell_id": "shell123"}}
        context1 = {"shell_id": "shell123"}
        score1 = scorer.calculate_context_score(op1, context1)
        assert score1 == 1.0

        # Different shell_id
        op2 = {"metadata": {"shell_id": "shell456"}}
        context2 = {"shell_id": "shell123"}
        score2 = scorer.calculate_context_score(op2, context2)
        assert score2 == 0.3  # Partial credit

        # No context
        score3 = scorer.calculate_context_score(op1, {})
        assert score3 == 0.5

    def test_score_operation(self):
        """Test scoring a single operation."""
        scorer = RelevanceScorer(
            similarity_weight=0.5,
            recency_weight=0.3,
            context_weight=0.2,
        )

        now = datetime.utcnow()
        operation = {
            "distance": 0.2,  # High similarity
            "metadata": {
                "timestamp": now.isoformat(),
                "shell_id": "shell123",
            },
        }
        context = {"shell_id": "shell123"}

        score = scorer.score_operation(operation, "query", context)

        # Should be high score (good similarity, recent, context match)
        assert score > 0.8

    def test_score_operations(self):
        """Test scoring multiple operations."""
        scorer = RelevanceScorer()

        now = datetime.utcnow()
        operations = [
            {
                "id": "op1",
                "distance": 0.1,
                "metadata": {"timestamp": now.isoformat()},
            },
            {
                "id": "op2",
                "distance": 0.5,
                "metadata": {"timestamp": (now - timedelta(hours=24)).isoformat()},
            },
            {
                "id": "op3",
                "distance": 0.9,
                "metadata": {"timestamp": (now - timedelta(hours=48)).isoformat()},
            },
        ]

        scored = scorer.score_operations(operations, "query", {})

        # Should have relevance_score added
        assert all("relevance_score" in op for op in scored)

        # Should be sorted by relevance (descending)
        assert scored[0]["relevance_score"] >= scored[1]["relevance_score"]
        assert scored[1]["relevance_score"] >= scored[2]["relevance_score"]


class TestPromptFormatter:
    """Test PromptFormatter class."""

    def test_format_operation(self):
        """Test formatting a single operation."""
        operation = {
            "metadata": {
                "command": "ls -la",
                "output_preview": "file1\nfile2",
                "timestamp": "2024-05-07T10:00:00",
                "shell_id": "shell123",
            },
            "relevance_score": 0.85,
        }

        formatted = PromptFormatter.format_operation(operation)

        assert "Command: ls -la" in formatted
        assert "Output: file1" in formatted
        assert "Shell: shell123" in formatted
        assert "Relevance: 0.85" in formatted

    def test_format_operations(self):
        """Test formatting multiple operations."""
        operations = [
            {
                "metadata": {"command": "pwd", "output_preview": "/home/user"},
                "relevance_score": 0.9,
            },
            {
                "metadata": {"command": "whoami", "output_preview": "root"},
                "relevance_score": 0.8,
            },
        ]

        formatted = PromptFormatter.format_operations(operations)

        assert "## Operation 1" in formatted
        assert "## Operation 2" in formatted
        assert "Command: pwd" in formatted
        assert "Command: whoami" in formatted

    def test_format_operations_empty(self):
        """Test formatting empty operations list."""
        formatted = PromptFormatter.format_operations([])
        assert formatted == "No recent operations"

    def test_format_tunnel(self):
        """Test formatting a single tunnel."""
        tunnel = {
            "id": "tunnel123",
            "name": "DMZ Tunnel",
            "tunnel_type": "chisel",
            "status": "active",
            "local_host": "127.0.0.1",
            "local_port": 8080,
            "remote_host": "10.0.1.5",
            "remote_port": 22,
            "parent_tunnel_id": None,
        }

        formatted = PromptFormatter.format_tunnel(tunnel)

        assert "DMZ Tunnel (tunnel123)" in formatted
        assert "Type: chisel" in formatted
        assert "Status: active" in formatted
        assert "Local: 127.0.0.1:8080" in formatted
        assert "Remote: 10.0.1.5:22" in formatted

    def test_format_tunnels(self):
        """Test formatting multiple tunnels."""
        tunnels = [
            {
                "id": "t1",
                "name": "Tunnel 1",
                "tunnel_type": "chisel",
                "status": "active",
                "local_host": "127.0.0.1",
                "local_port": 8080,
                "remote_host": "10.0.1.5",
                "remote_port": 22,
            },
        ]

        formatted = PromptFormatter.format_tunnels(tunnels)

        assert "Tunnel 1 (t1)" in formatted

    def test_format_tunnels_empty(self):
        """Test formatting empty tunnels list."""
        formatted = PromptFormatter.format_tunnels([])
        assert formatted == "No active tunnels"

    def test_format_shell(self):
        """Test formatting a single shell."""
        shell = {
            "id": "shell123",
            "name": "Web Server Shell",
            "shell_type": "reverse",
            "os_type": "linux",
            "status": "active",
            "target_host": "10.0.1.10",
            "target_port": 4444,
            "tunnel_id": "tunnel123",
            "working_directory": "/var/www",
            "privilege_level": "user",
        }

        formatted = PromptFormatter.format_shell(shell)

        assert "Web Server Shell (shell123)" in formatted
        assert "Type: reverse (linux)" in formatted
        assert "Status: active" in formatted
        assert "Target: 10.0.1.10:4444" in formatted
        assert "Tunnel: tunnel123" in formatted
        assert "Working Dir: /var/www" in formatted
        assert "Privilege: user" in formatted

    def test_format_shells(self):
        """Test formatting multiple shells."""
        shells = [
            {
                "id": "s1",
                "name": "Shell 1",
                "shell_type": "reverse",
                "os_type": "linux",
                "status": "active",
                "target_host": "10.0.1.10",
                "target_port": 4444,
            },
        ]

        formatted = PromptFormatter.format_shells(shells)

        assert "Shell 1 (s1)" in formatted

    def test_format_shells_empty(self):
        """Test formatting empty shells list."""
        formatted = PromptFormatter.format_shells([])
        assert formatted == "No active shells"

    def test_format_topology(self):
        """Test formatting network topology."""
        tunnels = [
            {
                "id": "t1",
                "name": "DMZ",
                "status": "active",
                "parent_tunnel_id": None,
            },
            {
                "id": "t2",
                "name": "Internal",
                "status": "active",
                "parent_tunnel_id": "t1",
            },
        ]

        formatted = PromptFormatter.format_topology(tunnels)

        assert "```mermaid" in formatted
        assert "graph LR" in formatted
        assert "Attacker[Attacker]" in formatted
        assert "Attacker --> Tt1[DMZ]" in formatted
        assert "Tt1 --> Tt2[Internal]" in formatted
        assert "```" in formatted

    def test_format_topology_empty(self):
        """Test formatting empty topology."""
        formatted = PromptFormatter.format_topology([])

        assert "```mermaid" in formatted
        assert "Attacker[Attacker]" in formatted


class TestPromptBuilder:
    """Test PromptBuilder class."""

    @pytest.fixture
    def mock_vector_store(self):
        """Mock VectorStore."""
        mock = Mock()
        mock.search_by_command.return_value = []
        mock.get_collection_stats.return_value = {
            "total_operations": 0,
            "collection_name": "test",
            "db_path": "/tmp/test",
        }
        return mock

    @pytest.fixture
    def mock_tunnel_manager(self):
        """Mock TunnelManager."""
        mock = Mock()
        mock_db = Mock()
        mock_session = Mock()
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)
        mock_db.session.return_value = mock_session
        mock.database = mock_db
        return mock

    @pytest.fixture
    def mock_shell_manager(self):
        """Mock ShellManager."""
        mock = Mock()
        mock_db = Mock()
        mock_session = Mock()
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)
        mock_db.session.return_value = mock_session
        mock.database = mock_db
        return mock

    def test_init(self, mock_vector_store, mock_tunnel_manager, mock_shell_manager):
        """Test PromptBuilder initialization."""
        builder = PromptBuilder(
            vector_store=mock_vector_store,
            tunnel_manager=mock_tunnel_manager,
            shell_manager=mock_shell_manager,
            max_tokens=5000,
        )

        assert builder.max_tokens == 5000
        assert builder.vector_store == mock_vector_store
        assert builder.tunnel_manager == mock_tunnel_manager
        assert builder.shell_manager == mock_shell_manager

    @patch("amp.storage.repository.TunnelRepository")
    @patch("amp.storage.repository.ShellRepository")
    def test_build_prompt(
        self,
        mock_shell_repo_class,
        mock_tunnel_repo_class,
        mock_vector_store,
        mock_tunnel_manager,
        mock_shell_manager,
    ):
        """Test building a complete prompt."""
        # Mock repositories
        mock_tunnel_repo = Mock()
        mock_tunnel_repo.list_active.return_value = []
        mock_tunnel_repo_class.return_value = mock_tunnel_repo

        mock_shell_repo = Mock()
        mock_shell_repo.list_active.return_value = []
        mock_shell_repo_class.return_value = mock_shell_repo

        builder = PromptBuilder(
            vector_store=mock_vector_store,
            tunnel_manager=mock_tunnel_manager,
            shell_manager=mock_shell_manager,
        )

        prompt = builder.build_prompt("Scan the network for open ports")

        # Check sections are present
        assert "# Current Task" in prompt
        assert "Scan the network for open ports" in prompt
        assert "# Network Topology" in prompt
        assert "# Active Tunnels" in prompt
        assert "# Active Shells" in prompt
        assert "# Recent Operations" in prompt
        assert "# Context" in prompt

    @patch("amp.storage.repository.TunnelRepository")
    def test_get_active_tunnels(
        self,
        mock_tunnel_repo_class,
        mock_vector_store,
        mock_tunnel_manager,
        mock_shell_manager,
    ):
        """Test getting active tunnels."""
        # Mock tunnel data
        mock_tunnel = Mock()
        mock_tunnel.id = "t1"
        mock_tunnel.name = "DMZ Tunnel"
        mock_tunnel.tunnel_type = "chisel"
        mock_tunnel.status = "active"
        mock_tunnel.local_host = "127.0.0.1"
        mock_tunnel.local_port = 8080
        mock_tunnel.remote_host = "10.0.1.5"
        mock_tunnel.remote_port = 22
        mock_tunnel.parent_tunnel_id = None

        mock_tunnel_repo = Mock()
        mock_tunnel_repo.list_active.return_value = [mock_tunnel]
        mock_tunnel_repo_class.return_value = mock_tunnel_repo

        builder = PromptBuilder(
            vector_store=mock_vector_store,
            tunnel_manager=mock_tunnel_manager,
            shell_manager=mock_shell_manager,
        )

        tunnels = builder.get_active_tunnels()

        assert len(tunnels) == 1
        assert tunnels[0]["id"] == "t1"
        assert tunnels[0]["name"] == "DMZ Tunnel"

    @patch("amp.storage.repository.ShellRepository")
    def test_get_active_shells(
        self,
        mock_shell_repo_class,
        mock_vector_store,
        mock_tunnel_manager,
        mock_shell_manager,
    ):
        """Test getting active shells."""
        # Mock shell data
        mock_shell = Mock()
        mock_shell.id = "s1"
        mock_shell.name = "Web Shell"
        mock_shell.shell_type = "reverse"
        mock_shell.os_type = "linux"
        mock_shell.status = "active"
        mock_shell.target_host = "10.0.1.10"
        mock_shell.target_port = 4444
        mock_shell.tunnel_id = "t1"
        mock_shell.working_directory = "/var/www"
        mock_shell.privilege_level = "user"

        mock_shell_repo = Mock()
        mock_shell_repo.list_active.return_value = [mock_shell]
        mock_shell_repo_class.return_value = mock_shell_repo

        builder = PromptBuilder(
            vector_store=mock_vector_store,
            tunnel_manager=mock_tunnel_manager,
            shell_manager=mock_shell_manager,
        )

        shells = builder.get_active_shells()

        assert len(shells) == 1
        assert shells[0]["id"] == "s1"
        assert shells[0]["name"] == "Web Shell"

    def test_get_relevant_operations(
        self,
        mock_vector_store,
        mock_tunnel_manager,
        mock_shell_manager,
    ):
        """Test getting relevant operations."""
        now = datetime.utcnow()

        # Mock vector store results
        mock_vector_store.search_by_command.return_value = [
            {
                "id": "op1",
                "distance": 0.1,
                "metadata": {
                    "command": "nmap -sV 10.0.1.0/24",
                    "output_preview": "Open ports: 22, 80, 443",
                    "timestamp": now.isoformat(),
                },
                "document": "Command: nmap -sV 10.0.1.0/24\nOutput: Open ports: 22, 80, 443",
            },
            {
                "id": "op2",
                "distance": 0.3,
                "metadata": {
                    "command": "nmap -p- 10.0.1.5",
                    "output_preview": "1000 ports scanned",
                    "timestamp": (now - timedelta(hours=2)).isoformat(),
                },
                "document": "Command: nmap -p- 10.0.1.5\nOutput: 1000 ports scanned",
            },
        ]

        builder = PromptBuilder(
            vector_store=mock_vector_store,
            tunnel_manager=mock_tunnel_manager,
            shell_manager=mock_shell_manager,
        )

        operations = builder.get_relevant_operations("scan network", limit=10)

        # Should return operations with relevance scores
        assert len(operations) > 0
        assert all("relevance_score" in op for op in operations)

    def test_estimate_prompt_tokens(
        self,
        mock_vector_store,
        mock_tunnel_manager,
        mock_shell_manager,
    ):
        """Test token estimation."""
        builder = PromptBuilder(
            vector_store=mock_vector_store,
            tunnel_manager=mock_tunnel_manager,
            shell_manager=mock_shell_manager,
        )

        # ~4 characters per token
        text = "a" * 400
        tokens = builder.estimate_prompt_tokens(text)

        assert tokens == 100

    def test_get_context_stats(
        self,
        mock_vector_store,
        mock_tunnel_manager,
        mock_shell_manager,
    ):
        """Test getting context statistics."""
        mock_vector_store.get_collection_stats.return_value = {
            "total_operations": 42,
        }

        builder = PromptBuilder(
            vector_store=mock_vector_store,
            tunnel_manager=mock_tunnel_manager,
            shell_manager=mock_shell_manager,
            max_tokens=5000,
            relevance_threshold=0.4,
        )

        with patch.object(builder, "get_active_tunnels", return_value=[{}, {}]):
            with patch.object(builder, "get_active_shells", return_value=[{}]):
                stats = builder.get_context_stats()

        assert stats["total_operations"] == 42
        assert stats["active_tunnels"] == 2
        assert stats["active_shells"] == 1
        assert stats["max_tokens"] == 5000
        assert stats["relevance_threshold"] == 0.4

    def test_build_prompt_with_context_filter(
        self,
        mock_vector_store,
        mock_tunnel_manager,
        mock_shell_manager,
    ):
        """Test building prompt with context filter."""
        builder = PromptBuilder(
            vector_store=mock_vector_store,
            tunnel_manager=mock_tunnel_manager,
            shell_manager=mock_shell_manager,
        )

        context = {"shell_id": "shell123"}

        with patch.object(builder, "get_active_tunnels", return_value=[]):
            with patch.object(builder, "get_active_shells", return_value=[]):
                with patch.object(builder, "get_relevant_operations", return_value=[]):
                    prompt = builder.build_prompt("test query", context=context)

        assert "# Current Task" in prompt
        assert "test query" in prompt
