terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
  }
}

# Configure the Google Cloud Provider
provider "google" {
  project = var.project_id
  region  = var.region
}

# Create a new project (optional - set create_project = true)
resource "google_project" "english_tutor" {
  count           = var.create_project ? 1 : 0
  name            = var.project_name
  project_id      = var.project_id
  billing_account = var.billing_account_id
  org_id          = var.org_id
  folder_id       = var.folder_id
}

# Enable required APIs
resource "google_project_service" "sheets_api" {
  project = var.create_project ? google_project.english_tutor[0].project_id : var.project_id
  service = "sheets.googleapis.com"

  disable_dependent_services = false
  disable_on_destroy         = false
}

resource "google_project_service" "drive_api" {
  project = var.create_project ? google_project.english_tutor[0].project_id : var.project_id
  service = "drive.googleapis.com"

  disable_dependent_services = false
  disable_on_destroy         = false
}

# Create service account
resource "google_service_account" "content_sync" {
  project      = var.create_project ? google_project.english_tutor[0].project_id : var.project_id
  account_id   = var.service_account_id
  display_name = "English Tutor Content Sync Service Account"
  description  = "Service account for syncing content from Google Sheets and Drive"
}

# Create and download service account key
resource "google_service_account_key" "content_sync_key" {
  service_account_id = google_service_account.content_sync.name
}

# Save credentials to file
resource "local_file" "credentials_json" {
  content         = base64decode(google_service_account_key.content_sync_key.private_key)
  filename        = var.credentials_output_path
  file_permission = "0600"
}

# Grant service account necessary permissions (if needed)
# Note: For Sheets/Drive, sharing is done at the resource level, not IAM
# But we can grant basic viewer access if needed
