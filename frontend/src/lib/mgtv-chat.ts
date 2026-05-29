export type ChatRole = "system" | "user" | "assistant";

export type ChatMessageState = "done" | "streaming" | "error";

export interface ChatMessage {
  id: string;
  role: Exclude<ChatRole, "system">;
  content: string;
  createdAt: string;
  state?: ChatMessageState;
  errorMessage?: string;
}

export interface ChatThread {
  id: string;
  title: string;
  model: string;
  createdAt: string;
  updatedAt: string;
  messages: ChatMessage[];
}

export interface ChatModelOption {
  value: string;
  label: string;
  description: string;
}

export const MGTV_CHAT_API_URL = "https://aigc-llm.mgtv.com/v1/chat/completions";
export const MGTV_CHAT_STORAGE_KEY = "moyu-ui-chat-history";
export const MGTV_CHAT_ACTIVE_KEY = "moyu-ui-chat-active-thread";
export const MGTV_CHAT_SK_STORAGE_KEY = "moyu-ui-chat-sk";
export const MGTV_CHAT_DEFAULT_MODEL = "qwen3.6-flash";
export const MGTV_CHAT_SYSTEM_PROMPT = "Please answer in concise, well-structured Markdown.";
export const MGTV_CHAT_SK = "";

export const MGTV_CHAT_MODELS: readonly ChatModelOption[] = [
  { value: "qwen3.6-flash", label: "Qwen 3.6 Flash", description: "Speed-first daily chat" },
  { value: "qwen3.6-plus", label: "Qwen 3.6 Plus", description: "Balanced quality and speed" },
  { value: "qwen3.6-max-preview", label: "Qwen 3.6 Max Preview", description: "Deeper reasoning, slower replies" },
  { value: "qwen3.5-plus", label: "Qwen 3.5 Plus", description: "Stable general-purpose fallback" },
  { value: "deepseek-v4-flash", label: "DeepSeek V4 Flash", description: "Fast coding and analysis" },
  { value: "deepseek-v4-pro", label: "DeepSeek V4 Pro", description: "Heavier reasoning tasks" },
  { value: "glm-5", label: "GLM 5", description: "General chat and drafting" },
  { value: "glm-5.1", label: "GLM 5.1", description: "Sharper follow-up responses" },
] as const;

export function createId(prefix: string): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

export function deriveThreadTitle(content: string): string {
  const normalized = content.replace(/\s+/g, " ").trim();
  if (!normalized) {
    return "New chat";
  }
  return normalized.length > 26 ? `${normalized.slice(0, 26)}...` : normalized;
}

export function createThread(model = MGTV_CHAT_DEFAULT_MODEL): ChatThread {
  const now = new Date().toISOString();
  return {
    id: createId("thread"),
    title: "New chat",
    model,
    createdAt: now,
    updatedAt: now,
    messages: [],
  };
}

export function createMessage(role: ChatMessage["role"], content: string): ChatMessage {
  return {
    id: createId(role),
    role,
    content,
    createdAt: new Date().toISOString(),
    state: "done",
  };
}

function isChatMessage(value: unknown): value is ChatMessage {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Partial<ChatMessage>;
  return (
    (candidate.role === "user" || candidate.role === "assistant") &&
    typeof candidate.id === "string" &&
    typeof candidate.content === "string" &&
    typeof candidate.createdAt === "string"
  );
}

function isChatThread(value: unknown): value is ChatThread {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Partial<ChatThread>;
  return (
    typeof candidate.id === "string" &&
    typeof candidate.title === "string" &&
    typeof candidate.model === "string" &&
    typeof candidate.createdAt === "string" &&
    typeof candidate.updatedAt === "string" &&
    Array.isArray(candidate.messages) &&
    candidate.messages.every(isChatMessage)
  );
}

export function parseStoredThreads(raw: string | null): ChatThread[] {
  if (!raw) {
    return [];
  }

  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter(isChatThread).sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
  } catch {
    return [];
  }
}
