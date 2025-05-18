import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App'; // Note:  Import now refers to the compiled JS version

createRoot(document.getElementById('root')!).render( //The '!'  is a non-null assertion operator
  <StrictMode>
    <App />
  </StrictMode>,
);