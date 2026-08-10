import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Clock3, Save, Send, Wifi } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import type { CurrentRound, SubmissionAnswers } from "@/api/ApiClient";
import { ApiError } from "@/api/ApiClient";
import { useApi } from "@/api/ApiProvider";
import { useSession } from "@/features/session/sessionContext";
import { Button } from "@/shared/ui/Button";
import { useCountdown } from "@/shared/lib/useCountdown";

import styles from "./GamePage.module.css";

const emptyAnswers: SubmissionAnswers = {
  activities: "",
  animals: "",
  brands: "",
  cities: "",
  countries: "",
  names: "",
  plants: "",
};

const categoryDetails: Record<keyof SubmissionAnswers, { hint: string; label: string }> =
  {
    countries: { hint: "ex. Polonia", label: "Țări" },
    cities: { hint: "ex. Ploiești", label: "Orașe" },
    brands: { hint: "ex. Puma", label: "Mărci" },
    activities: { hint: "ex. Pictură", label: "Activități" },
    names: { hint: "ex. Petru", label: "Nume" },
    animals: { hint: "ex. Pinguin", label: "Animale" },
    plants: { hint: "ex. Păpădie", label: "Plante" },
  };

function currentRoundKey(roomCode: string) {
  return ["current-round", roomCode] as const;
}

