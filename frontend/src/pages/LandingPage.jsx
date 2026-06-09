import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, MapPin, MessageCircle, Sparkles } from 'lucide-react';

import { API_URL, assetUrl } from '../api';

function destinationText(destination) {
  if (!destination) return '';

  return [
    destination.short_description,
    destination.highlight ? `Diem noi bat: ${destination.highlight}` : '',
    destination.best_time ? `Thoi diem dep: ${destination.best_time}` : '',
  ]
    .filter(Boolean)
    .join(' ');
}

export default function LandingPage({ destination, onBack, onNext }) {
  const [destinations, setDestinations] = useState(destination ? [destination] : []);
  const [selectedId, setSelectedId] = useState(destination?.id || null);
  const [typedText, setTypedText] = useState('');

  useEffect(() => {
    async function loadDestinations() {
      try {
        const res = await fetch(`${API_URL}/api/destinations`);
        const data = await res.json();

        if (Array.isArray(data.destinations) && data.destinations.length) {
          setDestinations(data.destinations);
          setSelectedId((current) => current || data.destinations[0].id);
        }
      } catch (e) {
        setSelectedId((current) => current || destination?.id || null);
      }
    }

    loadDestinations();
  }, [destination]);

  const selectedDestination = useMemo(() => {
    return destinations.find((item) => item.id === selectedId) || destinations[0] || destination || null;
  }, [destination, destinations, selectedId]);

  const heroImageUrl = assetUrl(selectedDestination?.image_url);
  const fullText = destinationText(selectedDestination);

  useEffect(() => {
    setTypedText('');
    if (!fullText) return undefined;

    let index = 0;
    const timer = window.setInterval(() => {
      index += 2;
      setTypedText(fullText.slice(0, index));
      if (index >= fullText.length) window.clearInterval(timer);
    }, 18);

    return () => window.clearInterval(timer);
  }, [fullText]);

  const heroStyle = heroImageUrl
    ? {
        backgroundImage: `linear-gradient(135deg, rgba(21, 83, 60, 0.76), rgba(31, 135, 90, 0.76)), url(${heroImageUrl})`,
      }
    : undefined;

  return (
    <div className="phone">
      <div className="hero landing-explore" style={heroStyle}>
        <div>
          <button className="back-btn hero-back-btn" onClick={onBack}>
            <ArrowLeft size={18} /> Video
          </button>

          <div className="badge">
            <Sparkles size={15} /> Dia diem noi bat
          </div>

          <h1>{selectedDestination?.name || 'Nui Ba Den'}</h1>
          <p className="typewriter-text">
            {typedText}
            <span className="typing-cursor" />
          </p>
        </div>

        <div className="hero-actions">
          <div className="featured-strip" aria-label="Chon dia diem noi bat">
            {destinations.map((item) => {
              const imageUrl = assetUrl(item.image_url);
              const isActive = item.id === selectedDestination?.id;

              return (
                <button
                  className={`featured-place ${isActive ? 'active' : ''}`}
                  key={item.id || item.dest_code || item.name}
                  onClick={() => setSelectedId(item.id)}
                  type="button"
                >
                  <span
                    className="featured-thumb"
                    style={imageUrl ? { backgroundImage: `url(${imageUrl})` } : undefined}
                  />
                  <span>{item.name}</span>
                </button>
              );
            })}
          </div>

          <div className="glass-card landing-info-card">
            <b>
              <MapPin size={16} style={{ verticalAlign: 'middle' }} />{' '}
              {selectedDestination?.location || 'Tay Ninh, Viet Nam'}
            </b>
            <p>
              Chon dia diem ban quan tam, sau do hoi AI Guide de nhan goi y phu hop
              voi thoi gian, gia dinh va cach di chuyen.
            </p>
          </div>

          <button className="primary-btn" onClick={() => onNext(selectedDestination)}>
            <MessageCircle size={17} style={{ verticalAlign: 'middle' }} /> Hoi AI Guide
          </button>
        </div>
      </div>
    </div>
  );
}
