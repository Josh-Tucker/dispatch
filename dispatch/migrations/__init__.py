"""
Migration runner for Dispatch RSS Reader.

This module automatically discovers and runs database migrations in the correct order.
Migrations are numbered sequentially (001, 002, etc.) and are run only once.
"""

import os
import sys
import importlib
import importlib.util
import glob
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def discover_migrations(migrations_dir=None):
    """
    Discover all migration files in the migrations directory.
    
    Returns:
        List of tuples: (migration_id, module_name, file_path)
    """
    if migrations_dir is None:
        migrations_dir = os.path.dirname(os.path.abspath(__file__))
    
    migration_files = glob.glob(os.path.join(migrations_dir, "[0-9][0-9][0-9]_*.py"))
    migrations = []
    
    for file_path in migration_files:
        filename = os.path.basename(file_path)
        if filename.startswith('__'):
            continue
            
        # Extract migration ID from filename (e.g., "001" from "001_add_column.py")
        migration_id = filename[:3]
        module_name = filename[:-3]  # Remove .py extension
        
        migrations.append((migration_id, module_name, file_path))
    
    # Sort by migration ID to ensure correct order
    migrations.sort(key=lambda x: x[0])
    return migrations

def load_migration_module(module_name, file_path):
    """
    Load a migration module dynamically.
    
    Args:
        module_name: Name of the module
        file_path: Path to the migration file
        
    Returns:
        The loaded module or None if loading failed
    """
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None:
            print(f"❌ Could not create spec for {module_name}")
            return None
            
        module = importlib.util.module_from_spec(spec)
        if module is None:
            print(f"❌ Could not create module for {module_name}")
            return None
            
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"❌ Error loading migration {module_name}: {e}")
        return None

def has_migration_table():
    """
    Check if the migrations tracking table exists.
    """
    try:
        from models import Session, engine
        import sqlite3
        
        # For SQLite databases
        if "sqlite:///" in str(engine.url):
            db_path = str(engine.url).split("///")[1]
            if not os.path.exists(db_path):
                return False
                
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='migrations'
            """)
            result = cursor.fetchone() is not None
            conn.close()
            return result
        else:
            # For other databases, use SQLAlchemy
            session = Session()
            try:
                session.execute("SELECT 1 FROM migrations LIMIT 1")
                session.close()
                return True
            except:
                session.close()
                return False
    except Exception as e:
        print(f"❌ Error checking migration table: {e}")
        return False

def create_migration_table():
    """
    Create the migrations tracking table.
    """
    try:
        from models import Session, engine
        import sqlite3
        
        # For SQLite databases
        if "sqlite:///" in str(engine.url):
            db_path = str(engine.url).split("///")[1]
            
            # Ensure database directory exists
            db_dir = os.path.dirname(db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            conn.close()
            print("✅ Created migrations tracking table")
        else:
            # For other databases, use SQLAlchemy
            session = Session()
            session.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    id VARCHAR(10) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    description TEXT,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            session.commit()
            session.close()
            print("✅ Created migrations tracking table")
            
        return True
    except Exception as e:
        print(f"❌ Error creating migration table: {e}")
        return False

def is_migration_applied(migration_id):
    """
    Check if a migration has already been applied.
    """
    try:
        from models import Session, engine
        import sqlite3
        
        # For SQLite databases
        if "sqlite:///" in str(engine.url):
            db_path = str(engine.url).split("///")[1]
            if not os.path.exists(db_path):
                return False
                
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT 1 FROM migrations WHERE id = ?", (migration_id,))
            result = cursor.fetchone() is not None
            conn.close()
            return result
        else:
            # For other databases, use SQLAlchemy
            session = Session()
            result = session.execute(
                "SELECT 1 FROM migrations WHERE id = :id", 
                {'id': migration_id}
            ).fetchone() is not None
            session.close()
            return result
    except Exception as e:
        print(f"❌ Error checking migration status: {e}")
        return False

def record_migration(migration_id, name, description):
    """
    Record that a migration has been applied.
    """
    try:
        from models import Session, engine
        import sqlite3
        
        # For SQLite databases
        if "sqlite:///" in str(engine.url):
            db_path = str(engine.url).split("///")[1]
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO migrations (id, name, description)
                VALUES (?, ?, ?)
            """, (migration_id, name, description))
            conn.commit()
            conn.close()
        else:
            # For other databases, use SQLAlchemy
            session = Session()
            session.execute("""
                INSERT INTO migrations (id, name, description)
                VALUES (:id, :name, :description)
            """, {
                'id': migration_id,
                'name': name, 
                'description': description
            })
            session.commit()
            session.close()
            
        return True
    except Exception as e:
        print(f"❌ Error recording migration: {e}")
        return False

