#!/usr/bin/env python3
"""Automated Google Cloud setup using Terraform.

This script uses Terraform to fully automate Google Cloud setup:
- Creates project (optional)
- Enables APIs
- Creates service account
- Downloads credentials
- Updates .env file
"""

import json
import subprocess
import sys
from pathlib import Path


def run_command(
    cmd: list[str], check: bool = True, cwd: Path | None = None
) -> subprocess.CompletedProcess:
    """Run a shell command."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=check,
        cwd=str(cwd) if cwd else None,
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr and result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
    return result


def check_terraform_installed() -> bool:
    """Check if Terraform is installed."""
    try:
        run_command(["terraform", "version"], check=False)
        return True
    except FileNotFoundError:
        return False


def check_gcloud_installed() -> bool:
    """Check if gcloud CLI is installed."""
    try:
        run_command(["gcloud", "version"], check=False)
        return True
    except FileNotFoundError:
        return False


def check_gcloud_auth() -> bool:
    """Check if gcloud is authenticated."""
    try:
        result = run_command(
            ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
            check=False,
        )
        return bool(result.stdout.strip())
    except Exception:
        return False


def check_application_default_credentials() -> bool:
    """Check if application default credentials are set up."""
    try:
        # Check if ADC file exists
        adc_path = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
        if adc_path.exists():
            return True

        # Try to verify with gcloud
        result = run_command(
            ["gcloud", "auth", "application-default", "print-access-token"],
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_billing_accounts() -> list[dict]:
    """Get list of billing accounts."""
    try:
        result = run_command(
            ["gcloud", "billing", "accounts", "list", "--format=json"], check=False
        )
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
        return []
    except Exception:
        return []


def main() -> None:
    """Main setup function."""
    print("=" * 60)
    print("Google Cloud Setup with Terraform")
    print("=" * 60)

    # Get paths
    script_dir = Path(__file__).parent
    backend_dir = script_dir.parent
    terraform_dir = backend_dir / "terraform"
    credentials_path = backend_dir / "credentials.json"

    # Check prerequisites
    print("\nChecking prerequisites...")
    if not check_terraform_installed():
        print("\nERROR: Terraform is not installed.")
        print("Install from: https://www.terraform.io/downloads")
        sys.exit(1)
    print("✓ Terraform installed")

    if not check_gcloud_installed():
        print("\nERROR: Google Cloud SDK (gcloud) is not installed.")
        print("Install from: https://cloud.google.com/sdk/docs/install")
        sys.exit(1)
    print("✓ Google Cloud SDK installed")

    if not check_gcloud_auth():
        print("\nERROR: Not authenticated with Google Cloud.")
        print("Run: gcloud auth login")
        sys.exit(1)
    print("✓ Authenticated with Google Cloud")

    if not check_application_default_credentials():
        print("\nWARNING: Application default credentials not set up.")
        print("Terraform requires application default credentials.")
        print("\nSetting up application default credentials...")
        result = run_command(["gcloud", "auth", "application-default", "login"], check=False)
        if result.returncode != 0:
            print("\nERROR: Failed to set up application default credentials.")
            print("Please run manually: gcloud auth application-default login")
            sys.exit(1)
        print("✓ Application default credentials configured")
    else:
        print("✓ Application default credentials configured")

    # Check if we need to re-authenticate with Sheets/Drive scopes for template creation
    print(
        "\nNOTE: To create template spreadsheets, you may need to re-authenticate with Sheets/Drive scopes:"
    )
    print(
        "  gcloud auth application-default login --scopes=https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/drive,https://www.googleapis.com/auth/cloud-platform"
    )

    # Set quota project if we have a project ID (after Terraform creates it)
    # This will be done after Terraform apply, but we can check here too

    # Get project information
    print("\n" + "=" * 60)
    print("Project Configuration")
    print("=" * 60)

    use_existing = input("\nUse existing GCP project? (y/n): ").strip().lower() == "y"

    if use_existing:
        # List existing projects
        print("\nFetching your projects...")
        result = run_command(["gcloud", "projects", "list", "--format=json"], check=False)
        if result.returncode == 0 and result.stdout:
            projects = json.loads(result.stdout)
            if projects:
                print("\nAvailable projects:")
                for i, project in enumerate(projects, 1):
                    print(f"  {i}. {project['projectId']} - {project.get('name', 'N/A')}")
                choice = input("\nEnter project number or project ID: ").strip()
                try:
                    idx = int(choice) - 1
                    project_id = projects[idx]["projectId"]
                except (ValueError, IndexError):
                    project_id = choice
            else:
                project_id = input("Enter project ID: ").strip()
        else:
            project_id = input("Enter project ID: ").strip()

        project_name = input("Enter project name (optional): ").strip() or project_id
        create_project = False
        billing_account_id = ""
    else:
        project_id = input("Enter new project ID (must be globally unique): ").strip()
        project_name = input("Enter project name: ").strip() or "English Tutor Bot"

        # Get billing account
        billing_accounts = get_billing_accounts()
        if billing_accounts:
            print("\nAvailable billing accounts:")
            for i, account in enumerate(billing_accounts, 1):
                print(f"  {i}. {account['displayName']} ({account['name']})")
            choice = input("\nEnter billing account number or ID: ").strip()
            try:
                idx = int(choice) - 1
                billing_account_id = billing_accounts[idx]["name"].split("/")[-1]
            except (ValueError, IndexError):
                billing_account_id = choice
        else:
            billing_account_id = input("Enter billing account ID: ").strip()

        create_project = True

    service_account_id = (
        input("Enter service account ID (default: english-tutor-content-sync): ").strip()
        or "english-tutor-content-sync"
    )

    # Create terraform directory if it doesn't exist
    terraform_dir.mkdir(exist_ok=True)

    # Create terraform.tfvars
    tfvars_content = f"""project_id = "{project_id}"
