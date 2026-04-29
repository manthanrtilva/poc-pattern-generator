import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import View from "./ViewImpl";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <View />
  </StrictMode>
);
