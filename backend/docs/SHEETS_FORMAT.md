# Google Sheets Format Guide

This document describes the required format for Google Sheets used with the English Tutor bot.

## Overview

The Google Sheet must contain three sheets:
1. **Tasks** - Learning activities/tasks
2. **Questions** - Questions associated with tasks
3. **Assessment** - Questions for level assessment (separate from task questions)

## Tasks Sheet

The "Tasks" sheet must have the following columns (in order):

| Column | Required | Description | Example Values |
|--------|----------|-------------|---------------|
| `row_id` | No | Unique row identifier | `task-001` |
| `level` | Yes | English proficiency level | `A1`, `A2`, `B1`, `B2`, `C1`, `C2` |
| `type` | Yes | Content type | `text`, `audio`, `video` |
| `title` | Yes | Task title | `"Simple Present Introduction"` |
| `content_text` | Yes* | Text content (for text tasks) | `"The simple present tense..."` |
| `content_drive_id` | Yes* | Google Drive file ID (for audio/video tasks) | `1a2b3c4d5e6f7g8h9i0j` |
| `explanation` | No | Educational explanation | `"Use simple present for routines"` |
| `status` | Yes | Task status | `draft`, `published` |

\* Required based on task type:
- `text` tasks require `content_text`
- `audio` tasks require `content_drive_id` (will be used as audio content)
- `video` tasks require `content_drive_id` (will be used as video content)

### Example Tasks Row

```
A1: task-001
B1: A1
C1: text
D1: Simple Present Introduction
E1: The simple present tense is used to describe habits, facts, and general truths.
F1: (empty)
G1: Use simple present for routines and facts.
H1: published
```

## Questions Sheet

The "Questions" sheet must have the following columns (in order):

| Column | Required | Description | Example Values |
|--------|----------|-------------|---------------|
| `row_id` | No | Unique row identifier | `question-001` |
| `task_row_id` | Yes | Matches `row_id` from Tasks sheet | `task-001` |
| `question_text` | Yes | Question text | `"What is the simple present form of 'to be' for 'I'?"` |
| `answer_options` | Yes | Answer options (see formats below) | `"am|is|are"` or `["am","is","are"]` |
| `correct_answer` | Yes | Index of correct answer (0-based) | `0` (first option), `1` (second option) |
| `weight` | No | Weight for scoring (default: 1.0) | `1.0`, `1.5`, `2.0` |
| `order` | Yes | Display order within task | `1`, `2`, `3` |

### Example Questions Row

```
A1: question-001
B1: task-001
C1: What is the simple present form of 'to be' for 'I'?
D1: am,is,are
E1: 0
F1: 1.0
G1: 1
```

## Answer Options Format

The `answer_options` column accepts multiple formats (in order of preference):

1. **JSON array** (most reliable): `["option1","option2","option3"]`
2. **Pipe-delimited** (recommended for options with commas): `option1|option2|option3`
3. **Semicolon-delimited**: `option1;option2;option3`
4. **CSV format** (handles quoted strings): `"option1, with comma","option2","option3"`
5. **Comma-separated** (fallback, may break if options contain commas): `option1,option2,option3`

**Important**: If your answer options contain commas (like "Had I known earlier, I would act differently."), use one of these formats:
- **Pipe-delimited** (easiest): `Had I known earlier, I would act differently.|If I knew earlier, I would have acted differently.`
- **JSON array**: `["Had I known earlier, I would act differently.","If I knew earlier, I would have acted differently."]`
- **CSV with quotes**: `"Had I known earlier, I would act differently.","If I knew earlier, I would have acted differently."`

The `correct_answer` is always a 0-based index:
- `0` = first option
- `1` = second option
- `2` = third option
- etc.

## Google Drive File IDs

For audio and video tasks, you need to:

1. Upload files to Google Drive
2. Get the file ID from the URL:
   ```
   https://drive.google.com/file/d/{FILE_ID}/view
   ```
3. Share the file with your service account email (from `credentials.json`)
4. Use the `FILE_ID` in the `content_drive_id` column (the system will determine if it's audio or video based on the `type` column)

## Status Values

- `draft` - Task is not yet published (won't be synced)
- `published` - Task is active and will be synced

## Template Creation

When running `make setup-google-terraform`, you can automatically create a template spreadsheet with:
- Correct column headers
- Example data
- Proper formatting

The template includes sample tasks and questions to help you understand the format.

## Validation

The sync process validates:
- Required columns are present
- Task types match required content fields
- Answer options are properly formatted
- Correct answer indices are valid
- Status is either `draft` or `published`

Rows with errors will be logged but won't stop the sync process.

## Assessment Sheet

The "Assessment" sheet contains questions used for initial level assessment. These are **separate** from task questions and are used to determine a user's English level (A1-C2).

The "Assessment" sheet must have the following columns (in order):

| Column | Required | Description | Example Values |
|--------|----------|-------------|---------------|
| `row_id` | No | Unique row identifier | `assess-001` |
| `level` | Yes | English level this question tests | `A1`, `A2`, `B1`, `B2`, `C1`, `C2` |
| `question_text` | Yes | Question text | `"What is 'hello' in English?"` |
| `answer_options` | Yes | Answer options (see formats below) | `"hi|hello|goodbye|thanks"` or `["hi","hello","goodbye","thanks"]` |
| `correct_answer` | Yes | Index of correct answer (0-based) | `0` (first option), `1` (second option) |
| `weight` | No | Weight for scoring (default: 1.0) | `1.0`, `1.5`, `2.0` |
| `skill_type` | No | Type of skill tested | `grammar`, `vocabulary`, `reading`, `listening` |

### Example Assessment Row

```
A1: assess-001
B1: A1
C1: What is 'hello' in English?
D1: hi,hello,goodbye,thanks
E1: 1
F1: 1.0
G1: vocabulary
```

### Assessment Question Selection

When a user runs `/assess`, the system:
1. Selects 2-3 questions from each level (A1-C2)
2. Randomizes the order
3. Presents questions one by one
4. Calculates score based on weighted answers
5. Determines user's level based on score thresholds

### Key Differences from Task Questions

- **Assessment questions**: Standalone, tagged by level, used for level determination
- **Task questions**: Belong to specific tasks, used for learning practice
- **Assessment questions**: Selected from multiple levels to diagnose ability
- **Task questions**: Selected from user's current level for practice
