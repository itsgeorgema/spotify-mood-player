const BACKEND_API_URL = import.meta.env.VITE_BACKEND_API_URL;

export const apiClient = {
  initiateLogin: () => {
    window.location.href = `${BACKEND_API_URL}/login`;
  },
};