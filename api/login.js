export default async function handler(req, res) {
    if (req.method !== 'GET') {
      return res.status(405).json({ error: 'Method not allowed' });
    }
  
    try {
      const backendUrl = process.env.BACKEND_API_URL || process.env.VITE_BACKEND_API_URL;
      if (!backendUrl) {
        return res.status(500).json({ error: 'Backend URL not configured' });
      }
  
      // Use URL constructor for proper URL handling
      const targetUrl = new URL('/api/login', backendUrl).toString();
  
      // Proxy the request to the backend
      const response = await fetch(targetUrl, {
        method: 'GET',
        headers: {
          'User-Agent': req.headers['user-agent'] || 'Vercel-Proxy',
          'Accept': req.headers.accept || 'text/html,application/json',
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
  
      // Forward the response
      const data = await response.text();
      response.headers.forEach((value, key) => {
        if (!['content-encoding', 'content-length', 'transfer-encoding'].includes(key.toLowerCase())) {
          res.setHeader(key, value);
        }
      });
  
      res.status(response.status).send(data);
    } catch (error) {
      res.status(500).json({ error: 'Proxy request failed' });
    }
  }