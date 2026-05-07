"""Unit tests for context storage layer."""

import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import numpy as np
import pytest

from amp.core.context.compression import ContextCompressor
from amp.core.context.embeddings import EmbeddingGenerator
from amp.core.context.search import SimilaritySearch
from amp.core.context.vector_store import VectorStore
from amp.exceptions import ContextException, VectorStoreFailed


class TestVectorStore:
    """Test VectorStore class."""

    @pytest.fixture
    def mock_chromadb(self):
        """Mock ChromaDB client."""
        # Patch at sys.modules level to intercept the import
        mock_chroma_module = Mock()
        mock_client = Mock()
        mock_collection = Mock()

        mock_chroma_module.PersistentClient.return_value = mock_client
        mock_client.get_collection.side_effect = Exception("Not found")
        mock_client.create_collection.return_value = mock_collection

        with patch.dict("sys.modules", {"chromadb": mock_chroma_module}):
            yield {
                "chromadb": mock_chroma_module,
                "client": mock_client,
                "collection": mock_collection,
            }

    def test_init_creates_collection(self, mock_chromadb):
        """Test VectorStore initialization creates collection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(tmpdir, "test_collection")

            assert store.collection_name == "test_collection"
            assert store.db_path == tmpdir
            mock_chromadb["client"].create_collection.assert_called_once()

    def test_init_loads_existing_collection(self, mock_chromadb):
        """Test VectorStore loads existing collection."""
        mock_collection = Mock()
        mock_chromadb["client"].get_collection.side_effect = None
        mock_chromadb["client"].get_collection.return_value = mock_collection

        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(tmpdir, "existing_collection")

            mock_chromadb["client"].get_collection.assert_called_once_with(
                name="existing_collection"
            )
            assert store._collection == mock_collection

    def test_init_without_chromadb_raises_error(self):
        """Test VectorStore raises error when ChromaDB not installed."""
        # Simulate ImportError when chromadb is not available
        with patch.dict("sys.modules", {"chromadb": None}):
            with pytest.raises(VectorStoreFailed) as exc_info:
                VectorStore("/tmp/test", "test")

            assert "not installed" in str(exc_info.value).lower()

    def test_add_operation(self, mock_chromadb):
        """Test adding operation to vector store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(tmpdir, "test")
            mock_collection = mock_chromadb["collection"]

            store.add_operation(
                operation_id="op123",
                command="ls -la",
                output="file1\nfile2\nfile3",
                metadata={
                    "shell_id": "shell123",
                    "timestamp": "2024-05-07T10:00:00",
                },
            )

            mock_collection.add.assert_called_once()
            call_args = mock_collection.add.call_args

            assert call_args.kwargs["ids"] == ["op123"]
            assert "ls -la" in call_args.kwargs["documents"][0]
            assert call_args.kwargs["metadatas"][0]["shell_id"] == "shell123"

    def test_search_by_command(self, mock_chromadb):
        """Test searching by command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(tmpdir, "test")
            mock_collection = mock_chromadb["collection"]

            # Mock query results
            mock_collection.query.return_value = {
                "ids": [["op1", "op2"]],
                "distances": [[0.1, 0.3]],
                "metadatas": [[
                    {"command": "ls -la", "shell_id": "shell1"},
                    {"command": "ls -l", "shell_id": "shell2"},
                ]],
                "documents": [["doc1", "doc2"]],
            }

            results = store.search_by_command("ls", top_k=5)

            assert len(results) == 2
            assert results[0]["id"] == "op1"
            assert results[0]["distance"] == 0.1
            assert results[0]["metadata"]["command"] == "ls -la"

    def test_search_by_output(self, mock_chromadb):
        """Test searching by output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(tmpdir, "test")
            mock_collection = mock_chromadb["collection"]

            mock_collection.query.return_value = {
                "ids": [["op1"]],
                "distances": [[0.2]],
                "metadatas": [[{"command": "cat file.txt"}]],
                "documents": [["Output: file contents"]],
            }

            results = store.search_by_output("file contents", top_k=5)

            assert len(results) == 1
            assert results[0]["id"] == "op1"

    def test_search_by_metadata(self, mock_chromadb):
        """Test searching by metadata filters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(tmpdir, "test")
            mock_collection = mock_chromadb["collection"]

            mock_collection.get.return_value = {
                "ids": ["op1", "op2"],
                "metadatas": [
                    {"shell_id": "shell123", "command": "pwd"},
                    {"shell_id": "shell123", "command": "whoami"},
                ],
                "documents": ["doc1", "doc2"],
            }

            results = store.search_by_metadata({"shell_id": "shell123"}, top_k=10)

            assert len(results) == 2
            assert results[0]["metadata"]["shell_id"] == "shell123"

    def test_delete_operation(self, mock_chromadb):
        """Test deleting operation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(tmpdir, "test")
            mock_collection = mock_chromadb["collection"]

            store.delete_operation("op123")

            mock_collection.delete.assert_called_once_with(ids=["op123"])

    def test_get_collection_stats(self, mock_chromadb):
        """Test getting collection statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorStore(tmpdir, "test")
            mock_collection = mock_chromadb["collection"]
            mock_collection.count.return_value = 42

            stats = store.get_collection_stats()

            assert stats["collection_name"] == "test"
            assert stats["total_operations"] == 42
            assert stats["db_path"] == tmpdir


class TestEmbeddingGenerator:
    """Test EmbeddingGenerator class."""

    @pytest.fixture
    def mock_sentence_transformer(self):
        """Mock SentenceTransformer."""
        # Patch at sys.modules level to intercept the import
        mock_st_module = Mock()
        mock_model = Mock()
        mock_st_module.SentenceTransformer.return_value = mock_model

        with patch.dict("sys.modules", {"sentence_transformers": mock_st_module}):
            yield mock_model

    def test_init_loads_model(self, mock_sentence_transformer):
        """Test EmbeddingGenerator loads model."""
        generator = EmbeddingGenerator("test-model")

        assert generator.model_name == "test-model"
        assert generator._model is not None

    def test_init_without_sentence_transformers_raises_error(self):
        """Test EmbeddingGenerator raises error when library not installed."""
        # Simulate ImportError when sentence_transformers is not available
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            with pytest.raises(ContextException) as exc_info:
                EmbeddingGenerator()

            assert "not installed" in str(exc_info.value).lower()

    def test_generate_embedding(self, mock_sentence_transformer):
        """Test generating single embedding."""
        mock_sentence_transformer.encode.return_value = np.array([0.1, 0.2, 0.3])

        generator = EmbeddingGenerator()
        embedding = generator.generate_embedding("test text")

        assert embedding == [0.1, 0.2, 0.3]
        mock_sentence_transformer.encode.assert_called_once()

    def test_generate_embedding_truncates_long_text(self, mock_sentence_transformer):
        """Test embedding generation truncates very long text."""
        mock_sentence_transformer.encode.return_value = np.array([0.1, 0.2])

        generator = EmbeddingGenerator()
        long_text = "a" * 10000
        _ = generator.generate_embedding(long_text)

        # Check that encode was called with truncated text
        call_args = mock_sentence_transformer.encode.call_args
        assert len(call_args[0][0]) <= 8000

    def test_generate_batch_embeddings(self, mock_sentence_transformer):
        """Test generating batch embeddings."""
        mock_sentence_transformer.encode.return_value = np.array([
            [0.1, 0.2],
            [0.3, 0.4],
            [0.5, 0.6],
        ])

        generator = EmbeddingGenerator()
        embeddings = generator.generate_batch_embeddings(["text1", "text2", "text3"])

        assert len(embeddings) == 3
        assert embeddings[0] == [0.1, 0.2]
        assert embeddings[2] == [0.5, 0.6]

    def test_get_embedding_dimension(self, mock_sentence_transformer):
        """Test getting embedding dimension."""
        mock_sentence_transformer.get_sentence_embedding_dimension.return_value = 384

        generator = EmbeddingGenerator()
        dimension = generator.get_embedding_dimension()

        assert dimension == 384


class TestSimilaritySearch:
    """Test SimilaritySearch class."""

    @pytest.fixture
    def mock_vector_store(self):
        """Mock VectorStore."""
        return Mock(spec=VectorStore)

    def test_find_similar_commands(self, mock_vector_store):
        """Test finding similar commands."""
        mock_vector_store.search_by_command.return_value = [
            {"id": "op1", "distance": 0.1, "metadata": {"command": "ls -la"}},
            {"id": "op2", "distance": 0.3, "metadata": {"command": "ls -l"}},
            {"id": "op3", "distance": 0.8, "metadata": {"command": "pwd"}},
        ]

        search = SimilaritySearch(mock_vector_store)
        results = search.find_similar_commands("ls", top_k=10, threshold=0.5)

        assert len(results) == 2  # op3 filtered out by threshold
        assert results[0]["id"] == "op1"
        assert results[1]["id"] == "op2"

    def test_find_similar_outputs(self, mock_vector_store):
        """Test finding similar outputs."""
        mock_vector_store.search_by_output.return_value = [
            {"id": "op1", "distance": 0.2, "metadata": {}},
        ]

        search = SimilaritySearch(mock_vector_store)
        results = search.find_similar_outputs("error message", top_k=5, threshold=0.5)

        assert len(results) == 1
        assert results[0]["id"] == "op1"

    def test_find_by_context_with_shell_id(self, mock_vector_store):
        """Test finding operations by shell context."""
        mock_vector_store.search_by_metadata.return_value = [
            {"id": "op1", "metadata": {"shell_id": "shell123"}},
            {"id": "op2", "metadata": {"shell_id": "shell123"}},
        ]

        search = SimilaritySearch(mock_vector_store)
        results = search.find_by_context(shell_id="shell123", top_k=10)

        assert len(results) == 2
        mock_vector_store.search_by_metadata.assert_called_once_with(
            {"shell_id": "shell123"}, top_k=10
        )

    def test_find_by_context_with_tunnel_id(self, mock_vector_store):
        """Test finding operations by tunnel context."""
        mock_vector_store.search_by_metadata.return_value = []

        search = SimilaritySearch(mock_vector_store)
        _ = search.find_by_context(tunnel_id="tunnel456", top_k=10)

        mock_vector_store.search_by_metadata.assert_called_once_with(
            {"tunnel_id": "tunnel456"}, top_k=10
        )

    def test_find_by_context_without_filters(self, mock_vector_store):
        """Test finding by context without filters returns empty."""
        search = SimilaritySearch(mock_vector_store)
        results = search.find_by_context(top_k=10)

        assert results == []
        mock_vector_store.search_by_metadata.assert_not_called()

    def test_rank_by_relevance(self, mock_vector_store):
        """Test ranking results by relevance."""
        now = datetime.utcnow()
        old_time = now - timedelta(hours=48)

        results = [
            {
                "id": "op1",
                "distance": 0.2,  # similarity = 0.8
                "metadata": {"timestamp": now.isoformat()},
            },
            {
                "id": "op2",
                "distance": 0.1,  # similarity = 0.9
                "metadata": {"timestamp": old_time.isoformat()},
            },
        ]

        search = SimilaritySearch(mock_vector_store)
        ranked = search.rank_by_relevance(results, "test query", recency_weight=0.3)

        assert len(ranked) == 2
        assert "relevance_score" in ranked[0]
        assert "similarity_score" in ranked[0]
        assert "recency_score" in ranked[0]

        # op1 should rank higher due to recency despite lower similarity
        assert ranked[0]["id"] == "op1"


class TestContextCompressor:
    """Test ContextCompressor class."""

    def test_init(self):
        """Test ContextCompressor initialization."""
        compressor = ContextCompressor(max_tokens=5000, threshold=0.6)

        assert compressor.max_tokens == 5000
        assert compressor.threshold == 0.6

    def test_filter_by_relevance(self):
        """Test filtering operations by relevance."""
        operations = [
            {"id": "op1", "relevance_score": 0.9},
            {"id": "op2", "relevance_score": 0.5},
            {"id": "op3", "relevance_score": 0.8},
            {"id": "op4", "relevance_score": 0.3},
        ]

        compressor = ContextCompressor(threshold=0.6)
        filtered = compressor.filter_by_relevance(operations, threshold=0.6)

        assert len(filtered) == 2
        assert filtered[0]["id"] == "op1"
        assert filtered[1]["id"] == "op3"

    def test_estimate_tokens(self):
        """Test token estimation."""
        compressor = ContextCompressor()

        # ~4 characters per token
        text = "a" * 400
        tokens = compressor.estimate_tokens(text)

        assert tokens == 100

    def test_select_top_operations(self):
        """Test selecting operations within token budget."""
        operations = [
            {"id": "op1", "document": "a" * 400},  # ~100 tokens
            {"id": "op2", "document": "b" * 400},  # ~100 tokens
            {"id": "op3", "document": "c" * 400},  # ~100 tokens
            {"id": "op4", "document": "d" * 400},  # ~100 tokens
        ]

        compressor = ContextCompressor(max_tokens=250)
        selected = compressor.select_top_operations(operations, max_tokens=250)

        # Should select first 2 operations (200 tokens total)
        assert len(selected) == 2
        assert selected[0]["id"] == "op1"
        assert selected[1]["id"] == "op2"

    def test_compress_operations(self):
        """Test full compression pipeline."""
        operations = [
            {"id": "op1", "relevance_score": 0.9, "document": "a" * 400},
            {"id": "op2", "relevance_score": 0.8, "document": "b" * 400},
            {"id": "op3", "relevance_score": 0.5, "document": "c" * 400},
            {"id": "op4", "relevance_score": 0.9, "document": "d" * 400},
        ]

        compressor = ContextCompressor(max_tokens=250, threshold=0.7)
        compressed = compressor.compress_operations(operations, query="test")

        # Should filter out op3 (relevance < 0.7), then select first 2 by token budget
        assert len(compressed) == 2
        assert compressed[0]["id"] == "op1"
        assert compressed[1]["id"] == "op2"

    def test_get_compression_stats(self):
        """Test getting compression statistics."""
        original = [
            {"id": "op1", "document": "a" * 400},
            {"id": "op2", "document": "b" * 400},
            {"id": "op3", "document": "c" * 400},
        ]

        compressed = [
            {"id": "op1", "document": "a" * 400},
        ]

        compressor = ContextCompressor(max_tokens=1000, threshold=0.7)
        stats = compressor.get_compression_stats(original, compressed)

        assert stats["original_count"] == 3
        assert stats["compressed_count"] == 1
        assert stats["compression_ratio"] == pytest.approx(1 / 3)
        assert stats["token_budget"] == 1000
        assert stats["threshold"] == 0.7
