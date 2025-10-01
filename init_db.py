#!/usr/bin/env python
"""
Database Initialization Script
Run this once after deployment to create all necessary database tables.

Usage:
    python init_db.py
"""

from movie_lottery import create_app, db

def init_database():
    """Initialize database tables"""
    app = create_app()
    
    with app.app_context():
        print("🔍 Checking database connection...")
        try:
            # Test connection
            db.engine.connect()
            print("✅ Database connection successful!")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False
        
        print("\n🏗️  Creating database tables...")
        try:
            db.create_all()
            print("✅ All tables created successfully!")
            
            # Verify tables
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"\n📋 Created tables: {', '.join(tables)}")
            
            return True
        except Exception as e:
            print(f"❌ Failed to create tables: {e}")
            return False

if __name__ == "__main__":
    print("=" * 60)
    print("Movie Lottery - Database Initialization")
    print("=" * 60)
    print()
    
    success = init_database()
    
    print()
    print("=" * 60)
    if success:
        print("✅ Database initialization completed successfully!")
        print("Your application is ready to use.")
    else:
        print("❌ Database initialization failed.")
        print("Please check your DATABASE_URL and try again.")
    print("=" * 60)

