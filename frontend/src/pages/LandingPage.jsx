import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, MapPin, MessageCircle, Mountain, Sparkles, Trees } from 'lucide-react';

import { API_URL, assetUrl } from '../api';

const LOCATION_CATEGORIES = [
  {
    key: 'summit',
    label: 'Đỉnh núi',
    description: 'Tượng, cột mốc, vườn cảnh và các điểm check-in trên đỉnh.',
    icon: Mountain,
  },
  {
    key: 'foot',
    label: 'Chân núi',
    description: 'Cổng chính, nhà ga, điểm trung chuyển và dịch vụ ở chân núi.',
    icon: Trees,
  },
  {
    key: 'pagoda',
    label: 'Chùa Bà',
    description: 'Các điểm tâm linh, hang động và tuyến tham quan Chùa Bà.',
    icon: Sparkles,
  },
];

function normalizeText(value) {
  return String(value || '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

function categoryFor(destination) {
  const text = normalizeText(
    [destination?.location, destination?.category, destination?.name].filter(Boolean).join(' '),
  );

  if (text.includes('dinh')) return 'summit';
  if (text.includes('chan') || text.includes('cong chinh') || text.includes('ga ')) return 'foot';
  return 'pagoda';
}

function destinationText(destination) {
  if (!destination) return '';

  return [
    destination.short_description || destination.description_detail,
    destination.highlight ? `Điểm nổi bật: ${destination.highlight}` : '',
    destination.best_time ? `Thời điểm đẹp: ${destination.best_time}` : '',
    destination.estimated_duration ? `Thời lượng gợi ý: ${destination.estimated_duration}` : '',
  ]
    .filter(Boolean)
    .join(' ');
}

export default function LandingPage({ destination, onBack, onNext }) {
  const [destinations, setDestinations] = useState(destination ? [destination] : []);
  const [activeCategory, setActiveCategory] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [typedText, setTypedText] = useState('');

  useEffect(() => {
    async function loadDestinations() {
      try {
        const res = await fetch(`${API_URL}/api/destinations`);
        const data = await res.json();

        if (Array.isArray(data.destinations) && data.destinations.length) {
          setDestinations(data.destinations);
        }
      } catch (e) {
        setDestinations(destination ? [destination] : []);
      }
    }

    loadDestinations();
  }, [destination]);

  const categoryCounts = useMemo(() => {
    return destinations.reduce(
      (counts, item) => {
        const key = categoryFor(item);
        counts[key] = (counts[key] || 0) + 1;
        return counts;
      },
      { summit: 0, foot: 0, pagoda: 0 },
    );
  }, [destinations]);

  const selectedDestination = useMemo(() => {
    return destinations.find((item) => item.id === selectedId) || null;
  }, [destinations, selectedId]);

  const filteredDestinations = useMemo(() => {
    if (!activeCategory) return [];
    return destinations.filter((item) => categoryFor(item) === activeCategory);
  }, [activeCategory, destinations]);

  const activeLabel = LOCATION_CATEGORIES.find((item) => item.key === activeCategory)?.label;
  const heroImageUrl = assetUrl(selectedDestination?.image_url || filteredDestinations[0]?.image_url);
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
        backgroundImage: `linear-gradient(135deg, rgba(21, 83, 60, 0.78), rgba(31, 135, 90, 0.78)), url(${heroImageUrl})`,
      }
    : undefined;

  function handleBack() {
    if (selectedDestination) {
      setSelectedId(null);
      return;
    }
    if (activeCategory) {
      setActiveCategory(null);
      return;
    }
    onBack();
  }

  function openCategory(key) {
    setActiveCategory(key);
    setSelectedId(null);
  }

  return (
    <div className="phone">
      <div className="hero landing-explore" style={heroStyle}>
        <div>
          <button className="back-btn hero-back-btn" onClick={handleBack}>
            <ArrowLeft size={18} /> {selectedDestination ? 'Địa điểm' : activeCategory ? 'Khu vực' : 'Video'}
          </button>

          <div className="badge">
            <Sparkles size={15} /> Địa điểm nổi bật
          </div>

          <h1>{selectedDestination?.name || activeLabel || 'Chọn khu vực'}</h1>
          {selectedDestination && (
            <p className="typewriter-text">{typedText}<span className="typing-cursor" /></p>
          )}
          <p className={selectedDestination ? 'typewriter-text is-hidden' : 'typewriter-text'}>
            {selectedDestination
              ? 'Phần giới thiệu địa điểm đang chạy bên dưới.'
              : activeCategory
                ? 'Bấm vào một địa điểm bên dưới để xem phần giới thiệu.'
                : 'Chọn một khu vực để xem các địa điểm nổi bật của Núi Bà Đen.'}
          </p>
        </div>

        <div className="hero-actions landing-actions">
          {!activeCategory && (
            <div className="location-grid">
              {LOCATION_CATEGORIES.map((category) => {
                const Icon = category.icon;
                return (
                  <button className="location-card" key={category.key} onClick={() => openCategory(category.key)} type="button">
                    <span className="location-icon"><Icon size={18} /></span>
                    <span>
                      <b>{category.label}</b>
                      <small>{category.description}</small>
                    </span>
                    <em>{categoryCounts[category.key]} điểm</em>
                  </button>
                );
              })}
            </div>
          )}

          {activeCategory && !selectedDestination && (
            <div className="area-destination-list">
              {filteredDestinations.map((item) => {
                const imageUrl = assetUrl(item.image_url);
                return (
                  <button className="area-destination-card" key={item.id || item.dest_code || item.name} onClick={() => setSelectedId(item.id)} type="button">
                    <span className="area-destination-thumb" style={imageUrl ? { backgroundImage: `url(${imageUrl})` } : undefined} />
                    <span>
                      <b>{item.name}</b>
                      <small><MapPin size={13} /> {item.location || 'Tây Ninh, Việt Nam'}</small>
                    </span>
                  </button>
                );
              })}
            </div>
          )}

          {selectedDestination && (
            <div className="glass-card selected-detail-card">
              <b>
                <MapPin size={16} style={{ verticalAlign: 'middle' }} />{' '}
                {selectedDestination.location || 'Tây Ninh, Việt Nam'}
              </b>
              <p>{typedText}<span className="typing-cursor" /></p>
            </div>
          )}

          <button className="primary-btn" disabled={!selectedDestination} onClick={() => onNext(selectedDestination)}>
            <MessageCircle size={17} style={{ verticalAlign: 'middle' }} /> Hỏi AI Guide
          </button>
        </div>
      </div>
    </div>
  );
}
