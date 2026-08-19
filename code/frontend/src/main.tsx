import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import RootApp from './App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RootApp />
  </StrictMode>,
);
