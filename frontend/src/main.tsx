import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "@/app/App";
import { AppErrorBoundary } from "@/app/AppErrorBoundary";
import { AppProviders } from "@/app/AppProviders";
import "@/app/styles/global.css";

const rootElement = document.querySelector<HTMLDivElement>("#root");

if (rootElement === null) {
  throw new Error("Application root element is missing");
}

createRoot(rootElement).render(
  <StrictMode>
    <BrowserRouter>
      <AppProviders>
        <AppErrorBoundary>
          <App />
        </AppErrorBoundary>
      </AppProviders>
    </BrowserRouter>
  </StrictMode>,
);
