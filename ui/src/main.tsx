import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { cargar } from "./datos";
import "./estilo.css";

const raiz = createRoot(document.getElementById("raiz")!);
cargar()
  .then((d) => raiz.render(<StrictMode><App d={d} /></StrictMode>))
  .catch((e: Error) => raiz.render(<p style={{ padding: 24 }}>{e.message}</p>));
