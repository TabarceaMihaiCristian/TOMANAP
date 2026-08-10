import { useQuery } from "@tanstack/react-query";
import { Crown, Home, Medal, Trophy } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { useApi } from "@/api/ApiProvider";
import { useSession } from "@/features/session/sessionContext";
import { Button } from "@/shared/ui/Button";

import styles from "./LeaderboardPage.module.css";

export function LeaderboardPage() {
  const { roomCode = "" } = useParams();
  const normalizedRoomCode = roomCode.toUpperCase();
  const { clearSession, session } = useSession();
  const api = useApi();
  const navigate = useNavigate();
  const leaderboard = useQuery({
    enabled: session !== null && session.roomCode === normalizedRoomCode,
    queryFn: () => api.getLeaderboard(normalizedRoomCode, session?.sessionToken ?? ""),
    queryKey: ["leaderboard", normalizedRoomCode],
  });

  if (leaderboard.isPending || leaderboard.data === undefined) {
    return <section className={styles.state}>Pregătim podiumul…</section>;
  }

  function goHome() {
    clearSession();
    void navigate("/", { replace: true });
  }

  const [winner, second, third, ...others] = leaderboard.data.entries;
  return (
    <section className={styles.page}>
      <header>
        <span className={styles.trophy}>
          <Trophy aria-hidden="true" />
        </span>
        <p>Joc încheiat</p>
        <h1>Avem un câștigător!</h1>
        <span>Mulțumim pentru o rundă zdravănă de TOMANAP.</span>
      </header>
      <div className={styles.podium}>
        {second !== undefined ? (
          <article className={styles.second}>
            <Medal aria-hidden="true" />
            <strong>{second.display_name}</strong>
            <span>{second.total_score} pct</span>
          </article>
        ) : null}
        {winner !== undefined ? (
          <article className={styles.first}>
            <Crown aria-hidden="true" />
            <small>Locul 1</small>
            <strong>{winner.display_name}</strong>
            <span>{winner.total_score} puncte</span>
          </article>
        ) : null}
        {third !== undefined ? (
          <article className={styles.third}>
            <Medal aria-hidden="true" />
            <strong>{third.display_name}</strong>
            <span>{third.total_score} pct</span>
          </article>
        ) : null}
      </div>
      {others.length > 0 ? (
        <ol className={styles.others}>
          {others.map((entry) => (
            <li key={entry.player_id}>
              <span>{entry.rank}</span>
              <strong>{entry.display_name}</strong>
              <b>{entry.total_score}</b>
            </li>
          ))}
        </ol>
      ) : null}
      <Button onClick={goHome} variant="secondary">
        <Home aria-hidden="true" size={18} /> Joacă din nou
      </Button>
    </section>
  );
}
