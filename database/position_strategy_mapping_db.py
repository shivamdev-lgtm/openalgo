"""
Position to Strategy Mapping Database
Tracks which strategy opened each position for grouping and analysis
"""

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Index
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.pool import NullPool
import os
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')

# Conditionally create engine based on DB type
if DATABASE_URL and 'sqlite' in DATABASE_URL:
    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool,
        connect_args={'check_same_thread': False}
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=50,
        max_overflow=100,
        pool_timeout=10
    )

db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()


class PositionStrategyMapping(Base):
    """Model for tracking which strategy opened a position"""
    __tablename__ = 'position_strategy_mappings'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False)
    symbol = Column(String(255), nullable=False)
    exchange = Column(String(50), nullable=False)
    strategy_name = Column(String(255), nullable=True)  # Strategy name (can be null for manual trades)
    strategy_id = Column(String(36), nullable=True)     # Webhook ID or python strategy ID
    strategy_type = Column(String(50), default='tradingview')  # tradingview, chartink, python, manual, etc
    
    # Position tracking
    entry_price = Column(String(50), nullable=True)
    entry_quantity = Column(Integer, nullable=True)
    entry_time = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Indexes for faster queries
    __table_args__ = (
        Index('idx_user_symbol_exchange', 'user_id', 'symbol', 'exchange'),
        Index('idx_user_strategy', 'user_id', 'strategy_id'),
        Index('idx_user_active', 'user_id', 'is_active'),
    )


def init_db():
    """Initialize the database"""
    from database.db_init_helper import init_db_with_logging
    init_db_with_logging(Base, engine, "Position Strategy Mapping DB", logger)


def create_position_mapping(user_id, symbol, exchange, strategy_name=None, strategy_id=None, 
                            strategy_type='manual', entry_price=None, entry_quantity=None, entry_time=None):
    """Create a new position to strategy mapping"""
    try:
        mapping = PositionStrategyMapping(
            user_id=user_id,
            symbol=symbol,
            exchange=exchange,
            strategy_name=strategy_name,
            strategy_id=strategy_id,
            strategy_type=strategy_type,
            entry_price=entry_price,
            entry_quantity=entry_quantity,
            entry_time=entry_time,
            is_active=True
        )
        db_session.add(mapping)
        db_session.commit()
        logger.info(f"Created position mapping for {symbol} {exchange} with strategy {strategy_name}")
        return mapping
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error creating position mapping: {e}")
        return None


def get_position_strategy(user_id, symbol, exchange):
    """Get the strategy that opened a specific position"""
    try:
        mapping = PositionStrategyMapping.query.filter_by(
            user_id=user_id,
            symbol=symbol,
            exchange=exchange,
            is_active=True
        ).first()
        return mapping
    except Exception as e:
        logger.error(f"Error getting position strategy: {e}")
        return None


def get_positions_by_strategy(user_id, strategy_id=None, strategy_name=None):
    """Get all positions opened by a specific strategy"""
    try:
        query = PositionStrategyMapping.query.filter_by(
            user_id=user_id,
            is_active=True
        )
        
        if strategy_id:
            query = query.filter_by(strategy_id=strategy_id)
        elif strategy_name:
            query = query.filter_by(strategy_name=strategy_name)
        
        return query.all()
    except Exception as e:
        logger.error(f"Error getting positions by strategy: {e}")
        return []


def get_user_positions_with_strategies(user_id):
    """Get all active position-strategy mappings for a user"""
    try:
        mappings = PositionStrategyMapping.query.filter_by(
            user_id=user_id,
            is_active=True
        ).all()
        return mappings
    except Exception as e:
        logger.error(f"Error getting user positions with strategies: {e}")
        return []


def close_position_mapping(user_id, symbol, exchange):
    """Mark a position mapping as closed"""
    try:
        mapping = PositionStrategyMapping.query.filter_by(
            user_id=user_id,
            symbol=symbol,
            exchange=exchange,
            is_active=True
        ).first()
        
        if mapping:
            mapping.is_active = False
            mapping.closed_at = func.now()
            db_session.commit()
            logger.info(f"Closed position mapping for {symbol} {exchange}")
            return mapping
        return None
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error closing position mapping: {e}")
        return None


def update_position_mapping(user_id, symbol, exchange, **kwargs):
    """Update a position mapping"""
    try:
        mapping = PositionStrategyMapping.query.filter_by(
            user_id=user_id,
            symbol=symbol,
            exchange=exchange,
            is_active=True
        ).first()
        
        if mapping:
            for key, value in kwargs.items():
                if hasattr(mapping, key):
                    setattr(mapping, key, value)
            db_session.commit()
            logger.info(f"Updated position mapping for {symbol} {exchange}")
            return mapping
        return None
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error updating position mapping: {e}")
        return None


def get_position_mappings_as_dict(user_id):
    """Get all position mappings as a dictionary for quick lookup"""
    try:
        mappings = PositionStrategyMapping.query.filter_by(
            user_id=user_id,
            is_active=True
        ).all()
        
        mapping_dict = {}
        for mapping in mappings:
            key = f"{mapping.symbol}_{mapping.exchange}"
            mapping_dict[key] = {
                'strategy_name': mapping.strategy_name,
                'strategy_id': mapping.strategy_id,
                'strategy_type': mapping.strategy_type,
                'entry_price': mapping.entry_price,
                'entry_quantity': mapping.entry_quantity,
                'entry_time': mapping.entry_time
            }
        return mapping_dict
    except Exception as e:
        logger.error(f"Error getting position mappings dict: {e}")
        return {}
