# 📋 Render Deployment Checklist

## Pre-Deployment (Local)

- [x] Remove `db.create_all()` from `__init__.py` 
- [x] Optimize database connection pool
- [x] Increase gunicorn timeout to 300s
- [x] Add `/health` endpoint
- [x] Create `init_db.py` script

## Deployment Steps

### 1. Commit and Push Changes
```bash
git add .
git commit -F COMMIT_MESSAGE_MEMORY_FIX.txt
git push origin main
```

### 2. Update Render Dashboard

- [ ] Go to https://dashboard.render.com
- [ ] Select your service
- [ ] Click "Settings"
- [ ] Update **Start Command** to:
  ```
  gunicorn --config gunicorn_config.py "movie_lottery:create_app()"
  ```
- [ ] Click "Save Changes"
- [ ] Wait for automatic redeploy (2-3 minutes)

### 3. Verify Deployment

Check logs for success indicators:
- [ ] `[INFO] Starting gunicorn 23.0.0`
- [ ] `[INFO] Listening at: http://0.0.0.0:10000`
- [ ] `[INFO] Booting worker with pid: XXX`
- [ ] `==> Your service is live 🎉`
- [ ] **NO** `WORKER TIMEOUT` errors
- [ ] **NO** `SIGKILL` errors

### 4. Initialize Database (ONE TIME)

Choose one method:

**Option A - Using Script (Recommended):**
```bash
python init_db.py
```

**Option B - Via Web Endpoint:**
```
https://your-app.onrender.com/init-db/super-secret-key-for-db-init-12345
```

### 5. Test Application

- [ ] Home page loads
- [ ] Can search for a movie (test with "Matrix")
- [ ] Can create a lottery
- [ ] Can draw a winner
- [ ] History page shows lotteries
- [ ] Library page loads

### 6. Optional: Configure Health Check

In Render Dashboard:
- [ ] Settings → Health Check Path: `/health`
- [ ] Health Check Interval: 60 seconds
- [ ] Save changes

## Troubleshooting

### If Still Timing Out

1. **Verify config is loaded:**
   - Check logs show: `--config gunicorn_config.py`
   
2. **Try alternative start command:**
   ```bash
   gunicorn --timeout 300 --workers 1 --worker-connections 100 "movie_lottery:create_app()"
   ```

3. **Check environment variables:**
   - `DATABASE_URL` is set
   - `SECRET_KEY` is set

4. **Check instance type:**
   - Should have at least 512 MB RAM (free tier)

### If Database Errors

1. **Verify DATABASE_URL format:**
   ```
   postgresql://user:password@host:port/database
   ```

2. **Run init_db.py:**
   ```bash
   python init_db.py
   ```

3. **Check tables exist:**
   ```python
   from movie_lottery import create_app, db
   app = create_app()
   with app.app_context():
       print(db.engine.table_names())
   ```

### If Memory Still Too High

Consider these additional optimizations:

1. **Lazy import heavy modules** (qbittorrentapi, requests)
2. **Disable Flask-Migrate** on production
3. **Reduce query logging**
4. **Upgrade to Starter plan** ($7/month, 2GB RAM)

## Success Criteria

✅ Application starts in < 20 seconds
✅ No worker timeouts in logs
✅ Memory usage < 400 MB
✅ Home page loads successfully
✅ Can create and play lotteries
✅ Application stable for 30+ minutes

## Emergency Contacts / Resources

- **Documentation:** See `EMERGENCY_FIX_RENDER.md`
- **Step-by-step:** See `RENDER_DASHBOARD_STEPS.txt`
- **Technical details:** See `MEMORY_TIMEOUT_FIX_2025-10-01.md`

## Post-Deployment Monitoring

Monitor these metrics in Render dashboard:

- **Memory usage:** Should stay under 400 MB
- **Response time:** Should be < 1 second
- **Error rate:** Should be 0%
- **Uptime:** Should be 100% (after initial deploy)

If any issues arise, check logs first:
```
Dashboard → Your Service → Logs
```

Look for:
- Error messages
- Memory warnings
- Timeout indicators
- Database connection issues

## Rollback Plan

If deployment fails:

1. **Quick rollback via Render:**
   - Dashboard → Your Service → "Rollback to previous deploy"

2. **Or revert git changes:**
   ```bash
   git revert HEAD
   git push origin main
   ```

3. **Or restore specific files:**
   - Restore `movie_lottery/__init__.py` with `db.create_all()`
   - Restore `gunicorn_config.py` with timeout=120

## Notes

- Free tier has 15-minute idle timeout
- First request after sleep takes 30-60 seconds (cold start)
- Database initialization is **one-time only**
- Health check endpoint: `/health` returns `{"status": "ok"}`

