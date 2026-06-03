import { ArrowLeft, Compass } from 'lucide-react';

export default function ActivitiesPage({ destination, onBack, onNext }) {
  const activities = Array.isArray(destination?.activities) ? destination.activities : [];

  return (
    <div className="phone">
      <div className="page">
        <button className="back-btn" onClick={onBack}>
          <ArrowLeft size={18} /> Video
        </button>

        <div className="topbar">
          <div>
            <div className="badge" style={{ color: '#1f875a', background: '#eaf7ef' }}>
              <Compass size={15} /> Hoạt động nổi bật
            </div>
            <h2>Bạn có thể trải nghiệm gì?</h2>
            <p className="small-text">
              Chọn nhanh các hoạt động nổi bật để người dùng hình dung trước khi hỏi AI.
            </p>
          </div>
        </div>

        <div className="activity-grid">
          {activities.map((item, index) => (
            <div className="activity-card" key={index}>
              <div className="activity-icon">{item.icon}</div>
              <b>{item.name}</b>
              <p className="small-text">{item.desc}</p>
            </div>
          ))}
        </div>

        <div style={{ height: 18 }} />

        <div className="card">
          <b>✨ Gợi ý nhanh</b>
          <p>
            Người thích thiên nhiên nên thử trekking và ngắm cảnh. Người đi gia đình
            nên chọn cáp treo và khu check-in.
          </p>
        </div>

        <div style={{ height: 18 }} />

        <button className="primary-btn" onClick={onNext}>
          Hỏi AI Guide →
        </button>
      </div>
    </div>
  );
}
