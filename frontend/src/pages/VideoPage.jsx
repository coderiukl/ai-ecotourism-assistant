import { ArrowLeft, Play, SkipForward } from 'lucide-react';

export default function VideoPage({ destination, onBack, onNext }) {
  const videoStyle = destination?.image_url
    ? {
        backgroundImage: `linear-gradient(rgba(0, 0, 0, 0.16), rgba(0, 0, 0, 0.42)), url(${destination.image_url})`,
      }
    : undefined;

  return (
    <div className="phone">
      <div className="page">
        <button className="back-btn" onClick={onBack}>
          <ArrowLeft size={18} /> Giới thiệu
        </button>

        <div className="topbar">
          <div>
            <div className="badge" style={{ color: '#1f875a', background: '#eaf7ef' }}>
              🎥 Video giới thiệu
            </div>
            <h2>Khám phá nhanh {destination?.name}</h2>
          </div>
        </div>

        <div className="video-box" style={videoStyle}>
          <div className="play">
            <Play fill="currentColor" />
          </div>
        </div>

        <div className="card">
          <b>🤖 AI Guide</b>
          <p>
            Video này giúp bạn có cái nhìn tổng quan về cảnh quan, hoạt động và
            giá trị sinh thái của địa điểm.
          </p>
        </div>

        <div style={{ height: 18 }} />

        <button className="primary-btn" onClick={onNext}>
          Tôi đã xem xong →
        </button>

        <div style={{ height: 10 }} />

        <button className="secondary-btn" onClick={onNext}>
          <SkipForward size={16} style={{ verticalAlign: 'middle' }} /> Bỏ qua video
        </button>
      </div>
    </div>
  );
}
