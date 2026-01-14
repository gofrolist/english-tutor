# Implementation Plan: English Tutor Telegram Bot

**Branch**: `001-english-tutor-bot` | **Date**: 2026-01-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-english-tutor-bot/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Build a Telegram bot for English learning/tutoring that provides personalized learning experiences. Users complete an initial assessment quiz to determine their English level (A1-C2), then receive text, audio, and video tasks appropriate to their level. Content managers (tutors) can update and review learning content externally via REST API without requiring application redeployment. The system tracks user progress and provides feedback on task completion.

Technical approach: Python 3.13 backend with FastAPI and python-telegram-bot library, Supabase (PostgreSQL) database with SQLAlchemy ORM, REST API for external content management, deployed on fly.io with Docker containers stored in ghcr.io registry.

## Technical Context

**Language/Version**: Python 3.13  
**Primary Dependencies**: FastAPI, python-telegram-bot (v20+), SQLAlchemy ORM, Supabase (PostgreSQL), Alembic (migrations)  
**Storage**: Supabase (PostgreSQL) database for user data, assessments, tasks, questions, content metadata, and progress tracking  
**Testing**: pytest with coverage requirements (minimum 80%)  
**Target Platform**: Linux server (fly.io)  
**Project Type**: Backend (telegram bot)  
**Performance Goals**: Support 1000 concurrent users without performance degradation; content updates available within 5 minutes; task delivery under 2 seconds p95  
**Constraints**: External content management without redeployment; Docker-based containerization; OpenAPI specification required; type safety (pyright checks mandatory)  
**Scale/Scope**: 1000+ concurrent users; multiple English levels (A1-C2); three content types (text/audio/video); hierarchical content organization

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Test-First (NON-NEGOTIABLE) ✓
**Gate**: TDD mandatory for all features. Tests written and approved before implementation.

**Status**: PASS - All features will follow TDD workflow. Test coverage minimum 80% enforced.

### II. Content Organization and Management ✓
**Gate**: Content organized hierarchically by level (A1-C2) and type (text/audio/video). Questions linked to tasks. Metadata includes level, type, difficulty, question-answer mappings.

**Status**: PASS - Data model will enforce hierarchical organization. Content management interface supports level/type organization.

### III. User Progression and Leveling ✓
**Gate**: Initial assessment quiz required. Tasks delivered based on assessed level. Progress tracking required. Level reassessment available.

**Status**: PASS - User Story 1 covers assessment, User Story 2 covers level-based task delivery. Progress tracking in data model.

### IV. Multimedia Support ✓
**Gate**: Support text, audio, and video content types with consistent question-answer interfaces.

**Status**: PASS - All three content types specified in requirements. Data model supports multiple content types.

### V. Simplicity and Maintainability ✓
**Gate**: Start simple, YAGNI principles, clear documentation, justify complexity.

**Status**: PASS - Plan follows YAGNI. Starting with essential features. Complexity tracking section available if needed.

### VI. Observability and Logging ✓
**Gate**: Structured logging for all interactions, content delivery, quiz submissions, errors. Include user IDs, content IDs, timestamps, context.

**Status**: PASS - Logging requirements will be implemented for all user interactions and system events.

**Overall Gate Status**: ✅ PASS - All constitution principles satisfied. Ready to proceed to Phase 0 research.

## Project Structure

### Documentation (this feature)

```text
specs/001-english-tutor-bot/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/          # Data models (User, Assessment, Task, Question, Content, Progress)
│   ├── services/        # Business logic (assessment, task delivery, content management)
│   ├── api/             # FastAPI routes and Telegram bot handlers
│   └── config.py        # Configuration management (existing)
└── tests/
    ├── contract/        # Contract tests for API endpoints
    ├── integration/     # Integration tests for user journeys
    └── unit/            # Unit tests for models and services
```

**Structure Decision**: Backend-only project structure. Telegram bot is a backend service using FastAPI. All source code organized under `backend/src/` with clear separation of models, services, and API layers. Tests organized by type (contract/integration/unit) following testing pyramid principles.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations detected. All constitution principles satisfied.
