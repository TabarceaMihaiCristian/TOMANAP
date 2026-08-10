import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { useApi } from "@/api/ApiProvider";
import type { AnonymousSession } from "@/features/session/sessionStore";

import { handleRealtimeMessage } from "./realtimeMessages";
import { invalidationScopesForEvent, isRejectedRealtimeSession } from "./realtimePolicy";

interface RoomRealtimeOptions {
  onSessionRejected: () => void;
  roomCode: string | null;
  session: AnonymousSession | null;
}

export function useRoomRealtime({
  onSessionRejected,
  roomCode,
  session,
}: RoomRealtimeOptions): void {
  const api = useApi();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (roomCode === null || session?.roomCode !== roomCode) {
      return;
    }
    const activeRoomCode = roomCode;
    const sessionToken = session.sessionToken;
    let closed = false;
    let reconnectTimer: number | null = null;
    let socket: WebSocket | null = null;
    let reconnectAttempt = 0;

    function scheduleReconnect(delayOverride?: number) {
      if (closed) return;
      const delay =
        delayOverride ?? Math.min(10_000, 750 * 2 ** Math.min(reconnectAttempt, 4));
      reconnectAttempt += 1;
      reconnectTimer = window.setTimeout(() => void connect(), delay);
    }

    async function connect() {
      try {
        const issued = await api.issueRealtimeTicket(activeRoomCode, sessionToken);
        if (closed) return;
        socket = new WebSocket(api.realtimeUrl(activeRoomCode), [
          "tomanap.ticket",
          issued.ticket,
        ]);
        socket.addEventListener("open", () => {
          reconnectAttempt = 0;
        });
        socket.addEventListener("message", (event) => {
          if (typeof event.data !== "string" || socket === null) return;
          handleRealtimeMessage(event.data, {
            invalidate: (eventType) => {
              for (const scope of invalidationScopesForEvent(eventType)) {
                const queryKey =
                  scope === "room"
                    ? ["room", activeRoomCode]
                    : scope === "round"
                      ? ["current-round", activeRoomCode]
                      : scope === "leaderboard"
                        ? ["leaderboard", activeRoomCode]
                        : ["review"];
                void queryClient.invalidateQueries({ queryKey });
              }
            },
            send: (message) => socket?.send(message),
          });
        });
        socket.addEventListener("close", (event) => {
          socket = null;
          if (event.code === 4403 || closed) return;
          scheduleReconnect(event.code === 4429 ? 5_000 : undefined);
        });
      } catch (error) {
        if (isRejectedRealtimeSession(error)) {
          closed = true;
          onSessionRejected();
          return;
        }
        scheduleReconnect();
      }
    }

    void connect();
    return () => {
      closed = true;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      socket?.close(1000, "page changed");
    };
  }, [api, onSessionRejected, queryClient, roomCode, session]);
}
