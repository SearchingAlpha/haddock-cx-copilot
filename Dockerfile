# Public demo image. Spec: docs/specs/deploy.md
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /srv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1 HADDOCK_PUBLIC=1

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY data ./data
COPY prompts ./prompts
# /codigo reads the specs, the evals and CLAUDE.md from disk (docs/specs/tour.md).
COPY docs/specs ./docs/specs
COPY evals ./evals
COPY CLAUDE.md ./
# The demo always starts from the known-good state: precomputed tickets, no reviews.
COPY haddock.golden.db ./haddock.db

EXPOSE 8080
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
