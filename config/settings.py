#!/usr/bin/env python3
"""
Configuration settings for the Creative Analysis Tool.
Contains environment variables and constants.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file in config folder
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Paths
CONFIG_DIR = Path(__file__).parent
PROJECT_ROOT = CONFIG_DIR.parent
BENCHMARKS_PATH = CONFIG_DIR / 'benchmarks.json'
ANALYSIS_CONFIG_PATH = CONFIG_DIR / 'analysis_config.json'

# Load analysis configuration
try:
    with open(ANALYSIS_CONFIG_PATH, 'r') as f:
        ANALYSIS_CONFIG = json.load(f)
    
    # Extract configuration values
    AD_SELECTION = ANALYSIS_CONFIG.get('ad_selection_criteria', {})
    ACCOUNT_FILTERS = ANALYSIS_CONFIG.get('account_filters', {})
    
    # Ad selection criteria
    DAYS_THRESHOLD = AD_SELECTION.get('days_since_launch', 7)
    SPEND_THRESHOLD = AD_SELECTION.get('minimum_spend', 250.0)
    
    # Account, adset, and campaign filters
    ENABLED_ACCOUNTS = ACCOUNT_FILTERS.get('enabled_accounts', ['GBR'])
    SPECIFIC_ADSET_IDS = ACCOUNT_FILTERS.get('specific_adset_ids', [])
    SPECIFIC_CAMPAIGN_IDS = ACCOUNT_FILTERS.get('specific_campaign_ids', [])
    
    # Benchmark configuration
    BENCHMARK_CONFIG = ANALYSIS_CONFIG.get('benchmarking', {})
    BENCHMARK_CAMPAIGN_ID = BENCHMARK_CONFIG.get('specific_campaign_id', '')
    BENCHMARK_ADSET_ID = BENCHMARK_CONFIG.get('specific_adset_id', '')
    
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"Error loading analysis configuration: {e}")
    # Default values if configuration file is missing or invalid
    DAYS_THRESHOLD = 7
    SPEND_THRESHOLD = 250.0
    ENABLED_ACCOUNTS = ['GBR']
    SPECIFIC_ADSET_IDS = []
    SPECIFIC_CAMPAIGN_IDS = []
    BENCHMARK_CAMPAIGN_ID = ''
    BENCHMARK_ADSET_ID = ''

# Meta API Settings
META_ACCESS_TOKEN = os.getenv('META_ACCESS_TOKEN', '')
META_API_VERSION = os.getenv('META_API_VERSION', 'v23.0')
META_BASE_URL = f"https://graph.facebook.com/{META_API_VERSION}"

# Ad Account IDs by Region
META_AD_ACCOUNTS = {
    'ASI': os.getenv('META_AD_ACCOUNT_ID_ASI', ''),
    'EUR': os.getenv('META_AD_ACCOUNT_ID_EUR', ''),
    'LAT': os.getenv('META_AD_ACCOUNT_ID_LAT', ''),
    'PAC': os.getenv('META_AD_ACCOUNT_ID_PAC', ''),
    'GBR': os.getenv('META_AD_ACCOUNT_ID_GBR', ''),
    'NAM': os.getenv('META_AD_ACCOUNT_ID_NAM', '')
}

# Filter accounts based on configuration
META_AD_ACCOUNTS = {k: v for k, v in META_AD_ACCOUNTS.items() if k in ENABLED_ACCOUNTS}

# Google Sheets
SHEETS_SPREADSHEET_ID = os.getenv('SHEETS_SPREADSHEET_ID', '')

# Run Mode
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')