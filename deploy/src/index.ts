// Public demo: one container instance behind the Worker. Spec: docs/specs/deploy.md
import { Container, getContainer } from "@cloudflare/containers";

interface Env {
  HADDOCK: DurableObjectNamespace<HaddockApp>;
  DEMO_PASSWORD: string;
  LANGFUSE_PUBLIC_KEY: string;
  LANGFUSE_SECRET_KEY: string;
  LANGFUSE_BASE_URL: string;
}

export class HaddockApp extends Container<Env> {
  defaultPort = 8080;
  sleepAfter = "30m";

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    // Secrets reach the app as env vars. No Anthropic or TypeSafe key: the pipeline is off.
    this.envVars = {
      HADDOCK_PUBLIC: "1",
      DEMO_PASSWORD: env.DEMO_PASSWORD,
      LANGFUSE_PUBLIC_KEY: env.LANGFUSE_PUBLIC_KEY,
      LANGFUSE_SECRET_KEY: env.LANGFUSE_SECRET_KEY,
      LANGFUSE_BASE_URL: env.LANGFUSE_BASE_URL,
    };
  }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    // A single instance: every request sees the same SQLite file.
    return getContainer(env.HADDOCK, "demo").fetch(request);
  },
};
