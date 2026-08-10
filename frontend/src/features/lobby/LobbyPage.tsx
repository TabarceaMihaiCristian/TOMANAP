import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  Circle,
  Copy,
  Crown,
  LogOut,
  Play,
  Settings,
  UserRound,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import type { Game } from "@/api/ApiClient";
import { ApiError } from "@/api/ApiClient";
import { useApi } from "@/api/ApiProvider";
import { useSession } from "@/features/session/sessionContext";
import { Button } from "@/shared/ui/Button";

import styles from "./LobbyPage.module.css";

function roomQueryKey(roomCode: string) {
  return ["room", roomCode] as const;
}

export function LobbyPage() {
  const { roomCode = "" } = useParams();
  const normalizedRoomCode = roomCode.toUpperCase();
  const { clearSession, session } = useSession();
  const api = useApi();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [copied, setCopied] = useState(false);
  const [roundCount, setRoundCount] = useState<number | null>(null);
  const [roundDuration, setRoundDuration] = useState<number | null>(null);

  const room = useQuery({
    enabled: normalizedRoomCode.length > 0,
    queryFn: () => api.getGame(normalizedRoomCode),
    queryKey: roomQueryKey(normalizedRoomCode),
    refetchInterval: 3_000,
  });

  useEffect(() => {
    if (room.data !== undefined) {
      if (room.data.status === "in_progress") {
        void navigate(`/room/${normalizedRoomCode}/play`, { replace: true });
      }
    }
  }, [navigate, normalizedRoomCode, room.data]);

  const updateCachedRoom = (game: Game) => {
    queryClient.setQueryData(roomQueryKey(normalizedRoomCode), game);
  };
  const ready = useMutation({
    mutationFn: (isReady: boolean) =>
      api.setReady(normalizedRoomCode, session?.sessionToken ?? "", isReady),
    onSuccess: updateCachedRoom,
  });
  const updateSettings = useMutation({
    mutationFn: () =>
      api.updateGame(normalizedRoomCode, session?.sessionToken ?? "", {
        round_count: roundCount ?? room.data?.round_count ?? 5,
        round_duration_seconds: roundDuration ?? room.data?.round_duration_seconds ?? 60,
      }),
    onSuccess: updateCachedRoom,
  });
  const start = useMutation({
    mutationFn: () => api.startGame(normalizedRoomCode, session?.sessionToken ?? ""),
    onSuccess: updateCachedRoom,
  });
  const leave = useMutation({
    mutationFn: () => api.leaveGame(normalizedRoomCode, session?.sessionToken ?? ""),
    onSuccess: () => {
      clearSession();
      void navigate("/", { replace: true });
    },
  });

  if (session?.roomCode !== normalizedRoomCode) {
    return (
      <section className={styles.centeredState}>
        <span className={styles.stateIcon}>
          <UserRound aria-hidden="true" />
        </span>
        <h1>Sesiunea acestei camere nu mai este disponibilă</h1>
        <p>Intră din nou cu codul camerei pentru a primi un loc nou.</p>
        <Link className={styles.textLink} to="/">
          Înapoi la pagina principală
        </Link>
      </section>
    );
  }

  if (room.isPending) {
    return (
      <section aria-busy="true" aria-label="Se încarcă camera" className={styles.loading}>
        <span />
        <span />
        <span />
      </section>
    );
  }

  if (room.isError || room.data === undefined) {
    const message =
      room.error instanceof ApiError
        ? room.error.message
        : "Camera nu a putut fi încărcată.";
    return (
      <section className={styles.centeredState}>
        <h1>Nu am găsit camera</h1>
        <p>{message}</p>
        <Button onClick={() => void room.refetch()} variant="secondary">
          Încearcă din nou
        </Button>
      </section>
    );
  }

  const game = room.data;
  const currentPlayer = game.players.find((player) => player.id === session.playerId);
  const isHost = currentPlayer?.is_host ?? false;
  const canStart =
    isHost &&
    game.players.length >= 2 &&
    game.players.filter((player) => !player.is_host).every((player) => player.is_ready);
  const mutationError = ready.error ?? updateSettings.error ?? start.error ?? leave.error;

  async function copyRoomCode() {
    if (navigator.clipboard !== undefined) {
      await navigator.clipboard.writeText(normalizedRoomCode);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1_500);
    }
  }

  return (
    <section className={styles.page}>
      <header className={styles.roomHeader}>
        <div>
          <p className={styles.kicker}>Camera de așteptare</p>
          <h1>Camera {normalizedRoomCode}</h1>
          <p>Trimite codul prietenilor și porniți când sunteți cu toții gata.</p>
        </div>
        <button
          className={styles.codeCard}
          onClick={() => void copyRoomCode()}
          type="button"
        >
          <span>Cod cameră</span>
          <strong>{normalizedRoomCode}</strong>
          <small>
            <Copy aria-hidden="true" size={15} /> {copied ? "Copiat!" : "Copiază"}
          </small>
        </button>
      </header>

      <div className={styles.layout}>
        <div className={styles.playersCard}>
          <div className={styles.sectionHeading}>
            <div>
              <span>Jucători</span>
              <strong>{game.players.length}/6</strong>
            </div>
            <p>{canStart ? "Toată lumea este gata!" : "Așteptăm confirmările…"}</p>
          </div>
          <ul className={styles.playerList}>
            {game.players.map((player) => (
              <li className={styles.player} key={player.id}>
                <span aria-hidden="true" className={styles.avatar}>
                  {player.display_name.slice(0, 1).toUpperCase()}
                </span>
                <div className={styles.playerName}>
                  <strong>
                    {player.display_name}
                    {player.id === session.playerId ? <small> tu</small> : null}
                  </strong>
                  <span>
                    {player.is_host ? (
                      <>
                        <Crown aria-hidden="true" size={14} /> Gazdă
                      </>
                    ) : player.is_ready ? (
                      "Pregătit"
                    ) : (
                      "Se pregătește"
                    )}
                  </span>
                </div>
                <span
                  aria-label={
                    player.is_ready || player.is_host ? "Pregătit" : "Nepregătit"
                  }
                  className={
                    player.is_ready || player.is_host ? styles.ready : styles.waiting
                  }
                >
                  {player.is_ready || player.is_host ? (
                    <Check aria-hidden="true" size={18} />
                  ) : (
                    <Circle aria-hidden="true" size={16} />
                  )}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <aside className={styles.sideCard}>
          {isHost ? (
            <>
              <div className={styles.sideTitle}>
                <Settings aria-hidden="true" />
                <div>
                  <h2>Regulile jocului</h2>
                  <p>Doar gazda le poate schimba.</p>
                </div>
              </div>
              <div className={styles.settingsGrid}>
                <label>
                  <span>Număr de runde</span>
                  <select
                    value={roundCount ?? game.round_count}
                    onChange={(event) => setRoundCount(Number(event.target.value))}
                  >
                    {[3, 5, 7, 10].map((value) => (
                      <option key={value} value={value}>
                        {value} runde
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span>Timp pe rundă</span>
                  <select
                    value={roundDuration ?? game.round_duration_seconds}
                    onChange={(event) => setRoundDuration(Number(event.target.value))}
                  >
                    {[45, 60, 90, 120].map((value) => (
                      <option key={value} value={value}>
                        {value < 120 ? `${String(value)} sec` : "2 min"}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <Button
                isFullWidth
                isLoading={updateSettings.isPending}
                onClick={() => updateSettings.mutate()}
                variant="ghost"
              >
                Salvează regulile
              </Button>
              <Button
                disabled={!canStart}
                isFullWidth
                isLoading={start.isPending}
                onClick={() => start.mutate()}
                variant="secondary"
              >
                <Play aria-hidden="true" fill="currentColor" size={18} /> Pornește jocul
              </Button>
              {!canStart ? (
                <p className={styles.startHint}>
                  Ai nevoie de cel puțin un prieten pregătit.
                </p>
              ) : null}
            </>
          ) : (
            <>
              <div className={styles.sideTitle}>
                <UserRound aria-hidden="true" />
                <div>
                  <h2>Ești gata?</h2>
                  <p>Confirmă și așteaptă ca gazda să pornească.</p>
                </div>
              </div>
              <Button
                isFullWidth
                isLoading={ready.isPending}
                onClick={() => ready.mutate(!(currentPlayer?.is_ready ?? false))}
                variant={currentPlayer?.is_ready ? "primary" : "secondary"}
              >
                {currentPlayer?.is_ready ? "Nu mai sunt gata" : "Sunt gata"}
              </Button>
            </>
          )}

          {mutationError !== null ? (
            <p className={styles.error} role="alert">
              {mutationError instanceof ApiError
                ? mutationError.message
                : "Acțiunea nu a putut fi finalizată."}
            </p>
          ) : null}
          <Button
            className={styles.leaveButton}
            isLoading={leave.isPending}
            onClick={() => leave.mutate()}
            variant="ghost"
          >
            <LogOut aria-hidden="true" size={17} /> Ieși din cameră
          </Button>
        </aside>
      </div>
    </section>
  );
}
