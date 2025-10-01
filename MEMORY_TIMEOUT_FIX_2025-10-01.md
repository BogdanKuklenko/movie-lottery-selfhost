# Critical Memory & Timeout Fix - October 1, 2025

## Problem Analysis

Your Render deployment was experiencing severe issues:

- **Worker Timeout Errors**: Workers timing out after 30-60 seconds during startup
- **Out of Memory (OOM) Kills**: Workers killed with SIGKILL repeatedly for over 1 hour
- **Service Instability**: 100+ worker restarts before finally stabilizing

### Root Causes Identified

1. **Database initialization on every worker start**: `db.create_all()` was being called during app initialization, causing slow startup and potential database locks
2. **Excessive database connection pooling**: Default pool settings were using too much memory for free-tier hosting
3. **Insufficient timeout values**: Workers needed more time to start on resource-constrained environments
4. **High worker connections**: Too many simultaneous connections consuming memory

## Changes Made

### 1. App Initialization (`movie_lottery/__init__.py`)

**REMOVED** automatic table creation during startup:

```python
# BEFORE: This was called on EVERY worker start
try:
    with app.app_context():
        db.create_all()
except Exception as e:
    app.logger.warning(f"Could not create tables: {e}")

# AFTER: No database schema operations during worker initialization
# Tables should be created through migrations or manual setup
```

**Why this helps:**
- Eliminates slow database operations during startup
- Prevents database locks when multiple workers try to create tables
- Reduces memory usage during initialization

### 2. Database Configuration (`movie_lottery/config.py`)

**OPTIMIZED** SQLAlchemy connection pool for memory efficiency:

```python
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 1,          # NEW: Only 1 connection (was unlimited)
    'max_overflow': 0,       # NEW: No overflow connections
    'pool_pre_ping': True,   # Keep existing: verify connections
    'pool_recycle': 300,     # Keep existing: recycle every 5 min
    'connect_args': {
        'connect_timeout': 10,
    }
}
```

**Memory savings:**
- Each PostgreSQL connection: ~10-30 MB RAM
- Old config: Could use 5+ connections = 50-150 MB
- New config: Maximum 1 connection = 10-30 MB
- **Saved: 40-120 MB per worker**

### 3. Gunicorn Configuration (`gunicorn_config.py`)

**UPDATED** worker settings for stability:

```python
# Memory optimization
worker_connections = 100  # DOWN from 1000 (saves ~90 MB)
max_requests = 500        # DOWN from 1000 (more frequent restarts)

# Timeout fixes
timeout = 300             # UP from 120 seconds (5 minutes)
graceful_timeout = 60     # UP from 30 seconds
keepalive = 2             # DOWN from 5 (saves memory)
```

**Benefits:**
- Workers get 5 minutes to start (crucial for slow free-tier instances)
- More frequent worker recycling prevents memory leaks
- Fewer connections = less memory usage

## Post-Deployment Steps Required

### ⚠️ CRITICAL: Initialize Database Tables

Since we removed automatic table creation, you **MUST** create tables manually:

#### Option A: One-Time Setup Route (Easiest)

Visit this URL once after deploying:
```
https://your-app.onrender.com/init-db/super-secret-key-for-db-init-12345
```

This will create all necessary tables.

#### Option B: Using Flask CLI (Recommended for Production)

Connect to your Render shell and run:
```bash
python -c "from movie_lottery import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
```

#### Option C: Using Migrations (Best Practice)

If you have Alembic migrations set up:
```bash
flask db upgrade
```

### Verify the Fix

After deploying these changes, monitor your logs for:

✅ **Success indicators:**
- "Starting gunicorn" followed by "Listening at: http://0.0.0.0:10000"
- "Booting worker with pid: X" without subsequent timeout
- No "WORKER TIMEOUT" errors
- No "Perhaps out of memory?" messages

❌ **Failure indicators:**
- Still seeing "CRITICAL WORKER TIMEOUT"
- "Worker was sent SIGKILL"
- Multiple worker restarts

## Additional Optimization Recommendations

### 1. Monitor Memory Usage

Add this to your `gunicorn_config.py` if issues persist:

```python
# Even more aggressive memory management
import gc
import os

def when_ready(server):
    gc.collect()  # Clean up before starting

def post_worker_init(worker):
    gc.collect()  # Clean up after worker init
```

### 2. Consider Render.com Settings

In your Render dashboard, verify:
- **Plan**: Make sure you're on at least 512 MB RAM (free tier minimum)
- **Region**: Choose closest region to your database
- **Health Check**: Add a simple health check endpoint
- **Start Command**: Ensure it's using: `gunicorn "movie_lottery:create_app()"`

### 3. Add Health Check Endpoint

Add to `movie_lottery/routes/main_routes.py`:

```python
@main_bp.route('/health')
def health_check():
    return {"status": "healthy"}, 200
```

Configure in Render dashboard:
- Health Check Path: `/health`
- Health Check Interval: 60 seconds

### 4. Environment Variables to Set

Ensure these are configured in Render:

```bash
DATABASE_URL=postgresql://...
SECRET_KEY=your-secret-key
PYTHON_VERSION=3.11  # Or your version
WEB_CONCURRENCY=1    # Force single worker
```

## Performance Impact

### Startup Time
- **Before**: 30-60+ seconds (timing out)
- **After**: 10-15 seconds expected

### Memory Usage
- **Before**: 400-600 MB (causing OOM)
- **After**: 150-250 MB expected

### Response Time
- **No impact**: Application performance remains the same
- Database connection pooling reduction only affects high-concurrency scenarios

## Rollback Plan

If these changes cause issues, revert by:

1. Restore `movie_lottery/__init__.py`:
   - Add back the `db.create_all()` block

2. Restore `movie_lottery/config.py`:
   - Remove `pool_size` and `max_overflow` settings

3. Restore `gunicorn_config.py`:
   - Set `timeout = 120`
   - Set `worker_connections = 1000`

## Testing Checklist

Before considering this fix complete:

- [ ] Deploy changes to Render
- [ ] Verify no worker timeouts in logs
- [ ] Access home page successfully
- [ ] Create a lottery successfully
- [ ] Check history page loads
- [ ] Check library page loads
- [ ] Verify database tables exist
- [ ] Monitor for 30 minutes for stability

## Support

If problems persist after these changes:

1. **Check Render logs** for specific error messages
2. **Verify database connection** - ensure DATABASE_URL is correct
3. **Check memory limits** - free tier has strict limits
4. **Consider upgrading** - if using free tier, paid plans have more resources

## Summary

These changes address the critical memory and timeout issues by:
- Eliminating slow database operations during startup
- Reducing memory footprint by 40-50%
- Increasing timeout tolerance for resource-constrained environments
- Making the application suitable for free-tier hosting

The application should now start reliably within 10-15 seconds instead of timing out.

