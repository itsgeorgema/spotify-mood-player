import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getApiEndpoint } from '../App';
import './MusicAnalysisLoading.css';

const MusicAnalysisLoading: React.FC = () => {
  const navigate = useNavigate();

  useEffect(() => {
    const analyzeLibrary = async () => {
      try {
        // check for existing analysis
        const checkResponse = await fetch(getApiEndpoint('/api/mood-tracks?mood=happy'), {
          credentials: 'include'
        });
        
        if (checkResponse.ok) {
          const checkData = await checkResponse.json();
          if (checkData.track_uris && checkData.track_uris.length > 0) {
            console.log('Analysis already done, redirecting to player...');
            navigate('/player', { replace: true });
            return;
          }
        }

        // If no mood data found, proceed with analysis
        console.log('Starting sentiment analysis...');
        const response = await fetch(getApiEndpoint('/api/sentiment_analysis'), {
          method: 'POST',
          credentials: 'include'
        });
        
        if (!response.ok) {
          const errorText = await response.text();
          console.error('Analysis failed:', errorText);
          throw new Error('Failed to analyze library');
        }

        const data = await response.json();
        console.log('Analysis response:', data);
        
        // Verify we have the moods data
        if (!data.available_moods || data.available_moods.length === 0) {
          console.error('No moods were categorized');
          throw new Error('No moods were categorized');
        }

        console.log('Analysis complete, redirecting to player...');
        // If we get here, analysis was successful and moods are in session
        navigate('/player', { replace: true });
      } catch (error) {
        console.error('Error in analysis:', error);
        // Even if analysis fails, redirect to player - they can try again from there
        navigate('/player', { replace: true });
      }
    };
    analyzeLibrary();
  }, [navigate]);

  return (
    <div className="loading-container">
      <div className="loading-modal">
        <div className="spinner"></div>
        <p>Analyzing your music library. This may take a few minutes...</p>
      </div>
    </div>
  );
};

export default MusicAnalysisLoading; 