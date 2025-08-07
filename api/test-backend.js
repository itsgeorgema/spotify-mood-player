// Test endpoint to check backend connectivity
export default async function handler(req, res) {
  try {
    const backendUrl = process.env.BACKEND_API_URL || process.env.VITE_BACKEND_API_URL;
    
    if (!backendUrl) {
      return res.status(500).json({ 
        error: 'Backend URL not configured',
        env_check: {
          BACKEND_API_URL: !!process.env.BACKEND_API_URL,
          VITE_BACKEND_API_URL: !!process.env.VITE_BACKEND_API_URL
        }
      });
    }

    // Test basic connectivity to backend
    const targetUrl = new URL('/api/health', backendUrl).toString();
    
    console.log(`Testing backend connectivity to: ${targetUrl}`);
    
    const response = await fetch(targetUrl, {
      method: 'GET',
      headers: {
        'User-Agent': 'Vercel-Test-Proxy',
        'Accept': 'application/json',
      },
      timeout: 10000, // 10 second timeout
    });

    const responseText = await response.text();
    
    return res.status(200).json({
      success: true,
      backend_url: backendUrl,
      backend_status: response.status,
      backend_response: responseText,
      headers: Object.fromEntries(response.headers.entries()),
    });

  } catch (error) {
    console.error('Backend test failed:', error);
    
    return res.status(500).json({
      error: 'Failed to connect to backend',
      details: error.message,
      backend_url: process.env.BACKEND_API_URL || process.env.VITE_BACKEND_API_URL,
    });
  }
}