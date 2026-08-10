import { Link } from "react-router-dom";

import styles from "./Logo.module.css";

const letters = ["T", "O", "M", "A", "N", "A", "P"];

export function Logo() {
  return (
    <Link aria-label="TOMANAP — pagina principală" className={styles.logo} to="/">
      {letters.map((letter, index) => (
        <span className={styles.letter} key={`${letter}-${String(index)}`}>
          {letter}
        </span>
      ))}
    </Link>
  );
}
