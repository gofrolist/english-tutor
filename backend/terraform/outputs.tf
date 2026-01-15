output "project_id" {
  description = "The GCP project ID"
  value       = var.create_project ? google_project.english_tutor[0].project_id : var.project_id
}

output "service_account_email" {
  description = "Service account email (use this to share Google Sheets/Drive files)"
  value       = google_service_account.content_sync.email
}

output "service_account_key_path" {
  description = "Path to the downloaded service account key"
  value       = var.credentials_output_path
}

output "credentials_base64" {
  description = "Base64 encoded service account key (for reference)"
  value       = google_service_account_key.content_sync_key.private_key
  sensitive   = true
}
