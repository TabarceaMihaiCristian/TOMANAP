import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppErrorBoundary } from "./AppErrorBoundary";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AppErrorBoundary", () => {
  it("contains an unexpected render failure and offers recovery", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const user = userEvent.setup();
    const reset = vi.fn();

    function BrokenFeature(): never {
      throw new Error("private implementation detail");
    }

    render(
      <AppErrorBoundary onReset={reset}>
        <BrokenFeature />
      </AppErrorBoundary>,
    );

    expect(screen.getByRole("heading", { name: /ceva nu a funcționat/i })).toBeVisible();
    expect(screen.queryByText(/private implementation detail/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /reîncarcă aplicația/i }));
    expect(reset).toHaveBeenCalledOnce();
  });
});
