import React from 'react';
import ReactDOM from 'react-dom/client';

function App() {
  return <p id="single">Single file works</p>;
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
