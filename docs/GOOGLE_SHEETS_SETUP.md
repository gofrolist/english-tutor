# Google Sheets Content Management Setup

This guide explains how to set up Google Sheets and Google Drive as the content management system for the English Tutor bot.

## Architecture Overview

- **Google Sheets** → Source of truth for tasks and questions
- **Google Drive** → Media storage (audio/video files)
- **Content Sync Service** → Syncs from Sheets/Drive to PostgreSQL database
- **Telegram Bot** → Reads published content from database

## Google Sheets Structure

### Tasks Sheet

Create a sheet named "Tasks" with the following columns:

| Column | Required | Description | Example |
|--------|----------|-------------|---------|
| level | Yes | English level (A1-C2) | B1 |
| type | Yes | Content type (text/audio/video) | audio |
| title | Yes | Task title | "Past Simple Practice" |
| content_text | Yes* | Text content (for text tasks) | "The past simple tense..." |
| content_audio_drive_id | Yes* | Google Drive file ID (for audio tasks) | 1a2b3c4d5e6f7g8h9i0j |
| content_video_drive_id | Yes* | Google Drive file ID (for video tasks) | 1a2b3c4d5e6f7g8h9i0j |
| explanation | No | Educational explanation | "Use past simple for..." |
| difficulty | No | Difficulty indicator | "medium" |
| status | Yes | Task status (draft/published) | published |
| row_id | No | Unique row identifier (auto-generated if not provided) | task-001 |

*Required based on task type (text requires content_text, audio requires content_audio_drive_id, etc.)

### Questions Sheet

Create a sheet named "Questions" with the following columns:

| Column | Required | Description | Example |
|--------|----------|-------------|---------|
| task_row_id | Yes | Matches row_id from Tasks sheet | task-001 |
| question_text | Yes | Question text | "What is the past simple of 'go'?" |
| answer_options | Yes | Comma-separated or JSON array | "goed,went,gone" or ["goed","went","gone"] |
| correct_answer | Yes | Index of correct answer (0-based) | 1 |
| weight | No | Weight for scoring (default: 1.0) | 1.5 |
| order | Yes | Display order within task | 1 |
| row_id | No | Unique row identifier (auto-generated if not provided) | question-001 |

## Google Drive Setup

1. **Upload Media Files:**
   - Upload audio files (MP3, WAV, etc.) to Google Drive
   - Upload video files (MP4, etc.) to Google Drive
   - Keep files organized in folders if desired

2. **Get File IDs:**
   - Right-click on a file in Google Drive
   - Click "Get link" or "Share"
   - The file ID is in the URL: `https://drive.google.com/file/d/{FILE_ID}/view`
   - Copy the `FILE_ID` part

3. **Share Files:**
   - For each media file, click "Share"
   - Add the service account email (from your credentials JSON)
   - Give it "Viewer" access
   - Alternatively, make files "Anyone with the link can view"

## Example Google Sheets Setup

### Tasks Sheet Example

```
level | type  | title              | content_text | content_audio_drive_id | status    | row_id
------|-------|-------------------|--------------|------------------------|-----------|--------
B1    | text  | Past Simple       | The past...  |                        | published | task-001
A2    | audio | Basic Vocabulary  |              | 1a2b3c4d5e6f7g8h9i0j  | published | task-002
B2    | video | Present Perfect   |              |                        | published | task-003
```

### Questions Sheet Example

```
task_row_id | question_text                    | answer_options      | correct_answer | order | row_id
------------|----------------------------------|---------------------|----------------|-------|--------
task-001    | What is past simple of 'go'?    | goed,went,gone      | 1              | 1     | q-001
task-001    | When do we use past simple?      | yesterday,now,soon  | 0              | 2     | q-002
task-002    | What did you hear?               | cat,dog,bird        | 0              | 1     | q-003
```

## Content Sync Process

1. **Manual Sync:**
   ```bash
   curl -X POST http://localhost:8080/sync
   ```

2. **Automatic Sync:**
   - Set `ENABLE_SYNC_SCHEDULER=true`
   - Set `SYNC_INTERVAL_MINUTES=60` (or desired interval)
   - Sync runs automatically in the background

3. **Sync Process:**
   - Reads tasks from "Tasks" sheet
   - Reads questions from "Questions" sheet
   - Resolves Google Drive file IDs to download URLs
   - Creates/updates tasks and questions in database
   - Only tasks with `status=published` are available to users

## Best Practices

1. **Row IDs:**
   - Use unique, stable row IDs (e.g., "task-001", "question-001")
   - Don't change row IDs after creation (used for tracking updates)

2. **Status Management:**
   - Use `draft` status for content being worked on
   - Use `published` status for content ready for users
   - Only published content is available to the bot

3. **Media Files:**
   - Use descriptive file names
   - Keep file sizes reasonable (Telegram has limits)
   - Test file access before syncing

4. **Content Organization:**
   - Organize by level (A1-C2) in separate sheets or sections
   - Use consistent naming conventions
   - Add comments/notes in separate columns if needed

5. **Backup:**
   - Keep backups of your Google Sheets
   - Version control important changes
   - Test sync in development before production

## Troubleshooting

### Sync Fails with "Permission Denied"

- Verify service account email has access to Sheets
- Check that files in Drive are shared with service account
- Verify credentials JSON file is correct

### Files Not Accessible

- Ensure files are shared with service account
- Check file IDs are correct in Sheets
- Verify file formats are supported

### Questions Not Linking to Tasks

- Verify `task_row_id` in Questions sheet matches `row_id` in Tasks sheet
- Check for typos or extra spaces
- Ensure task exists before creating questions

### Sync Takes Too Long

- Reduce number of rows in Sheets
- Optimize Drive file sizes
- Increase sync interval
- Use manual sync for testing
