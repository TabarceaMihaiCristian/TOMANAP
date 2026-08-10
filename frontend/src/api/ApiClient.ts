import type { components } from "./schema";

export type CreateGameRequest = components["schemas"]["CreateGameRequest"];
export type CurrentRound = components["schemas"]["CurrentRoundResponse"];
export type Game = components["schemas"]["GameResponse"];
export type JoinGameRequest = components["schemas"]["JoinGameRequest"];
export type Leaderboard = components["schemas"]["LeaderboardResponse"];
export type RealtimeTicket = components["schemas"]["RealtimeTicketResponse"];
export type RoundAdvance = components["schemas"]["RoundAdvanceResponse"];
export type RoundReview = components["schemas"]["RoundReviewResponse"];
export type SessionIssued = components["schemas"]["SessionIssuedResponse"];
export type Submission = components["schemas"]["SubmissionResponse"];
export type SubmissionAnswers = components["schemas"]["SubmissionAnswers"];
export type UpdateGameRequest = components["schemas"]["UpdateGameSettingsRequest"];

interface ErrorEnvelope {
  error: {
    code: string;
    message: string;
  };
}

interface RequestOptions extends Omit<RequestInit, "body" | "headers"> {
  body?: object;
  headers?: Record<string, string>;
  sessionToken?: string;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (typeof value !== "object" || value === null || !("error" in value)) {
    return false;
  }
  const error = value.error;
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    typeof error.code === "string" &&
    "message" in error &&
    typeof error.message === "string"
  );
}

function fallbackMessage(status: number): string {
  if (status === 429) return "Prea multe încercări. Așteaptă puțin și încearcă din nou.";
  if (status >= 500) return "Serverul nu răspunde momentan. Încearcă din nou.";
  return "Cererea nu a putut fi finalizată.";
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly fetcher: typeof fetch;

  constructor(baseUrl: string, fetcher: typeof fetch = fetch) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.fetcher = (input, init) => fetcher.call(globalThis, input, init);
  }

  private async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { body, headers: optionHeaders, sessionToken, ...requestInit } = options;
    const headers = new Headers(optionHeaders);
    headers.set("Accept", "application/json");
    if (body !== undefined) {
      headers.set("Content-Type", "application/json");
    }
    if (sessionToken !== undefined) {
      headers.set("X-TOMANAP-Session", sessionToken);
    }

    const fetchOptions: RequestInit = {
      ...requestInit,
      credentials: "omit",
      headers,
      referrerPolicy: "no-referrer",
    };
    if (body !== undefined) {
      fetchOptions.body = JSON.stringify(body);
    }

    let response: Response;
    try {
      response = await this.fetcher(`${this.baseUrl}${path}`, {
        ...fetchOptions,
      });
    } catch {
      throw new ApiError(0, "network_error", "Nu ne-am putut conecta la server.");
    }

    if (!response.ok) {
      let payload: unknown;
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }
      if (isErrorEnvelope(payload)) {
        throw new ApiError(response.status, payload.error.code, payload.error.message);
      }
      throw new ApiError(
        response.status,
        "request_failed",
        fallbackMessage(response.status),
      );
    }
    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  }

  createGame(request: CreateGameRequest): Promise<SessionIssued> {
    return this.request("/games", { body: request, method: "POST" });
  }

  joinGame(roomCode: string, request: JoinGameRequest): Promise<SessionIssued> {
    return this.request(`/games/${encodeURIComponent(roomCode)}/join`, {
      body: request,
      method: "POST",
    });
  }

  restoreSession(reconnectToken: string): Promise<SessionIssued> {
    return this.request("/sessions/restore", {
      body: { reconnect_token: reconnectToken },
      method: "POST",
    });
  }

  getGame(roomCode: string): Promise<Game> {
    return this.request(`/games/${encodeURIComponent(roomCode)}`);
  }

  setReady(roomCode: string, sessionToken: string, isReady: boolean): Promise<Game> {
    return this.request(`/games/${encodeURIComponent(roomCode)}/ready`, {
      body: { is_ready: isReady },
      method: "POST",
      sessionToken,
    });
  }

  updateGame(
    roomCode: string,
    sessionToken: string,
    request: UpdateGameRequest,
  ): Promise<Game> {
    return this.request(`/games/${encodeURIComponent(roomCode)}/settings`, {
      body: request,
      method: "PATCH",
      sessionToken,
    });
  }

  startGame(roomCode: string, sessionToken: string): Promise<Game> {
    return this.request(`/games/${encodeURIComponent(roomCode)}/start`, {
      headers: { "Idempotency-Key": crypto.randomUUID() },
      method: "POST",
      sessionToken,
    });
  }

  leaveGame(roomCode: string, sessionToken: string): Promise<void> {
    return this.request(`/games/${encodeURIComponent(roomCode)}/leave`, {
      method: "POST",
      sessionToken,
    });
  }

  getCurrentRound(roomCode: string, sessionToken: string): Promise<CurrentRound> {
    return this.request(`/games/${encodeURIComponent(roomCode)}/rounds/current`, {
      sessionToken,
    });
  }

  saveSubmission(
    roundId: string,
    sessionToken: string,
    answers: SubmissionAnswers,
  ): Promise<Submission> {
    return this.request(`/rounds/${encodeURIComponent(roundId)}/submission`, {
      body: { answers },
      method: "PUT",
      sessionToken,
    });
  }

  finalizeSubmission(roundId: string, sessionToken: string): Promise<Submission> {
    return this.request(`/rounds/${encodeURIComponent(roundId)}/submission/finalize`, {
      method: "POST",
      sessionToken,
    });
  }

  getReview(roundId: string, sessionToken: string): Promise<RoundReview> {
    return this.request(`/rounds/${encodeURIComponent(roundId)}/review`, {
      sessionToken,
    });
  }

  advanceRound(roomCode: string, sessionToken: string): Promise<RoundAdvance> {
    return this.request(`/games/${encodeURIComponent(roomCode)}/rounds/next`, {
      headers: { "Idempotency-Key": crypto.randomUUID() },
      method: "POST",
      sessionToken,
    });
  }

  getLeaderboard(roomCode: string, sessionToken: string): Promise<Leaderboard> {
    return this.request(`/games/${encodeURIComponent(roomCode)}/leaderboard`, {
      sessionToken,
    });
  }

  issueRealtimeTicket(roomCode: string, sessionToken: string): Promise<RealtimeTicket> {
    return this.request(`/games/${encodeURIComponent(roomCode)}/realtime-ticket`, {
      method: "POST",
      sessionToken,
    });
  }

  realtimeUrl(roomCode: string): string {
    const url = new URL(this.baseUrl);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = `/ws/games/${encodeURIComponent(roomCode)}`;
    url.search = "";
    url.hash = "";
    return url.toString();
  }
}

function apiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_URL as string | undefined;
  const value = configured ?? "http://127.0.0.1:8000";
  const parsed = new URL(value);
  if (!(["http:", "https:"] as string[]).includes(parsed.protocol)) {
    throw new Error("VITE_API_URL must use HTTP or HTTPS");
  }
  return parsed.toString();
}

export const apiClient = new ApiClient(apiBaseUrl());
