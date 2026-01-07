#!/usr/bin/env python
"""
Position Strategy Mapping Migration Script for OpenAlgo

This migration creates the position_strategy_mapping table to track which 
strategy opened each position. Enables grouping and filtering positions by strategy.

Usage:
    cd upgrade
    uv run migrate_position_strategy_mapping.py

Migration: Creates position_strategy_mappings table
Created: 2025-01-07
"""

import sys
import os
import argparse
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import OperationalError, IntegrityError
from utils.logging import get_logger
from dotenv import load_dotenv

logger = get_logger(__name__)

# Migration metadata
MIGRATION_NAME = "position_strategy_mapping"
MIGRATION_VERSION = "position_strategy_mapping_001"

# Load environment
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(parent_dir, '.env'))

def get_database_url():
    """Get database URL from environment"""
    from dotenv import load_dotenv

    # Get the project root directory (parent of upgrade folder)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Load .env from project root
    load_dotenv(os.path.join(project_root, '.env'))

    database_url = os.getenv('DATABASE_URL')

    # Convert relative SQLite paths to absolute paths
    if database_url and database_url.startswith('sqlite:///'):
        # Extract the relative path after sqlite:///
        relative_path = database_url.replace('sqlite:///', '', 1)

        # If it's not already an absolute path, make it absolute relative to project root
        if not os.path.isabs(relative_path):
            absolute_path = os.path.join(project_root, relative_path)
            database_url = f'sqlite:///{absolute_path}'

    return database_url

def get_db_engine():
    """Get database engine from environment"""
    db_url = get_database_url()
    if not db_url:
        raise ValueError("DATABASE_URL environment variable not set")
    return create_engine(db_url)


def table_exists(conn, table_name):
    """Check if a table exists"""
    inspector = inspect(conn)
    return table_name in inspector.get_table_names()


def create_position_strategy_mapping_table(conn):
    """Create position_strategy_mappings table"""
    logger.info("Creating position_strategy_mappings table...")
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS position_strategy_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(255) NOT NULL,
            symbol VARCHAR(255) NOT NULL,
            exchange VARCHAR(50) NOT NULL,
            strategy_name VARCHAR(255),
            strategy_id VARCHAR(36),
            strategy_type VARCHAR(50) DEFAULT 'manual',
            entry_price VARCHAR(50),
            entry_quantity INTEGER,
            entry_time DATETIME,
            is_active BOOLEAN DEFAULT 1,
            closed_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    logger.info("Created position_strategy_mappings table")


def create_indexes(conn):
    """Create indexes for performance"""
    logger.info("Creating indexes for position_strategy_mappings table...")
    
    # Index for position lookup by user, symbol, exchange
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_user_symbol_exchange 
        ON position_strategy_mappings(user_id, symbol, exchange)
    """))
    logger.info("Created index: idx_user_symbol_exchange")
    
    # Index for strategy-based queries
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_user_strategy 
        ON position_strategy_mappings(user_id, strategy_id)
    """))
    logger.info("Created index: idx_user_strategy")
    
    # Index for active positions lookup
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_user_active 
        ON position_strategy_mappings(user_id, is_active)
    """))
    logger.info("Created index: idx_user_active")


def run_migration():
    """Run the migration"""
    try:
        logger.info(f"Starting migration: {MIGRATION_NAME}")
        logger.info(f"Migration version: {MIGRATION_VERSION}")
        
        engine = get_db_engine()
        
        with engine.connect() as conn:
            # Check if table already exists
            if table_exists(conn, 'position_strategy_mappings'):
                logger.info("Table 'position_strategy_mappings' already exists")
                logger.info("Migration skipped - table already created")
                return True
            
            # Create table
            create_position_strategy_mapping_table(conn)
            
            # Create indexes
            create_indexes(conn)
            
            # Commit transaction
            conn.commit()
            
            logger.info(f"Migration '{MIGRATION_NAME}' completed successfully")
            return True
            
    except OperationalError as e:
        logger.error(f"Database operational error: {e}")
        return False
    except IntegrityError as e:
        logger.error(f"Database integrity error: {e}")
        return False
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_status():
    """Check if migration is already applied"""
    try:
        engine = get_db_engine()
        
        with engine.connect() as conn:
            inspector = inspect(conn)
            tables = inspector.get_table_names()
            
            if 'position_strategy_mappings' in tables:
                print(f"✓ Migration '{MIGRATION_NAME}' is already applied")
                
                # Check for indexes
                indexes = inspector.get_indexes('position_strategy_mappings')
                index_names = [idx['name'] for idx in indexes]
                
                expected_indexes = [
                    'idx_user_symbol_exchange',
                    'idx_user_strategy',
                    'idx_user_active'
                ]
                
                missing = [idx for idx in expected_indexes if idx not in index_names]
                
                if missing:
                    print(f"  ⚠ Missing indexes: {', '.join(missing)}")
                    return False
                else:
                    print(f"  ✓ All indexes present")
                    return True
            else:
                print(f"✗ Migration '{MIGRATION_NAME}' is not applied")
                return False
                
    except Exception as e:
        print(f"Error checking status: {e}")
        return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description=f"Migration: {MIGRATION_NAME}"
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='Check if migration is already applied'
    )
    
    args = parser.parse_args()
    
    if args.status:
        return 0 if check_status() else 1
    
    # Run migration
    if run_migration():
        print(f"\n✓ Migration completed successfully")
        return 0
    else:
        print(f"\n✗ Migration failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
