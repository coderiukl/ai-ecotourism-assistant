import { Camera, Leaf } from 'lucide-react';
import { QRCodeSVG } from 'qrcode.react';

import { PUBLIC_APP_URL } from '../api';

const DEMO_QR_CODE = 'ECO_NUI_BA_DEN_001';
const DEMO_QR_TARGET_URL = `${PUBLIC_APP_URL}/?qr=${encodeURIComponent(DEMO_QR_CODE)}`;

export default function QRScanPage() {
  return (
    <div className="phone">
      <main className="page qr-start-page">
        <div className="topbar">
          <div>
            <div className="badge" style={{ color: '#1f875a', background: '#eaf7ef' }}>
              <Leaf size={15} /> AI Ecotourism
            </div>
            <h2>Bắt đầu hành trình</h2>
            <p className="small-text">
              Quét mã QR tại điểm tham quan để mở đúng hướng dẫn viên AI.
            </p>
          </div>

          <div className="icon-pill" aria-hidden="true">
            <Camera size={22} />
          </div>
        </div>

        <div className="qr-frame qr-entry-visual qr-entry-visual-standalone">
          <div className="qr-code">
            <QRCodeSVG
              level="M"
              size={160}
              value={DEMO_QR_TARGET_URL}
            />
          </div>
          <span>Đưa camera điện thoại vào mã QR tại điểm tham quan</span>
        </div>
      </main>
    </div>
  );
}
