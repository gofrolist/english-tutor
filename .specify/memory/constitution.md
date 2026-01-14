<!--
Sync Impact Report:
Version: 1.0.1 (technology stack clarifications)
Ratified: 2026-01-10
Last Amended: 2026-01-10

Changes:
- Added OpenAPI specification requirement
- Updated deployment to specify fly.io platform
- Added Docker image registry (ghcr.io) specification
- Templates checked: ✅ plan-template.md, ✅ spec-template.md, ✅ tasks-template.md

Templates Status:
✅ plan-template.md - Constitution Check section compatible
✅ spec-template.md - No changes needed
✅ tasks-template.md - No changes needed
-->

# English Tutor Constitution

## Core Principles

### I. Test-First (NON-NEGOTIABLE)

Every feature MUST be developed using Test-Driven Development (TDD). Tests MUST be written and approved before implementation begins. The Red-Green-Refactor cycle is strictly enforced. Tests MUST cover core functionality including quiz logic, content delivery, and user progression tracking. Rationale: Educational software requires high reliability to ensure accurate level assessment and appropriate task delivery.

### II. Content Organization and Management

Educational content MUST be organized hierarchically by English level (e.g., A1, A2, B1, B2, C1, C2) and content type (text, audio, video). Questions MUST be explicitly linked to their parent tasks with clear relationships. Content metadata MUST include level, type, difficulty indicators, and question-answer mappings. Rationale: Structured content organization ensures maintainable content database and enables accurate level-based task delivery.

### III. User Progression and Leveling

Users MUST complete an initial assessment quiz to determine their English level. Tasks MUST be delivered based on the user's assessed level. The system MUST track user progress and performance metrics. Level reassessment MUST be available when user performance indicates level changes. Rationale: Personalized learning requires accurate level assessment and adaptive content delivery.

### IV. Multimedia Support

The system MUST support three content types: text (explanations with questions), audio (audio messages with comprehension questions), and video (inline or via links with associated questions). Each content type MUST have consistent question-answer interfaces. Rationale: Diverse content types enhance learning effectiveness and engagement.

### V. Simplicity and Maintainability

Start simple and avoid premature optimization. Follow YAGNI (You Aren't Gonna Need It) principles. Code MUST be clear, readable, and well-documented. Complexity MUST be justified when introduced. Rationale: Maintainable codebase is essential for long-term content management and feature additions.

### VI. Observability and Logging

Structured logging MUST be implemented for all user interactions, content delivery events, quiz submissions, and system errors. Logs MUST include user identifiers, content identifiers, timestamps, and relevant context. Performance metrics MUST be tracked for content delivery and quiz processing. Rationale: Observability enables debugging, content performance analysis, and user learning pattern insights.

## Technology Stack

**Language/Version**: Python 3.13  
**Framework**: FastAPI for bot backend (Telegram Bot API integration)  
**API Specification**: OpenAPI (FastAPI auto-generates OpenAPI schema)  
**Testing**: pytest with coverage requirements (minimum 80%)  
**Code Quality**: ruff for linting and formatting, pyright for type checking  
**Dependency Management**: uv  
**Storage**: [TBD - Database solution for user data and content]  
**Deployment**: 
- Platform: fly.io
- Container Registry: ghcr.io (GitHub Container Registry)
- Containerization: Docker-based (existing Dockerfile structure)

**Backend Linting Requirements**: All code changes in backend folder MUST pass `uv run ruff check` and `uv run pyright` before merge.

## Development Workflow

**Code Review**: All changes MUST pass linting checks (ruff, pyright) and tests before merge.  
**Testing Gate**: Test coverage MUST not decrease below 80% threshold.  
**Type Safety**: Type hints MUST be used throughout codebase; pyright checks are mandatory.  
**Content Management**: Content additions MUST follow the established level and type organization structure.  
**User Data Privacy**: User progression data and quiz results MUST be handled according to privacy requirements (details TBD).

## Governance

This constitution supersedes all other development practices. All pull requests and code reviews MUST verify compliance with these principles. When principles conflict or complexity is required, deviations MUST be documented with explicit justification in the Complexity Tracking section of implementation plans.

Amendments to this constitution require:
1. Documentation of the proposed change and rationale
2. Review and approval
3. Version increment according to semantic versioning (MAJOR.MINOR.PATCH)
4. Update of dependent templates and documentation

**Version**: 1.0.1 | **Ratified**: 2026-01-10 | **Last Amended**: 2026-01-10
