import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

import styles from "./AppState.module.css";

export function NotFoundPage() {
  return (
    <section className={styles.state}>
      <p className={styles.code} aria-hidden="true">
        404
      </p>
      <h1>Pagina nu există</h1>
      <p>Adresa poate fi greșită sau camera nu mai este disponibilă.</p>
      <Link className={styles.homeLink} to="/">
        <ArrowLeft aria-hidden="true" size={17} /> Înapoi acasă
      </Link>
    </section>
  );
}
