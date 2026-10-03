"""Regression: classify() must not hang when called from several threads (evals use asyncio.to_thread).

A cached pydantic-ai Agent kept an async HTTP client bound to the first event loop; a second call from
another thread then waited forever. TestModel has no HTTP client, so this guards the no-cache design.
"""

import asyncio

from pydantic_ai.models.test import TestModel

from app import classify as classify_module


def test_classify_works_from_several_threads():
    model = TestModel()
    classify_module.classify("Factura", "texto", model=model)  # first call on the main thread

    async def many():
        return await asyncio.wait_for(asyncio.gather(*[
            asyncio.to_thread(classify_module.classify, "Banco", f"texto {i}", model=model) for i in range(3)
        ]), timeout=30)

    assert len(asyncio.run(many())) == 3


def test_agents_are_not_cached():
    assert classify_module._agent("test") is not classify_module._agent("test")
