import { ArrowLeft, MapPin, Sparkles } from 'lucide-react';

export default function LandingPage({ destination, onBack, onNext }) {
  const heroStyle = destination?.image_url
    ? {
        backgroundImage: `linear-gradient(135deg, rgba(21, 83, 60, 0.72), rgba(31, 135, 90, 0.72)), url(${destination.image_url})`,
      }
    : undefined;

  return (
    <div className="phone">
      <div className="hero" style={heroStyle}>
        <div>
          <button className="back-btn hero-back-btn" onClick={onBack}>
            <ArrowLeft size={18} /> Dashboard
          </button>

          <div className="badge">
            <Sparkles size={15} /> Trợ lý du lịch sinh thái AI
          </div>

          <h1>{destination?.name || 'Núi Bà Đen'}</h1>
          <p>
            {destination?.short_description ||
              'Khám phá thiên nhiên, văn hóa và các hoạt động nổi bật tại điểm đến.'}
          </p>
        </div>

        <div className="hero-actions">
          <div className="glass-card">
            <b>
              <MapPin size={16} style={{ verticalAlign: 'middle' }} />{' '}
              {destination?.location || 'Tây Ninh, Việt Nam'}
            </b>
            <p>
              Trải nghiệm nhanh trong 3-5 phút: xem video, khám phá hoạt động,
              hỏi AI.
            </p>
          </div>

          <button className="primary-btn" onClick={onNext}>
            Bắt đầu khám phá →
          </button>
        </div>
      </div>
    </div>
  );
}
