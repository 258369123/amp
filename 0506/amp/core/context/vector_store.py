"""ChromaDB vector store wrapper for operation history."""

import logging
from typing import Any

from amp.exceptions import VectorStoreFailed

logger = logging.getLogger(__name__)


class VectorStore:
    """ChromaDB wrapper for storing and querying operation embeddings."""

    def __init__(self, db_path: str, collection_name: str = "operations"):
        """Initialize ChromaDB client.

        Args:
            db_path: Path to ChromaDB database directory
            collection_name: Name of the collection to use
        """
        self.db_path = db_path
        self.collection_name = collection_name
        self._client = None
        self._collection = None

        try:
            import chromadb

            # Use PersistentClient for the new ChromaDB API
            self._client = chromadb.PersistentClient(path=db_path)

            # Get or create collection
            try:
                self._collection = self._client.get_collection(name=collection_name)
                logger.info(f"Loaded existing collection: {collection_name}")
            except Exception:
                self._collection = self._client.create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info(f"Created new collection: {collection_name}")

        except ImportError as e:
            raise VectorStoreFailed(
                "ChromaDB not installed. Install with: pip install chromadb",
                {"error": str(e)},
            ) from e
        except Exception as e:
            raise VectorStoreFailed(
                f"Failed to initialize ChromaDB: {e}",
                {"db_path": db_path, "error": str(e)},
            ) from e

    def add_operation(
        self,
        operation_id: str,
        command: str,
        output: str,
        metadata: dict[str, Any],
    ) -> None:
        """Store operation with embeddings.

        Args:
            operation_id: Unique operation ID
            command: Command text
            output: Command output text
            metadata: Additional metadata (shell_id, tunnel_id, timestamp, etc.)
        """
        try:
            # Combine command and output for embedding
            # Store command separately for command-specific search
            document = f"Command: {command}\nOutput: {output[:1000]}"  # Limit output length

            self._collection.add(
                documents=[document],
                metadatas=[{
                    "operation_id": operation_id,
                    "command": command,
                    "output_preview": output[:500],  # Store preview in metadata
                    **metadata,
                }],
                ids=[operation_id],
            )

            logger.debug(f"Added operation {operation_id} to vector store")

        except Exception as e:
            logger.error(f"Failed to add operation {operation_id}: {e}")
            raise VectorStoreFailed(
                f"Failed to add operation: {e}",
                {"operation_id": operation_id, "error": str(e)},
            ) from e

    def search_by_command(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar commands.

        Args:
            query: Query text (command to search for)
            top_k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of results with metadata and distances
        """
        try:
            query_text = f"Command: {query}"
            where = filters if filters else None

            results = self._collection.query(
                query_texts=[query_text],
                n_results=top_k,
                where=where,
            )

            return self._format_results(results)

        except Exception as e:
            logger.error(f"Search by command failed: {e}")
            raise VectorStoreFailed(
                f"Search failed: {e}",
                {"query": query, "error": str(e)},
            ) from e

    def search_by_output(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar outputs.

        Args:
            query: Query text (output pattern to search for)
            top_k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of results with metadata and distances
        """
        try:
            query_text = f"Output: {query}"
            where = filters if filters else None

            results = self._collection.query(
                query_texts=[query_text],
                n_results=top_k,
                where=where,
            )

            return self._format_results(results)

        except Exception as e:
            logger.error(f"Search by output failed: {e}")
            raise VectorStoreFailed(
                f"Search failed: {e}",
                {"query": query, "error": str(e)},
            ) from e

    def search_by_metadata(
        self,
        filters: dict[str, Any],
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Filter operations by metadata.

        Args:
            filters: Metadata filters (e.g., {"shell_id": "abc123"})
            top_k: Number of results to return

        Returns:
            List of results with metadata
        """
        try:
            results = self._collection.get(
                where=filters,
                limit=top_k,
            )

            # Format get() results (different structure than query())
            formatted = []
            if results["ids"]:
                for i, op_id in enumerate(results["ids"]):
                    formatted.append({
                        "id": op_id,
                        "metadata": results["metadatas"][i] if results["metadatas"] else {},
                        "document": results["documents"][i] if results["documents"] else "",
                        "distance": 0.0,  # No distance for metadata-only search
                    })

            return formatted

        except Exception as e:
            logger.error(f"Search by metadata failed: {e}")
            raise VectorStoreFailed(
                f"Metadata search failed: {e}",
                {"filters": filters, "error": str(e)},
            ) from e

    def delete_operation(self, operation_id: str) -> None:
        """Remove operation from vector store.

        Args:
            operation_id: Operation ID to delete
        """
        try:
            self._collection.delete(ids=[operation_id])
            logger.debug(f"Deleted operation {operation_id} from vector store")

        except Exception as e:
            logger.warning(f"Failed to delete operation {operation_id}: {e}")
            # Don't raise - deletion failures are non-critical

    def get_collection_stats(self) -> dict[str, Any]:
        """Get collection statistics.

        Returns:
            Dictionary with collection stats
        """
        try:
            count = self._collection.count()
            return {
                "collection_name": self.collection_name,
                "total_operations": count,
                "db_path": self.db_path,
            }

        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {
                "collection_name": self.collection_name,
                "total_operations": 0,
                "db_path": self.db_path,
                "error": str(e),
            }

    def _format_results(self, results: dict[str, Any]) -> list[dict[str, Any]]:
        """Format ChromaDB query results.

        Args:
            results: Raw ChromaDB query results

        Returns:
            Formatted list of results
        """
        formatted = []

        if not results["ids"] or not results["ids"][0]:
            return formatted

        # ChromaDB returns nested lists for batch queries
        ids = results["ids"][0]
        distances = results["distances"][0] if results["distances"] else [0.0] * len(ids)
        metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(ids)
        documents = results["documents"][0] if results["documents"] else [""] * len(ids)

        for i, op_id in enumerate(ids):
            formatted.append({
                "id": op_id,
                "distance": distances[i],
                "metadata": metadatas[i],
                "document": documents[i],
            })

        return formatted
