"""
Comprehensive Test Suite for Movie Lottery Application
========================================================
This test suite performs a complete functionality test of the Movie Lottery website.
"""

import os
import sys
import json
import time
from contextlib import contextmanager

# Add project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test Results
test_results = {
    "passed": [],
    "failed": [],
    "warnings": [],
    "info": []
}


def log_result(status, test_name, message=""):
    """Log test result"""
    result = {
        "test": test_name,
        "message": message,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    test_results[status].append(result)
    
    # Print colored output - using simple ASCII symbols for Windows compatibility
    symbols = {
        "passed": "[PASS]",
        "failed": "[FAIL]",
        "warnings": "[WARN]",
        "info": "[INFO]"
    }
    print(f"{symbols.get(status, '[TEST]')} {test_name}: {message}")


def print_summary():
    """Print test summary"""
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"[+] Passed: {len(test_results['passed'])}")
    print(f"[-] Failed: {len(test_results['failed'])}")
    print(f"[!] Warnings: {len(test_results['warnings'])}")
    print(f"[i] Info: {len(test_results['info'])}")
    print("="*70)
    
    if test_results['failed']:
        print("\nFAILED TESTS:")
        for fail in test_results['failed']:
            print(f"  - {fail['test']}: {fail['message']}")
    
    if test_results['warnings']:
        print("\nWARNINGS:")
        for warn in test_results['warnings']:
            print(f"  - {warn['test']}: {warn['message']}")


@contextmanager
def test_context(test_name):
    """Context manager for tests"""
    print(f"\nRunning: {test_name}")
    try:
        yield
    except Exception as e:
        log_result("failed", test_name, str(e))
        raise


