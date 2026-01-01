import { Routes, Route } from "react-router-dom";
import CampaignList from "./pages/CampaignList";
import CampaignCreate from "./pages/CampaignCreate";
import useWPAuth from "./hooks/useWPAuth";

export default function App() {
  useWPAuth();

  return (
    <Routes>
      <Route path="/" element={<CampaignList />} />
      <Route path="/new" element={<CampaignCreate />} />
    </Routes>
  );
}
