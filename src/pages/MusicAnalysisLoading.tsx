import React, { useEffect, useState, useRef } from 'react';
import './MusicAnalysisLoading.css';
import { getApiEndpoint } from '../App';

const MusicAnalysisLoading: React.FC = () => {
  const [progress, setProgress] = useState(0);
  const [loadingText, setLoadingText] = useState("Analyzing your music library...");
  const [error, setError] = useState<string | null>(null);
  const [isAnimating, setIsAnimating] = useState(false);
  const prevProgressRef = useRef(0);

  useEffect(() => {
    const messages = [
      "Analyzing your music library...",
      "Extracting song features...",
      "Finding the perfect mood matches...",
      "Preparing your personalized experience..."
    ];

    const textInterval = setInterval(() => {
      setLoadingText(prev => {
        const currentIndex = messages.indexOf(prev);
        return messages[(currentIndex + 1) % messages.length];
      });
    }, 6000);

    // Poll for progress updates
    const progressInterval = setInterval(async () => {
      try {
        const response = await fetch(getApiEndpoint('/api/analysis_progress'), {
          credentials: 'include'
        });
        
        if (!response.ok) {
          throw new Error('Failed to fetch progress');
        }
        
        const data = await response.json();
        
        if (data.status === 'failed') {
          setError('Analysis failed. Please try again.');
          clearInterval(progressInterval);
          clearInterval(textInterval);
          return;
        }
        
        if (data.status === 'completed') {
          setProgress(100);
          clearInterval(progressInterval);
          clearInterval(textInterval);
          return;
        }
        
        if (data.total_tracks > 0) {
          const currentProgress = (data.analyzed_tracks / data.total_tracks) * 100;
          const newProgress = Math.min(currentProgress, 99); // Cap at 99% until complete
          
          // Only trigger animation if progress has changed
          if (newProgress !== prevProgressRef.current) {
            setIsAnimating(true);
            setProgress(newProgress);
            prevProgressRef.current = newProgress;
            
            // Remove animation class after animation completes
            setTimeout(() => {
              setIsAnimating(false);
            }, 500);
          }
        }
      } catch (err) {
        console.error('Error fetching progress:', err);
        // Don't stop the progress bar on error, just continue showing current progress
      }
    }, 1000);

    return () => {
      clearInterval(textInterval);
      clearInterval(progressInterval);
    };
  }, []);

  if (error) {
    return (
      <div className="app loading-app-bg">
        <div className="loading-center-stack">
          <div className="loading-modal-wrapper">
            <div className="loading-bg-conic" />
            <div className="loading-modal">
              <h2 className="loading-title">Analysis Failed</h2>
              <p className="loading-message">{error}</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="app loading-app-bg">
      <div className="loading-center-stack">
        <div className="loading-modal-wrapper">
          <div className="loading-bg-conic" />
          <div className="loading-modal">
            <h2 className="loading-title">Preparing Your Experience</h2>
            <p className="loading-message">{loadingText}</p>
            <div className="progress-bar">
              <div 
                className={`progress-fill ${isAnimating ? 'animating' : ''}`}
                style={{ width: `${progress}%` }}
              />
            </div>
            <span className="progress-text">{Math.round(progress)}%</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MusicAnalysisLoading; 