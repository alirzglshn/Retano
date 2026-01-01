import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axios";
import "../styles/campaign.css";

const initialState = {
  name: "",
  week: "فرقی نمی کند",
  activation_base: "همیشه",
  comparison_type: "بزرگتر از",
  comparison_value: 1,
  value_unit: "روز",
  customer_type: "همه",
  gender: "همه",
  skin_type: "همه",
  hair_type: "همه",
  product_source: "اولین محصول پرفروش",
  is_active: true,
  message_pattern: "",
};

export default function CampaignForm() {
  const [data, setData] = useState(initialState);
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  function handleChange(e) {
    const { name, value, type, checked } = e.target;
    setData({ ...data, [name]: type === "checkbox" ? checked : value });
  }

  function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);

    const formData = new FormData();
    Object.entries(data).forEach(([k, v]) => formData.append(k, v));
    if (file) formData.append("customers_file", file);

    api.post("/api/campaigns/", formData)
      .then(() => navigate("/"))
      .catch(err => {
        console.error(err);
        alert("Failed to create campaign");
      })
      .finally(() => setLoading(false));
  }

  return (
    <form className="form" onSubmit={handleSubmit}>
      <div className="form-grid">

        <label>
          Campaign Name
          <input name="name" required onChange={handleChange} />
        </label>

        <label>
          Week
          <select name="week" onChange={handleChange}>
            <option>اول</option>
            <option>دوم</option>
            <option>سوم</option>
            <option>چهارم</option>
            <option>فرقی نمی کند</option>
          </select>
        </label>

        <label>
          Activation Base
          <select name="activation_base" onChange={handleChange}>
            <option>همیشه</option>
            <option>آخرین خرید</option>
            <option>اولین خرید</option>
            <option>تاریخ خرید بعدی</option>
          </select>
        </label>

        <label>
          Comparison
          <select name="comparison_type" onChange={handleChange}>
            <option>بزرگتر از</option>
            <option>کوچکتر از</option>
            <option>برابر با</option>
          </select>
        </label>

        <label>
          Value
          <input type="number" name="comparison_value" onChange={handleChange} />
        </label>

        <label>
          Unit
          <select name="value_unit" onChange={handleChange}>
            <option>روز</option>
            <option>تومان</option>
            <option>تعداد</option>
            <option>درصد</option>
          </select>
        </label>

        <label>
          Customers File (Excel)
          <input type="file" onChange={e => setFile(e.target.files[0])} />
        </label>

        <label className="full">
          Message Pattern
          <textarea
            name="message_pattern"
            rows="4"
            onChange={handleChange}
          />
        </label>

        <label className="checkbox">
          <input
            type="checkbox"
            name="is_active"
            checked={data.is_active}
            onChange={handleChange}
          />
          Active
        </label>

      </div>

      <button className="btn-primary" disabled={loading}>
        {loading ? "Saving..." : "Create Campaign"}
      </button>
    </form>
  );
}
