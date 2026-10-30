import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeft, ChevronLeft, ChevronRight, MapPin, MessageCircle, Mountain, Navigation, Sparkles, Trees } from 'lucide-react';

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

function destinationMedia(destination) {
  const gallery = Array.isArray(destination?.media_assets)
    ? destination.media_assets.filter((media) => media?.url)
    : [];

  if (gallery.length) return gallery;
  if (!destination?.image_url) return [];

  return [{
    id: `${destination.id || destination.dest_code || 'destination'}-cover`,
    url: destination.image_url,
    caption: destination.image_caption || '',
    alt_text: destination.image_alt || destination.name || '',
  }];
}

export default function LandingPage({ destination, onBack, onNext }) {
  const [destinations, setDestinations] = useState(destination ? [destination] : []);
  const [activeCategory, setActiveCategory] = useState(
    destination ? categoryFor(destination) : null,
  );
  const [selectedId, setSelectedId] = useState(destination?.id ?? null);
  const [typedText, setTypedText] = useState('');
  const [activeMediaIndex, setActiveMediaIndex] = useState(0);
  const [thumbnailFrame, setThumbnailFrame] = useState(0);
  const galleryRef = useRef(null);

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
  const hasAnimatedThumbnails = useMemo(
    () => filteredDestinations.some((item) => destinationMedia(item).length > 1),
    [filteredDestinations],
  );

  const activeLabel = LOCATION_CATEGORIES.find((item) => item.key === activeCategory)?.label;
  const selectedMedia = useMemo(
    () => destinationMedia(selectedDestination),
    [selectedDestination],
  );
  const activeMedia = selectedMedia[activeMediaIndex] || selectedMedia[0];
  const heroImageUrl = assetUrl(activeMedia?.url || filteredDestinations[0]?.image_url);
  const fullText = destinationText(selectedDestination);

  useEffect(() => {
    setThumbnailFrame(0);
  }, [activeCategory]);

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    if (!activeCategory || selectedId || !hasAnimatedThumbnails || prefersReducedMotion) {
      return undefined;
    }

    const timer = window.setInterval(() => {
      setThumbnailFrame((current) => current + 1);
    }, 3800);

    return () => window.clearInterval(timer);
  }, [activeCategory, hasAnimatedThumbnails, selectedId]);

  useEffect(() => {
    setActiveMediaIndex(0);
    requestAnimationFrame(() => galleryRef.current?.scrollTo({ left: 0, behavior: 'auto' }));
  }, [selectedId]);

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

  function scrollToMedia(index) {
    const gallery = galleryRef.current;
    if (!gallery || !selectedMedia.length) return;
    const nextIndex = (index + selectedMedia.length) % selectedMedia.length;
    gallery.scrollTo({ left: gallery.clientWidth * nextIndex, behavior: 'smooth' });
    setActiveMediaIndex(nextIndex);
  }

  function showPreviousMedia() {
    scrollToMedia(activeMediaIndex - 1);
  }

  function showNextMedia() {
    scrollToMedia(activeMediaIndex + 1);
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
                const itemMedia = destinationMedia(item);
                const thumbnailIndex = itemMedia.length ? thumbnailFrame % itemMedia.length : 0;
                return (
                  <button className="area-destination-card" key={item.id || item.dest_code || item.name} onClick={() => setSelectedId(item.id)} type="button">
                    <span className="area-destination-thumb">
                      {itemMedia.length > 0 && (
                        <span
                          className="area-destination-thumb-track"
                          style={{ transform: `translateX(-${thumbnailIndex * 100}%)` }}
                        >
                          {itemMedia.map((media, index) => (
                            <img
                              key={`${media.id || media.url}-${index}`}
                              src={assetUrl(media.url)}
                              alt={media.alt_text || media.caption || `${item.name} ${index + 1}`}
                              loading="lazy"
                            />
                          ))}
                        </span>
                      )}
                      {itemMedia.length > 1 && (
                        <span className="area-destination-photo-count">
                          {thumbnailIndex + 1}/{itemMedia.length}
                        </span>
                      )}
                    </span>
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
              {selectedMedia.length > 0 && (
                <div className="destination-gallery" aria-label={`Ảnh ${selectedDestination.name}`}>
                  <div className="gallery-toolbar">
                    <span>{activeMediaIndex + 1}/{selectedMedia.length}</span>
                    {selectedMedia.length > 1 && (
                      <div className="gallery-controls">
                        <button type="button" onClick={showPreviousMedia} aria-label="Ảnh trước">
                          <ChevronLeft size={16} />
                        </button>
                        <button type="button" onClick={showNextMedia} aria-label="Ảnh tiếp theo">
                          <ChevronRight size={16} />
                        </button>
                      </div>
                    )}
                  </div>

                  <div
                    className="gallery-swipe-viewport"
                    ref={galleryRef}
                    onScroll={(event) => {
                      const viewport = event.currentTarget;
                      if (!viewport.clientWidth) return;
                      const index = Math.round(viewport.scrollLeft / viewport.clientWidth);
                      setActiveMediaIndex(Math.min(selectedMedia.length - 1, Math.max(0, index)));
                    }}
                    onKeyDown={(event) => {
                      if (event.key === 'ArrowLeft') {
                        event.preventDefault();
                        showPreviousMedia();
                      }
                      if (event.key === 'ArrowRight') {
                        event.preventDefault();
                        showNextMedia();
                      }
                    }}
                    tabIndex="0"
                  >
                    {selectedMedia.map((media, index) => (
                      <figure className="gallery-slide" key={`${media.id || media.url}-${index}`}>
                        <img
                          src={assetUrl(media.url)}
                          alt={media.alt_text || media.caption || `${selectedDestination.name} ${index + 1}`}
                          loading={index === 0 ? 'eager' : 'lazy'}
                        />
                      </figure>
                    ))}
                  </div>
                  {selectedMedia.length > 1 && (
                    <div className="gallery-dots" aria-hidden="true">
                      {selectedMedia.map((media, index) => (
                        <span className={index === activeMediaIndex ? 'is-active' : ''} key={media.id || media.url || index} />
                      ))}
                    </div>
                  )}
                  {(activeMedia?.caption || activeMedia?.alt_text) && (
                    <small className="gallery-caption">
                      {activeMedia.caption || activeMedia.alt_text}
                    </small>
                  )}
                </div>
              )}

              <b>
                <MapPin size={16} style={{ verticalAlign: 'middle' }} />{' '}
                {selectedDestination.location || 'Tây Ninh, Việt Nam'}
              </b>
              <p>{typedText}<span className="typing-cursor" /></p>
              {selectedDestination.navigation_note && (
                <small className="navigation-note">
                  {selectedDestination.navigation_note}
                </small>
              )}
            </div>
          )}

          {selectedDestination?.google_maps_url && (
            <a
              className="maps-link"
              href={selectedDestination.google_maps_url}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Mở chỉ đường đến ${selectedDestination.name} trên Google Maps`}
            >
              <Navigation size={17} /> Mở Google Maps
            </a>
          )}

          <button className="primary-btn" disabled={!selectedDestination} onClick={() => onNext(selectedDestination)}>
            <MessageCircle size={17} style={{ verticalAlign: 'middle' }} /> Hỏi AI Guide
          </button>
        </div>
      </div>

    </div>
  );
}
