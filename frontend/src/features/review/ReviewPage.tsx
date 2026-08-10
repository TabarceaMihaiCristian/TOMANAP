import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, Check, Crown, Minus, Trophy, X } from "lucide-react";
import { useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/ApiClient";
import { useApi } from "@/api/ApiProvider";
import { useSession } from "@/features/session/sessionContext";
import { Button } from "@/shared/ui/Button";

import styles from "./ReviewPage.module.css";

const categoryLabels: Record<string, string> = {
  activities: "Activități",
  animals: "Animale",
  brands: "Mărci",
  cities: "Orașe",
  countries: "Țări",
  names: "Nume",
  plants: "Plante",
};

export function ReviewPage() {
  const { roomCode = "", roundId = "" } = useParams();
  const normalizedRoomCode = roomCode.toUpperCase();
  const { session } = useSession();
  const api = useApi();
  const navigate = useNavigate();
  const enabled = session !== null && session.roomCode === normalizedRoomCode;

  const review = useQuery({
    enabled,
    queryFn: () => api.getReview(roundId, session?.sessionToken ?? ""),
    queryKey: ["review", roundId],
  });
  const leaderboard = useQuery({
    enabled,
    queryFn: () => api.getLeaderboard(normalizedRoomCode, session?.sessionToken ?? ""),
    queryKey: ["leaderboard", normalizedRoomCode],
  });
  const game = useQuery({
    enabled,
    queryFn: () => api.getGame(normalizedRoomCode),
    queryKey: ["room", normalizedRoomCode],
  });
  const currentRound = useQuery({
    enabled,
    queryFn: () => api.getCurrentRound(normalizedRoomCode, session?.sessionToken ?? ""),
    queryKey: ["current-round", normalizedRoomCode],
    refetchInterval: 2_500,
  });
  const advance = useMutation({
    mutationFn: () => api.advanceRound(normalizedRoomCode, session?.sessionToken ?? ""),
    onSuccess: (result) => {
      void navigate(
        result.game_status === "completed"
          ? `/room/${normalizedRoomCode}/results`
          : `/room/${normalizedRoomCode}/play`,
        { replace: true },
      );
    },
  });

  useEffect(() => {
    if (game.data?.status === "completed") {
      void navigate(`/room/${normalizedRoomCode}/results`, { replace: true });
      return;
    }
    const activeRound = currentRound.data?.round;
    if (
      activeRound !== undefined &&
      activeRound.id !== roundId &&
      activeRound.status === "active"
    ) {
      void navigate(`/room/${normalizedRoomCode}/play`, { replace: true });
    }
  }, [currentRound.data, game.data?.status, navigate, normalizedRoomCode, roundId]);

  if (!enabled) {
    return (
      <section className={styles.state}>
        <h1>Sesiunea de joc lipsește</h1>
        <Link to="/">Înapoi acasă</Link>
      </section>
    );
  }
  if (review.isPending || leaderboard.isPending || game.isPending) {
    return (
      <section aria-busy="true" className={styles.state}>
        <h1>Calculăm punctele…</h1>
      </section>
    );
  }
  if (
    review.isError ||
    leaderboard.isError ||
    game.isError ||
    review.data === undefined ||
    leaderboard.data === undefined ||
    game.data === undefined
  ) {
    return (
      <section className={styles.state}>
        <h1>Rezultatele nu sunt încă disponibile</h1>
        <Button onClick={() => void review.refetch()} variant="secondary">
          Încearcă din nou
        </Button>
      </section>
    );
  }

  const isHost = game.data.players.some(
    (player) => player.id === session.playerId && player.is_host,
  );
  const topEntry = leaderboard.data.entries[0];

  return (
    <section className={styles.page}>
      <header className={styles.header}>
        <div className={styles.letter} aria-hidden="true">
          {review.data.letter}
        </div>
        <div>
          <p>Runda s-a încheiat</p>
          <h1>Rezultatele rundei</h1>
          <span>Răspuns unic: 10 puncte · răspuns comun: 5 puncte</span>
        </div>
      </header>

      <div className={styles.layout}>
        <div className={styles.results}>
          {review.data.players.map((player) => (
            <article className={styles.playerResult} key={player.player_id}>
              <header>
                <div>
                  <span className={styles.avatar} aria-hidden="true">
                    {player.display_name.slice(0, 1)}
                  </span>
                  <div>
                    <h2>{player.display_name}</h2>
                    <small>
                      {player.player_id === session.playerId
                        ? "Răspunsurile tale"
                        : "Jucător"}
                    </small>
                  </div>
                </div>
                <strong>+{player.total_score} pct</strong>
              </header>
              <ul>
                {player.answers.map((answer) => (
                  <li key={answer.category}>
                    <span>{categoryLabels[answer.category] ?? answer.category}</span>
                    <strong
                      className={!answer.original_answer ? styles.emptyAnswer : undefined}
                    >
                      {answer.original_answer || "—"}
                    </strong>
                    <span
                      className={
                        answer.points === 10
                          ? styles.ten
                          : answer.points === 5
                            ? styles.five
                            : styles.zero
                      }
                    >
                      {answer.points === 10 ? (
                        <Check aria-hidden="true" size={14} />
                      ) : answer.points === 5 ? (
                        <Minus aria-hidden="true" size={14} />
                      ) : (
                        <X aria-hidden="true" size={14} />
                      )}
                      +{answer.points}
                    </span>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>

        <aside className={styles.leaderboard}>
          <div className={styles.boardTitle}>
            <Trophy aria-hidden="true" />
            <div>
              <h2>Clasament</h2>
              <p>Scorul total după această rundă</p>
            </div>
          </div>
          {topEntry !== undefined ? (
            <div className={styles.currentLeader}>
              <Crown aria-hidden="true" />
              <span>În frunte</span>
              <strong>{topEntry.display_name}</strong>
            </div>
          ) : null}
          <ol>
            {leaderboard.data.entries.map((entry) => (
              <li key={entry.player_id}>
                <span>{entry.rank}</span>
                <strong>{entry.display_name}</strong>
                <b>{entry.total_score}</b>
              </li>
            ))}
          </ol>
          {isHost ? (
            <Button
              isFullWidth
              isLoading={advance.isPending}
              onClick={() => advance.mutate()}
              variant="secondary"
            >
              {game.data.status === "completed" ? "Vezi podiumul" : "Runda următoare"}
              <ArrowRight aria-hidden="true" size={18} />
            </Button>
          ) : (
            <p className={styles.waiting}>Așteptăm ca gazda să continue…</p>
          )}
          {advance.error !== null ? (
            <p className={styles.error} role="alert">
              {advance.error instanceof ApiError
                ? advance.error.message
                : "Nu am putut porni runda următoare."}
            </p>
          ) : null}
        </aside>
      </div>
    </section>
  );
}
