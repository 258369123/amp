"""Embedding generation for operation text."""

import logging

from amp.exceptions import ContextException

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generate embeddings for operation text using sentence transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize embedding model.

        Args:
            model_name: Name of the sentence-transformers model
        """
        self.model_name = model_name
        self._model = None

        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(model_name)
            logger.info(f"Loaded embedding model: {model_name}")

        except ImportError as e:
            raise ContextException(
                "sentence-transformers not installed. Install with: pip install sentence-transformers",
                {"error": str(e)},
            ) from e
        except Exception as e:
            raise ContextException(
                f"Failed to load embedding model: {e}",
                {"model_name": model_name, "error": str(e)},
            ) from e

    def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for text.

        Args:
            text: Input text

        Returns:
            Embedding vector as list of floats
        """
        try:
            # Truncate very long text to avoid memory issues
            max_length = 8000  # characters
            if len(text) > max_length:
                text = text[:max_length]
                logger.debug(f"Truncated text to {max_length} characters")

            embedding = self._model.encode(text, convert_to_numpy=True)
            return embedding.tolist()

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise ContextException(
                f"Embedding generation failed: {e}",
                {"text_length": len(text), "error": str(e)},
            ) from e

    def generate_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of input texts

        Returns:
            List of embedding vectors
        """
        try:
            # Truncate long texts
            max_length = 8000
            truncated_texts = [
                text[:max_length] if len(text) > max_length else text
                for text in texts
            ]

            embeddings = self._model.encode(
                truncated_texts,
                convert_to_numpy=True,
                show_progress_bar=len(texts) > 10,
            )

            return [emb.tolist() for emb in embeddings]

        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise ContextException(
                f"Batch embedding generation failed: {e}",
                {"batch_size": len(texts), "error": str(e)},
            ) from e

    def get_embedding_dimension(self) -> int:
        """Get the dimension of embedding vectors.

        Returns:
            Embedding dimension
        """
        try:
            return self._model.get_sentence_embedding_dimension()
        except Exception as e:
            logger.warning(f"Failed to get embedding dimension: {e}")
            # Default dimension for all-MiniLM-L6-v2
            return 384
