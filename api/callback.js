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
    const url = new URL('/api/callback', backendUrl);
    url.search = queryParams.toString();
    
    // Proxy the request to the backend
    const response = await fetch(url.toString(), {
      method: 'GET',
      headers: {
        'User-Agent': req.headers['user-agent'] || 'Vercel-Proxy',
        'Accept': req.headers.accept || 'text/html,application/json',
        'Cookie': req.headers.cookie || '',
      },
      redirect: 'manual', // Don't follow redirects automatically
    });

    // Handle redirects from backend
    if (response.status >= 300 && response.status < 400) {
      const location = response.headers.get('location');
      if (location) {
        return res.redirect(302, location);
      }
    }

    // Forward cookies from backend to client
    const setCookieHeaders = response.headers.get('set-cookie');
    if (setCookieHeaders) {
      res.setHeader('Set-Cookie', setCookieHeaders);
    }

    // If backend callback was successful, redirect to login success page
    if (response.status === 200 || response.status === 302) {
      // Redirect to the frontend login success page
      return res.redirect(302, '/login-success');
    }

    // If there was an error, redirect to failure page
    if (response.status >= 400) {
      const data = await response.text();
      console.error('Callback error:', data);
      return res.redirect(302, '/failure?error=callback_failed');
    }

    // Forward the response for any other cases
    const data = await response.text();
    
    // Copy other headers from backend response
    response.headers.forEach((value, key) => {
      if (!['content-encoding', 'content-length', 'transfer-encoding', 'set-cookie'].includes(key.toLowerCase())) {
        res.setHeader(key, value);
      }
    });

    res.status(response.status).send(data);
  } catch (error) {
    console.error('Proxy error:', error);
    res.status(500).json({ error: 'Proxy request failed' });
  }
}