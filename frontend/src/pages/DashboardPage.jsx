import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, ArrowRight, Loader2, MapPin, Star } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || '';

const LOCATION_CATEGORIES = [
  {
    key: 'summit',
    label: 'Khu vực đỉnh núi',
    description: 'Tượng, cột mốc, vườn cảnh và các điểm check-in trên đỉnh.',
  },
  {
    key: 'foot',
    label: 'Khu vực chân núi',
    description: 'Cổng chính, nhà ga, điểm trung chuyển và dịch vụ ở chân núi.',
  },
  {
    key: 'pagoda',
    label: 'Khu vực Chùa Bà - Điện Bà',
    description: 'Các điểm tâm linh, hang động và tuyến tham quan Chùa Bà.',
  },
];

function normalizeText(value) {
  return (value || '')
    .toString()
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase();
}

function categoryFor(destination) {
  const location = normalizeText(destination.location);

  if (location.includes('dinh')) return 'summit';
  if (location.includes('chan') || location.includes('cong chinh')) return 'foot';

  return 'pagoda';
}

export default function DashboardPage({ initialDestination, onBack, onSelect }) {
  const [destinations, setDestinations] = useState(
    initialDestination ? [initialDestination] : [],
  );
  const [loading, setLoading] = useState(true);
  const [activeCategory, setActiveCategory] = useState(null);
  const [coverErrors, setCoverErrors] = useState({});

  const handleCoverError = (destinationId) => {
    setCoverErrors((prev) => ({ ...prev, [destinationId]: true }));
  };

  useEffect(() => {
    async function loadDestinations() {
      try {
        const res = await fetch(`${API_URL}/api/destinations`);
        const data = await res.json();

        if (Array.isArray(data.destinations)) {
          setDestinations(data.destinations);
        }
      } catch (e) {
        if (!initialDestination) {
          setDestinations([]);
        }
      } finally {
        setLoading(false);
      }
    }

    loadDestinations();
  }, [initialDestination]);

  const categoryCounts = useMemo(() => {
    return destinations.reduce(
      (counts, destination) => {
        const key = categoryFor(destination);
        counts[key] = (counts[key] || 0) + 1;
        return counts;
      },
      { summit: 0, foot: 0, pagoda: 0 },
    );
  }, [destinations]);

  const filteredDestinations = useMemo(() => {
    if (!activeCategory) return [];

    return destinations.filter((destination) => categoryFor(destination) === activeCategory);
  }, [activeCategory, destinations]);

  const activeLabel = LOCATION_CATEGORIES.find(
    (category) => category.key === activeCategory,
  )?.label;

  return (
    <div className="phone">
      <div className="page dashboard-page">
        <button className="back-btn" onClick={onBack}>
          <ArrowLeft size={18} /> Quay lại QR
        </button>

        <div className="topbar dashboard-topbar">
          <div>
            <div className="badge" style={{ color: '#1f875a', background: '#eaf7ef' }}>
              <Star size={15} /> Dashboard địa điểm
            </div>
            <h2>Địa điểm nổi bật</h2>
            <p className="small-text">Chọn một khu vực để xem các địa điểm tương ứng.</p>
          </div>
        </div>

        {loading && (
          <div className="dashboard-loading">
            <Loader2 className="spin" size={20} /> Đang tải địa điểm...
          </div>
        )}

        {!loading && destinations.length === 0 && (
          <div className="card">
            <b>Chưa có dữ liệu địa điểm</b>
            <p className="small-text">Hãy kiểm tra backend hoặc file Excel destinations.</p>
          </div>
        )}

        {!loading && destinations.length > 0 && (
          <>
            {!activeCategory && (
              <>
                <div className="category-grid">
                  {LOCATION_CATEGORIES.map((category) => (
                    <button
                      className="category-card"
                      key={category.key}
                      onClick={() => setActiveCategory(category.key)}
                    >
                      <div>
                        <b>{category.label}</b>
                        <p>{category.description}</p>
                      </div>
                      <span>{categoryCounts[category.key]} địa điểm</span>
                    </button>
                  ))}
                </div>

                <div className="category-empty">
                  Bấm vào một danh mục để hiển thị các địa điểm trong khu vực đó.
                </div>
              </>
            )}

            {activeCategory && (
              <>
                <button className="back-btn category-back-btn" onClick={() => setActiveCategory(null)}>
                  <ArrowLeft size={18} /> Chọn khu vực khác
                </button>

                <div className="category-title">
                  <b>{activeLabel}</b>
                  <span>{filteredDestinations.length} địa điểm</span>
                </div>

                <div className="destination-list">
                  {filteredDestinations.map((destination) => {
                    const destinationKey =
                      destination.id || destination.dest_code || destination.name;
                    const hasCoverError = coverErrors[destinationKey];
                    const hasImage = !!destination.image_url;

                    return (
                      <button
                        className="destination-card"
                        key={destinationKey}
                        onClick={() => onSelect(destination)}
                      >
                        <div
                          className="destination-cover"
                          style={
                            hasImage && !hasCoverError
                              ? {
                                  backgroundImage: `linear-gradient(135deg, rgba(21, 83, 60, 0.18), rgba(31, 135, 90, 0.56)), url(${destination.image_url})`,
                                }
                              : undefined
                          }
                        >
                          {hasImage && !hasCoverError && (
                            <img
                              alt={destination.image_alt || destination.name}
                              src={destination.image_url}
                              onError={() => handleCoverError(destinationKey)}
                              style={{
                                position: 'absolute',
                                inset: 0,
                                opacity: 0,
                                pointerEvents: 'none',
                              }}
                            />
                          )}
                          <span>{destination.category || 'Du lịch sinh thái'}</span>
                        </div>

                        <div className="destination-content">
                          <h3>{destination.name}</h3>

                          <div className="destination-location">
                            <MapPin size={14} />{' '}
                            {destination.location || 'Tây Ninh, Việt Nam'}
                          </div>

                          <p>{destination.short_description || destination.description_detail}</p>

                          <div className="destination-meta">
                            <span>{destination.estimated_duration || '1 ngày'}</span>
                            <span>{destination.difficulty_level || 'Dễ'}</span>
                            <ArrowRight size={17} />
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
