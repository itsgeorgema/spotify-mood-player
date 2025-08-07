export default async function handler(req, res) {
  const backendUrl = process.env.BACKEND_API_URL || process.env.VITE_BACKEND_API_URL;
  if (!backendUrl) {
    return res.status(500).json({ error: 'Backend URL not configured' });
  }

  const { path } = req.query;
  const targetPath = Array.isArray(path) ? path.join('/') : path;
  const targetUrl = new URL(`/api/${targetPath}`.replace(/\/+/g, '/'), backendUrl);

  // Debug: Log incoming request
  console.log('[Proxy] Incoming:', {
    method: req.method,
    url: req.url,
    targetUrl: targetUrl.toString(),
    headers: req.headers,
  });

  // Prepare request options
  const requestOptions = {
    method: req.method,
    headers: {
      ...req.headers,
      host: undefined, // Remove host header to avoid issues
    },
    body: ['GET', 'HEAD'].includes(req.method) ? undefined : req.body,
    redirect: 'manual',
  };

  // Proxy the request
  const response = await fetch(targetUrl, requestOptions);

  // Debug: Log backend response
  const preview = await response.clone().text();
  console.log('[Proxy] Backend response:', {
    status: response.status,
    statusText: response.statusText,
    headers: Object.fromEntries(response.headers.entries()),
    preview: preview.slice(0, 200),
  });

  // Handle redirects
  if (response.status >= 300 && response.status < 400) {
    const location = response.headers.get('location');
    if (location) {
      return res.redirect(302, location);
    }
  }

  // Forward Set-Cookie headers
  const setCookie = response.headers.get('set-cookie');
  if (setCookie) {
    res.setHeader('Set-Cookie', setCookie);
  }

  // Forward status, headers, and body
  res.status(response.status);
  response.headers.forEach((value, key) => {
    if (!['content-encoding', 'content-length', 'transfer-encoding', 'set-cookie'].includes(key.toLowerCase())) {
      res.setHeader(key, value);
    }
  });
  res.send(preview);
}