import type { AutonomyConfig } from "./types.js";
import { EventLogger } from "./event-logger.js";

interface OllamaChatResponse {
  model: string;
  message?: { role: string; content: string };
  done?: boolean;
  prompt_eval_count?: number;
  eval_count?: number;
  total_duration?: number;
}

interface OllamaTagsResponse {
  models?: Array<{ name: string; model?: string }>;
}

export interface StructuredRequest<T> {
  model: string;
  schema: Record<string, unknown>;
  system: string;
  user: string;
  taskId?: string;
  validate: (value: unknown) => value is T;
  validationError: () => string;
  onRawResponse?: (content: string, parsed: unknown) => void;
}

const delay = (milliseconds: number): Promise<void> =>
  new Promise((resolvePromise) => setTimeout(resolvePromise, milliseconds));

export function parseStructuredJson(content: string): unknown {
  const trimmed = content.trim();
  try {
    return JSON.parse(trimmed);
  } catch (directError) {
    const fenced = /^```(?:json)?\s*\r?\n([\s\S]*?)\r?\n```$/i.exec(trimmed);
    if (!fenced?.[1]) throw directError;
    return JSON.parse(fenced[1].trim());
  }
}

export class OllamaClient {
  constructor(
    private readonly config: AutonomyConfig,
    private readonly logger: EventLogger,
  ) {}

  async availableModels(): Promise<string[]> {
    const response = await fetch(`${this.config.ollama.url}/api/tags`, {
      signal: AbortSignal.timeout(Math.min(this.config.ollama.timeout_ms, 10000)),
    });
    if (!response.ok) throw new Error(`Ollama tags request failed: HTTP ${response.status}`);
    const body = await response.json() as OllamaTagsResponse;
    return (body.models ?? []).flatMap((item) => [item.name, item.model ?? item.name]);
  }

  async waitUntilAvailable(): Promise<string[]> {
    let lastError: unknown;
    for (let attempt = 0; attempt <= this.config.ollama.availability_retries; attempt += 1) {
      try {
        const models = await this.availableModels();
        const required = [this.config.ollama.coder_model, this.config.ollama.reviewer_model];
        const missing = required.filter((model) => !models.includes(model));
        if (missing.length > 0) throw new Error(`Ollama models not installed: ${missing.join(", ")}`);
        this.logger.log("ollama_available", { models: [...new Set(required)] });
        return models;
      } catch (error) {
        lastError = error;
        this.logger.log("ollama_unavailable", {
          attempt,
          error: error instanceof Error ? error.message : String(error),
        }, { level: "warn" });
        if (attempt < this.config.ollama.availability_retries) {
          await delay(this.config.ollama.availability_delay_ms);
        }
      }
    }
    throw new Error(`Ollama unavailable after configured retries: ${lastError instanceof Error ? lastError.message : String(lastError)}`);
  }

  async structured<T>(request: StructuredRequest<T>): Promise<T> {
    const messages: Array<{ role: string; content: string }> = [
      { role: "system", content: request.system },
      { role: "user", content: request.user },
    ];
    let lastError = "unknown";

    for (let attempt = 0; attempt <= this.config.ollama.response_retries; attempt += 1) {
      const started = Date.now();
      this.logger.log("ollama_request", {
        model: request.model,
        attempt,
        prompt_chars: messages.reduce((sum, message) => sum + message.content.length, 0),
        schema_id: request.schema.$id ?? null,
      }, { taskId: request.taskId });

      const response = await fetch(`${this.config.ollama.url}/api/chat`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          model: request.model,
          stream: false,
          messages,
          format: request.schema,
          options: {
            temperature: this.config.ollama.temperature,
            num_ctx: this.config.ollama.context_size,
          },
        }),
        signal: AbortSignal.timeout(this.config.ollama.timeout_ms),
      });
      if (!response.ok) {
        throw new Error(`Ollama chat failed: HTTP ${response.status} ${await response.text()}`);
      }
      const body = await response.json() as OllamaChatResponse;
      const content = body.message?.content ?? "";
      let parsed: unknown;
      try {
        parsed = parseStructuredJson(content);
      } catch (error) {
        lastError = `Invalid JSON: ${error instanceof Error ? error.message : String(error)}`;
      }
      if (parsed !== undefined && request.validate(parsed)) {
        request.onRawResponse?.(content, parsed);
        this.logger.log("ollama_response_valid", {
          model: request.model,
          attempt,
          duration_ms: Date.now() - started,
          prompt_tokens: body.prompt_eval_count ?? null,
          output_tokens: body.eval_count ?? null,
        }, { taskId: request.taskId });
        return parsed;
      }
      if (parsed !== undefined) lastError = request.validationError();
      this.logger.log("ollama_response_invalid", {
        model: request.model,
        attempt,
        error: lastError,
        content_preview: content.slice(0, 1000),
      }, { taskId: request.taskId, level: "warn" });
      messages.push({ role: "assistant", content });
      messages.push({
        role: "user",
        content: `Your previous response was invalid: ${lastError}. Return exactly one JSON object matching the supplied schema, without Markdown.`,
      });
    }
    throw new Error(`Ollama failed to produce a schema-valid response: ${lastError}`);
  }
}
