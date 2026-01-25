from sqlalchemy import Column, Integer, String, Float, Date, JSON, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/invoices")

Base = declarative_base()

class Provider(Base):
    __tablename__ = "providers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    vendor_name = Column(String)
    category = Column(String)
    patterns = Column(JSON) # Stores invoice_number, date, vendor, total_amount, nif patterns

class ExtractionLog(Base):
    __tablename__ = "extraction_logs"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, server_default=func.now())
    file_name = Column(String)
    raw_text = Column(Text)
    matching_scores = Column(JSON)
    final_json = Column(JSON)

class Invoice(Base):
    __tablename__ = "invoices"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String)
    date = Column(Date)
    vendor_name = Column(String)
    total_amount = Column(Float)
    currency = Column(String)
    type = Column(String) # 'Purchase' or 'Sale'
    file_path = Column(String)
    category = Column(String) # 'Electricity', 'Gas', 'Telecom', 'Water', etc.
    consumption = Column(Float)
    consumption_unit = Column(String) # 'kWh', 'm3', 'min', etc.

from sqlalchemy import create_engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
