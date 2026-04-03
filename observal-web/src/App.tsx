import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { Provider } from 'urql';
import { client } from './lib/urql';
import { TraceExplorer } from './components/TraceExplorer';
import { TraceDetail } from './components/TraceDetail';
import { Overview } from './components/Overview';
import { McpMetrics } from './components/McpMetrics';

export default function App() {
  return (
    <Provider value={client}>
      <BrowserRouter>
        <nav style={{ padding: '1rem', borderBottom: '1px solid #ccc' }}>
          <Link to="/">Overview</Link>{' | '}
          <Link to="/traces">Traces</Link>
        </nav>
        <main style={{ padding: '1rem' }}>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/traces" element={<TraceExplorer />} />
            <Route path="/traces/:traceId" element={<TraceDetail />} />
            <Route path="/mcps/:mcpId/metrics" element={<McpMetrics />} />
          </Routes>
        </main>
      </BrowserRouter>
    </Provider>
  );
}
