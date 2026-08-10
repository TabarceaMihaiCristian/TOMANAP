import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { SessionController, SessionStatus } from "./sessionContext";
import { SessionContext } from "./sessionContext";
import { SessionGate } from "./SessionGate";

const authenticatedSession = {
  playerId: "player-1",
  reconnectToken: "reconnect-token",
  roomCode: "ABC123",
  sessionToken: "session-token",
};

function renderGate(status: SessionStatus, overrides: Partial<SessionController> = {}) {
  const controller: SessionController = {
    acceptIssued: vi.fn(),
    clearSession: vi.fn(),
    restorationError: null,
    retryRestore: vi.fn().mockResolvedValue(undefined),
    session: status === "authenticated" ? authenticatedSession : null,
    status,
    ...overrides,
  };
  render(
    <MemoryRouter>
      <SessionContext.Provider value={controller}>
        <SessionGate>
          <h1>Protected room</h1>
        </SessionGate>
      </SessionContext.Provider>
    </MemoryRouter>,
  );
  return controller;
}

describe("SessionGate", () => {
  it("waits for credential rotation before rendering room content", () => {
    renderGate("restoring");

    expect(screen.getByRole("status")).toHaveTextContent(/restaurăm sesiunea/i);
    expect(screen.queryByText("Protected room")).not.toBeInTheDocument();
  });

  it("allows a transient restoration failure to be retried", async () => {
    const user = userEvent.setup();
    const controller = renderGate("restore-failed", {
      restorationError: "Server indisponibil",
    });

    expect(screen.getByRole("alert")).toHaveTextContent("Server indisponibil");
    await user.click(screen.getByRole("button", { name: /încearcă din nou/i }));

    expect(controller.retryRestore).toHaveBeenCalledOnce();
  });

  it("offers a safe route home when no session remains", () => {
    renderGate("anonymous");

    expect(
      screen.getByRole("heading", { name: /sesiunea nu mai este disponibilă/i }),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: /pagina principală/i })).toHaveAttribute(
      "href",
      "/",
    );
  });

  it("renders room content only for an authenticated session", () => {
    renderGate("authenticated");

    expect(screen.getByText("Protected room")).toBeVisible();
  });
});
