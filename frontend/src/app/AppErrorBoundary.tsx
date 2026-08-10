import type { ReactNode } from "react";
import { Component } from "react";

import { Button } from "@/shared/ui/Button";

import styles from "./AppState.module.css";

interface AppErrorBoundaryProps {
  children: ReactNode;
  onReset?: () => void;
}

interface AppErrorBoundaryState {
  hasFailed: boolean;
}

export class AppErrorBoundary extends Component<
  AppErrorBoundaryProps,
  AppErrorBoundaryState
> {
  state: AppErrorBoundaryState = { hasFailed: false };

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { hasFailed: true };
  }

  private readonly reset = () => {
    if (this.props.onReset !== undefined) {
      this.props.onReset();
      return;
    }
    window.location.reload();
  };

  render() {
    if (!this.state.hasFailed) {
      return this.props.children;
    }
    return (
      <section className={styles.state} role="alert">
        <p className={styles.code} aria-hidden="true">
          !
        </p>
        <h1>Ceva nu a funcționat</h1>
        <p>
          Interfața a întâmpinat o problemă neașteptată. Detaliile tehnice nu sunt afișate
          pentru a-ți proteja datele.
        </p>
        <div className={styles.actions}>
          <Button onClick={this.reset} variant="secondary">
            Reîncarcă aplicația
          </Button>
          <a href="/">Pagina principală</a>
        </div>
      </section>
    );
  }
}
