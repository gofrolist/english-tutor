# English Tutor Telegram Bot

A Telegram bot for English learning/tutoring that provides personalized learning experiences. Users complete an initial assessment quiz to determine their English level (A1-C2), then receive text, audio, and video tasks appropriate to their level. Content managers (tutors) can update and review learning content externally via REST API without requiring application redeployment.

## Features

- **Initial Assessment**: Users complete an assessment quiz to determine their English proficiency level (A1-C2)
- **Personalized Task Delivery**: Tasks delivered based on user's assessed level
- **Multimedia Support**: Text, audio, and video content types
- **Content Management**: REST API for content managers to update content without redeployment
- **Progress Tracking**: User progress tracking and performance metrics
- **Level Reassessment**: Support for reassessment when user performance indicates level changes

## Architecture

- **Platform**: Telegram Bot (backend service)
- **Framework**: FastAPI (Python 3.13)
- **Database**: Supabase (PostgreSQL) with SQLAlchemy ORM
- **Deployment**: fly.io (Docker containers, ghcr.io registry)
- **Content Management**: REST API (external, no redeployment required)

## Prerequisites

Before you begin, ensure you have the following installed and configured:

### Required Software

1. **Python 3.13**
   - Check your version: `python --version` or `python3 --version`
   - Download from [python.org](https://www.python.org/downloads/) if needed

2. **uv** (Python package manager)
   - Installation: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Or via pip: `pip install uv`
   - Verify: `uv --version`

3. **Supabase Account** (for database)
   - Sign up at [supabase.com](https://supabase.com)
   - Create a new project
   - Get your connection string from Project Settings → Database

4. **Telegram Bot Token**
   - Create a bot via [@BotFather](https://t.me/BotFather) on Telegram
   - Use `/newbot` command and follow instructions
   - Save your bot token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

5. **Google Cloud Project** (for Google Sheets/Drive integration)
   - Create a project at [Google Cloud Console](https://console.cloud.google.com)
   - Enable Google Sheets API and Google Drive API
   - Create a Service Account and download credentials JSON
   - Share your Google Sheets with the service account email
   - Share media files in Google Drive with the service account email

### Optional but Recommended

- **Git** (for version control)
- **Docker** (for containerization, if deploying)
- **PostgreSQL client** (for direct database access, optional)

## Configuration

### 1. Clone the Repository

```bash
git clone <repository-url>
cd english-tutor
```

### 2. Set Up Environment Variables

Create a `.env` file in the `backend/` directory. The application will automatically load all variables from this file:

Create a `.env` file in the `backend/` directory with the following content:

```bash
# Required: Supabase database connection string
# Option 1: Direct connection (port 5432)
DATABASE_URL=postgresql://postgres:[PASSWORD]@[PROJECT_REF].supabase.co:5432/postgres

# Option 2: Connection pooler (recommended for production, port 6543)
# DATABASE_URL=postgresql://postgres:[PASSWORD]@[PROJECT_REF].supabase.co:6543/postgres?pgbouncer=true

# Required: Telegram bot token
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Optional: API configuration
API_HOST=0.0.0.0
API_PORT=8080
DEBUG=false

# Optional: SQL query logging
SQL_ECHO=false

# Google Sheets/Drive integration (for content management)
GOOGLE_CREDENTIALS_PATH=./credentials.json
GOOGLE_SHEETS_ID=your_spreadsheet_id_here

# Optional: Content sync scheduler
ENABLE_SYNC_SCHEDULER=false
SYNC_INTERVAL_MINUTES=60
```

**Note**: The `.env` file is automatically loaded by the application. You don't need to export these variables manually.

**Getting Your Supabase Connection String:**

1. Go to your Supabase project dashboard
2. Navigate to **Project Settings** → **Database**
3. Under **Connection string**, select **URI**
4. Copy the connection string
5. Replace `[YOUR-PASSWORD]` with your database password
6. Your connection string should look like:
   ```
   postgresql://postgres.xxxxx:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres?pgbouncer=true
   ```

**Getting Your Telegram Bot Token:**

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Start a conversation and use `/newbot`
3. Follow the prompts to name your bot
4. Copy the token provided (keep it secure!)

**Setting Up Google Sheets/Drive Integration:**

**Option 1: Fully Automated Setup with Terraform (Recommended)**

This option uses Terraform to fully automate Google Cloud setup - no manual steps required!

**Prerequisites:**
- Install [Terraform](https://www.terraform.io/downloads)
- Install [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
- Authenticate: `gcloud auth login && gcloud auth application-default login`

**Run the setup:**
```bash
cd backend
make setup-google-terraform
```

This will automatically:
- Create or use existing GCP project
- Enable Google Sheets API and Google Drive API
- Create service account
- Download and save credentials
- **Create a template Google Sheet** with correct structure (optional)
- Update your `.env` file

**After setup, you only need to:**
- If you created a template: Review and fill in your content
- If using existing sheet: Share your Google Sheets with the service account email (shown at the end)
- Share your Google Drive files with the service account email

**Google Sheets Format:**
See `backend/docs/SHEETS_FORMAT.md` for detailed format requirements. The template includes:
- **Tasks sheet**: Columns for level, type, title, content, explanation, difficulty, status, row_id
- **Questions sheet**: Columns for task_row_id, question_text, answer_options, correct_answer, weight, order, row_id

**Option 2: Manual Setup**

1. **Create Google Cloud Project:**
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create a new project or select existing one

2. **Enable APIs:**
   - Navigate to "APIs & Services" → "Library"
   - Enable "Google Sheets API"
   - Enable "Google Drive API"

3. **Create Service Account:**
   - Go to "APIs & Services" → "Credentials"
   - Click "Create Credentials" → "Service Account"
   - Give it a name (e.g., "english-tutor-content-sync")
   - Create and download the JSON key file
   - Save it as `credentials.json` in the `backend/` directory

4. **Share Google Sheets:**
   - Open your Google Sheets spreadsheet
   - Click "Share" and add the service account email (from the JSON file, field `client_email`)
   - Give it "Viewer" access (read-only is sufficient)

5. **Share Google Drive Files:**
   - For each audio/video file in Google Drive:
     - Right-click → "Share"
     - Add the service account email
     - Give it "Viewer" access

6. **Get Spreadsheet ID:**
   - Open your Google Sheets
   - The ID is in the URL: `https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit`
   - Copy the `SPREADSHEET_ID` part

7. **Update `.env` file:**
   ```bash
   GOOGLE_CREDENTIALS_PATH=./credentials.json
   GOOGLE_SHEETS_ID=your_spreadsheet_id_here
   ```

### 3. Install Dependencies

```bash
cd backend
uv sync
```

This will install all required dependencies including:
- FastAPI and Uvicorn
- python-telegram-bot
- SQLAlchemy and Alembic
- psycopg2-binary (PostgreSQL driver)
- pytest and testing tools

### 4. Run Database Migrations

```bash
cd backend

# Run all migrations
uv run alembic upgrade head

# Or run migrations from a specific revision
uv run alembic upgrade <revision>
```

This will create all necessary database tables:
- `users` - User accounts and level information
- `assessments` - Assessment quiz records
- `tasks` - Learning tasks (text, audio, video)
- `questions` - Questions associated with tasks
- `progress` - User progress tracking

### 5. Verify Installation

Run the tests to verify everything is set up correctly:

```bash
cd backend

# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_models_user.py -v
```

## Running the Application

### Development Mode

#### Option 1: Run FastAPI Server (Content Management API)

```bash
cd backend

# Start the FastAPI server
uv run uvicorn src.api.app:app --host 0.0.0.0 --port 8080 --reload

# The API will be available at:
# - API: http://localhost:8080
# - Health check: http://localhost:8080/health
# - API docs: http://localhost:8080/docs
# - OpenAPI schema: http://localhost:8080/openapi.json
```

#### Option 2: Run Telegram Bot

```bash
cd backend

# Start the Telegram bot (polling mode)
# You'll need to create a script to start the bot, or run:
uv run python -c "import asyncio; from src.api.bot import start_bot; asyncio.run(start_bot())"
```

**Note**: For production, you typically run both the FastAPI server and the Telegram bot. The FastAPI server handles content management API requests, while the bot handles Telegram interactions.

### Production Mode

For production deployment on fly.io, see the deployment section below.

## Project Structure

```
backend/
├── src/
│   ├── api/
│   │   ├── app.py                 # FastAPI application
│   │   ├── bot.py                 # Telegram bot application
│   │   ├── bot/
│   │   │   └── handlers/          # Bot command handlers
│   │   ├── content/               # Content management API
│   │   │   ├── tasks.py           # Task CRUD endpoints
│   │   │   └── questions.py       # Question management endpoints
│   │   └── dependencies.py        # FastAPI dependencies
│   ├── models/                    # SQLAlchemy models
│   │   ├── user.py                # User model
│   │   ├── assessment.py          # Assessment model
│   │   ├── task.py                # Task model
│   │   ├── question.py            # Question model
│   │   ├── progress.py            # Progress model
│   │   └── base.py                # Base model class
│   ├── services/                  # Business logic
│   │   ├── assessment.py          # Assessment service
│   │   ├── task_delivery.py       # Task delivery service
│   │   └── task_completion.py     # Task completion service
│   ├── utils/                     # Utility modules
│   │   ├── logger.py              # Logging configuration
│   │   └── exceptions.py          # Custom exceptions
│   └── config.py                  # Configuration management
├── tests/
│   ├── unit/                      # Unit tests
│   ├── integration/               # Integration tests
│   └── contract/                  # Contract tests
├── alembic/                       # Database migrations
│   ├── versions/                  # Migration files
│   └── env.py                     # Alembic environment
├── alembic.ini                    # Alembic configuration
├── pyproject.toml                 # Project dependencies
├── Dockerfile                     # Docker configuration
├── fly.toml                       # Fly.io configuration
└── main.py                        # Application entry point
```

## API Documentation

When the FastAPI server is running, you can access:

- **Interactive API Docs (Swagger)**: http://localhost:8080/docs
- **ReDoc Documentation**: http://localhost:8080/redoc
- **OpenAPI Schema**: http://localhost:8080/openapi.json

### Content Management API Endpoints

**Content Sync (Google Sheets/Drive):**
- `POST /sync` - Trigger manual content synchronization from Google Sheets/Drive

**Task Management (Read-only, content comes from Google Sheets):**
- `GET /tasks` - List tasks (with filtering by level, type, status)
- `GET /tasks/{task_id}` - Get task by ID

**Question Management (Read-only, content comes from Google Sheets):**
- `GET /tasks/{task_id}/questions` - List questions for a task
- `GET /questions/{question_id}` - Get question by ID

**Note**: The REST API endpoints for creating/updating tasks and questions are still available but are primarily for backward compatibility. Content should be managed via Google Sheets and synced using the `/sync` endpoint.

## Telegram Bot Commands

- `/start` - Start conversation and initiate assessment (if needed)
- `/assess` - Start or retake the assessment quiz
- `/task` - Get a new learning task (requires completed assessment)

## Testing

### Run All Tests

```bash
cd backend
uv run pytest
```

### Run Specific Test Categories

```bash
# Unit tests only
uv run pytest tests/unit/ -v

# Integration tests only
uv run pytest tests/integration/ -v

# Contract tests only
uv run pytest tests/contract/ -v
```

### Run Tests with Coverage

```bash
uv run pytest --cov=src --cov-report=html --cov-report=term

# View HTML coverage report
open htmlcov/index.html
```

### Test Requirements

- Minimum 80% code coverage (enforced by pytest)
- All tests must pass before deployment
- Follow TDD (Test-Driven Development) principles

## Database Migrations

### Create a New Migration

```bash
cd backend

# Auto-generate migration from model changes
uv run alembic revision --autogenerate -m "description of changes"

# Manual migration
uv run alembic revision -m "description of changes"
```

### Apply Migrations

```bash
# Apply all pending migrations
uv run alembic upgrade head

# Apply specific migration
uv run alembic upgrade <revision>

# Rollback one migration
uv run alembic downgrade -1

# Rollback to specific revision
uv run alembic downgrade <revision>
```

### Check Migration Status

```bash
# Show current database revision
uv run alembic current

# Show migration history
uv run alembic history
```

## Code Quality

### Linting

```bash
cd backend

# Run ruff linter
uv run ruff check src/

# Auto-fix linting issues
uv run ruff check --fix src/
```

### Type Checking

```bash
cd backend

# Run pyright type checker
uv run pyright src/
```

## Deployment

### Fly.io Deployment

1. **Install Fly CLI**: Follow instructions at [fly.io/docs](https://fly.io/docs/hands-on/install-flyctl/)

2. **Login to Fly.io**:
   ```bash
   fly auth login
   ```

3. **Deploy Application**:
   ```bash
   cd backend
   fly deploy
   ```

4. **Set Environment Variables on Fly.io**:
   ```bash
   fly secrets set DATABASE_URL="your_supabase_connection_string"
   fly secrets set TELEGRAM_BOT_TOKEN="your_bot_token"
   ```

5. **Run Migrations on Fly.io**:
   ```bash
   fly ssh console
   # Inside the console:
   alembic upgrade head
   ```

### Docker Build

```bash
cd backend

# Build Docker image
docker build -t english-tutor:latest .

# Run container locally
docker run -p 8080:8080 \
  -e DATABASE_URL="your_connection_string" \
  -e TELEGRAM_BOT_TOKEN="your_bot_token" \
  english-tutor:latest
```

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ Yes | - | Supabase PostgreSQL connection string |
| `TELEGRAM_BOT_TOKEN` | ✅ Yes | - | Telegram bot token from @BotFather |
| `API_HOST` | No | `0.0.0.0` | FastAPI server host |
| `API_PORT` | No | `8080` | FastAPI server port |
| `DEBUG` | No | `false` | Enable debug mode |
| `SQL_ECHO` | No | `false` | Log SQL queries to console |
| `GOOGLE_CREDENTIALS_PATH` | Yes* | - | Path to Google service account credentials JSON |
| `GOOGLE_SHEETS_ID` | Yes* | - | Google Sheets spreadsheet ID |
| `ENABLE_SYNC_SCHEDULER` | No | `false` | Enable automatic content sync scheduler |
| `SYNC_INTERVAL_MINUTES` | No | `60` | Content sync interval in minutes |

*Required if using Google Sheets/Drive for content management

## Troubleshooting

### Database Connection Issues

- **Check connection string format**: Ensure it matches Supabase connection string format
- **Verify credentials**: Check your Supabase project password
- **Check network access**: Ensure your IP is allowed (Supabase dashboard → Database → Connection pooling)
- **Test connection**: Use `psql` or a PostgreSQL client to test the connection string

### Telegram Bot Not Responding

- **Verify bot token**: Ensure `TELEGRAM_BOT_TOKEN` is set correctly
- **Check bot is running**: Verify the bot process is running
- **Check logs**: Look for error messages in application logs
- **Test with /start**: Try sending `/start` command to your bot

### Migration Issues

- **Check database state**: Run `alembic current` to see current revision
- **Review migration files**: Check migration files in `alembic/versions/`
- **Manual fix**: You may need to manually fix database schema if migrations fail
- **Backup first**: Always backup your database before running migrations

### Import Errors

- **Check dependencies**: Run `uv sync` to ensure all dependencies are installed
- **Check Python version**: Ensure Python 3.13 is being used
- **Virtual environment**: Ensure you're using `uv run` or the correct virtual environment

## Development Workflow

1. **Create feature branch**: `git checkout -b feature/my-feature`
2. **Write tests first** (TDD): Write failing tests
3. **Implement feature**: Write code to make tests pass
4. **Run tests**: `uv run pytest`
5. **Check code quality**: `uv run ruff check src/ && uv run pyright src/`
6. **Create migration** (if needed): `uv run alembic revision --autogenerate -m "description"`
7. **Commit changes**: `git commit -m "description"`
8. **Push and create PR**: Push branch and create pull request

## Support and Documentation

- **Full Specification**: See `specs/001-english-tutor-bot/spec.md`
- **Implementation Plan**: See `specs/001-english-tutor-bot/plan.md`
- **Quickstart Guide**: See `specs/001-english-tutor-bot/quickstart.md`
- **Data Model**: See `specs/001-english-tutor-bot/data-model.md`
- **API Contract**: See `specs/001-english-tutor-bot/contracts/openapi.yaml`

## License

MIT

## Contributing

1. Follow TDD (Test-Driven Development) principles
2. Ensure all tests pass before submitting
3. Maintain minimum 80% code coverage
4. Follow code style (ruff and pyright checks must pass)
5. Update documentation as needed
