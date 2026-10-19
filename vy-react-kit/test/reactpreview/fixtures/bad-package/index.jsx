import { createRoot } from 'react-dom/client';
import debounce from 'lodash/debounce';

createRoot(document.getElementById('root')).render(<p>{typeof debounce}</p>);
