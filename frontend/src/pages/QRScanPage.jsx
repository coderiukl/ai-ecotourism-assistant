import { Camera, Leaf, QrCode } from 'lucide-react';

import { API_URL } from '../api';

const DEMO_QR_CODE = 'ECO_NUI_BA_DEN_001';

export default function QRScanPage({ onSuccess }) {
  const qrTargetUrl = `${window.location.origin}${window.location.pathname}?qr=${encodeURIComponent(
    DEMO_QR_CODE,
  )}`;
  const qrImageUrl = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(
    qrTargetUrl,
  )}`;

  async function handleDemoScan() {
    try {
      const res = await fetch(`${API_URL}/api/qr/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ qr_code: DEMO_QR_CODE }),
      });

      const data = await res.json();

      if (data.status === 'valid') {
        onSuccess(data.destination);
        return;
      }

      alert(data.message);
    } catch (e) {
      alert('Không kết nối được backend. Hãy kiểm tra FastAPI server.');
    }
  }

  return (
    <div className="phone">
      <div className="page">
        <div className="topbar">
          <div>
            <div className="badge" style={{ color: '#1f875a', background: '#eaf7ef' }}>
              <Leaf size={15} /> AI Ecotourism
            </div>
            <h2>Quét QR để bắt đầu</h2>
            <p className="small-text">Đưa mã QR tại điểm du lịch vào khung quét.</p>
          </div>

          <div className="icon-pill">
            <Camera size={22} />
          </div>
        </div>

        <div className="qr-frame">
          <img className="qr-code" src={qrImageUrl} alt={`QR demo ${DEMO_QR_CODE}`} />
          {/* <span className="qr-label">{DEMO_QR_CODE}</span> */}
        </div>

        <div className="card">
          <b>📌 Hướng dẫn</b>
          <p className="small-text">
            Sau khi quét QR, hệ thống sẽ mở video giới thiệu, chọn địa điểm nổi bật,
            chat với AI Guide và kết thúc trải nghiệm.
          </p>
        </div>

        <div style={{ height: 18 }} />

        <button className="primary-btn" onClick={handleDemoScan}>
          <QrCode size={17} style={{ verticalAlign: 'middle' }} /> Quét QR demo
        </button>
      </div>
    </div>
  );
}
