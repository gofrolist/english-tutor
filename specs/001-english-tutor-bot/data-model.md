# Data Model: English Tutor Telegram Bot

**Created**: 2026-01-10  
**Feature**: English Tutor Telegram Bot  
**Phase**: Phase 1 - Design & Contracts

## Entity Overview

The data model consists of six core entities representing users, assessments, tasks, questions, content, and progress tracking. Content is organized hierarchically by English level (A1-C2) and content type (text/audio/video).

## Entities

### User

Represents a learner using the bot.

**Attributes**:
- `id`: Unique identifier (UUID or integer)
- `telegram_user_id`: Telegram user ID (unique, indexed)
- `username`: Telegram username (optional)
- `current_level`: English proficiency level (A1, A2, B1, B2, C1, C2) - nullable until first assessment
- `created_at`: Timestamp when user first interacted with bot
- `updated_at`: Timestamp of last update
- `is_active`: Boolean indicating if user is actively using the bot

**Relationships**:
- One-to-many with Assessment (user can have multiple assessments)
- One-to-many with Progress (user has multiple progress records)

**Validation Rules**:
- `telegram_user_id` must be unique
- `current_level` must be one of: A1, A2, B1, B2, C1, C2, or NULL
- `telegram_user_id` is required

**State Transitions**:
- User created → `current_level` is NULL
- After first assessment → `current_level` set to assessed level
- After reassessment → `current_level` updated to new assessed level

### Assessment

Represents an evaluation session to determine English level.

**Attributes**:
- `id`: Unique identifier (UUID or integer)
- `user_id`: Foreign key to User
- `questions`: JSON array of question IDs used in assessment
- `answers`: JSON object mapping question IDs to user answers
- `score`: Numeric score (calculated from weighted answers)
- `resulting_level`: English level determined from assessment (A1, A2, B1, B2, C1, C2)
- `started_at`: Timestamp when assessment began
- `completed_at`: Timestamp when assessment was completed (nullable if incomplete)
- `status`: Enum (in_progress, completed, abandoned)

**Relationships**:
- Many-to-one with User (user can have multiple assessments)
- Assessment uses questions from Question entity (via question IDs)

**Validation Rules**:
- `user_id` is required
- `resulting_level` must be one of: A1, A2, B1, B2, C1, C2
- `score` must be non-negative
- `completed_at` can only be set when `status` is 'completed'

**State Transitions**:
- Assessment created → `status` = 'in_progress'
- User completes assessment → `status` = 'completed', `completed_at` set, `resulting_level` calculated
- User abandons assessment → `status` = 'abandoned'

### Task

Represents a learning activity delivered to users.

**Attributes**:
- `id`: Unique identifier (UUID or integer)
- `level`: English level (A1, A2, B1, B2, C1, C2)
- `type`: Content type (text, audio, video)
- `title`: Task title/name
- `content_text`: Text content for text-type tasks (nullable for audio/video)
- `content_audio_url`: URL or Telegram file ID for audio content (nullable for text/video)
- `content_video_url`: URL or Telegram file ID for video content (nullable for text/audio)
- `explanation`: Educational explanation/rules (for text tasks)
- `difficulty`: Numeric difficulty indicator (optional)
- `created_at`: Timestamp when task was created
- `updated_at`: Timestamp of last update
- `status`: Enum (draft, published)

**Relationships**:
- One-to-many with Question (task has multiple questions)
- Task belongs to Content entity (content organization)

**Validation Rules**:
- `level` must be one of: A1, A2, B1, B2, C1, C2
- `type` must be one of: text, audio, video
- At least one content field must be non-null based on type:
  - text type: `content_text` required
  - audio type: `content_audio_url` required
  - video type: `content_video_url` required
- `title` is required

**State Transitions**:
- Task created → `status` = 'draft'
- Task approved → `status` = 'published' (becomes available to users)
- Task updated → `updated_at` modified, status can remain or change

### Question

Represents an inquiry within a task.

**Attributes**:
- `id`: Unique identifier (UUID or integer)
- `task_id`: Foreign key to Task
- `question_text`: The question text
- `answer_options`: JSON array of answer options (multiple choice)
- `correct_answer`: Index or value of correct answer
- `weight`: Numeric weight for scoring (optional, defaults to 1.0)
- `order`: Display order within task
- `created_at`: Timestamp when question was created
- `updated_at`: Timestamp of last update

**Relationships**:
- Many-to-one with Task (question belongs to one task)
- Used in Assessment (via question IDs in assessment questions array)

**Validation Rules**:
- `task_id` is required
- `question_text` is required
- `answer_options` must be non-empty array
- `correct_answer` must be valid index or value within `answer_options`
- `order` must be positive integer
- `weight` must be positive number

**Constraints**:
- Questions explicitly linked to parent task via `task_id`
- Questions cannot exist without a parent task (cascade delete if task deleted)

### Content

Represents educational material in the content management system (synonym for Task in content management context).

**Attributes**:
- Same as Task entity (Task and Content refer to the same data)
- `metadata`: JSON object storing additional metadata (level, type, difficulty indicators, question-answer mappings summary)

**Relationships**:
- Content is organized hierarchically by level and type (queries filter by Task.level and Task.type)

**Note**: Content and Task refer to the same entity. "Content" is the terminology used in content management interface, while "Task" is the terminology used in user-facing bot interactions.

### Progress

Represents user performance tracking for completed tasks.

**Attributes**:
- `id`: Unique identifier (UUID or integer)
- `user_id`: Foreign key to User
- `task_id`: Foreign key to Task
- `answers`: JSON object mapping question IDs to user answers
- `score`: Numeric score (calculated from correct answers)
- `percentage_correct`: Percentage of questions answered correctly
- `completed_at`: Timestamp when task was completed
- `time_taken_seconds`: Duration to complete task (optional)

**Relationships**:
- Many-to-one with User (user has multiple progress records)
- Many-to-one with Task (progress recorded for specific task)

**Validation Rules**:
- `user_id` is required
- `task_id` is required
- `score` must be non-negative
- `percentage_correct` must be between 0 and 100
- `completed_at` is required

**Indexes**:
- Composite index on (user_id, task_id) to prevent duplicate progress records
- Index on user_id for user progress queries
- Index on completed_at for progress analytics

## Data Organization

### Hierarchical Organization

Content is organized hierarchically by:
1. **English Level**: A1, A2, B1, B2, C1, C2
2. **Content Type**: text, audio, video

Queries filter tasks by level and type to deliver appropriate content to users.

### Content Status Workflow

1. **Draft**: Content created but not yet available to users
2. **Published**: Content approved and available to users

Content managers can create/update content in draft status, then review and publish. Published content is immediately available to users (within 5 minutes per success criteria).

## Database Schema Decisions

- **Primary Keys**: UUID for all entities (better for distributed systems, avoids sequential ID issues)
- **Timestamps**: `created_at` and `updated_at` on all entities for audit trail
- **JSON Fields**: Use PostgreSQL JSONB for flexible data (answers, metadata, options)
- **Indexes**: 
  - Foreign keys indexed
  - `telegram_user_id` unique index
  - Composite indexes for common query patterns (user_id + task_id, level + type)
- **Soft Deletes**: Consider `deleted_at` timestamp for content (preserve historical data, allow recovery)
- **Migrations**: Use Alembic for database schema versioning and migrations
