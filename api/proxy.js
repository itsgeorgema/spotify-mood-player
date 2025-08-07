export default async function handler(req, res) {
  try {
    const backendUrl = process.env.BACKEND_API_URL || process.env.VITE_BACKEND_API_URL;
    if (!backendUrl) {
      console.error('Backend URL not configured');
      return res.status(500).json({ error: 'Backend URL not configured' });
    }

    // Get the endpoint from query parameter
    const { endpoint } = req.query;
    if (!endpoint) {
      return res.status(400).json({ error: 'Missing endpoint parameter' });
    }

    // Construct the backend URL using URL constructor
    const targetUrl = new URL(`/api/${endpoint}`, backendUrl);
    
    // Forward query parameters (excluding the endpoint parameter)
    const queryParams = new URLSearchParams();
    Object.entries(req.query).forEach(([key, value]) => {
      if (key !== 'endpoint') {
        queryParams.append(key, value);
      }
    });

    if (queryParams.toString()) {
      targetUrl.search = queryParams.toString();
    }

    // Prepare request options
    const requestOptions = {
      method: req.method,
      headers: {
        'User-Agent': req.headers['user-agent'] || 'Vercel-Proxy',
        'Accept': req.headers.accept || 'application/json',
        'Cookie': req.headers.cookie || '',
      },
    };

    // Add Content-Type and body for POST/PUT requests
    if (['POST', 'PUT', 'PATCH'].includes(req.method)) {
      requestOptions.headers['Content-Type'] = req.headers['content-type'] || 'application/json';
      if (req.body) {
        requestOptions.body = JSON.stringify(req.body);
      }
    }

    // Proxy the request to the backend
    const response = await fetch(targetUrl.toString(), requestOptions);

    // Handle redirects
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

    // Determine response type
    const contentType = response.headers.get('content-type');
    let data;
    
    if (contentType && contentType.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }
    
    // Copy other headers from backend response
    response.headers.forEach((value, key) => {
      if (!['content-encoding', 'content-length', 'transfer-encoding', 'set-cookie'].includes(key.toLowerCase())) {
        res.setHeader(key, value);
      }
    });

    // Send appropriate response
    if (contentType && contentType.includes('application/json')) {
      res.status(response.status).json(data);
    } else {
      res.status(response.status).send(data);
    }
  } catch (error) {
    console.error('Proxy error:', error);
    res.status(500).json({ error: 'Proxy request failed' });
  }
}