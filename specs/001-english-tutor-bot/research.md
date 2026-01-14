# Research: English Tutor Telegram Bot

**Created**: 2026-01-10  
**Feature**: English Tutor Telegram Bot  
**Phase**: Phase 0 - Outline & Research

## Research Decisions

### Database Solution for User Data and Content Storage

**Decision**: Use Supabase (PostgreSQL) with SQLAlchemy ORM

**Rationale**:
- Supabase provides managed PostgreSQL database with ACID compliance, essential for educational data (user progress, assessments)
- PostgreSQL foundation ensures compatibility with SQLAlchemy ORM
- SQLAlchemy ORM aligns with Python ecosystem and FastAPI best practices
- Supports hierarchical data structures needed for content organization (level/type relationships)
- JSONB support enables flexible content metadata storage
- Excellent performance for read-heavy workloads (content delivery, progress queries)
- Mature ecosystem with migration tools (Alembic)
- Supabase managed service simplifies deployment and scaling
- Connection pooler available for high-concurrency scenarios
- Supports transactional updates for content management operations

**Alternatives Considered**:
- SQLite: Simple but insufficient for 1000+ concurrent users; limited concurrent write performance
- MongoDB: Document-based storage, but complex relationships (tasks→questions) better suited for relational model
- Redis: Good for caching but not primary storage for structured data requiring ACID guarantees

### Telegram Bot API Library

**Decision**: Use python-telegram-bot library (version 20+)

**Rationale**:
- Most popular and actively maintained Telegram bot library for Python
- Excellent FastAPI integration support
- Supports all Telegram Bot API features (text, audio, video messages)
- Async/await support aligns with FastAPI async patterns
- Comprehensive documentation and community support
- Built-in handlers for message types and callbacks
- Supports webhook and polling modes (webhook preferred for production)

**Alternatives Considered**:
- aiogram: Another popular async library, but python-telegram-bot has larger community
- telebot (pyTelegramBotAPI): Simpler but less feature-rich for complex interactions
- Direct HTTP requests: Too low-level, requires manual handling of all Telegram API details

### Content Management Interface Pattern

**Decision**: REST API for external content management

**Rationale**:
- REST API enables external management without requiring bot interface changes
- OpenAPI specification aligns with constitution requirement
- Can be accessed via web UI, CLI, or other tools
- Separation of concerns: bot handles user interactions, API handles content management
- FastAPI auto-generates OpenAPI schema
- Standard HTTP authentication/authorization patterns
- Content updates can be made independently of bot operations

**Alternatives Considered**:
- Telegram bot interface for content management: Less suitable for complex content editing, not ideal for non-technical users
- Direct database access: Too low-level, lacks validation and business logic layer
- GraphQL API: More complex than needed for initial version (YAGNI principle)

### External Content Management Without Redeployment

**Decision**: Database-backed content storage with API-driven updates

**Rationale**:
- Content stored in database (not hardcoded in application code)
- API endpoints allow content managers to create/update/review content
- Changes take effect immediately after database update (no code changes needed)
- Supports draft/published status workflow for content review
- Meets requirement: "Content updates become available to users within 5 minutes"

**Implementation Approach**:
- Content entities (Task, Question, Content) stored in Supabase (PostgreSQL)
- REST API endpoints for CRUD operations on content
- Content status field (draft/published) for review workflow
- Bot queries database for content on-demand
- No application redeployment required for content changes

### Assessment Quiz Scoring Algorithm

**Decision**: Use weighted scoring with level thresholds

**Rationale**:
- Questions weighted by difficulty/importance
- Score thresholds map to CEFR levels (A1, A2, B1, B2, C1, C2)
- Simple algorithm aligns with YAGNI principle
- Can be refined later based on user performance data
- Transparent scoring approach suitable for educational context

**Implementation Approach**:
- Each assessment question has difficulty weight
- Total score calculated from weighted correct answers
- Predefined score ranges for each CEFR level
- Level assigned based on score range

**Alternatives Considered**:
- Machine learning-based assessment: Too complex for initial version, requires training data
- Adaptive testing (CAT): More sophisticated but not needed for MVP

### Media Storage for Audio/Video Content

**Decision**: Use external storage (URLs) for audio/video files

**Rationale**:
- Telegram supports inline audio/video and external links
- Avoids database bloat from binary file storage
- Enables CDN usage for performance
- Standard practice for media-rich applications
- Supports both inline Telegram media and external links

**Implementation Approach**:
- Store audio/video URLs in database
- Content managers upload files to storage service (e.g., S3, cloud storage)
- Store URLs in Task/Content entities
- Bot sends media via Telegram using URLs or file IDs

**Alternatives Considered**:
- Database BLOB storage: Not suitable for large files, impacts performance
- Telegram file storage: Limited to Telegram's storage, less flexible
