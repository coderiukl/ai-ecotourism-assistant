import { ArrowLeft, SkipForward } from 'lucide-react';

import { assetUrl } from '../api';

const INTRO_VIDEO_URL = import.meta.env.VITE_INTRO_VIDEO_URL || '/videos/intro.mp4';

export default function VideoPage({ destination, onBack, onNext }) {
  const posterUrl = assetUrl(destination?.image_url);

  return (
    <div className="phone">
      <div className="page video-page">
        <button className="back-btn" onClick={onBack}>
          <ArrowLeft size={18} /> QR
        </button>

        <div className="topbar">
          <div>
            <div className="badge" style={{ color: '#1f875a', background: '#eaf7ef' }}>
              Video giới thiệu
            </div>
            <h2>Khám phá nhanh núi Bà Đen</h2>
          </div>
        </div>

        <div className="video-box intro-video-box">
          <video
            className="intro-video"
            controls
            playsInline
            poster={posterUrl || undefined}
            preload="metadata"
            src={INTRO_VIDEO_URL}
          />
        </div>

        <div className="card">
          <b>AI Guide</b>
          <p>
            Xem video tổng quan trước, sau đó chọn các địa điểm nổi bật và hỏi AI
            Guide để được gợi ý chi tiết.
          </p>
        </div>

        <div style={{ height: 18 }} />

        <button className="primary-btn" onClick={onNext}>
          Tôi đã xem xong
        </button>

        <div style={{ height: 10 }} />

        <button className="secondary-btn" onClick={onNext}>
          <SkipForward size={16} style={{ verticalAlign: 'middle' }} /> Bỏ qua video
        </button>
      </div>
    </div>
  );
}
