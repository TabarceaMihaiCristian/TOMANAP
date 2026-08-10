import { z } from "zod";

const STORAGE_KEY = "tomanap.session.v1";

const sessionSchema = z
  .object({
    roomCode: z.string().min(4).max(8),
    playerId: z.string().min(1),
    sessionToken: z.string().min(1),
    reconnectToken: z.string().min(1),
  })
  .strict();

export type AnonymousSession = z.infer<typeof sessionSchema>;

export interface SessionStore {
  clear: () => void;
  load: () => AnonymousSession | null;
  save: (session: AnonymousSession) => void;
}

export function createSessionStore(storage: Storage): SessionStore {
  return {
    clear() {
      storage.removeItem(STORAGE_KEY);
    },
    load() {
      const rawSession = storage.getItem(STORAGE_KEY);
      if (rawSession === null) {
        return null;
      }
      try {
        const result = sessionSchema.safeParse(JSON.parse(rawSession));
        if (result.success) {
          return result.data;
        }
      } catch {
        // Corrupt or legacy credentials must never reach an API header.
      }
      storage.removeItem(STORAGE_KEY);
      return null;
    },
    save(session) {
      storage.setItem(STORAGE_KEY, JSON.stringify(sessionSchema.parse(session)));
    },
  };
}

export const sessionStore = createSessionStore(window.sessionStorage);
