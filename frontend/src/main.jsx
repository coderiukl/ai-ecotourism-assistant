import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';

import './style.css';
import ChatbotPage from './pages/ChatbotPage';
import LandingPage from './pages/LandingPage';
import QRScanPage from './pages/QRScanPage';
import ThankYouPage from './pages/ThankYouPage';
import VideoPage from './pages/VideoPage';
import { API_URL } from './api';

function App() {
  const [step, setStep] = useState('qr');
  const [destination, setDestination] = useState(null);

  useEffect(() => {
    async function scanQrFromUrl() {
      const qrCode = new URLSearchParams(window.location.search).get('qr');
      if (!qrCode) return;

      try {
        const res = await fetch(`${API_URL}/api/qr/scan`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ qr_code: qrCode }),
        });
        const data = await res.json();
        if (data.status === 'valid') {
          setDestination(data.destination || null);
          setStep('video');
          window.history.replaceState({}, '', window.location.pathname);
        }
      } catch (e) {
        setStep('qr');
      }
    }

    scanQrFromUrl();
  }, []);

  return (
    <div className="app-shell">
      {step === 'qr' && (
        <QRScanPage
          onSuccess={(data) => {
            setDestination(data || null);
            setStep('video');
          }}
        />
      )}

      {step === 'video' && (
        <VideoPage
          destination={destination}
          onBack={() => setStep('qr')}
          onNext={() => setStep('landing')}
        />
      )}

      {step === 'landing' && (
        <LandingPage
          destination={destination}
          onBack={() => setStep('video')}
          onNext={(data) => {
            setDestination(data || destination);
            setStep('chatbot');
          }}
        />
      )}

      {step === 'chatbot' && (
        <ChatbotPage
          destination={destination}
          onBack={() => setStep('landing')}
          onDone={() => setStep('thankyou')}
        />
      )}

      {step === 'thankyou' && <ThankYouPage onRestart={() => setStep('qr')} />}
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
