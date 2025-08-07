// Use Vercel API routes as proxy to avoid CORS/third-party cookie issues
const API_BASE = '/api';

export const apiClient = {
  initiateLogin: () => {
    window.location.href = `${API_BASE}/login`;
  },

  checkAuth: async () => {
    const response = await fetch(`${API_BASE}/check_auth`, {
      method: 'GET',
      credentials: 'include', // Include cookies
      headers: {
        'Content-Type': 'application/json',
      },
    });
    try {
      return await response.json();
    } catch (err) {
      if (response.status === 401 || response.status === 403) {
        return { isAuthenticated: false };
      }
      // If not JSON and not an auth error, throw
      throw new Error('Auth check failed: Not valid JSON');
    }
  },

  analyze: async () => {
    const response = await fetch(`${API_BASE}/analyze`, {
      method: 'POST',
      credentials: 'include', // Include cookies
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.json();
  },

  getMoodTracks: async (mood: string) => {
    const response = await fetch(`${API_BASE}/mood-tracks?mood=${encodeURIComponent(mood)}`, {
      method: 'GET',
      credentials: 'include', // Include cookies
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.json();
  },

  getDevices: async () => {
    const response = await fetch(`${API_BASE}/devices`, {
      method: 'GET',
      credentials: 'include', // Include cookies
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.json();
  },

  playTracks: async (trackUris: string[], deviceId?: string) => {
    const response = await fetch(`${API_BASE}/play`, {
      method: 'POST',
      credentials: 'include', // Include cookies
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        track_uris: trackUris,
        device_id: deviceId,
      }),
    });
    return response.json();
  },

  logout: async () => {
    const response = await fetch(`${API_BASE}/logout`, {
      method: 'POST',
      credentials: 'include', // Include cookies
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.json();
  },

  // Generic proxy method for any other endpoints
  proxy: async (endpoint: string, options: RequestInit = {}) => {
    const response = await fetch(`${API_BASE}/proxy?endpoint=${encodeURIComponent(endpoint)}`, {
      ...options,
      credentials: 'include', // Include cookies
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });
    return response.json();
  },
};