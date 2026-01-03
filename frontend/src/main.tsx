import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { RefreshProvider } from "./context/RefreshContext";
import { SelectedDateProvider } from "./context/SelectedDateContext";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <RefreshProvider>
        <SelectedDateProvider>
          <App />
        </SelectedDateProvider>
      </RefreshProvider>
    </BrowserRouter>
  </React.StrictMode>
);
