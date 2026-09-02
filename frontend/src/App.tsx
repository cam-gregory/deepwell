import { Suspense, lazy } from "react";
import { Routes, Route } from "react-router-dom";

const Ask = lazy(() => import("./pages/Ask"));
const Library = lazy(() => import("./pages/Library"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Debug = lazy(() => import("./pages/Debug"));
const Add = lazy(() => import("./pages/Add"));

function LoadingScreen() {
  return (
    <div className="flex min-h-screen items-center justify-center gap-2 text-sm text-ink-faint">
      <span className="h-2 w-2 animate-pulse-soft rounded-full bg-accent" />
      Loading…
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<LoadingScreen />}>
      <Routes>
        <Route path="/" element={<Ask />} />
        <Route path="/library" element={<Library />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/debug" element={<Debug />} />
        <Route path="/add" element={<Add />} />
      </Routes>
    </Suspense>
  );
}
