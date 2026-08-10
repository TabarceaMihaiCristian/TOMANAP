import { ArrowRight, Check, Sparkles, Users } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import type { SubmitEvent } from "react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/ApiClient";
import { useApi } from "@/api/ApiProvider";
import { useSession } from "@/features/session/sessionContext";
import { Button } from "@/shared/ui/Button";
import { TextField } from "@/shared/ui/TextField";

import styles from "./HomePage.module.css";

type EntryMode = "create" | "join";

type EntryCommand =
  | {
      mode: "create";
      displayName: string;
      roundCount: number;
      roundDurationSeconds: number;
    }
  | { mode: "join"; displayName: string; roomCode: string };

const categories = [
  ["T", "Țări"],
  ["O", "Orașe"],
  ["M", "Mărci"],
  ["A", "Activități"],
  ["N", "Nume"],
  ["A", "Animale"],
  ["P", "Plante"],
] as const;

function stringField(data: FormData, name: string): string {
  const value = data.get(name);
  return typeof value === "string" ? value : "";
}

export function HomePage() {
  const api = useApi();
  const { acceptIssued } = useSession();
  const navigate = useNavigate();
  const [mode, setMode] = useState<EntryMode>("create");
  const [formError, setFormError] = useState<string | null>(null);
  const entry = useMutation({
    mutationFn: async (command: EntryCommand) => {
      if (command.mode === "create") {
        return api.createGame({
          display_name: command.displayName,
          round_count: command.roundCount,
          round_duration_seconds: command.roundDurationSeconds,
        });
      }
      return api.joinGame(command.roomCode, { display_name: command.displayName });
    },
    onSuccess: (issued) => {
      acceptIssued(issued);
      void navigate(`/room/${issued.game.room_code}`);
    },
  });

  function selectMode(nextMode: EntryMode) {
    setMode(nextMode);
    setFormError(null);
    entry.reset();
  }

  function submitEntry(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    const data = new FormData(event.currentTarget);
    const displayName = stringField(data, "displayName").trim();
    if (displayName.length === 0) {
      setFormError("Scrie cum te cheamă ca să putem continua.");
      return;
    }
    if (mode === "join") {
      const roomCode = stringField(data, "roomCode").trim().toUpperCase();
      if (!/^[A-Z0-9]{4,8}$/.test(roomCode)) {
        setFormError("Codul camerei trebuie să aibă între 4 și 8 caractere.");
        return;
      }
      entry.mutate({ displayName, mode, roomCode });
      return;
    }
    entry.mutate({
      displayName,
      mode,
      roundCount: Number(data.get("roundCount")),
      roundDurationSeconds: Number(data.get("roundDurationSeconds")),
    });
  }

  const requestError =
    entry.error instanceof ApiError
      ? entry.error.message
      : entry.isError
        ? "Nu am putut continua. Încearcă din nou."
        : null;

  return (
    <section className={styles.page}>
      <div className={styles.intro}>
        <div className={styles.eyebrow}>
          <Sparkles aria-hidden="true" size={17} />
          Jocul de pe foaie, împreună online
        </div>
        <h1>
          O literă. <span>Șapte categorii.</span>
          <br /> Cine găsește cele mai bune cuvinte?
        </h1>
        <p className={styles.lead}>
          Adună-ți prietenii, pornește cronometrul și umple toate rubricile înaintea lor.
          Fără cont, direct din browser.
        </p>

        <div aria-label="Categoriile jocului" className={styles.categories}>
          {categories.map(([letter, label], index) => (
            <div className={styles.category} key={`${label}-${String(index)}`}>
              <span aria-hidden="true">{letter}</span>
              <small>{label}</small>
            </div>
          ))}
        </div>

        <div className={styles.reassurance}>
          <span>
            <Users aria-hidden="true" size={18} /> 2–6 jucători
          </span>
          <span>
            <Check aria-hidden="true" size={18} /> Gratuit și fără cont
          </span>
        </div>
      </div>

      <div className={styles.entryCard}>
        <div aria-label="Alege cum intri în joc" className={styles.tabs} role="tablist">
          <button
            aria-controls="entry-panel"
            aria-selected={mode === "create"}
            className={styles.tab}
            onClick={() => selectMode("create")}
            role="tab"
            type="button"
          >
            Joc nou
          </button>
          <button
            aria-controls="entry-panel"
            aria-selected={mode === "join"}
            className={styles.tab}
            onClick={() => selectMode("join")}
            role="tab"
            type="button"
          >
            Intră cu cod
          </button>
        </div>

        <div className={styles.formPanel} id="entry-panel" role="tabpanel">
          <div className={styles.formHeading}>
            <span className={styles.formIcon}>
              {mode === "create" ? (
                <Sparkles aria-hidden="true" />
              ) : (
                <Users aria-hidden="true" />
              )}
            </span>
            <div>
              <h2>{mode === "create" ? "Creează o cameră" : "Intră în cameră"}</h2>
              <p>
                {mode === "create"
                  ? "Primești un cod pe care îl trimiți prietenilor."
                  : "Folosește codul primit de la gazda jocului."}
              </p>
            </div>
          </div>

          <form className={styles.form} noValidate onSubmit={submitEntry}>
            {mode === "join" ? (
              <TextField
                autoCapitalize="characters"
                autoComplete="off"
                label="Codul camerei"
                maxLength={8}
                minLength={4}
                name="roomCode"
                placeholder="ex. MUNTE7"
                required
              />
            ) : null}
            <TextField
              autoComplete="nickname"
              label="Cum te cheamă?"
              maxLength={40}
              name="displayName"
              placeholder="Scrie prenumele tău"
              required
            />

            {mode === "create" ? (
              <div className={styles.settingsRow}>
                <label>
                  <span>Runde</span>
                  <select defaultValue="5" name="roundCount">
                    <option value="3">3</option>
                    <option value="5">5</option>
                    <option value="7">7</option>
                    <option value="10">10</option>
                  </select>
                </label>
                <label>
                  <span>Timp / rundă</span>
                  <select defaultValue="60" name="roundDurationSeconds">
                    <option value="45">45 sec</option>
                    <option value="60">60 sec</option>
                    <option value="90">90 sec</option>
                    <option value="120">2 min</option>
                  </select>
                </label>
              </div>
            ) : null}

            {(formError ?? requestError) ? (
              <p className={styles.formError} role="alert">
                {formError ?? requestError}
              </p>
            ) : null}

            <Button
              isFullWidth
              isLoading={entry.isPending}
              type="submit"
              variant="secondary"
            >
              {mode === "create" ? "Creează joc" : "Intră în joc"}
              <ArrowRight aria-hidden="true" size={19} />
            </Button>
          </form>

          <p className={styles.privacy}>Nu cerem email, parolă sau cont.</p>
        </div>
      </div>
    </section>
  );
}
