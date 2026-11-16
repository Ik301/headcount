import { Navigate, Route, Routes } from "react-router-dom";
import StoryPage from "./story/StoryPage";
import ChallengePage from "./challenge/ChallengePage";

/*
 * The live claim checker (checker/, POST /claim) needs the FastAPI service, which was
 * turned off after HackPrinceton judging to stop API costs. The site is now static:
 * the story and the game read site_data.json. "/" and old /claim links go to the story.
 * To bring the checker back, restore its routes and deploy with an API base.
 */
export default function App() {
  return (
    <Routes>
      <Route path="/story" element={<StoryPage />} />
      <Route path="/challenge" element={<ChallengePage />} />
      <Route path="*" element={<Navigate to="/story" replace />} />
    </Routes>
  );
}
