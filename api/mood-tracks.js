export default async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const backendUrl = process.env.BACKEND_API_URL || process.env.VITE_BACKEND_API_URL;
    if (!backendUrl) {
      console.error('Backend URL not configured');
      return res.status(500).json({ error: 'Backend URL not configured' });
    }

    // Forward query parameters
    const queryParams = new URLSearchParams();
    Object.entries(req.query).forEach(([key, value]) => {
      queryParams.append(key, value);
    });

    // Use URL constructor for proper URL handling
    const url = new URL('/api/mood-tracks', backendUrl);
    url.search = queryParams.toString();
    
    // Proxy the request to the backend with cookies
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'User-Agent': req.headers['user-agent'] || 'Vercel-Proxy',
        'Accept': req.headers.accept || 'application/json',
        'Cookie': req.headers.cookie || '',
      },
    });

    // Forward cookies from backend to client
    const setCookieHeaders = response.headers.get('set-cookie');
    if (setCookieHeaders) {
      res.setHeader('Set-Cookie', setCookieHeaders);
    }

    const data = await response.json();
    
    // Copy other headers from backend response
    response.headers.forEach((value, key) => {
      if (!['content-encoding', 'content-length', 'transfer-encoding', 'set-cookie'].includes(key.toLowerCase())) {
        res.setHeader(key, value);
      }
    });

    res.status(response.status).json(data);
  } catch (error) {
    console.error('Proxy error:', error);
    res.status(500).json({ error: 'Proxy request failed' });
  }
}