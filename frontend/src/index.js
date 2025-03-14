// filepath: /Users/lucas/Development/FreelanceBill/freelance-bill/frontend/src/index.js
import React from 'react';
import ReactDOM from 'react-dom/client';
import { ThemeProvider } from "@mui/material/styles";
import theme from './theme/theme'; // Import the theme file
import App from './App';
import './index.css';

console.log("Rendering index.js");
console.log("API URL:", process.env.REACT_APP_API_URL);

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <App />
    </ThemeProvider>
  </React.StrictMode>
);
