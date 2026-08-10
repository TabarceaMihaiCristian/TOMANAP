import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/shared/ui/Button";

import styles from "./SessionGate.module.css";
import { useSession } from "./sessionContext";

interface SessionGateProps {
  children: ReactNode;
}

export function SessionGate({ children }: SessionGateProps) {
  const { restorationError, retryRestore, status } = useSession();

  if (status === "authenticated") {
    return children;
  }

  if (status === "restoring") {
    return (
      <section aria-busy="true" aria-live="polite" className={styles.state} role="status">
        <span aria-hidden="true" className={styles.spinner} />
        <h1>Restaurăm sesiunea…</h1>
        <p>Îți reconectăm locul în cameră înainte să încărcăm jocul.</p>
      </section>
    );
  }

  if (status === "restore-failed") {
    return (
      <section className={styles.state}>
        <span aria-hidden="true" className={styles.connectionIcon}>
          !
        </span>
        <h1>Reconectarea nu a reușit</h1>
        <p role="alert">
          {restorationError ?? "Serverul nu răspunde momentan. Sesiunea este păstrată."}
        </p>
        <div className={styles.actions}>
          <Button onClick={() => void retryRestore()} variant="secondary">
            Încearcă din nou
          </Button>
          <Link to="/">Pagina principală</Link>
        </div>
      </section>
    );
  }

  return (
    <section className={styles.state}>
      <span aria-hidden="true" className={styles.connectionIcon}>
        ×
      </span>
      <h1>Sesiunea nu mai este disponibilă</h1>
      <p>Intră din nou în cameră pentru a primi un loc activ.</p>
      <Link className={styles.homeLink} to="/">
        Pagina principală
      </Link>
    </section>
  );
}
