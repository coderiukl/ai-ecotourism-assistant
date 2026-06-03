import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';

import './style.css';
import ActivitiesPage from './pages/ActivitiesPage';
import ChatbotPage from './pages/ChatbotPage';
import DashboardPage from './pages/DashboardPage';
import LandingPage from './pages/LandingPage';
import QRScanPage from './pages/QRScanPage';
import ThankYouPage from './pages/ThankYouPage';
import VideoPage from './pages/VideoPage';

const API_URL = import.meta.env.VITE_API_URL || '';

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
          setDestination(data.destination);
          setStep('dashboard');
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
            setDestination(data);
            setStep('dashboard');
          }}
        />
      )}

      {step === 'dashboard' && (
        <DashboardPage
          initialDestination={destination}
          onBack={() => setStep('qr')}
          onSelect={(data) => {
            setDestination(data);
            setStep('landing');
          }}
        />
      )}

      {step === 'landing' && (
        <LandingPage
          destination={destination}
          onBack={() => setStep('dashboard')}
          onNext={() => setStep('video')}
        />
      )}

      {step === 'video' && (
        <VideoPage
          destination={destination}
          onBack={() => setStep('landing')}
          onNext={() => setStep('activities')}
        />
      )}

      {step === 'activities' && (
        <ActivitiesPage
          destination={destination}
          onBack={() => setStep('video')}
          onNext={() => setStep('chatbot')}
        />
      )}

      {step === 'chatbot' && (
        <ChatbotPage
          destination={destination}
          onBack={() => setStep('activities')}
          onDone={() => setStep('thankyou')}
        />
      )}

      {step === 'thankyou' && <ThankYouPage onRestart={() => setStep('qr')} />}
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
