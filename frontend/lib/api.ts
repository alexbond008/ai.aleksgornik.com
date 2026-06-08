const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

export async function register(name: string, email: string) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "Registration failed");
  }
  return res.json() as Promise<{ token: string; remaining_messages: number }>;
}

export async function getMe(token: string) {
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Auth failed");
  return res.json() as Promise<{
    user_id: string;
    email: string;
    remaining_messages: number;
  }>;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
}

export async function* streamChat(
  token: string,
  messages: Message[]
): AsyncGenerator<{ type: "remaining"; value: number } | { type: "text"; value: string } | { type: "done" }> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ messages }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "Chat failed");
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let firstEvent = true;

  while (true) {
    const { done, value } = await reader.read();
    if (done) { yield { type: "done" }; return; }

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const data = line.slice(6);
      if (data === "[DONE]") { yield { type: "done" }; return; }

      if (firstEvent) {
        // First event is the remaining message count
        const count = parseInt(data, 10);
        if (!isNaN(count)) { yield { type: "remaining", value: count }; }
        firstEvent = false;
        continue;
      }

      yield { type: "text", value: data.replace(/\\n/g, "\n") };
    }
  }
}
