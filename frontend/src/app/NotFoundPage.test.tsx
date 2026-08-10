import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderApp } from "@/test/render";

import { NotFoundPage } from "./NotFoundPage";

describe("NotFoundPage", () => {
  it("explains the invalid address and provides a route home", () => {
    renderApp(<NotFoundPage />);

    expect(screen.getByRole("heading", { name: /pagina nu există/i })).toBeVisible();
    expect(screen.getByRole("link", { name: /înapoi acasă/i })).toHaveAttribute(
      "href",
      "/",
    );
  });
});
