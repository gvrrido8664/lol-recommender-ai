import axios from 'axios';

// Instancia global de Axios apuntando al backend local de FastAPI
export const apiClient = axios.create({
  baseURL: 'http://localhost:8000/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const simularEnfrentamiento = async (aliado: string, enemigo: string, rol: string) => {
  const response = await apiClient.post('/simulador', { aliado, enemigo, rol });
  return response.data;
};
