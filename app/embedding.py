from dataclasses import dataclass

MODEL_NAME = "BAAI/bge-m3"
CHUNK_TOKENS = 256
OVERLAP_TOKENS = 40


class InvalidText(ValueError):
    """Text cannot be embedded within the service's supported limits."""


@dataclass(frozen=True)
class Chunk:
    text: str
    start: int
    end: int


def split_text(
    text: str, tokenizer, size: int = CHUNK_TOKENS, overlap: int = OVERLAP_TOKENS
) -> list[Chunk]:
    """Use token windows but preserve exact source substrings through offsets."""
    if not 0 <= overlap < size:
        raise ValueError("Expected 0 <= overlap < size")
    offsets = tokenizer(
        text, add_special_tokens=False, return_offsets_mapping=True, truncation=False
    )["offset_mapping"]
    if not offsets:
        raise InvalidText("Text contains no searchable tokens")
    chunks = []
    for first in range(0, len(offsets), size - overlap):
        last = min(first + size, len(offsets))
        start = offsets[first][0]
        end = offsets[last - 1][1]
        chunks.append(Chunk(text[start:end], start, end))
        if last == len(offsets):
            break
    return chunks


class LocalEmbedder:
    def __init__(self):
        # Lazy import keeps unit tests independent of heavyweight model downloads.
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(MODEL_NAME, device="cpu")
        self.dimension = self.model.get_embedding_dimension()

    def chunks(self, text: str) -> list[Chunk]:
        return split_text(text, self.model.tokenizer)

    def encode(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        # BGE-M3 uses the same unprefixed input for queries and passages.
        inputs = texts
        lengths = self.model.tokenizer(inputs, truncation=False)["input_ids"]
        if any(len(tokens) > self.model.max_seq_length for tokens in lengths):
            raise InvalidText("Input exceeds the embedding model token limit")
        return self.model.encode(
            inputs, normalize_embeddings=True, batch_size=16, show_progress_bar=False
        ).tolist()
