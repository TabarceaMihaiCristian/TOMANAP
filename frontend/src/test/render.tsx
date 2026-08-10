import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";

import { ApiClient } from "@/api/ApiClient";
import { ApiProvider } from "@/api/ApiProvider";
import { SessionProvider } from "@/features/session/SessionProvider";

interface RenderAppOptions {
  client?: ApiClient;
  route?: string;
}

export function renderApp(
  element: ReactElement,
  {
    client = new ApiClient("https://api.example.test"),
    route = "/",
  }: RenderAppOptions = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  return render(
    <MemoryRouter initialEntries={[route]}>
      <ApiProvider client={client}>
        <QueryClientProvider client={queryClient}>
          <SessionProvider restoreOnMount={false}>{element}</SessionProvider>
        </QueryClientProvider>
      </ApiProvider>
    </MemoryRouter>,
  );
}