project_name = "{project_name}"
create_project = {str(create_project).lower()}
service_account_id = "{service_account_id}"
credentials_output_path = "../credentials.json"
"""
    if create_project:
        tfvars_content += f'billing_account_id = "{billing_account_id}"\n'

    tfvars_path = terraform_dir / "terraform.tfvars"
    with open(tfvars_path, "w") as f:
        f.write(tfvars_content)

    print(f"\n✓ Created {tfvars_path}")

    # Initialize Terraform
    print("\n" + "=" * 60)
    print("Initializing Terraform")
    print("=" * 60)
    run_command(["terraform", "init"], cwd=terraform_dir)

    # Plan Terraform changes
    print("\n" + "=" * 60)
    print("Planning Terraform Changes")
    print("=" * 60)
    result = run_command(["terraform", "plan"], cwd=terraform_dir, check=False)
    if result.returncode != 0:
        print("\nERROR: Terraform plan failed.")
        sys.exit(1)

    # Check if there are any changes
    has_changes = (
        "No changes" not in result.stdout
        and "0 to add, 0 to change, 0 to destroy" not in result.stdout
    )

    # Apply Terraform changes (only if there are changes)
    if has_changes:
        print("\n" + "=" * 60)
        print("Applying Terraform Changes")
        print("=" * 60)
        confirm = input("\nApply these changes? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("Skipping Terraform apply. Continuing with setup...")
        else:
            run_command(["terraform", "apply", "-auto-approve"], cwd=terraform_dir)
    else:
        print("\n✓ No infrastructure changes needed (already up to date)")

    # Get outputs
    print("\n" + "=" * 60)
    print("Getting Terraform Outputs")
    print("=" * 60)
    result = run_command(["terraform", "output", "-json"], cwd=terraform_dir)
    outputs = json.loads(result.stdout)

    project_id = outputs["project_id"]["value"]
    service_account_email = outputs["service_account_email"]["value"]

    # Set quota project for application-default credentials
    print("\nSetting quota project for application-default credentials...")
    result = run_command(
        ["gcloud", "auth", "application-default", "set-quota-project", project_id],
        check=False,
    )
    if result.returncode == 0:
        print(f"✓ Set quota project to: {project_id}")
    else:
        print(f"WARNING: Could not set quota project: {result.stderr}")
        print("You may see quota errors. Run manually:")
        print(f"  gcloud auth application-default set-quota-project {project_id}")

    # Credentials should already be saved by Terraform local_file resource
    if credentials_path.exists():
        print(f"✓ Credentials saved to {credentials_path}")
    else:
        print(f"WARNING: Credentials file not found at {credentials_path}")
        print("Terraform should have created it automatically.")

    # Update .env file
    print("\n" + "=" * 60)
    print("Updating .env File")
    print("=" * 60)

    env_path = backend_dir / ".env"
    env_vars = {}

    # Read existing .env
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()

    # Update Google variables
    env_vars["GOOGLE_CREDENTIALS_PATH"] = "./credentials.json"

    # Offer to create template spreadsheet
    print("\n" + "=" * 60)
    print("Google Sheets Template")
    print("=" * 60)
    create_template = (
        input("\nCreate a template Google Sheet with correct structure? (y/n): ").strip().lower()
        == "y"
    )

    spreadsheet_id = ""
    if create_template:
        print("\nCreating template spreadsheet...")
        try:
            # Import the template creation function
            script_dir = Path(__file__).parent
            template_script = script_dir / "create_sheets_template.py"

            result = run_command(
                [
                    "uv",
                    "run",
                    "python",
                    str(template_script),
                    str(credentials_path),
                    service_account_email,
                ],
                check=False,
            )

            if result.returncode == 0:
                # Extract spreadsheet ID from output
                for line in result.stdout.split("\n"):
                    if "Spreadsheet ID:" in line:
                        spreadsheet_id = line.split("Spreadsheet ID:")[-1].strip()
                        break
                    elif "spreadsheets/d/" in line:
                        # Extract from URL
                        parts = line.split("spreadsheets/d/")
                        if len(parts) > 1:
                            spreadsheet_id = parts[1].split("/")[0].strip()
                            break

                if spreadsheet_id:
                    print(f"✓ Template spreadsheet created: {spreadsheet_id}")
                    env_vars["GOOGLE_SHEETS_ID"] = spreadsheet_id
                else:
                    print("WARNING: Could not extract spreadsheet ID from output")
                    spreadsheet_id = input("\nEnter the Spreadsheet ID manually: ").strip()
                    if spreadsheet_id:
                        env_vars["GOOGLE_SHEETS_ID"] = spreadsheet_id
            else:
                print("WARNING: Failed to create template spreadsheet")
                print("You can create it manually later or enter an existing spreadsheet ID")
                spreadsheet_id = input(
                    "\nEnter your Google Sheets Spreadsheet ID (or press Enter to skip): "
                ).strip()
                if spreadsheet_id:
                    env_vars["GOOGLE_SHEETS_ID"] = spreadsheet_id
        except Exception as e:
            print(f"WARNING: Error creating template: {e}")
            spreadsheet_id = input(
                "\nEnter your Google Sheets Spreadsheet ID (or press Enter to skip): "
            ).strip()
            if spreadsheet_id:
                env_vars["GOOGLE_SHEETS_ID"] = spreadsheet_id
    else:
        spreadsheet_id = input(
            "\nEnter your Google Sheets Spreadsheet ID (or press Enter to skip): "
        ).strip()
        if spreadsheet_id:
            env_vars["GOOGLE_SHEETS_ID"] = spreadsheet_id

    # Write .env
    with open(env_path, "w") as f:
        f.write("# Google Sheets/Drive integration\n")
        f.write(f"GOOGLE_CREDENTIALS_PATH={env_vars['GOOGLE_CREDENTIALS_PATH']}\n")
        if spreadsheet_id:
            f.write(f"GOOGLE_SHEETS_ID={env_vars['GOOGLE_SHEETS_ID']}\n")
        f.write("\n")

        # Write other variables
        for key, value in env_vars.items():
            if key not in ["GOOGLE_CREDENTIALS_PATH", "GOOGLE_SHEETS_ID"]:
                f.write(f"{key}={value}\n")

    print(f"✓ Updated {env_path}")

    # Final instructions
    print("\n" + "=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    print(f"""
✓ Google Cloud project configured: {project_id}
✓ APIs enabled: Google Sheets API, Google Drive API
✓ Service account created: {service_account_email}
✓ Credentials saved: {credentials_path}
✓ Environment variables updated: {env_path}

Next steps:
1. Share your Google Sheets with this email: {service_account_email}
   - Open your Google Sheets
   - Click "Share"
   - Add: {service_account_email}
   - Give "Viewer" access

2. Share your Google Drive files with this email: {service_account_email}
   - For each audio/video file:
     - Right-click → "Share"
     - Add: {service_account_email}
     - Give "Viewer" access

3. Test the integration:
   cd {backend_dir}
   make run
   curl -X POST http://localhost:8080/sync

Terraform state is saved in: {terraform_dir}/terraform.tfstate
To destroy resources: cd {terraform_dir} && terraform destroy
""")


if __name__ == "__main__":
    main()
