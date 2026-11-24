// Auth
export interface LoginRequest {
  username: string;
  password: string;
}
export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}
export interface DoctorUser {
  id: number;
  username: string;
  email: string | null;
  full_name: string | null;
  is_active: boolean;
  is_admin: boolean;
  last_login: string | null;
  created_at: string;
}

// Patient
export interface Patient {
  id: number;
  patient_id: string;
  full_name: string;
  age: number | null;
  notes: string | null;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
  device?: Device;
}
export interface PatientCreate {
  patient_id: string;
  full_name: string;
  age?: number;
  notes?: string;
}
export interface PatientUpdate {
  full_name?: string;
  age?: number;
  notes?: string;
  is_archived?: boolean;
}

// Device
export interface Device {
  id: number;
  device_id: string;
  description: string | null;
  patient_id: number | null;
  is_active: boolean;
  api_key_prefix?: string | null;
  api_key_revoked_at?: string | null;
  last_seen: string | null;
  last_batch_id: string | null;
  firmware_version: string | null;
  created_at: string;
  plain_api_key?: string;
}
export interface DeviceCreate {
  device_id: string;
  description?: string;
  patient_id?: number;
}
export interface DeviceKeyRotateResponse {
  device_id: string;
  api_key_prefix: string;
  plain_api_key: string;
  rotated_at: string;
}
export interface DeviceKeyRevokeResponse {
  device_id: string;
  is_revoked: boolean;
  revoked_at: string;
  message: string;
}

// ECG
export interface ECGSession {
  id: number;
  session_id: string;
  recording_id?: string;
  patient_id: number;
  patient_code?: string;
  patient_name?: string;
  device_id: number;
  device_code?: string;
  started_at: string;
  recorded_at?: string;
  ended_at: string | null;
  sampling_rate_hz: number;
  unit: string;
  ecg_unit?: string;
  status: "Recording" | "Completed" | "Interrupted" | "Incomplete";
  total_samples: number;
  sample_count?: number;
  total_batches: number;
  expected_batches: number | null;
  is_simulated: boolean;
  lead_off?: boolean;
  lead_off_count: number;
  signal_quality: string | null;
  ai_analysis_status: string;
  ai_classification?: string | null;
  ai_confidence?: number | null;
  notes: string | null;
  created_at: string;
}

// Backwards-compatible alias
export type ECGRecording = ECGSession;

export interface ECGSamplesResponse {
  recording_id: string;
  session_id?: string;
  sampling_rate_hz: number;
  ecg_unit: string;
  samples: (number | null)[];
  filtered_samples?: (number | null)[];
  time_axis?: number[];
  sample_count: number;
  duration_seconds: number;
  recorded_at: string;
  is_simulated: boolean;
  missing_sequences?: number[];
  has_gaps?: boolean;
}

// Vitals
export interface VitalReading {
  id: number;
  patient_id: number;
  device_id: number;
  batch_id: string;
  recorded_at: string;
  heart_rate_bpm: number | null;
  spo2_percent: number | null;
  temperature_c: number | null;
  is_simulated: boolean;
  created_at: string;
}

// Dashboard
export interface DashboardStats {
  total_patients: number;
  total_devices: number;
  active_devices: number;
  latest_uploads_count: number;
  recent_ecg_count: number;
  recent_events: RecentEvent[];
  ingestion_errors: number;
}
export interface RecentEvent {
  event_type: string;
  actor_type: string;
  actor_id: string | null;
  detail: string | null;
  created_at: string;
}

// Settings
export interface AppSettings {
  app_version: string;
  stale_reading_threshold_minutes: number;
  max_ecg_samples_per_batch: number;
  database_url: string;
  total_records: number;
  server_time: string;
}

// API response wrappers
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface DoctorNote {
  id: number;
  patient_id: number;
  doctor_id: number;
  content: string;
  created_at: string;
}

// Prescriptions & Doctor-to-Patient Directives
export interface Prescription {
  id: number;
  patient_id: number;
  patient_code?: string | null;
  patient_name?: string | null;
  device_id: number | null;
  device_code?: string | null;
  doctor_id?: number | null;
  doctor_name?: string | null;
  assessment: string;
  medication: string;
  dosage: string;
  frequency: string;
  duration: string;
  instructions?: string | null;
  follow_up_date?: string | null;
  status: 'Pending' | 'Delivered' | 'Acknowledged';
  created_at: string;
  delivered_at?: string | null;
  acknowledged_at?: string | null;
}

export interface PrescriptionCreate {
  patient_id?: number;
  device_id?: number | null;
  assessment: string;
  medication: string;
  dosage: string;
  frequency: string;
  duration: string;
  instructions?: string;
  follow_up_date?: string;
}
