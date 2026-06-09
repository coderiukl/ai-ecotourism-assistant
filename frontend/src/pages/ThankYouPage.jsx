export default function ThankYouPage({ onRestart }) {
  return (
    <div className="phone">
      <div className="page">
        <div className="success-icon">✅</div>

        <h2 style={{ textAlign: 'center' }}>Cảm ơn bạn!</h2>
        <p className="small-text" style={{ textAlign: 'center' }}>
          Hy vọng bạn có trải nghiệm thú vị cùng AI Ecotourism
          Assistant.
        </p>

        <div style={{ height: 30 }} />

        <button className="primary-btn" onClick={onRestart}>
          Quay lại màn hình QR
        </button>
      </div>
    </div>
  );
}
