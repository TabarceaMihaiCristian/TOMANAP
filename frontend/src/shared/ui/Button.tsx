import type { ButtonHTMLAttributes, ReactNode } from "react";

import styles from "./Button.module.css";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  isLoading?: boolean;
  isFullWidth?: boolean;
  variant?: ButtonVariant;
}

export function Button({
  children,
  className = "",
  disabled = false,
  isFullWidth = false,
  isLoading = false,
  type = "button",
  variant = "primary",
  ...props
}: ButtonProps) {
  const classes = [
    styles.button,
    styles[variant],
    isFullWidth ? styles.fullWidth : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      {...props}
      aria-busy={isLoading}
      className={classes}
      disabled={disabled || isLoading}
      type={type}
    >
      <span className={isLoading ? styles.mutedLabel : undefined}>{children}</span>
      {isLoading ? <span aria-hidden="true" className={styles.spinner} /> : null}
    </button>
  );
}
