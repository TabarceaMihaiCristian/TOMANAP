import type { InputHTMLAttributes } from "react";
import { forwardRef, useId } from "react";

import styles from "./TextField.module.css";

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  hint?: string;
}

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { error, hint, id, label, ...props },
  ref,
) {
  const generatedId = useId();
  const fieldId = id ?? generatedId;
  const descriptionId = `${fieldId}-description`;

  return (
    <label className={styles.field} htmlFor={fieldId}>
      <span className={styles.label}>{label}</span>
      <input
        {...props}
        ref={ref}
        aria-describedby={error || hint ? descriptionId : undefined}
        aria-invalid={Boolean(error)}
        className={styles.input}
        id={fieldId}
      />
      {error ? (
        <span className={styles.error} id={descriptionId} role="alert">
          {error}
        </span>
      ) : hint ? (
        <span className={styles.hint} id={descriptionId}>
          {hint}
        </span>
      ) : null}
    </label>
  );
});
