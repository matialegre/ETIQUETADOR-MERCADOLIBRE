export type Segment = {
  id: number;
  name: string;
  description?: string | null;
  criteria?: string | null;
};

export type Customer = {
  id: number;
  email: string;
  full_name: string;
  phone_number?: string | null;
  source?: string | null;
  tags?: string | null;
  preferences?: string | null;
  is_vip: boolean;
  created_at: string;
  segments: Segment[];
};

export type Campaign = {
  id: number;
  name: string;
  channel: string;
  status: string;
  scheduled_at?: string | null;
  budget?: number | null;
  notes?: string | null;
  segment_id?: number | null;
  created_at: string;
};

export type MessageTemplate = {
  id: number;
  title: string;
  channel: string;
  content: string;
  language: string;
  is_approved: boolean;
  created_at: string;
};

export type InteractionLog = {
  id: number;
  customer_id: number;
  channel: string;
  direction: string;
  message: string;
  occurred_at: string;
};

export type DashboardSummary = {
  total_customers: number;
  vip_customers: number;
  active_campaigns: number;
  queued_messages: number;
};

export type IntegrationsStatus = {
  pos: Array<{ provider: string; status: string; last_sync: string }>;
  ecommerce: Array<{ provider: string; status: string; last_sync: string }>;
  reports: Array<{ name: string; status: string; frequency: string }>;
};
