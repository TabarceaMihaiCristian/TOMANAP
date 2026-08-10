import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "@/api/ApiClient";
import { useApi } from "@/api/ApiProvider";

import {
  issuedToSession,
  SessionContext,
  type SessionController,
  type SessionStatus,
} from "./sessionContext";
import { sessionStore } from "./sessionStore";
import type { AnonymousSession } from "./sessionStore";

interface SessionProviderProps {
  children: ReactNode;
  restoreOnMount?: boolean;
}

function isRejectedCredential(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 401 || error.status === 403);
}

export function SessionProvider({
  children,
  restoreOnMount = true,
}: SessionProviderProps) {
  const api = useApi();
  const [initialSession] = useState(() => sessionStore.load());
  const [session, setSession] = useState<AnonymousSession | null>(initialSession);
  const [status, setStatus] = useState<SessionStatus>(() => {
    if (initialSession === null) return "anonymous";
    return restoreOnMount ? "restoring" : "authenticated";
  });
  const [restorationError, setRestorationError] = useState<string | null>(null);
  const restoreStarted = useRef(false);
  const restoreInFlight = useRef(false);

  const acceptIssued = useCallback(
    (issued: Parameters<SessionController["acceptIssued"]>[0]) => {
      const acceptedSession = issuedToSession(issued);
      sessionStore.save(acceptedSession);
      setSession(acceptedSession);
      setRestorationError(null);
      setStatus("authenticated");
    },
    [],
  );

  const clearSession = useCallback(() => {
    sessionStore.clear();
    setSession(null);
    setRestorationError(null);
    setStatus("anonymous");
  }, []);

  const retryRestore = useCallback(async () => {
    if (session === null || restoreInFlight.current) return;
    restoreInFlight.current = true;
    setRestorationError(null);
    setStatus("restoring");
    try {
      acceptIssued(await api.restoreSession(session.reconnectToken));
    } catch (error) {
      if (isRejectedCredential(error)) {
        clearSession();
      } else {
        setRestorationError(
          error instanceof ApiError
            ? error.message
            : "Sesiunea nu a putut fi restaurată momentan.",
        );
        setStatus("restore-failed");
      }
    } finally {
      restoreInFlight.current = false;
    }
  }, [acceptIssued, api, clearSession, session]);

  useEffect(() => {
    if (!restoreOnMount || initialSession === null || restoreStarted.current) return;
    restoreStarted.current = true;
    void retryRestore();
  }, [initialSession, restoreOnMount, retryRestore]);

  const value = useMemo<SessionController>(
    () => ({
      acceptIssued,
      clearSession,
      restorationError,
      retryRestore,
      session: status === "authenticated" ? session : null,
      status,
    }),
    [acceptIssued, clearSession, restorationError, retryRestore, session, status],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
