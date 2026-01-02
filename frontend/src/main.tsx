import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { SelectedDateProvider } from "./context/SelectedDateContext";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <SelectedDateProvider>
        <App />
      </SelectedDateProvider>
    </BrowserRouter>
  </React.StrictMode>
);
