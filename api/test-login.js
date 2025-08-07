// Test endpoint to check backend login connectivity
export default async function handler(req, res) {
  try {
    const backendUrl = process.env.BACKEND_API_URL || process.env.VITE_BACKEND_API_URL;
    
    if (!backendUrl) {
      return res.status(500).json({ 
        error: 'Backend URL not configured'
      });
    }

    // Test login endpoint connectivity
    const targetUrl = new URL('/api/login', backendUrl).toString();
    
    console.log(`Testing backend login endpoint: ${targetUrl}`);
    
    const response = await fetch(targetUrl, {
      method: 'GET',
      headers: {
        'User-Agent': 'Vercel-Test-Proxy',
        'Accept': 'text/html,application/json',
      },
      redirect: 'manual', // Don't follow redirects
      timeout: 10000, // 10 second timeout
    });

    let responseText;
    try {
      responseText = await response.text();
    } catch (e) {
      responseText = 'Could not read response body';
    }
    
    return res.status(200).json({
      success: true,
      backend_url: backendUrl,
      target_url: targetUrl,
      status: response.status,
      status_text: response.statusText,
      is_redirect: response.status >= 300 && response.status < 400,
      location_header: response.headers.get('location'),
      response_preview: responseText.substring(0, 500),
      headers: Object.fromEntries(response.headers.entries()),
    });

  } catch (error) {
    console.error('Backend login test failed:', error);
    
    return res.status(500).json({
      error: 'Failed to connect to backend login endpoint',
      details: error.message,
      backend_url: process.env.BACKEND_API_URL || process.env.VITE_BACKEND_API_URL,
    });
  }
}