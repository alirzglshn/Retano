import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../api/axios";
import "../styles/CampaignList.css";


export default function CampaignList() {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchRule, setSearchRule] = useState("");

  useEffect(() => {
    api
      .get("/api/campaigns/")
      .then((res) => setCampaigns(res.data))
      .catch(() => alert("Authentication failed"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="container my-5">در حال بارگذاری...</div>;
  }

  const filteredCampaigns = campaigns.filter((c) =>
    searchRule
      ? String(c.rule_number || "").includes(searchRule)
      : true
  );

  return (
    <div className="container my-5" dir="rtl" lang="fa">
      {/* Top bar */}
      <div className="d-flex justify-content-between align-items-center mb-4">
        <span className="text-muted">
          کمپین‌های ایجاد شده: <strong>{campaigns.length}</strong>
        </span>

        <Link to="/new" className="btn btn-create">
          ایجاد کمپین جدید
        </Link>
      </div>

      {/* Search */}
      <div className="input-group mb-4">
        <button className="btn btn-search">جست و جو</button>
        <input
          type="text"
          className="form-control"
          placeholder="شماره رولز خود را وارد فرمایید..."
          value={searchRule}
          onChange={(e) => setSearchRule(e.target.value)}
        />
      </div>

      {/* Table Head */}
      <div className="row table-head d-none d-md-flex">
        <div className="col">جزئیات</div>
        <div className="col">الگوی پیام</div>
        <div className="col">فعال بودن کمپین</div>
        <div className="col">منبع محصولات</div>
        <div className="col">جنسیت</div>
        <div className="col">نوع فعال سازی</div>
        <div className="col">هفته</div>
        <div className="col">شماره رولز</div>
      </div>

      {/* Campaign Items */}
      {filteredCampaigns.length === 0 ? (
        <p className="text-center text-muted">کمپینی یافت نشد</p>
      ) : (
        filteredCampaigns.map((c) => (
          <div className="campaign-item" key={c.id}>
            <div className="row align-items-center text-center text-md-start">
              <div className="col">
                <Link to={`/campaign/${c.id}`} className="btn btn-details">
                  مشاهده
                </Link>
              </div>

              <div className="col">
                {c.message_template || "Message Template"}
              </div>

              <div className="col">
                {c.is_active ? (
                  <span className="badge bg-success">هست</span>
                ) : (
                  <span className="badge bg-danger">نیست</span>
                )}
              </div>

              <div className="col">
                {c.product_source || "Product Source"}
              </div>

              <div className="col">
                {c.gender || "مرد"}
              </div>

              <div className="col">
                {c.trigger_type || "Trigger Type"}
              </div>

              <div className="col">
                {c.week || "فرقی نمی‌کند"}
              </div>

              <div className="col text-muted">
                {c.rule_number ?? "—"}
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
