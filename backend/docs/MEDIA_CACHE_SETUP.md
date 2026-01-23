# Media Cache Setup Guide

This guide explains how to set up persistent storage for media file caching on Fly.io.

## Overview

The English Tutor bot caches audio and video files downloaded from Google Drive in a persistent volume on Fly.io. This improves performance by avoiding repeated downloads and reduces API calls to Google Drive.

## Setup Steps

### 1. Create Persistent Volume

Before deploying, create a persistent volume for media cache:

```bash
cd backend
./scripts/setup_media_cache_volume.sh
```

Or manually:

```bash
flyctl volumes create media_cache \
    --size 10 \
    --region lax \
    --app english-tutor
```

**Note:** The volume size (10GB) can be adjusted based on your needs. Each media file typically ranges from 1-10MB.

### 2. Verify Volume Configuration

The `fly.toml` file includes a mount configuration:

```toml
[[mounts]]
  source = "media_cache"
  destination = "/app/data"
```

This mounts the volume at `/app/data`, and the cache service stores files in `/app/data/media_cache`.

### 3. Deploy Application

Deploy the application as usual:

```bash
flyctl deploy
```

The volume will be automatically mounted when the app starts.

## How It Works

1. **First Request**: When a user requests an audio/video task:
   - The bot checks the cache for the file
   - If not found, downloads from Google Drive
   - Saves the file to the persistent volume
   - Sends the file to the user

2. **Subsequent Requests**:
   - The bot finds the file in cache
   - Sends the cached file directly (much faster!)

## Cache Management

The cache service automatically:
- Creates the cache directory if it doesn't exist
- Uses SHA256 hashes of file IDs as cache keys
- Handles file extensions automatically
- Provides methods to clear cache if needed

## Configuration

The cache directory can be configured via environment variable:

```bash
MEDIA_CACHE_DIR=/app/data/media_cache  # Default
```

## Monitoring Cache Size

You can check cache size programmatically using the `MediaCacheService`:

```python
from src.english_tutor.services.media_cache import MediaCacheService

cache = MediaCacheService()
size_bytes = cache.get_cache_size()
print(f"Cache size: {size_bytes / 1024 / 1024:.2f} MB")
```

## Troubleshooting

### Volume Not Mounted

If the volume isn't mounting, verify:

1. Volume exists: `flyctl volumes list -a english-tutor`
2. Volume is in the same region as your app
3. `fly.toml` has the correct mount configuration

### Cache Directory Not Accessible

If you see errors about cache directory:

1. Check volume is mounted: `flyctl ssh console -a english-tutor -C "ls -la /app/data"`
2. Verify permissions: The app user should have write access
3. Check disk space: `flyctl ssh console -a english-tutor -C "df -h"`

### Clearing Cache

To clear the cache (if needed):

```python
from src.english_tutor.services.media_cache import MediaCacheService

cache = MediaCacheService()
cache.clear()  # Clears entire cache
# Or clear specific file:
cache.clear(file_id="your-file-id")
```

## Benefits

- **Performance**: Cached files load instantly
- **Reliability**: Reduces dependency on Google Drive API
- **Cost**: Fewer API calls to Google Drive
- **User Experience**: Faster task delivery
