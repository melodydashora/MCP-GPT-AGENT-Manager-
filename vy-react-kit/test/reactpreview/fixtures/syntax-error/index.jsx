import { createRoot } from 'react-dom/client';

function App() {
  return <div>
    <span>unclosed
  </div>;
}

createRoot(document.getElementById('root')).render(<App />);
