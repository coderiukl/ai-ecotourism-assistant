import { useEffect, useRef, useState } from 'react';
import { SkipForward, Volume2 } from 'lucide-react';

import { assetUrl } from '../api';

const INTRO_VIDEO_URL = import.meta.env.VITE_INTRO_VIDEO_URL || 'https://res.cloudinary.com/df6nsfnjk/video/upload/q_auto/f_auto/v1780989537/intro_nui_ba_den_xzcgcs.mp4';

export default function VideoPage({ destination, onNext }) {
  const posterUrl = assetUrl(destination?.image_url);
  const [isVideoRaised, setIsVideoRaised] = useState(true);
  const [needsSoundTap, setNeedsSoundTap] = useState(false);
  const pageRef = useRef(null);
  const videoBoxRef = useRef(null);
  const raisedVideoRef = useRef(null);

  async function playWithSound(video) {
    if (!video) return;
    video.muted = false;
    video.volume = 1;

    try {
      await video.play();
      setNeedsSoundTap(false);
    } catch {
      video.muted = true;
      try {
        await video.play();
      } catch {}
      setNeedsSoundTap(true);
    }
  }

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
    pageRef.current?.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  }, [destination?.id]);

  useEffect(() => {
    if (!isVideoRaised) return undefined;

    requestAnimationFrame(() => {
      playWithSound(raisedVideoRef.current);
    });

    return undefined;
  }, [isVideoRaised]);

  function enableSound() {
    playWithSound(raisedVideoRef.current);
  }

  function lowerVideo() {
    raisedVideoRef.current?.pause();
    setIsVideoRaised(false);
    requestAnimationFrame(() => {
      videoBoxRef.current?.scrollIntoView({ block: 'start', inline: 'nearest', behavior: 'smooth' });
    });
  }

  function raiseVideo() {
    setIsVideoRaised(true);
  }

  return (
    <div className="phone">
      <div className="page video-page" ref={pageRef}>
        {isVideoRaised && (
          <div className="video-spotlight" onClick={lowerVideo} role="presentation">
            <div className="video-spotlight-player" onClick={(event) => event.stopPropagation()}>
              <video
                ref={raisedVideoRef}
                className="intro-video"
                autoPlay
                controls
                playsInline
                poster={posterUrl || undefined}
                preload="auto"
                src={INTRO_VIDEO_URL}
              />
              {needsSoundTap && (
                <button className="sound-unlock-btn" onClick={enableSound} type="button">
                  <Volume2 size={17} /> Bật tiếng
                </button>
              )}
            </div>
          </div>
        )}

        <div className="topbar">
          <div>
            <div className="badge" style={{ color: '#1f875a', background: '#eaf7ef' }}>
              Video giới thiệu
            </div>
            <h2>Khám phá nhanh núi Bà Đen</h2>
          </div>
        </div>

        <button className="video-box intro-video-box intro-video-strip" onClick={raiseVideo} ref={videoBoxRef} type="button">
          <video
            className="intro-video"
            muted
            playsInline
            poster={posterUrl || undefined}
            preload="metadata"
            src={INTRO_VIDEO_URL}
          />
        </button>

        <div className="card">
          <b>AI Guide</b>
          <p>
            Xem video tổng quan trước, sau đó chọn các địa điểm nổi bật và hỏi AI
            Guide để được gợi ý chi tiết.
          </p>
        </div>


        <button className="primary-btn" onClick={onNext}>
          Tôi đã xem xong
        </button>


        <button className="secondary-btn" onClick={onNext}>
          <SkipForward size={16} style={{ verticalAlign: 'middle' }} /> Bỏ qua video
        </button>
      </div>
    </div>
  );
}
