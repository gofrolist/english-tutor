variable "project_id" {
  description = "The GCP project ID (must be globally unique)"
  type        = string
}

variable "project_name" {
  description = "The GCP project name"
  type        = string
  default     = "English Tutor Bot"
}

variable "create_project" {
  description = "Whether to create a new project (requires billing account)"
  type        = bool
  default     = false
}

variable "billing_account_id" {
  description = "Billing account ID (required if create_project = true)"
  type        = string
  default     = ""
}

variable "org_id" {
  description = "Organization ID (optional, for organization-level projects)"
  type        = string
  default     = ""
}

variable "folder_id" {
  description = "Folder ID (optional, for folder-level projects)"
  type        = string
  default     = ""
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "service_account_id" {
  description = "Service account ID (short name, not email)"
  type        = string
  default     = "english-tutor-content-sync"
}

variable "credentials_output_path" {
  description = "Path where to save the service account key JSON file"
  type        = string
  default     = "../credentials.json"
}
