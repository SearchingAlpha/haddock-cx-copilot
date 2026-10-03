"""Smoke test: send one nested trace to Langfuse and print its URL."""

from dotenv import load_dotenv
from langfuse import get_client, observe

load_dotenv()


@observe(name="lookup")
def lookup(ticket_id: str) -> dict:
    return {"ticket_id": ticket_id, "status": "ok"}


@observe(name="hello-langfuse")
def run(ticket_id: str) -> str:
    lookup(ticket_id)
    return get_client().get_current_trace_id() or ""


def main() -> None:
    langfuse = get_client()
    if not langfuse.auth_check():
        raise SystemExit("Langfuse auth failed: check LANGFUSE_* in .env")

    trace_id = run("T-0000")
    langfuse.flush()
    print("Trace sent. Open Langfuse -> Tracing -> 'hello-langfuse'.")
    if trace_id:
        print(langfuse.get_trace_url(trace_id=trace_id))


if __name__ == "__main__":
    main()
