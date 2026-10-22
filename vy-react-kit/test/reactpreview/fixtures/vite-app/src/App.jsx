import { useState } from 'react';
import Greeting from './components/Greeting';
import data from './data.json';

// Probe: runs as page code, so the page's Content-Security-Policy applies to it.
const evalStatus = (() => {
  try {
    new Function('return 1')();
    return 'allowed';
  } catch (e) {
    return 'blocked';
  }
})();

export default function App() {
  const [count, setCount] = useState(0);
  return (
    <main className="app">
      <Greeting name={data.name} />
      <ul>
        {data.items.map((item) => <li key={item}>{item}</li>)}
      </ul>
      <button id="counter" onClick={() => setCount((c) => c + 1)}>
        Count: {count}
      </button>
      <p id="env">{process.env.NODE_ENV}</p>
      <p id="eval">{evalStatus}</p>
    </main>
  );
}