def run_migrations():
    """
    Run all pending migrations in the correct order.
    
    Returns:
        True if all migrations ran successfully, False otherwise
    """
    print("🔄 Starting migration process...")
    
    # Ensure migration tracking table exists
    if not has_migration_table():
        print("📋 Creating migrations tracking table...")
        if not create_migration_table():
            return False
    
    # Discover all migrations
    migrations = discover_migrations()
    if not migrations:
        print("✅ No migrations found")
        return True
    
    print(f"🔍 Found {len(migrations)} migration(s)")
    
    success_count = 0
    skip_count = 0
    
    for migration_id, module_name, file_path in migrations:
        print(f"\n📦 Processing migration {migration_id}: {module_name}")
        
        # Check if migration is already applied
        if is_migration_applied(migration_id):
            print(f"⏭️  Migration {migration_id} already applied - skipping")
            skip_count += 1
            continue
        
        # Load the migration module
        module = load_migration_module(module_name, file_path)
        if module is None:
            print(f"❌ Failed to load migration {migration_id}")
            return False
        
        # Get migration metadata
        name = getattr(module, 'MIGRATION_NAME', module_name)
        description = getattr(module, 'MIGRATION_DESCRIPTION', 'No description')
        
        print(f"📝 Running: {description}")
        
        # Run the migration
        try:
            # Try the standardized run_migration function first
            if hasattr(module, 'run_migration'):
                result = module.run_migration()
            elif hasattr(module, 'migrate_database'):
                # Fallback for legacy migrations
                result = module.migrate_database()
            elif hasattr(module, 'main'):
                # Last resort - call main function
                result = module.main()
                if result is None:
                    result = True  # Assume success if no return value
            else:
                print(f"❌ Migration {migration_id} has no runnable function")
                return False
            
            if result:
                # Record successful migration
                if record_migration(migration_id, name, description):
                    print(f"✅ Migration {migration_id} completed successfully")
                    success_count += 1
                else:
                    print(f"❌ Failed to record migration {migration_id}")
                    return False
            else:
                print(f"❌ Migration {migration_id} failed")
                return False
                
        except Exception as e:
            print(f"❌ Migration {migration_id} failed with exception: {e}")
            return False
    
    print(f"\n🎉 Migration process completed!")
    print(f"   ✅ {success_count} migration(s) applied")
    print(f"   ⏭️  {skip_count} migration(s) skipped (already applied)")
    
    return True

def get_migration_status():
    """
    Get the status of all migrations.
    
    Returns:
        List of dictionaries with migration information
    """
    migrations = discover_migrations()
    status = []
    
    for migration_id, module_name, file_path in migrations:
        applied = is_migration_applied(migration_id)
        
        # Try to get metadata from module
        module = load_migration_module(module_name, file_path)
        name = getattr(module, 'MIGRATION_NAME', module_name) if module else module_name
        description = getattr(module, 'MIGRATION_DESCRIPTION', 'No description') if module else 'No description'
        
        status.append({
            'id': migration_id,
            'name': name,
            'description': description,
            'applied': applied,
            'file_path': file_path
        })
    
    return status

if __name__ == "__main__":
    # Run migrations when called directly
    success = run_migrations()
    sys.exit(0 if success else 1)