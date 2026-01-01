import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api/axios";
import "../styles/campaign.css";

export default function CampaignList() {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/api/campaigns/")
      .then(res => setCampaigns(res.data))
      .catch(() => alert("Authentication failed"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="page">Loading campaigns...</div>;
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>My Campaigns</h1>
        <Link className="btn-primary" to="/new">+ New Campaign</Link>
      </div>

      {campaigns.length === 0 ? (
        <p className="empty">No campaigns created yet.</p>
      ) : (
        <table className="campaign-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Name</th>
              <th>Status</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {campaigns.map(c => (
              <tr key={c.id}>
                <td>{c.rule_number}</td>
                <td>{c.name}</td>
                <td>
                  <span className={c.is_active ? "active" : "inactive"}>
                    {c.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
                <td>{new Date(c.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
