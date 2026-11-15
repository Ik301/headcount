import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "@fontsource-variable/schibsted-grotesk/wght.css";
import "@fontsource-variable/schibsted-grotesk/wght-italic.css";
import "@fontsource/fragment-mono/400.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/checker.css";
import "./styles/sorter.css";
import "./styles/story.css";
import "./styles/guide.css";
import "./styles/challenge.css";
import "./styles/motion.css";
import App from "./App";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>,
);
