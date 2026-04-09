import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

export const api = axios.create({
    baseURL: API_BASE_URL,
});

// Request Interceptor: Attach access token
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('rakshak_access_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Response Interceptor: Handle 401 and Refresh
api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;
        if (error.response?.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true;
            const refreshToken = localStorage.getItem('rakshak_refresh_token');
            if (refreshToken) {
                try {
                    const resp = await axios.post(`${API_BASE_URL}/refresh?refresh_token=${refreshToken}`);
                    const newAccess = resp.data.access_token;
                    localStorage.setItem('rakshak_access_token', newAccess);
                    originalRequest.headers.Authorization = `Bearer ${newAccess}`;
                    return axios(originalRequest);
                } catch (e) {
                    localStorage.removeItem('rakshak_access_token');
                    localStorage.removeItem('rakshak_refresh_token');
                    localStorage.removeItem('rakshak_user_id');
                    return Promise.reject(e);
                }
            }
        }
        return Promise.reject(error);
    }
);

export const getVitalsSummary = async (days = 7) => {
    const response = await api.get(`/summary?days=${days}`);
    return response.data;
};

export const syncVitals = async (user_id, days = 7) => {
    const response = await api.post(`/sync-vitals?user_id=${user_id}&days=${days}`);
    return response.data;
};

export const analyzeHealth = async (user_id, query) => {
    const response = await api.post('/analyze', { user_id, query });
    return response.data;
};

export const diagnoseSymptoms = async (user_id, symptoms) => {
    const response = await api.post('/diagnose', { user_id, symptoms });
    return response.data;
};

export const uploadDocument = async (user_id, file) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post(`/upload-doc?user_id=${user_id}`, formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};

export const getUserDocuments = async (user_id) => {
    const response = await api.get(`/documents?user_id=${user_id}`);
    return response.data;
};

export const getVitalsHistory = async (user_id, days = 7) => {
    const response = await api.get(`/vitals/history?user_id=${user_id}&days=${days}`);
    return response.data;
};

export default api;
