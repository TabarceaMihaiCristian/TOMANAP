import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { renderApp } from "@/test/render";

import { AppShell } from "./AppShell";

describe("AppShell", () => {
  it("opens and closes accessible help", async () => {
    const user = userEvent.setup();
    renderApp(
      <AppShell>
        <p>Conținut</p>
      </AppShell>,
    );

    await user.click(screen.getByRole("button", { name: "Ajutor" }));

    expect(screen.getByRole("dialog", { name: "Cum se joacă" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Închide ajutorul" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("exposes the current sound preference", async () => {
    const user = userEvent.setup();
    renderApp(
      <AppShell>
        <p>Conținut</p>
      </AppShell>,
    );

    const soundButton = screen.getByRole("button", { name: "Sunet pornit" });
    expect(soundButton).toHaveAttribute("aria-pressed", "true");

    await user.click(soundButton);

    expect(screen.getByRole("button", { name: "Sunet oprit" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("announces loss and recovery of the browser network connection", async () => {
    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: false,
    });
    renderApp(
      <AppShell>
        <p>Conținut</p>
      </AppShell>,
    );

    expect(screen.getByRole("status")).toHaveTextContent(/fără conexiune/i);

    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: true,
    });
    await act(() => window.dispatchEvent(new Event("online")));

    expect(screen.queryByText(/fără conexiune/i)).not.toBeInTheDocument();
  });
});
