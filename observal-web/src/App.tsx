import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Provider } from "urql";
import { client } from "@/lib/urql";
import { AppLayout } from "@/components/layout/AppLayout";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Traces from "@/pages/Traces";
import TraceDetail from "@/pages/TraceDetail";
import Sessions from "@/pages/Sessions";
import McpServers from "@/pages/McpServers";
import McpDetail from "@/pages/McpDetail";
import Agents from "@/pages/Agents";
import AgentDetail from "@/pages/AgentDetail";
import Reviews from "@/pages/Reviews";
import Scores from "@/pages/Scores";
import Evaluations from "@/pages/Evaluations";
import Users from "@/pages/Users";
import Settings from "@/pages/Settings";

export default function App() {
  return (
    <Provider value={client}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<AppLayout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/traces" element={<Traces />} />
            <Route path="/traces/:traceId" element={<TraceDetail />} />
            <Route path="/sessions" element={<Sessions />} />
            <Route path="/mcps" element={<McpServers />} />
            <Route path="/mcps/:mcpId" element={<McpDetail />} />
            <Route path="/agents" element={<Agents />} />
            <Route path="/agents/:agentId" element={<AgentDetail />} />
            <Route path="/reviews" element={<Reviews />} />
            <Route path="/scores" element={<Scores />} />
            <Route path="/evals" element={<Evaluations />} />
            <Route path="/users" element={<Users />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </Provider>
  );
}
