# Terraform Google Cloud Setup

This directory contains Terraform configuration to fully automate Google Cloud setup for the English Tutor bot.

## Prerequisites

1. **Terraform** (>= 1.0)
   ```bash
   # macOS
   brew install terraform
   
   # Or download from: https://www.terraform.io/downloads
   ```

2. **Google Cloud SDK (gcloud)**
   ```bash
   # macOS
   brew install google-cloud-sdk
   
   # Or download from: https://cloud.google.com/sdk/docs/install
   ```

3. **Authenticate with Google Cloud**
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

## Quick Start

Run the automated setup script:

```bash
cd backend
make setup-google-terraform
```

Or manually:

```bash
cd backend/terraform
terraform init
terraform plan
terraform apply
```

## What It Creates

- **Google Cloud Project** (optional, if `create_project = true`)
- **Google Sheets API** (enabled)
- **Google Drive API** (enabled)
- **Service Account** (`english-tutor-content-sync` by default)
- **Service Account Key** (saved to `../credentials.json`)

## Configuration

Edit `terraform.tfvars` or pass variables:

```hcl
project_id = "your-project-id"
project_name = "English Tutor Bot"
create_project = false  # Set to true to create new project
service_account_id = "english-tutor-content-sync"
credentials_output_path = "../credentials.json"
```

## Outputs

After running `terraform apply`, you'll get:

- `service_account_email` - Email to share Google Sheets/Drive files with
- `project_id` - The GCP project ID
- `credentials_base64` - Base64 encoded credentials (sensitive)

## Sharing Resources

After setup, share your resources with the service account email:

1. **Google Sheets:**
   - Open your spreadsheet
   - Click "Share"
   - Add the service account email
   - Give "Viewer" access

2. **Google Drive Files:**
   - Right-click on each file
   - Click "Share"
   - Add the service account email
   - Give "Viewer" access

## Cleanup

To destroy all created resources:

```bash
cd backend/terraform
terraform destroy
```

## Manual Setup

If you prefer to set up manually or customize:

1. Copy `terraform.tfvars.example` to `terraform.tfvars`
2. Edit `terraform.tfvars` with your values
3. Run `terraform init && terraform apply`

## Troubleshooting

### "Project not found"
- Make sure the project ID is correct
- If creating a new project, ensure billing is enabled
- Check you have permissions to create projects

### "API not enabled"
- Terraform should enable APIs automatically
- If it fails, enable manually in Google Cloud Console

### "Permission denied"
- Ensure you're authenticated: `gcloud auth list`
- Check you have necessary IAM permissions
- For new projects, you need "Project Creator" or "Owner" role
