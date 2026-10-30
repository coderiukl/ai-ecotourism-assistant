import { Camera, Leaf, QrCode } from 'lucide-react';

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

        <div className="qr-frame qr-entry-visual qr-entry-visual-standalone" aria-hidden="true">
          <QrCode size={120} strokeWidth={1.2} />
          <span>Đưa camera điện thoại vào mã QR tại điểm tham quan</span>
        </div>
      </main>
    </div>
  );
}
