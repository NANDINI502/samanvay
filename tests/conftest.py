"""All tests run offline: Nemotron calls are replaced by labelled stub replies
(MEDBOT_MOCK_LLM=1), and indexes are built once if missing."""
import os
from pathlib import Path

import pytest

os.environ["MEDBOT_MOCK_LLM"] = "1"


@pytest.fixture(scope="session", autouse=True)
def built_indexes():
    from agents.registry import ORGANS
    from rag.ingest import INDEX_DIR, build_index
    for organ in ORGANS:
        if not (Path(INDEX_DIR) / f"{organ}.faiss").exists():
            build_index(organ)
