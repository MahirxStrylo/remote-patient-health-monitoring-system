import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  LoginRequest, TokenResponse, DoctorUser,
  Patient, PatientCreate, PatientUpdate,
  Device, DeviceCreate, DeviceKeyRotateResponse, DeviceKeyRevokeResponse,
  ECGSession, ECGRecording, ECGSamplesResponse,
  VitalReading, DashboardStats, AppSettings,
  PaginatedResponse, DoctorNote,
  Prescription, PrescriptionCreate
} from '../types';

/**
 * Resolve the API base URL.
 * Supports:
 * - Full URLs configured via VITE_API_BASE_URL (e.g. https://remote-health-backend-4np8.onrender.com or with /api/v1)
 * - Automatic trailing slash removal
 * - Guarantees /api/v1 suffix is present without duplication
 * - Fallback to /api/v1 for local dev (proxies to http://localhost:8000 via Vite dev server)
 */
export const getBaseUrl = (): string => {
  const envUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
  if (!envUrl) {
    return '/api/v1';
  }
  const clean = envUrl.replace(/\/+$/, '');
  return clean.endsWith('/api/v1') ? clean : `${clean}/api/v1`;
};

export const BASE_URL = getBaseUrl();

class ApiService {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: BASE_URL,
      timeout: 30000,
    });

    // Attach token to every request
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('access_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    // Handle 401 globally
    this.client.interceptors.response.use(
      (res) => res,
      (error: AxiosError) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('user');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  // Auth
  async login(data: LoginRequest): Promise<TokenResponse> {
    const form = new URLSearchParams();
    form.append('username', data.username);
    form.append('password', data.password);
    const res = await this.client.post<TokenResponse>('/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
    return res.data;
  }

  async getMe(): Promise<DoctorUser> {
    const res = await this.client.get<DoctorUser>('/auth/me');
    return res.data;
  }

  // Dashboard
  async getDashboardStats(): Promise<DashboardStats> {
    const res = await this.client.get<DashboardStats>('/dashboard/stats');
    return res.data;
  }

  // Patients
  async getPatients(params?: { search?: string; archived?: boolean; page?: number; size?: number }): Promise<PaginatedResponse<Patient>> {
    const res = await this.client.get<PaginatedResponse<Patient>>('/patients', { params });
    return res.data;
  }

  async getPatient(patientId: string): Promise<Patient> {
    const res = await this.client.get<Patient>(`/patients/${patientId}`);
    return res.data;
  }

  async createPatient(data: PatientCreate): Promise<Patient> {
    const res = await this.client.post<Patient>('/patients', data);
    return res.data;
  }

  async updatePatient(patientId: string, data: PatientUpdate): Promise<Patient> {
    const res = await this.client.patch<Patient>(`/patients/${patientId}`, data);
    return res.data;
  }

  async getPatientVitals(patientId: string, limit?: number): Promise<VitalReading[]> {
    const res = await this.client.get<VitalReading[]>(`/patients/${patientId}/readings`, { params: { limit } });
    return res.data;
  }

  async getPatientECGRecordings(patientId: string): Promise<ECGRecording[]> {
    const res = await this.client.get<ECGRecording[]>(`/patients/${patientId}/ecg-recordings`);
    return res.data;
  }

  async getPatientNotes(patientId: string): Promise<DoctorNote[]> {
    const res = await this.client.get<DoctorNote[]>(`/patients/${patientId}/notes`);
    return res.data;
  }

  async addPatientNote(patientId: string, content: string): Promise<DoctorNote> {
    const res = await this.client.post<DoctorNote>(`/patients/${patientId}/notes`, { content });
    return res.data;
  }

  // Devices
  async getDevices(): Promise<Device[]> {
    const res = await this.client.get<Device[]>('/devices');
    return res.data;
  }

  async createDevice(data: DeviceCreate): Promise<Device> {
    const res = await this.client.post<Device>('/devices', data);
    return res.data;
  }

  async updateDevice(deviceId: string, data: Partial<DeviceCreate>): Promise<Device> {
    const res = await this.client.patch<Device>(`/devices/${deviceId}`, data);
    return res.data;
  }

  async rotateDeviceKey(deviceId: string): Promise<DeviceKeyRotateResponse> {
    const res = await this.client.post<DeviceKeyRotateResponse>(`/devices/${deviceId}/rotate-key`);
    return res.data;
  }

  async revokeDeviceKey(deviceId: string): Promise<DeviceKeyRevokeResponse> {
    const res = await this.client.post<DeviceKeyRevokeResponse>(`/devices/${deviceId}/revoke-key`);
    return res.data;
  }

  // ECG Sessions & Waveforms
  async getECGSessions(params?: { patient_id?: number; status?: string; page?: number; size?: number }): Promise<PaginatedResponse<ECGSession>> {
    const res = await this.client.get<PaginatedResponse<ECGSession>>('/ecg/sessions', { params });
    return res.data;
  }

  async getECGRecording(recordingId: string): Promise<ECGRecording> {
    const res = await this.client.get<ECGRecording>(`/ecg-recordings/${recordingId}`);
    return res.data;
  }

  async getECGSamples(recordingId: string, filterMode: 'none' | 'bandpass' = 'none'): Promise<ECGSamplesResponse> {
    const res = await this.client.get<ECGSamplesResponse>(`/ecg-recordings/${recordingId}/samples`, {
      params: { filter: filterMode }
    });
    return res.data;
  }

  async completeECGSession(sessionId: string): Promise<ECGSession> {
    const res = await this.client.post<ECGSession>(`/ecg/sessions/${sessionId}/complete`);
    return res.data;
  }

  getECGExportCSVUrl(recordingId: string): string {
    return `${BASE_URL}/ecg-recordings/${recordingId}/export.csv`;
  }

  getECGExportPNGUrl(recordingId: string): string {
    return `${BASE_URL}/ecg-recordings/${recordingId}/plot.png`;
  }

  // Prescriptions & Messaging
  async getPrescriptions(params?: {
    patient_id?: number;
    device_id?: number;
    status?: string;
    page?: number;
    size?: number;
  }): Promise<PaginatedResponse<Prescription>> {
    const res = await this.client.get<PaginatedResponse<Prescription>>('/prescriptions', { params });
    return res.data;
  }

  async getPatientPrescriptions(patientId: string): Promise<Prescription[]> {
    const res = await this.client.get<Prescription[]>(`/patients/${patientId}/prescriptions`);
    return res.data;
  }

  async createPrescription(patientId: string, data: PrescriptionCreate): Promise<Prescription> {
    const res = await this.client.post<Prescription>(`/patients/${patientId}/prescriptions`, data);
    return res.data;
  }

  // Settings
  async getSettings(): Promise<AppSettings> {
    const res = await this.client.get<AppSettings>('/settings');
    return res.data;
  }

  // Health & Diagnostics
  async getHealth(): Promise<{ status: string; version: string; database: string }> {
    const res = await this.client.get('/health');
    return res.data;
  }

  getBaseUrl(): string {
    return BASE_URL;
  }
}

export const api = new ApiService();
export default api;
