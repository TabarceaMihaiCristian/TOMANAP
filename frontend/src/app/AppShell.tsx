import { HelpCircle, Volume2, VolumeX, WifiOff, X } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";

import { Button } from "@/shared/ui/Button";
import { Logo } from "@/shared/ui/Logo";
import { useOnlineStatus } from "@/shared/lib/useOnlineStatus";

import styles from "./AppShell.module.css";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const isOnline = useOnlineStatus();
  const [helpOpen, setHelpOpen] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(
    () => localStorage.getItem("tomanap.sound") !== "off",
  );

  useEffect(() => {
    if (!helpOpen) return;
    document.querySelector<HTMLButtonElement>("#close-help")?.focus();
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setHelpOpen(false);
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      document.querySelector<HTMLButtonElement>("#open-help")?.focus();
    };
  }, [helpOpen]);

  function toggleSound() {
    const nextValue = !soundEnabled;
    setSoundEnabled(nextValue);
    localStorage.setItem("tomanap.sound", nextValue ? "on" : "off");
  }

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <Logo />
        <nav aria-label="Acțiuni generale" className={styles.actions}>
          <Button
            aria-label="Ajutor"
            className={styles.iconButton}
            id="open-help"
            onClick={() => setHelpOpen(true)}
            variant="ghost"
          >
            <HelpCircle aria-hidden="true" size={21} />
          </Button>
          <Button
            aria-label={soundEnabled ? "Sunet pornit" : "Sunet oprit"}
            aria-pressed={soundEnabled}
            className={styles.iconButton}
            onClick={toggleSound}
            variant="ghost"
          >
            {soundEnabled ? (
              <Volume2 aria-hidden="true" size={21} />
            ) : (
              <VolumeX aria-hidden="true" size={21} />
            )}
          </Button>
        </nav>
      </header>
      {!isOnline ? (
        <div className={styles.offlineBanner} role="status">
          <WifiOff aria-hidden="true" size={17} />
          Fără conexiune. Păstrăm ce ai completat și reluăm când revine internetul.
        </div>
      ) : null}
      <main>{children}</main>
      <footer className={styles.footer}>
        <span>Făcut pentru seri cu prietenii.</span>
        <span aria-hidden="true">•</span>
        <span>Fără cont. Fără reclame.</span>
      </footer>
      {helpOpen ? (
        <div className={styles.backdrop}>
          <section
            aria-labelledby="help-title"
            aria-modal="true"
            className={styles.helpDialog}
            role="dialog"
          >
            <header>
              <div>
                <span className={styles.helpIcon}>
                  <HelpCircle aria-hidden="true" />
                </span>
                <h2 id="help-title">Cum se joacă</h2>
              </div>
              <Button
                aria-label="Închide ajutorul"
                className={styles.iconButton}
                id="close-help"
                onClick={() => setHelpOpen(false)}
                variant="ghost"
              >
                <X aria-hidden="true" size={21} />
              </Button>
            </header>
            <ol>
              <li>Creează o cameră și trimite codul prietenilor.</li>
              <li>La fiecare rundă primești o literă și șapte categorii.</li>
              <li>Completează răspunsurile înainte să expire timpul.</li>
              <li>Răspunsurile unice valorează mai mult decât cele comune.</li>
            </ol>
            <p>Gazda pornește jocul și trece la runda următoare.</p>
          </section>
        </div>
      ) : null}
    </div>
  );
}
