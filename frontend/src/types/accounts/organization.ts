export interface Organization {
  id: string;
  name: string;
  domain: string;
  logo: string | null;
  created_at: string;
}

export interface OrganizationFormData {
  name: string;
  domain: string;
  logo?: File | null;
}