# 🚨 EMERGENCY FIX - Render Configuration Not Loading

## The Problem

Your deployment is **STILL timing out** because the `gunicorn_config.py` file is **NOT being used**!

### Evidence from Your Logs:

```
==> Running 'gunicorn "movie_lottery:create_app()"'
```

This should say:

```
==> Running 'gunicorn --config gunicorn_config.py "movie_lottery:create_app()"'
```

Without loading the config:
- ❌ Timeout is 30 seconds (default) instead of 300 seconds
- ❌ Worker connections is 1000 (default) instead of 100  
- ❌ All memory optimizations are ignored

## 🔧 IMMEDIATE FIX REQUIRED

### Step 1: Update Render Start Command

1. Go to: https://dashboard.render.com
2. Select your **movie-lottery** service
3. Click **"Settings"** (top right)
4. Scroll to **"Start Command"**
5. Change it to:

```bash
gunicorn --config gunicorn_config.py "movie_lottery:create_app()"
```

6. Click **"Save Changes"**
7. Render will automatically redeploy

### Alternative Start Commands (if the above doesn't work):

**Option A** - Short form:
```bash
gunicorn -c gunicorn_config.py "movie_lottery:create_app()"
```

**Option B** - Inline parameters (if config file can't be found):
```bash
gunicorn --workers 1 --timeout 300 --worker-connections 100 --max-requests 500 "movie_lottery:create_app()"
```

**Option C** - With explicit Python path:
```bash
python -m gunicorn --config gunicorn_config.py "movie_lottery:create_app()"
```

## 📊 What This Will Fix

| Setting | Current (Wrong) | Correct |
|---------|----------------|---------|
| Timeout | 30 seconds | 300 seconds |
| Workers | 1 | 1 ✅ |
| Connections | 1000 | 100 |
| Max Requests | ∞ | 500 |

## 🔍 How to Verify It Worked

After redeploying, check your logs. You should see:

✅ **SUCCESS - These lines in your logs:**
```
[INFO] Starting gunicorn 23.0.0
[INFO] Listening at: http://0.0.0.0:10000
[INFO] Using worker: sync
[INFO] Booting worker with pid: 123
==> Your service is live 🎉
```

❌ **FAILURE - If you still see:**
```
[CRITICAL] WORKER TIMEOUT (pid:xxx)
[ERROR] Worker was sent SIGKILL! Perhaps out of memory?
```

## 🆘 If It Still Doesn't Work

### Additional Render Settings to Check

1. **Environment Tab**
   - Verify `DATABASE_URL` is set (should auto-populate if you added PostgreSQL)
   - Set `SECRET_KEY` to a random string
   - Optional: Set `PYTHON_VERSION` to `3.11` or `3.10`

2. **Instance Type**
   - Free tier: 512 MB RAM (should be enough now)
   - If still crashing: Consider upgrading to "Starter" plan ($7/month, 2GB RAM)

3. **Build Command** (should be):
   ```bash
   pip install -r requirements.txt
   ```

4. **Health Check Path** (optional but recommended):
   - Path: `/health`
   - First, add this endpoint to `movie_lottery/routes/main_routes.py`:
   ```python
   @main_bp.route('/health')
   def health():
       return {"status": "ok"}, 200
   ```

## 🔧 Nuclear Option: If Nothing Works

If the config file absolutely won't load, update `movie_lottery/__init__.py` to set timeouts programmatically:

```python
def create_app():
    app = Flask(__name__, instance_relative_config=True)
    
    # Force longer timeout via app config
    app.config['SQLALCHEMY_POOL_TIMEOUT'] = 300
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 1,
        'max_overflow': 0,
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_timeout': 300,  # 5 minutes
        'connect_args': {
            'connect_timeout': 10,
            'command_timeout': 60,
        } if os.environ.get('DATABASE_URL') else {}
    }
    
    # ... rest of the code
```

However, this **won't fix the gunicorn worker timeout** - you MUST update the start command!

## 📈 Expected Results After Fix

- **Startup time**: 10-20 seconds
- **Memory usage**: 150-300 MB (under 512 MB limit)
- **Worker timeouts**: None (has 5 minutes to start)
- **Stability**: Should run for hours without crashes

## ⚠️ Important Notes

### 1. Database Initialization

Remember, you removed `db.create_all()` from startup. After the first successful deployment:

```bash
python init_db.py
```

Or visit:
```
https://your-app.onrender.com/init-db/super-secret-key-for-db-init-12345
```

### 2. Render Free Tier Limitations

- **512 MB RAM** - Your app should fit now
- **Spins down after 15 min** of inactivity
- **Slow cold starts** - First request after sleep takes 30-60 seconds

### 3. If Free Tier Is Still Not Enough

Consider these optimizations:

**A. Lazy Import Heavy Modules**

In `movie_lottery/routes/api_routes.py`, only import when needed:

```python
# At top - remove these
# from qbittorrentapi import Client, exceptions as qbittorrent_exceptions
# import requests

# In functions that use them - add these
def start_download(kinopoisk_id):
    from qbittorrentapi import Client  # Import only when needed
    # ... rest of function
```

**B. Disable Flask-Migrate on Production**

In `movie_lottery/__init__.py`:

```python
# Only enable migrations in development
if not os.environ.get('RENDER'):
    Migrate(app, db)
```

**C. Use Lazy Loading for SQLAlchemy**

In `movie_lottery/__init__.py`:

```python
db.init_app(app)
app.config['SQLALCHEMY_ECHO'] = False  # Disable query logging
```

## 📝 Summary

1. ✅ **Update Render start command** to load `gunicorn_config.py`
2. ⏱️ **Wait 2-3 minutes** for redeploy
3. 👀 **Check logs** for success/failure
4. 🗄️ **Initialize database** with `python init_db.py`
5. 🎉 **Test application** in browser

The timeout will go from 30 seconds to 300 seconds, giving your app plenty of time to start!

