import React, { useEffect, useState } from 'react';
import './MusicAnalysisLoading.css';

const MusicAnalysisLoading: React.FC = () => {
  const [progress, setProgress] = useState(0);
  const [loadingText, setLoadingText] = useState("Analyzing your music library...");

  useEffect(() => {
    const messages = [
      "Analyzing your music library...",
      "Finding the perfect mood matches...",
      "Calculating emotional patterns...",
      "Preparing your personalized experience..."
    ];

    const textInterval = setInterval(() => {
      setLoadingText(prev => {
        const currentIndex = messages.indexOf(prev);
        return messages[(currentIndex + 1) % messages.length];
      });
    }, 6000);

    const progressInterval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 95) return prev;
        return prev + Math.random() * 5;
      });
    }, 1000);

    return () => {
      clearInterval(textInterval);
      clearInterval(progressInterval);
    };
  }, []);

  return (
    <div className="app loading-app-bg">
      <div className="loading-center-stack">
        <div className="loading-bg-conic" />
        <div className="loading-modal">
          <h2 className="loading-title">Preparing Your Experience</h2>
          <p className="loading-message">{loadingText}</p>
          <div className="progress-bar">
            <div 
              className="progress-fill" 
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="progress-text">{Math.round(progress)}%</span>
        </div>
      </div>
    </div>
  );
};

export default MusicAnalysisLoading; 