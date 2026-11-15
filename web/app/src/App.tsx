import { Navigate, Route, Routes } from "react-router-dom";
import CheckerPage from "./checker/CheckerPage";
import ClaimPage from "./checker/ClaimPage";
import StoryPage from "./story/StoryPage";
import ChallengePage from "./challenge/ChallengePage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<CheckerPage />} />
      <Route path="/claim/:id" element={<ClaimPage />} />
      <Route path="/story" element={<StoryPage />} />
      <Route path="/challenge" element={<ChallengePage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
