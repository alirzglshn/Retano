import CampaignForm from "../components/CampaignForm";
import "../styles/campaign.css";

export default function CampaignCreate() {
  return (
    <div className="page">
      <h1>Create New Campaign</h1>
      <CampaignForm />
    </div>
  );
}
