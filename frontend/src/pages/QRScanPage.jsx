import { useState } from 'react';
import { ArrowRight, Camera, Leaf, LoaderCircle, QrCode } from 'lucide-react';

import { API_URL } from '../api';

const DEMO_QR_CODE = 'ECO_NUI_BA_DEN_001';

export default function QRScanPage({ onSuccess }) {
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function submitCode(rawCode) {
    const qrCode = String(rawCode || '').trim();
    if (!qrCode || loading) return;

    setLoading(true);
    setError('');
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 10000);

    try {
      const response = await fetch(`${API_URL}/api/qr/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ qr_code: qrCode }),
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const data = await response.json();
      if (data.status !== 'valid' || !data.destination?.id) {
        setError(data.message || 'Mã QR không hợp lệ. Vui lòng kiểm tra và thử lại.');
        return;
      }

      onSuccess(data.destination);
    } catch (requestError) {
      setError(
        requestError?.name === 'AbortError'
          ? 'Máy chủ phản hồi quá lâu. Vui lòng thử lại.'
          : 'Chưa kết nối được hệ thống. Hãy kiểm tra backend rồi thử lại.',
      );
    } finally {
      window.clearTimeout(timeout);
      setLoading(false);
    }
  }

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
              Nhập mã trên bảng QR tại điểm tham quan để mở đúng hướng dẫn viên AI.
            </p>
          </div>

          <div className="icon-pill" aria-hidden="true">
            <Camera size={22} />
          </div>
        </div>

        <div className="qr-frame qr-entry-visual" aria-hidden="true">
          <QrCode size={92} strokeWidth={1.35} />
          <span>Quét bằng camera điện thoại hoặc nhập mã bên dưới</span>
        </div>

        <form
          className="qr-code-form"
          onSubmit={(event) => {
            event.preventDefault();
            submitCode(code);
          }}
        >
          <label htmlFor="qr-code">Mã điểm tham quan</label>
          <div className="qr-code-input-row">
            <input
              id="qr-code"
              autoCapitalize="characters"
              autoComplete="off"
              onChange={(event) => {
                setCode(event.target.value.toUpperCase());
                setError('');
              }}
              placeholder="Ví dụ: ECO_NUI_BA_DEN_001"
              spellCheck="false"
              value={code}
            />
            <button aria-label="Kiểm tra mã" disabled={!code.trim() || loading} type="submit">
              {loading ? <LoaderCircle className="spin" size={19} /> : <ArrowRight size={19} />}
            </button>
          </div>
          {error && <p className="form-error" role="alert">{error}</p>}
        </form>

        <div className="demo-entry">
          <span>Bạn đang xem bản MVP?</span>
          <button disabled={loading} onClick={() => submitCode(DEMO_QR_CODE)} type="button">
            Dùng mã demo
          </button>
        </div>
      </main>
    </div>
  );
}
