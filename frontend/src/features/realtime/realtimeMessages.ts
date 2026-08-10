interface MessageActions {
  invalidate: (eventType: string) => void;
  send: (message: string) => void;
}

export function handleRealtimeMessage(rawMessage: string, actions: MessageActions): void {
  let parsed: unknown;
  try {
    parsed = JSON.parse(rawMessage);
  } catch {
    return;
  }
  if (typeof parsed !== "object" || parsed === null || !("type" in parsed)) {
    return;
  }
  const type = parsed.type;
  if (type === "connection.ping") {
    actions.send(JSON.stringify({ type: "pong" }));
    return;
  }
  if (typeof type === "string") {
    actions.invalidate(type);
  }
}
