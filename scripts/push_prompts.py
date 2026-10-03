"""Push prompts/ files to Langfuse. A new version is created only when the text or config changed.

    python -m scripts.push_prompts                       # all prompts -> label production
    python -m scripts.push_prompts cx-agent-system --label staging -m "v2: channel-aware formatting"
"""

import argparse

from app.observability import init_tracing
from app.prompts import AGENT_SYSTEM, DEFAULT_CONFIG, JUDGE, local_text


def push(name: str, label: str, message: str | None) -> None:
    langfuse = init_tracing()
    text, config = local_text(name), DEFAULT_CONFIG.get(name, {})
    try:
        current = langfuse.get_prompt(name, label=label, cache_ttl_seconds=0, max_retries=1)
        if current.prompt == text and (current.config or {}) == config:
            print(f"{name}@{label}: unchanged (version {current.version})")
            return
    except Exception:
        pass  # first version
    created = langfuse.create_prompt(
        name=name, prompt=text, type="text", labels=[label], config=config, commit_message=message,
    )
    print(f"{name}: created version {created.version} with label '{label}'")


def main() -> None:
    parser = argparse.ArgumentParser(prog="scripts.push_prompts")
    parser.add_argument("names", nargs="*", default=[AGENT_SYSTEM, JUDGE])
    parser.add_argument("--label", default="production")
    parser.add_argument("-m", "--message")
    args = parser.parse_args()
    for name in args.names:
        push(name, args.label, args.message)


if __name__ == "__main__":
    main()
