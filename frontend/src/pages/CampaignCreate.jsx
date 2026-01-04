import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axios";
import "../styles/create.css";

const initialState = {
  name: "",
  week: "فرق نمی‌کند",
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

export default function CampaignCreate() {
  const [data, setData] = useState(initialState);
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  function handleChange(e) {
    const { name, value } = e.target;
    setData({ ...data, [name]: value });
  }

  function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);

    const formData = new FormData();
    Object.entries(data).forEach(([k, v]) => formData.append(k, v));
    if (file) formData.append("customers_file", file);

    api
      .post("/api/campaigns/", formData)
      .then(() => navigate("/"))
      .catch(() => alert("Failed to create campaign"))
      .finally(() => setLoading(false));
  }

  return (
    <div className="campaign-form" dir="rtl" lang="fa">
      <div className="text-center mb-4 d-flex justify-content-between align-items-center">
        {/* EXACT structure preserved */}
        <button
          type="button"
          className="btn btn-orange mb-3"
          onClick={() => window.location.href = "/format.xlsx"}
        >
          دانلود نمونه فایل اکسل مشتریان
        </button>

        <button
          type="button"
          className="btn btn-orange mb-3"
          onClick={() => navigate("/")}
        >
          مدیریت کمپین‌ها
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="row g-3">

          <div className="col-md-3">
            <label className="form-label">شماره رولز</label>
            <input
              type="text"
              className="form-control"
              name="name"
              onChange={handleChange}
            />
          </div>

          <div className="col-md-3">
            <label className="week">هفته</label>
            <select
              className="form-select"
              name="week"
              onChange={handleChange}
            >
              <option>فرق نمی‌کند</option>
              <option>اول</option>
              <option>دوم</option>
              <option>سوم</option>
              <option>چهارم</option>
            </select>
          </div>

          <div className="col-md-3">
            <label className="form-label">مبنای فعال‌سازی</label>
            <select
              className="form-select"
              name="activation_base"
              onChange={handleChange}
            >
              <option>همیشه</option>
              <option>آخرین خرید</option>
              <option>اولین خرید</option>
              <option>تاریخ خرید بعدی</option>
              <option>دسته بندی مشتریان</option>
              <option>یاداوری خرید بعدی</option>
            </select>
          </div>

          <div className="col-md-3">
            <label className="form-label">نحوه مقایسه</label>
            <select
              className="form-select"
              name="comparison_type"
              onChange={handleChange}
            >
              <option>بزرگتر از</option>
              <option>کوچک تر</option>
              <option>برابر</option>
            </select>
          </div>

          <div className="col-md-3">
            <label className="form-label">مقدار مقایسه</label>
            <select
              className="form-select"
              name="comparison_value"
              onChange={handleChange}
            >
              {[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,40,50,60,90]
                .map(n => <option key={n}>{n}</option>)
              }
            </select>
          </div>

          <div className="col-md-3">
            <label className="form-label">واحد مقدار</label>
            <select
              className="form-select"
              name="value_unit"
              onChange={handleChange}
            >
              <option>روز</option>
              <option>درصد</option>
              <option>تومان</option>
              <option>سفارش</option>
              <option>تعداد</option>
            </select>
          </div>

          <div className="col-md-3">
            <label className="form-label">دسته مشتریان</label>
            <select
              className="form-select"
              name="customer_type"
              onChange={handleChange}
            >
              <option>همه</option>
              <option>ویژه</option>
              <option>فعال</option>
              <option>جدید</option>
              <option>در خطر ریزش</option>
              <option>از دست رفته</option>
            </select>
          </div>

          <div className="col-md-3">
            <label className="form-label">جنسیت</label>
            <select
              className="form-select"
              name="gender"
              onChange={handleChange}
            >
              <option>مرد</option>
              <option>زن</option>
              <option>همه</option>
            </select>
          </div>

          <div className="col-md-3">
            <label className="form-label">نوع پوست</label>
            <select
              className="form-select"
              name="skin_type"
              onChange={handleChange}
            >
              <option>پوست مختلط</option>
              <option>پوست چرب</option>
              <option>پوست خشک</option>
              <option>همه</option>
            </select>
          </div>

          <div className="col-md-3">
            <label className="form-label">نوع مو</label>
            <select
              className="form-select"
              name="hair_type"
              onChange={handleChange}
            >
              <option>مو مختلط</option>
              <option>مو چرب</option>
              <option>مو خشک</option>
              <option>همه</option>
            </select>
          </div>

          <div className="col-md-3">
            <label className="form-label">کمپین فعال</label>
            <select
              className="form-select"
              name="is_active"
              onChange={e =>
                setData({ ...data, is_active: e.target.value === "هست" })
              }
            >
              <option>هست</option>
              <option>نیست</option>
            </select>
          </div>

          <div className="col-md-3">
            <label className="form-label">منبع محصول</label>
            <select
              className="form-select"
              name="product_source"
              onChange={handleChange}
            >
              <option>اولین محصول پرفروش</option>
              <option>دومین محصول پرفروش</option>
              <option>سومین محصول پرفروش</option>
              <option>آخرین خرید+میانگین دوره خرید محصول</option>
              <option>پر تکرار ترین محصول خریداری شده</option>
              <option>هیچکدام</option>
            </select>
          </div>

          <div className="col-md-3 file-input-wrapper">
            <label className="form-label">دیتا مشتریان</label>
            <input
              type="file"
              className="form-control"
              onChange={e => setFile(e.target.files[0])}
            />
          </div>

          <div className="col-md-3">
            <label className="form-label">اولویت</label>
            <select className="form-select">
              <option>خیلی بالا</option>
              <option>بالا</option>
              <option>متوسط</option>
              <option>پایین</option>
              <option>خیلی پایین</option>
            </select>
          </div>

          <div className="col-6">
            <label className="form-label">الگوی پیام</label>
            <textarea
              className="form-control"
              rows="3"
              name="message_pattern"
              onChange={handleChange}
            />
          </div>
        </div>

        <div className="mt-4 text-center">
          <button
            type="submit"
            className="btn btn-orange btn-lg w-100"
            disabled={loading}
          >
            {loading ? "در حال ارسال..." : "ارسال"}
          </button>
        </div>
      </form>
    </div>
  );
}
