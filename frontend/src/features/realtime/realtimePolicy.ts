import { ApiError } from "@/api/ApiClient";

export type RealtimeInvalidationScope = "leaderboard" | "review" | "room" | "round";

const completeResync = ["room", "round", "review", "leaderboard"] as const;

const eventScopes: Readonly<Record<string, readonly RealtimeInvalidationScope[]>> = {
  "connection.ready": completeResync,
  "game.completed": completeResync,
  "game.started": ["room", "round"],
  "lobby.updated": ["room"],
  "round.closed": completeResync,
  "round.started": ["room", "round"],
  "submission.finalized": ["round", "review", "leaderboard"],
  "submission.updated": ["round"],
};

export function invalidationScopesForEvent(
  eventType: string,
): readonly RealtimeInvalidationScope[] {
  return eventScopes[eventType] ?? ["room"];
}

export function isRejectedRealtimeSession(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 401 || error.status === 403);
}
