const BASE_URL = import.meta.env.VITE_OLLAMA_URL || "http://192.168.10.49:11434";
const MODEL = import.meta.env.VITE_OLLAMA_MODEL || "techcorp-finance:latest";

/**
 * Streams a chat completion from Ollama.
 * @param {{role: "user"|"assistant"|"system", content: string}[]} messages
 * @param {(chunk: string) => void} onChunk called with each new token
 * @param {AbortSignal} signal
 */
export async function streamChat(messages, onChunk, signal) {
  const response = await fetch(`${BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: MODEL, messages, stream: true }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`Ollama a répondu avec le statut ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.trim()) continue;
      const data = JSON.parse(line);
      if (data.message?.content) {
        onChunk(data.message.content);
      }
      if (data.done) return;
    }
  }
}

/** Quick health check against the Ollama server. */
export async function checkOllamaStatus() {
  try {
    const res = await fetch(`${BASE_URL}/api/tags`);
    return res.ok;
  } catch {
    return false;
  }
}

export const OLLAMA_MODEL = MODEL;