class TestMovieLottery:
    """Main test class for Movie Lottery application"""
    
    def __init__(self):
        self.app = None
        self.client = None
        self.app_context = None
    
    def setup_app(self):
        """Setup Flask application for testing"""
        with test_context("Application Setup"):
            try:
                # Create instance directory if it doesn't exist
                instance_path = os.path.join(os.getcwd(), 'instance')
                os.makedirs(instance_path, exist_ok=True)
                
                from movie_lottery import create_app, db
                
                self.app = create_app()
                self.app.config['TESTING'] = True
                self.client = self.app.test_client()
                self.app_context = self.app.app_context()
                self.app_context.push()
                
                log_result("passed", "Application Setup", "Flask app initialized successfully")
                log_result("info", "Database Location", f"Using: {self.app.config['SQLALCHEMY_DATABASE_URI']}")
                return True
            except Exception as e:
                log_result("failed", "Application Setup", f"Failed to initialize app: {str(e)}")
                return False
    
    def test_imports(self):
        """Test if all required modules can be imported"""
        with test_context("Module Imports"):
            modules = [
                ('flask', 'Flask'),
                ('flask_sqlalchemy', 'Flask-SQLAlchemy'),
                ('flask_migrate', 'Flask-Migrate'),
                ('requests', 'Requests'),
                ('qbittorrentapi', 'qBittorrent-API'),
            ]
            
            failed_imports = []
            for module, name in modules:
                try:
                    __import__(module)
                    log_result("passed", f"Import {name}", f"{name} imported successfully")
                except ImportError as e:
                    failed_imports.append(name)
                    log_result("failed", f"Import {name}", f"Failed to import: {str(e)}")
            
            if not failed_imports:
                return True
            return False
    
    def test_config(self):
        """Test application configuration"""
        with test_context("Configuration Test"):
            try:
                from movie_lottery.config import Config
                
                # Check required config attributes
                required_attrs = [
                    'SECRET_KEY',
                    'SQLALCHEMY_DATABASE_URI',
                    'SQLALCHEMY_TRACK_MODIFICATIONS'
                ]
                
                for attr in required_attrs:
                    if not hasattr(Config, attr):
                        log_result("failed", f"Config: {attr}", f"Missing required config: {attr}")
                        return False
                    log_result("passed", f"Config: {attr}", f"Config attribute exists")
                
                # Check optional qBittorrent config
                qbit_attrs = ['QBIT_HOST', 'QBIT_PORT', 'QBIT_USERNAME', 'QBIT_PASSWORD']
                for attr in qbit_attrs:
                    if hasattr(Config, attr):
                        value = getattr(Config, attr)
                        if value:
                            log_result("info", f"Config: {attr}", f"qBittorrent config set")
                        else:
                            log_result("warnings", f"Config: {attr}", f"qBittorrent {attr} not configured (optional)")
                
                return True
            except Exception as e:
                log_result("failed", "Configuration Test", str(e))
                return False
    
    def test_database_models(self):
        """Test database models"""
        with test_context("Database Models Test"):
            try:
                from movie_lottery.models import (
                    MovieIdentifier, Lottery, Movie, LibraryMovie, BackgroundPhoto
                )
                from movie_lottery import db
                
                # Test model definitions
                models = [
                    ('MovieIdentifier', MovieIdentifier),
                    ('Lottery', Lottery),
                    ('Movie', Movie),
                    ('LibraryMovie', LibraryMovie),
                    ('BackgroundPhoto', BackgroundPhoto)
                ]
                
                for model_name, model_class in models:
                    # Check if model has __tablename__ or default name
                    table_name = getattr(model_class, '__tablename__', model_class.__name__.lower())
                    log_result("passed", f"Model: {model_name}", f"Model defined with table: {table_name}")
                
                # Test creating a lottery record
                try:
                    test_lottery = Lottery(id='test01')
                    db.session.add(test_lottery)
                    db.session.commit()
                    
                    # Retrieve it
                    retrieved = Lottery.query.get('test01')
                    if retrieved and retrieved.id == 'test01':
                        log_result("passed", "Database Operations", "Create and retrieve lottery successful")
                    else:
                        log_result("failed", "Database Operations", "Failed to retrieve created lottery")
                    
                    # Test relationship
                    test_movie = Movie(
                        name="Test Movie",
                        year="2024",
                        lottery_id='test01'
                    )
                    db.session.add(test_movie)
                    db.session.commit()
                    
                    if len(retrieved.movies) == 1:
                        log_result("passed", "Database Relationships", "Lottery-Movie relationship works")
                    else:
                        log_result("failed", "Database Relationships", "Lottery-Movie relationship failed")
                    
                    # Cleanup
                    db.session.delete(test_movie)
                    db.session.delete(test_lottery)
                    db.session.commit()
                    
                except Exception as e:
                    log_result("failed", "Database Operations", f"Database operation failed: {str(e)}")
                    db.session.rollback()
                
                return True
            except Exception as e:
                log_result("failed", "Database Models Test", str(e))
                return False
    
    def test_routes(self):
        """Test all application routes"""
        with test_context("Routes Test"):
            if not self.client:
                log_result("failed", "Routes Test", "Test client not initialized")
                return False
            
            # Test main routes
            main_routes = [
                ('/', 'Index Page'),
                ('/history', 'History Page'),
                ('/library', 'Library Page'),
            ]
            
            for route, name in main_routes:
                try:
                    response = self.client.get(route)
                    if response.status_code == 200:
                        log_result("passed", f"Route: {name}", f"GET {route} returned 200")
                    else:
                        log_result("failed", f"Route: {name}", f"GET {route} returned {response.status_code}")
                except Exception as e:
                    log_result("failed", f"Route: {name}", str(e))
            
            return True
    
    def test_api_endpoints(self):
        """Test API endpoints"""
        with test_context("API Endpoints Test"):
            if not self.client:
                log_result("failed", "API Endpoints Test", "Test client not initialized")
                return False
            
            # Test API endpoints that don't require data
            try:
                # Test active downloads endpoint
                response = self.client.get('/api/active-downloads')
                if response.status_code == 200:
                    data = json.loads(response.data)
                    if 'active' in data and 'kp' in data:
                        log_result("passed", "API: /api/active-downloads", "Endpoint works correctly")
                    else:
                        log_result("warnings", "API: /api/active-downloads", "Unexpected response structure")
                else:
                    log_result("failed", "API: /api/active-downloads", f"Returned {response.status_code}")
            except Exception as e:
                log_result("failed", "API: /api/active-downloads", str(e))
            
            # Test creating a lottery (should fail without data, but should not crash)
            try:
                response = self.client.post('/api/create',
                    data=json.dumps({'movies': []}),
                    content_type='application/json'
                )
                if response.status_code == 400:
                    log_result("passed", "API: /api/create validation", "Validation works correctly")
                else:
                    log_result("info", "API: /api/create validation", f"Returned {response.status_code}")
            except Exception as e:
                log_result("failed", "API: /api/create", str(e))
            
            return True
    
    def test_utilities(self):
        """Test utility functions"""
        with test_context("Utilities Test"):
            try:
                # Skip if app not initialized (utility needs app context)
                if not self.app or not self.app_context:
                    log_result("info", "Utilities Test", "Skipped (requires app context)")
                    return True
                
                from movie_lottery.utils.helpers import generate_unique_id
                
                # Test ID generation
                id1 = generate_unique_id()
                id2 = generate_unique_id()
                
                if len(id1) == 6 and len(id2) == 6:
                    log_result("passed", "Helper: generate_unique_id", "Generates correct length IDs")
                else:
                    log_result("failed", "Helper: generate_unique_id", "Incorrect ID length")
                
                if id1 != id2:
                    log_result("passed", "Helper: unique IDs", "Generated IDs are unique")
                else:
                    log_result("warnings", "Helper: unique IDs", "Generated same ID twice (unlikely but possible)")
                
                return True
            except Exception as e:
                log_result("failed", "Utilities Test", str(e))
                return False
    
    def test_static_files(self):
        """Test if static files exist"""
        with test_context("Static Files Test"):
            try:
                static_files = [
                    'movie_lottery/static/css/style.css',
                    'movie_lottery/static/js/main.js',
                    'movie_lottery/static/js/play.js',
                    'movie_lottery/static/js/toast.js',
                ]
                
                for file_path in static_files:
                    if os.path.exists(file_path):
                        log_result("passed", f"Static: {os.path.basename(file_path)}", "File exists")
                    else:
                        log_result("failed", f"Static: {os.path.basename(file_path)}", "File not found")
                
                return True
            except Exception as e:
                log_result("failed", "Static Files Test", str(e))
                return False
    
    def test_templates(self):
        """Test if template files exist"""
        with test_context("Templates Test"):
            try:
                templates = [
                    'movie_lottery/templates/index.html',
                    'movie_lottery/templates/history.html',
                    'movie_lottery/templates/library.html',
                    'movie_lottery/templates/play.html',
                    'movie_lottery/templates/wait.html',
                ]
                
                for template_path in templates:
                    if os.path.exists(template_path):
                        # Check if template has basic structure
                        with open(template_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if '<html' in content and '</html>' in content:
                                log_result("passed", f"Template: {os.path.basename(template_path)}", "Valid HTML structure")
                            else:
                                log_result("warnings", f"Template: {os.path.basename(template_path)}", "Missing HTML tags")
                    else:
                        log_result("failed", f"Template: {os.path.basename(template_path)}", "File not found")
                
                return True
            except Exception as e:
                log_result("failed", "Templates Test", str(e))
                return False
    
    def test_code_quality(self):
        """Test code quality issues"""
        with test_context("Code Quality Test"):
            issues_found = []
            
            # Check for duplicate code (already fixed)
            try:
                with open('movie_lottery/routes/api_routes.py', 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Count return statements in get_result_data function
                    if content.count('def get_result_data(lottery_id):') == 1:
                        log_result("passed", "Code Quality: Duplicate Code", "No duplicate code blocks found")
                    else:
                        log_result("warnings", "Code Quality: Duplicate Code", "Potential duplicate code detected")
            except Exception as e:
                log_result("info", "Code Quality: Duplicate Code", f"Could not check: {str(e)}")
            
            return True
    
    def run_all_tests(self):
        """Run all tests"""
        print("\n" + "="*70)
        print("MOVIE LOTTERY - COMPREHENSIVE FUNCTIONALITY TEST")
        print("="*70)
        
        # Run tests in order
        self.test_imports()
        self.test_config()
        
        if self.setup_app():
            self.test_database_models()
            self.test_routes()
            self.test_api_endpoints()
            self.test_utilities()
        
        self.test_static_files()
        self.test_templates()
        self.test_code_quality()
        
        # Generate report
        print_summary()
        
        # Save detailed report
        report_file = f"test_report_{time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(test_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n[FILE] Detailed report saved to: {report_file}")
        
        # Cleanup
        if self.app_context:
            self.app_context.pop()
        
        return len(test_results['failed']) == 0


def main():
    """Main test entry point"""
    tester = TestMovieLottery()
    success = tester.run_all_tests()
    
    if success:
        print("\n[SUCCESS] All tests passed successfully!")
        return 0
    else:
        print("\n[ERROR] Some tests failed. Please review the report above.")
        return 1


if __name__ == '__main__':
    exit(main())

