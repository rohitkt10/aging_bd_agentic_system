from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer
from transformers.utils import logging as hf_logging
import logging
hf_logging.set_verbosity_error()
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)


def embed_texts(
    texts: list[str],
    model_id: str,
    batch_size: int,
    device: str,
    normalize: bool = True,
) -> np.ndarray:
    """
    Generate embeddings for a list of texts using SentenceTransformers.
    """
    if not texts:
        raise ValueError("The 'texts' list is empty. Cannot generate embeddings.")

    model = SentenceTransformer(model_id, device=device)

    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=normalize,
        convert_to_numpy=True,
    )

    return embeddings.astype(np.float32)
