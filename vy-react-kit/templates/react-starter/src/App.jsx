import { useState } from 'react';

export default function App() {
  const [count, setCount] = useState(0);
  return (
    <main className="app">
      <h1>Hello from VY</h1>
      <p>Edit src/App.jsx, then open the preview again.</p>
      <button onClick={() => setCount((c) => c + 1)}>Clicked {count} times</button>
    </main>
  );
}