export function GamePage() {
  const { roomCode = "" } = useParams();
  const normalizedRoomCode = roomCode.toUpperCase();
  const { session } = useSession();
  const api = useApi();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const initializedRound = useRef<string | null>(null);
  const [answers, setAnswers] = useState<SubmissionAnswers>(emptyAnswers);
  const [savedRevision, setSavedRevision] = useState<number | null>(null);

  const current = useQuery({
    enabled: session !== null && session.roomCode === normalizedRoomCode,
    queryFn: () => api.getCurrentRound(normalizedRoomCode, session?.sessionToken ?? ""),
    queryKey: currentRoundKey(normalizedRoomCode),
    refetchInterval: 2_500,
  });

  useEffect(() => {
    const data = current.data;
    if (data === undefined) return;
    if (initializedRound.current !== data.round.id) {
      initializedRound.current = data.round.id;
      setAnswers({ ...emptyAnswers, ...(data.submission?.answers ?? {}) });
      setSavedRevision(data.submission?.revision ?? null);
    }
    if (data.round.status === "review" || data.round.status === "completed") {
      void navigate(`/room/${normalizedRoomCode}/review/${data.round.id}`, {
        replace: true,
      });
    }
  }, [current.data, navigate, normalizedRoomCode]);

  const save = useMutation({
    mutationFn: ({ roundId, values }: { roundId: string; values: SubmissionAnswers }) =>
      api.saveSubmission(roundId, session?.sessionToken ?? "", values),
    onSuccess: (submission) => {
      setSavedRevision(submission.revision);
      queryClient.setQueryData<CurrentRound>(
        currentRoundKey(normalizedRoomCode),
        (old) => (old === undefined ? old : { ...old, submission }),
      );
    },
  });
  const finalize = useMutation({
    mutationFn: async ({
      roundId,
      values,
    }: {
      roundId: string;
      values: SubmissionAnswers;
    }) => {
      await api.saveSubmission(roundId, session?.sessionToken ?? "", values);
      return api.finalizeSubmission(roundId, session?.sessionToken ?? "");
    },
    onSuccess: (submission) => {
      queryClient.setQueryData<CurrentRound>(
        currentRoundKey(normalizedRoomCode),
        (old) => (old === undefined ? old : { ...old, submission }),
      );
      void current.refetch();
    },
  });

  const deadline = current.data?.round.ends_at ?? null;
  const remainingSeconds = useCountdown(deadline);

  if (session?.roomCode !== normalizedRoomCode) {
    return (
      <section className={styles.state}>
        <h1>Sesiunea de joc lipsește</h1>
        <Link to="/">Înapoi la pagina principală</Link>
      </section>
    );
  }
  if (current.isPending) {
    return (
      <section aria-busy="true" className={styles.state}>
        <h1>Pregătim foaia de joc…</h1>
      </section>
    );
  }
  if (current.isError || current.data === undefined) {
    return (
      <section className={styles.state}>
        <h1>Runda nu a putut fi încărcată</h1>
        <p>
          {current.error instanceof ApiError
            ? current.error.message
            : "Verifică legătura și încearcă din nou."}
        </p>
        <Button onClick={() => void current.refetch()} variant="secondary">
          Încearcă din nou
        </Button>
      </section>
    );
  }

  const round = current.data.round;
  const isFinalized = current.data.submission?.is_finalized ?? false;
  const isExpired = remainingSeconds === 0;
  const minutes = Math.floor(remainingSeconds / 60);
  const seconds = String(remainingSeconds % 60).padStart(2, "0");
  const filledCount = Object.values(answers).filter((answer) => answer.trim()).length;
  const error = save.error ?? finalize.error;

  return (
    <section className={styles.page}>
      <header className={styles.roundHeader}>
        <div className={styles.roundMeta}>
          <span>Runda {round.sequence_number}</span>
          <span>
            <Wifi aria-hidden="true" size={14} /> Camera {normalizedRoomCode}
          </span>
        </div>
        <div className={styles.letterBlock}>
          <div aria-hidden="true" className={styles.letter}>
            {round.letter}
          </div>
          <div>
            <p>Toate răspunsurile încep cu</p>
            <h1>Litera {round.letter}</h1>
          </div>
        </div>
        <div
          aria-live="polite"
          className={remainingSeconds <= 10 ? styles.timerDanger : styles.timer}
        >
          <Clock3 aria-hidden="true" />
          <span>
            {minutes}:{seconds}
          </span>
        </div>
      </header>

      <div className={styles.progressRow}>
        <span>{filledCount}/7 rubrici completate</span>
        <div aria-hidden="true" className={styles.progressTrack}>
          <span style={{ width: `${String((filledCount / 7) * 100)}%` }} />
        </div>
        {savedRevision !== null ? (
          <span className={styles.saved}>
            <Check aria-hidden="true" size={14} /> Ciornă salvată
          </span>
        ) : (
          <span>Completează în ritmul tău</span>
        )}
      </div>

      <div className={styles.sheet}>
        {current.data.categories.map((category, index) => {
          const details = categoryDetails[category];
          return (
            <label className={styles.answerRow} key={category}>
              <span aria-hidden="true" className={styles.categoryNumber}>
                {index + 1}
              </span>
              <span className={styles.categoryLabel}>{details.label}</span>
              <input
                aria-label={details.label}
                autoComplete="off"
                disabled={isFinalized || isExpired}
                maxLength={80}
                onChange={(event) =>
                  setAnswers((currentAnswers) => ({
                    ...currentAnswers,
                    [category]: event.target.value,
                  }))
                }
                placeholder={details.hint}
                value={answers[category]}
              />
              <span aria-hidden="true" className={styles.initialLetter}>
                {round.letter}
              </span>
            </label>
          );
        })}
      </div>

      {isFinalized ? (
        <div className={styles.waitingBanner} role="status">
          <Check aria-hidden="true" />
          <div>
            <strong>Răspunsurile tale sunt trimise</strong>
            <span>Așteptăm ca și ceilalți jucători să termine.</span>
          </div>
        </div>
      ) : (
        <div className={styles.actions}>
          <Button
            disabled={isExpired}
            isLoading={save.isPending}
            onClick={() => save.mutate({ roundId: round.id, values: answers })}
            variant="ghost"
          >
            <Save aria-hidden="true" size={18} /> Salvează ciorna
          </Button>
          <Button
            disabled={isExpired}
            isLoading={finalize.isPending}
            onClick={() => finalize.mutate({ roundId: round.id, values: answers })}
            variant="secondary"
          >
            Trimite răspunsurile <Send aria-hidden="true" size={18} />
          </Button>
        </div>
      )}

      {error !== null ? (
        <p className={styles.error} role="alert">
          {error instanceof ApiError
            ? error.message
            : "Răspunsurile nu au putut fi salvate."}
        </p>
      ) : null}
    </section>
  );
}
