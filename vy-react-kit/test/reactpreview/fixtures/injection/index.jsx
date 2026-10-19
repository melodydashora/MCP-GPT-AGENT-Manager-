import { createRoot } from 'react-dom/client';

const tricky = "</script><script>window.__pwned = true</script><!-- &  ";
createRoot(document.getElementById('root')).render(<p id="tricky">{tricky}</p>);
