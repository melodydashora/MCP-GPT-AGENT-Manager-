import { createRoot } from 'react-dom/client';

function Broken() {
  throw new Error('Broken component exploded');
}

createRoot(document.getElementById('root')).render(<Broken />);
