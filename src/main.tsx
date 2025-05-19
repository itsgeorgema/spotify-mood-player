import React from 'react'; 
import ReactDOM from 'react-dom/client'; 

import App from './App';
import './index.css'; //base styles
import './App.css';   //specific styles for app

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error("Failed to find the root element. Ensure there's an element with id='root' in your index.html.");
}

const root = ReactDOM.createRoot(rootElement);

root.render(
  <React.StrictMode> 
    <App />
  </React.StrictMode>
);