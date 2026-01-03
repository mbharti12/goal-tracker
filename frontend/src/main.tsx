import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { NotificationsProvider } from "./context/NotificationsContext";
import { RefreshProvider } from "./context/RefreshContext";
import { SelectedDateProvider } from "./context/SelectedDateContext";
import { ToastProvider } from "./context/ToastContext";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <RefreshProvider>
        <NotificationsProvider>
          <SelectedDateProvider>
            <ToastProvider>
              <App />
            </ToastProvider>
          </SelectedDateProvider>
        </NotificationsProvider>
      </RefreshProvider>
    </BrowserRouter>
  </React.StrictMode>
);
