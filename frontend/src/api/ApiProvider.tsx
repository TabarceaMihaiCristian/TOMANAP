import { createContext, useContext } from "react";
import type { ReactNode } from "react";

import { apiClient } from "./ApiClient";
import type { ApiClient } from "./ApiClient";

const ApiContext = createContext<ApiClient | null>(null);

interface ApiProviderProps {
  children: ReactNode;
  client?: ApiClient;
}

export function ApiProvider({ children, client = apiClient }: ApiProviderProps) {
  return <ApiContext.Provider value={client}>{children}</ApiContext.Provider>;
}

export function useApi(): ApiClient {
  const client = useContext(ApiContext);
  if (client === null) {
    throw new Error("ApiProvider is missing");
  }
  return client;
}
