import { Camera, Leaf } from 'lucide-react';

const DEMO_QR_CODE = 'ECO_NUI_BA_DEN_001';

export default function QRScanPage() {
  const qrTargetUrl = `${window.location.origin}${window.location.pathname}?qr=${encodeURIComponent(
    DEMO_QR_CODE,
  )}`;
  const qrImageUrl = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(
    qrTargetUrl,
  )}`;

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
        </div>
      </div>
    </div>
  );
}
