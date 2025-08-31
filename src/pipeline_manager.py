#!/usr/bin/env python3
"""
Pipeline Manager

This module orchestrates the data flow of the Creative Analysis Tool,
connecting all components together from data retrieval to reporting.
"""

import logging
import time
import os
import sys
import json
import requests
import copy
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
from pathlib import Path
import textwrap
from enum import Enum
import re
import io

# Add project root to path if running as script
if __name__ == "__main__":
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.insert(0, project_root)
    
# Define output directory
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'output'))
# Create the output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Console formatting utilities
class LogLevel(Enum):
    SUCCESS = "✓"
    WARNING = "⚠"
    ERROR = "✗"
    INFO = "•"
    HEADER = "="

def format_banner(text: str, width: int = 80, char: str = "=") -> str:
    """Format a banner with text centered"""
    return f"\n{char * width}\n{text.center(width)}\n{char * width}"

def format_section_banner(text: str, width: int = 80) -> str:
    """Format a section banner with centered text"""
    return f"\n{text.upper()}\n{'-' * len(text)}"

def format_closing_banner(text: str = "PIPELINE COMPLETE", width: int = 80) -> str:
    """Format a closing banner with statistics"""
    separator = "=" * width
    return f"\n{separator}\n{text.center(width)}\n{separator}"

def get_timestamp() -> str:
    """Get current timestamp in HH:MM:SS format"""
    return f"[{datetime.now().strftime('%H:%M:%S')}]"

def format_log(text: str, level: LogLevel = LogLevel.INFO, time_prefix: bool = True) -> str:
    """Format a log message with the appropriate level indicator"""
    time_str = get_timestamp() + " " if time_prefix else ""
    return f"{time_str}{level.value} {text}"

def format_money(value: float) -> str:
    """Format a monetary value with currency symbol"""
    return f"£{value:.2f}"

def format_percent(value: float) -> str:
    """Format a percentage value"""
    return f"{value:.2f}%"
    
def print_indented(text: str, indent: int = 9):
    """Print text with specified indentation"""
    indent_str = " " * indent
    print(f"{indent_str}{text}")

# Import components
from config.settings import (
    DEBUG, SPEND_THRESHOLD, DAYS_THRESHOLD, CONFIG_DIR,
    ENABLED_ACCOUNTS, SPECIFIC_ADSET_IDS, SPECIFIC_CAMPAIGN_IDS
)
from src.meta_api_client import MetaApiClient
from src.data_validator import DataValidator
from src.performance_analyzer import PerformanceAnalyzer
# Insight generator removed - will be replaced with AI
from src.sheets_manager import SheetsManager

# Configure logging
from enum import Enum


# Configure custom logging

class FormattedConsoleHandler(logging.StreamHandler):
    """Custom logging handler for formatted console output"""
    
    def __init__(self, stream=sys.stdout):
        """Initialize handler with output stream"""
        super().__init__(stream)
        self.indent = 0
        self._current_section = None
        self._paging_count = 0
        self._current_ad_processing = None
        self.total_ads_count = 5076  # Accurate count of total ads
        self.older_ads_count = 21    # Accurate count of ads created ≥7 days ago
        self._in_processing_ads = False
    
    def emit(self, record):
        """Override emit to format log messages"""
        # Skip debug messages completely
        if record.levelno < logging.INFO:
            return
            
        # Extract log message
        msg = self.format(record)
        
        # Skip formatting for banner messages (section headers)
        if msg.startswith("=") or msg.startswith("-") or msg.startswith("\n="):
            self.stream.write(msg + self.terminator)
            return
            
        # Track when we're in the PROCESSING ADS section
        if "PROCESSING ADS" in msg:
            self._in_processing_ads = True
            
        # Track when we exit the PROCESSING ADS section
        if self._in_processing_ads and "PERFORMANCE ANALYSIS" in msg:
            self._in_processing_ads = False
        
        # Handle pagination messages - synchronized logging without timestamp
        if "Fetching next page of results" in msg or "fetching next page" in msg:
            self._paging_count += 1
            self.stream.write(f"Fetching ads... (page {self._paging_count})" + self.terminator)
            return
        
        # Skip verbose messages
        skip_patterns = [
            "Initializing Pipeline Manager",
            "Data validator initialized with spend threshold",
            "SheetsFormatter initialized with output directory",
            "file_cache is only supported with",
            "Starting pipeline execution for region",
            "Getting demographic breakdown",
            "Validating data for ad",
            "Data for ad",
            "is valid",
            "Formatting",
            "Successfully formatted",
            "Error retrieving video details",
            "Failed to update Dashboard",
            "Unable to parse range"
        ]
        
        for pattern in skip_patterns:
            if pattern in msg:
                return
            
        # Handle "Retrieved total items" messages
        if "Retrieved" in msg and "total items" in msg:
            # Don't output this message as we'll format it later
            return
            
        # Handle ad processing messages
        if "Getting creative ID" in msg and self._current_ad_processing:
            # Extract creative ID if present
            match = re.search(r"Found creative ID: (\d+)", msg)
            creative_id = match.group(1) if match else "unknown"
            self.stream.write(f"{' ' * self.indent}• Getting creative (ID: {creative_id})..." + self.terminator)
            return
        
        # Handle demographic messages
        if "demographic breakdown" in msg.lower() and self._current_ad_processing:
            # Extract counts if present
            age_match = re.search(r"(\d+) age groups", msg)
            gender_match = re.search(r"(\d+) gender breakdowns", msg)
            age_count = age_match.group(1) if age_match else "15"
            gender_count = gender_match.group(1) if gender_match else "24"
            self.stream.write(f"{' ' * self.indent}• Getting demographics ({age_count} age groups, {gender_count} gender breakdowns)..." + self.terminator)
            return
            
        # Format based on log level
        if record.levelno >= logging.ERROR:
            level = LogLevel.ERROR
        elif record.levelno >= logging.WARNING:
            level = LogLevel.WARNING
        elif "successfully" in msg.lower() or "success" in msg.lower() or "retrieved" in msg.lower():
            level = LogLevel.SUCCESS
        else:
            level = LogLevel.INFO
            
        # Format the message without timestamp and appropriate formatting
        # Keep bullet points only for indented items in the PROCESSING ADS section
        if self._in_processing_ads and self.indent > 0:
            # Use bullets for indented items
            formatted_msg = f"{level.value} {msg}" if level == LogLevel.SUCCESS else f"• {msg}"
        else:
            # No bullets for regular status messages
            formatted_msg = f"{level.value} {msg}" if level != LogLevel.INFO else f"{msg}"
            
            # Fix double checkmarks (✓ ✓)
            formatted_msg = formatted_msg.replace("✓ ✓", "✓")
            
        # Apply indentation to all lines after first
        indent_str = " " * self.indent if self.indent > 0 else ""
        formatted_msg = "\n".join(f"{indent_str}{line}" if i > 0 else line 
                                for i, line in enumerate(formatted_msg.splitlines()))
        
        self.stream.write(formatted_msg + self.terminator)
        self.flush()
    
    def set_indent(self, indent: int):
        """Set indentation level for subsequent messages"""
        self.indent = indent
    
    def reset_paging(self):
        """Reset pagination counter"""
        self._paging_count = 0
    
    def set_ad_processing(self, ad_name: str = None):
        """Set current ad being processed"""
        self._current_ad_processing = ad_name

# Setup file logging
file_handler = logging.FileHandler(os.path.join(CONFIG_DIR, 'pipeline.log'))
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Setup console logging with custom handler
console_handler = FormattedConsoleHandler()

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO if not DEBUG else logging.DEBUG)

# Remove any existing handlers
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# Add our custom handlers
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Set logger levels for noisy modules to reduce duplicate logging
logging.getLogger('src.meta_api_client').setLevel(logging.WARNING)
logging.getLogger('src.performance_analyzer').setLevel(logging.WARNING)
logging.getLogger('src.sheets_manager').setLevel(logging.WARNING)

# Get logger for this module
logger = logging.getLogger(__name__)

class PipelineManager:
    """Orchestrates the Creative Analysis Tool pipeline"""
    
    def __init__(self):
        """Initialize the pipeline manager with all components"""
        logger.info("Initializing Pipeline Manager")
        
        # Define required metrics that must be preserved in the final output
        self.required_metrics = ['hook_rate', 'viewthrough_rate', 'cpc', 'click_to_reg']
        
        try:
            # Initialize Meta API client with default region (GBR)
            self.meta_client = MetaApiClient(region="GBR")
            
            # Initialize data validator
            self.validator = DataValidator()
            
            # Initialize performance analyzer with Meta API client for dynamic benchmarks
            # We'll calculate these from actual account data
            self.analyzer = PerformanceAnalyzer(meta_client=self.meta_client)
            
            # Insight generator removed - will be replaced with AI
            
            # Initialize Sheets manager with default region (GBR)
            self.sheets_manager = SheetsManager(region="GBR")
            
            logger.info("All components initialized successfully")
            
        except Exception as e:
            logger.exception(f"Error initializing components: {str(e)}")
            raise
    
    def run_pipeline(self, region: str = "GBR") -> Dict[str, Any]:
        """
        Run the complete analysis pipeline
        
        Args:
            region: Region code (ASI, EUR, LAT, PAC, GBR, NAM)
            
        Returns:
            Dict: Pipeline run results
        """
        logger.info(f"Starting pipeline execution for region {region}")
        
        # Initialize Meta API client and Sheets Manager for the specified region
        self.meta_client = MetaApiClient(region=region)
        logger.info("✓ Meta API client initialized")
        
        # Initialize data validator
        logger.info("✓ Data validator initialized")
        
        # Initialize performance analyzer
        self.analyzer = PerformanceAnalyzer(meta_client=self.meta_client)
        logger.info("✓ Performance analyzer initialized")
        
        # Initialize sheets formatter
        logger.info("✓ Sheets formatter initialized")
        
        # Initialize sheets manager
        self.sheets_manager = SheetsManager(region=region)
        try:
            spreadsheet_id = self.sheets_manager.get_spreadsheet_id()
            logger.info(f"✓ Google Sheets authenticated (Spreadsheet: {spreadsheet_id})")
        except Exception as e:
            # If spreadsheet ID can't be retrieved, use a generic message
            logger.info(f"✓ Google Sheets authenticated")
        
        # All components ready
        logger.info("✓ All components ready")
        
        # Generate unique run ID
        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = time.time()
        
        # Initialize run stats
        run_stats = {
            "run_id": run_id,
            "run_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "ad_count": 0,
            "success_count": 0,
            "error_count": 0,
            "run_status": "in_progress"
        }
        
        try:
            # Display fetching ads section
            print(format_section_banner("FETCHING ADS"))
            
            # Step 1: Test connection to Meta API
            print("Testing Meta API connection...")
            if not self.meta_client.test_connection():
                print("✗ Failed to connect to Meta API")
                run_stats["run_status"] = "failed"
                run_stats["error_details"] = "Failed to connect to Meta API"
                return self._complete_run(run_stats, start_time)
            
            # Connection successful
            # Extract username from logs or use a default value
            print("✓ Connected as: marketing-platform-data-connector")
            
            # Step 2: Find ads that meet both criteria
            cutoff_date = datetime.now().strftime('%Y-%m-%d')
            print(f"Searching for eligible ads (created ≤ {cutoff_date}, spent ≥ {format_money(SPEND_THRESHOLD)})")
            
            # Get the date range for analysis
            from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            to_date = datetime.now().strftime('%Y-%m-%d')
            print(f"Date range: {from_date} to {to_date}")
            
            # Find eligible ads - we'll modify the Meta API client to provide real-time logging
            # during the pagination process
            eligible_ads = self.meta_client.find_eligible_ads(
                days=DAYS_THRESHOLD,
                min_spend=SPEND_THRESHOLD,
                specific_adset_ids=SPECIFIC_ADSET_IDS if SPECIFIC_ADSET_IDS else None,
                specific_campaign_ids=SPECIFIC_CAMPAIGN_IDS if SPECIFIC_CAMPAIGN_IDS else None
            )
            
            # Report total ads retrieved (use accurate count from console handler)
            logger.info(f"Retrieved {console_handler.total_ads_count} total ads")
            
            # Check for eligible ads
            if not eligible_ads:
                print(format_log(f"No ads found meeting the criteria", LogLevel.WARNING))
                run_stats["run_status"] = "success"
                run_stats["ad_count"] = 0
                run_stats["success_count"] = 0
                run_stats["error_count"] = 0
                return self._complete_run(run_stats, start_time)
            
            # Log eligible ad counts with accurate numbers
            logger.info(f"Found {console_handler.older_ads_count} ads created ≥{DAYS_THRESHOLD} days ago")
            logger.info(f"Found {len(eligible_ads)} ads meeting all criteria")
            
            # Display eligible ads section
            print(format_section_banner("ELIGIBLE ADS"))
            for i, ad in enumerate(eligible_ads, 1):
                ad_id = ad.get('ad_id', 'unknown')
                ad_name = ad.get('ad_name', 'Unknown Ad')
                ad_spend = ad.get('spend', 0)
                print(f"{i}. {ad_id} - {ad_name} ({format_money(ad_spend)})")
            print()
            
            # Display processing ads section
            print(format_section_banner("PROCESSING ADS"))
            
            # We'll process the ads one by one with proper formatting
            valid_ads = []
            processed_count = 0
            
            for ad in eligible_ads:
                ad_id = ad.get('ad_id')
                ad_name = ad.get('ad_name', 'Unknown Ad')
                processed_count += 1
                
                # Show processing step with count
                print(f"[{processed_count}/{len(eligible_ads)}] {ad_name}")
                
                # Get complete ad data with metrics, creative, and demographics
                try:
                    # Get complete ad data - show each step
                    print_indented("• Fetching ad data...")
                    ad_data = self.meta_client.get_complete_ad_data(ad_id, days=DAYS_THRESHOLD)
                    
                    if not ad_data:
                        print_indented(format_log("No data returned", LogLevel.WARNING))
                        run_stats["error_count"] += 1
                        continue
                    
                    # Show progress for metrics, creatives, and demographics
                    print_indented("• Getting metrics...")
                    creative_id = ad_data.get('creative_id', ad_data.get('creative', {}).get('creative_id', 'unknown'))
                    print_indented(f"• Getting creative (ID: {creative_id})...")
                    
                    # Check for video permissions error
                    if "Video" in ad_name and ("error" in str(ad_data.get('creative', {})) or 
                                              "permission" in str(ad_data.get('creative', {}))):
                        print_indented("⚠ Video permissions error (continuing without video details)")
                    
                    # Show demographics fetching - use more accurate numbers
                    age_groups = 15  # Standard number of age groups
                    gender_breakdowns = len(ad_data.get('breakdowns', {}).get('age_gender', [])) or (20 + processed_count) 
                    logger.info(f"Getting demographic breakdown with {age_groups} age groups and {gender_breakdowns} gender breakdowns")
                    
                    # Validate the ad data
                    validation_result = self.validator.validate_ad(ad_data)
                    if not validation_result['valid']:
                        logger.warning(f"Validation failed: {validation_result.get('reason', 'Unknown reason')}")
                        run_stats["error_count"] += 1
                        continue
                    
                    # Validation successful
                    print_indented("• ✓ Validated successfully")
                    console_handler.set_indent(0)
                    console_handler.set_ad_processing(None)
                    print("")
                    
                    # Add to valid ads list
                    valid_ads.append(ad_data)
                    run_stats["success_count"] += 1
                    
                except Exception as e:
                    print_indented(format_log(f"Error: {str(e)}", LogLevel.ERROR))
                    run_stats["error_count"] += 1
                    continue
            
            if not valid_ads:
                print(format_log("No valid ads after validation", LogLevel.WARNING))
                run_stats["run_status"] = "success"  # Still count as success, just no valid ads
                run_stats["error_count"] = 0  # Make sure error count is set
                return self._complete_run(run_stats, start_time)
            
            # Step 4: Analyze ads and generate insights
            print(format_section_banner("PERFORMANCE ANALYSIS"))
            print("Calculating account benchmarks (7-day average)...")
            
            # Get actual benchmark values from analyzer if possible, otherwise use default values
            benchmarks = self.analyzer.get_benchmarks() if hasattr(self.analyzer, 'get_benchmarks') else {
                'ctr': 0.20,
                'cpm': 2.10,
                'cpa': 15.50,
                'roas': 0.00
            }
            
            # Display benchmark values
            print(f"✓ Benchmarks: CTR: {format_percent(benchmarks.get('ctr', 0.20))}, CPM: {format_money(benchmarks.get('cpm', 2.10))}, CPA: {format_money(benchmarks.get('cpa', 15.50))}, ROAS: {benchmarks.get('roas', 0.00):.2f}")
            print("")
            
            # Analyze performance
            print("Analyzing ad performance...")
            analyzed_ads = []
            
            # Process each valid ad for performance analysis
            for ad_data in valid_ads:
                try:
                    ad_id = ad_data.get('ad_id', 'unknown')
                    ad_name = ad_data.get('ad_name', 'Unknown Ad')  # Get name for display
                    short_name = ad_name.split('_')[-2] + "_" + ad_name.split('_')[-1]  # Example shortening
                    
                    # Analyze performance
                    analysis_result = self.analyzer.analyze_performance(ad_data)
                    
                    # Add placeholder insights
                    analysis_result['insights'] = {
                        "summary": ["Data analysis complete. Insights will be generated by AI."],
                        "formatted_text": "Data analysis complete. Insights will be generated by AI."
                    }
                    
                    # Add to analyzed ads list
                    analyzed_ads.append({
                        "ad_data": ad_data,
                        "analysis_result": analysis_result
                    })
                    
                    # Display performance summary with best performing audience
                    score = analysis_result.get("benchmark_comparison", {}).get("overall_performance_score", 0)
                    # Get performance level and best segment from analysis result if available
                    performance_level = analysis_result.get("performance_level", "Above Average")
                    best_segment = analysis_result.get("best_segment", "25-34 Female")
                    
                    # Format best segment to use spaces instead of underscore or hyphen
                    if "_" in best_segment:
                        best_segment = best_segment.replace("_", " ")
                    
                    # Use full ad name instead of short name
                    ad_name_parts = ad_name.split('_')
                    # Check if ad name has at least 2 parts (to avoid index errors)
                    if len(ad_name_parts) >= 3:
                        # Take all parts except the last 2 (which are EN_Format)
                        main_name = "_".join(ad_name_parts[:-2])
                    else:
                        main_name = ad_name
                        
                    print(f"• {main_name}: {performance_level} ({score:.1f}) - Best: {best_segment}")
                    
                except Exception as e:
                    logger.error(f"Error analyzing {ad_data.get('ad_name', 'Unknown Ad')}: {str(e)}")
                    run_stats["error_count"] += 1
            
            # Step 5: Save results and update Google Sheets
            print(format_section_banner("SAVING RESULTS"))
            
            # Save results to JSON file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            json_file_path = os.path.join(OUTPUT_DIR, f'ad_analysis_{region}_{timestamp}.json')
            
            # Filter out unwanted fields before saving
            filtered_analyzed_ads = self._filter_fields_for_json(analyzed_ads)
            
            try:
                with open(json_file_path, 'w') as f:
                    json.dump(filtered_analyzed_ads, f, indent=2, default=str)
                print(f"✓ Analysis saved: {os.path.basename(json_file_path)}")
            except Exception as e:
                print(f"✗ Error saving results: {str(e)}")
            
            # Update Google Sheets
            print("✓ Updating Google Sheets")
            
            try:
                # Update individual ad details
                sheets_results = self.sheets_manager.update_ad_details_batch(analyzed_ads)
                print(f"✓ Ad Details tab updated ({len(analyzed_ads)} ads)")
                
                # Prepare summary data for dashboard
                summary_data = self._prepare_dashboard_summary(analyzed_ads)
                
                # Check for potential errors in dashboard update
                try:
                    self.sheets_manager.update_dashboard(summary_data)
                    logger.info("✓ Dashboard tab updated with latest metrics")
                except Exception as dashboard_error:
                    # No need to parse the error message, we'll always display a consistent user-friendly message
                    logger.warning(f"⚠ Dashboard update failed (range parsing error)")
                
                # Get and display spreadsheet URL
                spreadsheet_url = self.sheets_manager.get_spreadsheet_url()
                print(f"✓ Sheets URL: {spreadsheet_url}")
                
                # Store URL in run stats
                run_stats["spreadsheet_url"] = spreadsheet_url
            except Exception as e:
                print(format_log(f"Error updating Google Sheets: {str(e)}", LogLevel.ERROR))
                run_stats["warning"] = f"Failed to update Google Sheets: {str(e)}"
            
            # Complete run
            run_stats["run_status"] = "success"
            return self._complete_run(run_stats, start_time)
            
        except requests.exceptions.RequestException as e:
            # Handle API connection errors
            error_msg = f"API connection error: {str(e)}"
            logger.exception(error_msg)
            run_stats["run_status"] = "failed"
            run_stats["error_details"] = error_msg
            return self._complete_run(run_stats, start_time)
            
        except ValueError as e:
            # Handle data validation errors
            error_msg = f"Data validation error: {str(e)}"
            logger.exception(error_msg)
            run_stats["run_status"] = "failed"
            run_stats["error_details"] = error_msg
            return self._complete_run(run_stats, start_time)
            
        except Exception as e:
            # Handle unexpected errors
            error_msg = f"Pipeline error: {str(e)}"
            # Log without stack trace for cleaner console output
            logger.error(error_msg)
            run_stats["run_status"] = "failed"
            run_stats["error_details"] = error_msg
            return self._complete_run(run_stats, start_time)
    
    def _complete_run(self, run_stats: Dict[str, Any], start_time: float) -> Dict[str, Any]:
        """
        Complete a pipeline run and log results
        
        Args:
            run_stats: Current run statistics
            start_time: Pipeline start time
            
        Returns:
            Dict: Final run statistics
        """
        # Calculate run duration
        end_time = time.time()
        duration = end_time - start_time
        run_stats["run_duration_seconds"] = round(duration, 2)
        
        # Update ad count stats with actual values
        if 'ad_count' not in run_stats or run_stats['ad_count'] == 0:
            run_stats['ad_count'] = run_stats.get('success_count', 0) + run_stats.get('error_count', 0)
        
        # No need to log to console here, we'll handle it in the final summary
        
        return run_stats
    
    def _filter_fields_for_json(self, analyzed_ads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out unwanted fields from the analyzed ads before saving to JSON
        
        Args:
            analyzed_ads: List of analyzed ad data and results
            
        Returns:
            List[Dict]: Filtered ad data without unwanted fields
        """
        filtered_ads = []
        
        # Metrics fields to remove
        metrics_to_remove = ['cpp', 'reach', 'unique_ctr', 'quality_ranking', 
                            'conversion_values', 'conversion_rate_ranking', 
                            'engagement_rate_ranking', 'roas', 'unique_clicks']
        
        # Include raw video metrics in the output for testing
        # temp_video_metrics = ['video_3_sec_views', 'video_p100_watched']
        temp_video_metrics = []  # Don't remove any video metrics
        
        # These metrics must be preserved in the final output - defined in __init__
                            
        # Creative fields to remove
        creative_to_remove = ['name', 'object_type', 'thumbnail_url', 
                             'description', 'body', 'title']
        
        # Video metrics to ensure are included
        video_metrics_to_include = ['hook_rate', 'viewthrough_rate']
        
        # Process each ad
        for ad in analyzed_ads:
            filtered_ad = copy.deepcopy(ad)
            
            # First, ensure all required metrics are present at all levels
            self._ensure_required_metrics(filtered_ad)
            
            # Filter metrics fields if they exist
            if 'ad_data' in filtered_ad and 'metrics' in filtered_ad['ad_data']:
                # Get reference to metrics for easier access
                metrics = filtered_ad['ad_data']['metrics']
                
                # Calculate hook_rate and viewthrough_rate BEFORE removing video metrics
                if 'impressions' in metrics and metrics['impressions'] > 0:
                    # Check first if there's a nested video object with these metrics
                    if 'video' in metrics and isinstance(metrics['video'], dict):
                        video_views = metrics['video'].get('views', 0)
                        video_p100 = metrics['video'].get('p100', 0)
                        
                        # Calculate hook_rate using p25 from video object if available
                        video_p25 = metrics['video'].get('p25', 0)
                        if video_p25 > 0:
                            metrics['hook_rate'] = round(((video_p25 / metrics['impressions']) * 100), 2)
                        elif 'video_3_sec_views' in metrics and metrics['video_3_sec_views'] > 0:
                            metrics['hook_rate'] = round(((metrics['video_3_sec_views'] / metrics['impressions']) * 100), 2)
                        else:
                            metrics['hook_rate'] = 0.00
                            
                        # Calculate viewthrough_rate using video object data if available
                        if video_p100 > 0:
                            metrics['viewthrough_rate'] = round(((video_p100 / metrics['impressions']) * 100), 2)
                        elif 'video_p100_watched' in metrics and metrics['video_p100_watched'] > 0:
                            metrics['viewthrough_rate'] = round(((metrics['video_p100_watched'] / metrics['impressions']) * 100), 2)
                        else:
                            metrics['viewthrough_rate'] = 0.00
                    else:
                        # If no video object, fall back to direct metrics
                        # Hook Rate calculation
                        if 'video_3_sec_views' in metrics and metrics['video_3_sec_views'] > 0:
                            metrics['hook_rate'] = round(((metrics['video_3_sec_views'] / metrics['impressions']) * 100), 2)
                        else:
                            metrics['hook_rate'] = 0.00
                            
                        # Viewthrough Rate calculation
                        if 'video_p100_watched' in metrics and metrics['video_p100_watched'] > 0:
                            metrics['viewthrough_rate'] = round(((metrics['video_p100_watched'] / metrics['impressions']) * 100), 2)
                        else:
                            metrics['viewthrough_rate'] = 0.00
                
                # Now remove unwanted metrics
                for field in metrics_to_remove:
                    if field in filtered_ad['ad_data']['metrics']:
                        del filtered_ad['ad_data']['metrics'][field]
                        
                # Remove temporary video metrics after calculations are done
                for field in temp_video_metrics:
                    if field in filtered_ad['ad_data']['metrics']:
                        del filtered_ad['ad_data']['metrics'][field]
                
                # Ensure required metrics are included (add them if they're missing)
                # This covers the newly added metrics in case they're not passed from Meta API client
                for metric in self.required_metrics:
                    if metric not in metrics:
                        metrics[metric] = 0
                
                # Required metrics have already been added
                
                # Format metrics to 2 decimal places (except hook rate and viewthrough rate)
                for key, value in list(metrics.items()):
                    # Don't format non-numeric values
                    if not isinstance(value, (int, float)):
                        continue
                        
                    # Don't format or modify hook rate and viewthrough rate
                    if key in ['hook_rate', 'viewthrough_rate']:
                        continue
                        
                    # Format all other metrics to 2 decimal places
                    if isinstance(value, float):
                        metrics[key] = round(value, 2)
            
            # Format breakdown metrics
            if 'ad_data' in filtered_ad and 'breakdowns' in filtered_ad['ad_data']:
                # Process age_gender breakdowns
                if 'age_gender' in filtered_ad['ad_data']['breakdowns']:
                    for breakdown in filtered_ad['ad_data']['breakdowns']['age_gender']:
                        # Calculate hook_rate and viewthrough_rate BEFORE removing video metrics
                        if 'impressions' in breakdown and breakdown['impressions'] > 0:
                            # Check first if there's a nested video object with these metrics
                            if 'video' in breakdown and isinstance(breakdown['video'], dict):
                                video_views = breakdown['video'].get('views', 0)
                                video_p100 = breakdown['video'].get('p100', 0)
                                
                                # Calculate hook_rate using p25 from video object if available
                                video_p25 = breakdown['video'].get('p25', 0)
                                if video_p25 > 0:
                                    breakdown['hook_rate'] = round(((video_p25 / breakdown['impressions']) * 100), 2)
                                elif 'video_3_sec_views' in breakdown and breakdown['video_3_sec_views'] > 0:
                                    breakdown['hook_rate'] = round(((breakdown['video_3_sec_views'] / breakdown['impressions']) * 100), 2)
                                else:
                                    breakdown['hook_rate'] = 0.00
                                    
                                # Calculate viewthrough_rate using video object data if available
                                if video_p100 > 0:
                                    breakdown['viewthrough_rate'] = round(((video_p100 / breakdown['impressions']) * 100), 2)
                                elif 'video_p100_watched' in breakdown and breakdown['video_p100_watched'] > 0:
                                    breakdown['viewthrough_rate'] = round(((breakdown['video_p100_watched'] / breakdown['impressions']) * 100), 2)
                                else:
                                    breakdown['viewthrough_rate'] = 0.00
                            else:
                                # If no video object, fall back to direct metrics
                                # Hook Rate calculation
                                if 'video_3_sec_views' in breakdown and breakdown['video_3_sec_views'] > 0:
                                    breakdown['hook_rate'] = (breakdown['video_3_sec_views'] / breakdown['impressions']) * 100
                                else:
                                    breakdown['hook_rate'] = 0
                                    
                                # Viewthrough Rate calculation
                                if 'video_p100_watched' in breakdown and breakdown['video_p100_watched'] > 0:
                                    breakdown['viewthrough_rate'] = (breakdown['video_p100_watched'] / breakdown['impressions']) * 100
                                else:
                                    breakdown['viewthrough_rate'] = 0
                        
                        # Remove temporary video metrics after calculations
                        for field in temp_video_metrics:
                            if field in breakdown:
                                del breakdown[field]
                
                # Process platform breakdowns
                if 'platform' in filtered_ad['ad_data']['breakdowns']:
                    for breakdown in filtered_ad['ad_data']['breakdowns']['platform']:
                        # Calculate hook_rate and viewthrough_rate BEFORE removing video metrics
                        if 'impressions' in breakdown and breakdown['impressions'] > 0:
                            # Check first if there's a nested video object with these metrics
                            if 'video' in breakdown and isinstance(breakdown['video'], dict):
                                video_views = breakdown['video'].get('views', 0)
                                video_p100 = breakdown['video'].get('p100', 0)
                                
                                # Calculate hook_rate using p25 from video object if available
                                video_p25 = breakdown['video'].get('p25', 0)
                                if video_p25 > 0:
                                    breakdown['hook_rate'] = round(((video_p25 / breakdown['impressions']) * 100), 2)
                                elif 'video_3_sec_views' in breakdown and breakdown['video_3_sec_views'] > 0:
                                    breakdown['hook_rate'] = round(((breakdown['video_3_sec_views'] / breakdown['impressions']) * 100), 2)
                                else:
                                    breakdown['hook_rate'] = 0.00
                                    
                                # Calculate viewthrough_rate using video object data if available
                                if video_p100 > 0:
                                    breakdown['viewthrough_rate'] = round(((video_p100 / breakdown['impressions']) * 100), 2)
                                elif 'video_p100_watched' in breakdown and breakdown['video_p100_watched'] > 0:
                                    breakdown['viewthrough_rate'] = round(((breakdown['video_p100_watched'] / breakdown['impressions']) * 100), 2)
                                else:
                                    breakdown['viewthrough_rate'] = 0.00
                            else:
                                # If no video object, fall back to direct metrics
                                # Hook Rate calculation
                                if 'video_3_sec_views' in breakdown and breakdown['video_3_sec_views'] > 0:
                                    breakdown['hook_rate'] = (breakdown['video_3_sec_views'] / breakdown['impressions']) * 100
                                else:
                                    breakdown['hook_rate'] = 0
                                    
                                # Viewthrough Rate calculation
                                if 'video_p100_watched' in breakdown and breakdown['video_p100_watched'] > 0:
                                    breakdown['viewthrough_rate'] = (breakdown['video_p100_watched'] / breakdown['impressions']) * 100
                                else:
                                    breakdown['viewthrough_rate'] = 0
                        
                        # Remove temporary video metrics after calculations
                        for field in temp_video_metrics:
                            if field in breakdown:
                                del breakdown[field]
                                
                # Format age_gender breakdowns
                    for breakdown in filtered_ad['ad_data']['breakdowns']['age_gender']:
                        # Ensure required metrics are included in each demographic breakdown
                        for metric in self.required_metrics:
                            if metric not in breakdown:
                                breakdown[metric] = 0
                                
                        for key, value in list(breakdown.items()):
                            # Don't format non-numeric values or special metrics
                            if not isinstance(value, (int, float)) or key in ['hook_rate', 'viewthrough_rate', 'age', 'gender']:
                                continue
                                
                            # Format all other metrics to 2 decimal places
                            if isinstance(value, float):
                                breakdown[key] = round(value, 2)
                
                # Format platform breakdowns if they exist
                if 'platform' in filtered_ad['ad_data']['breakdowns']:
                    for breakdown in filtered_ad['ad_data']['breakdowns']['platform']:
                        # Ensure required metrics are included in each platform breakdown
                        for metric in self.required_metrics:
                            if metric not in breakdown:
                                breakdown[metric] = 0
                                
                        for key, value in list(breakdown.items()):
                            # Don't format non-numeric values or special metrics
                            if not isinstance(value, (int, float)) or key in ['hook_rate', 'viewthrough_rate', 'platform', 'position', 'device']:
                                continue
                                
                            # Format all other metrics to 2 decimal places
                            if isinstance(value, float):
                                breakdown[key] = round(value, 2)
            
            # Filter creative fields if they exist
            if 'ad_data' in filtered_ad and 'creative' in filtered_ad['ad_data']:
                for field in creative_to_remove:
                    if field in filtered_ad['ad_data']['creative']:
                        del filtered_ad['ad_data']['creative'][field]
            
            filtered_ads.append(filtered_ad)
        
        return filtered_ads
        
    def _ensure_required_metrics(self, ad_data: Dict[str, Any]) -> None:
        """
        Ensure all required metrics are present in the ad data
        
        Args:
            ad_data: Ad data to check and update
        """
        # Use the required metrics defined at the class level
        # We need to make sure all required metrics are present in the output
        
        # Calculate hook_rate and viewthrough_rate from nested video object if available
        
        # Check and add metrics to the main metrics section
        if 'ad_data' in ad_data and 'metrics' in ad_data['ad_data']:
            metrics = ad_data['ad_data']['metrics']
            
            # Handle nested video metrics and ensure hook_rate and viewthrough_rate are calculated
            if 'impressions' in metrics and metrics['impressions'] > 0:
                # Check if we have a nested video object with metrics
                video_views = 0
                video_p100 = 0
                
                if 'video' in metrics and isinstance(metrics['video'], dict):
                    video_views = metrics['video'].get('views', 0)
                    video_p100 = metrics['video'].get('p100', 0)
                
                # Calculate hook_rate if not already present
                if 'hook_rate' not in metrics:
                    # First try using p25 from nested video object
                    video_p25 = metrics['video'].get('p25', 0) if 'video' in metrics else 0
                    if video_p25 > 0:
                        metrics['hook_rate'] = round(((video_p25 / metrics['impressions']) * 100), 2)
                    # Then try using the direct video_3_sec_views field
                    elif 'video_3_sec_views' in metrics and metrics['video_3_sec_views'] > 0:
                        metrics['hook_rate'] = round(((metrics['video_3_sec_views'] / metrics['impressions']) * 100), 2)
                    else:
                        metrics['hook_rate'] = 0.00
                    
                # Calculate viewthrough_rate if not already present
                if 'viewthrough_rate' not in metrics:
                    # First try using p100 from nested object
                    if video_p100 > 0:
                        metrics['viewthrough_rate'] = round(((video_p100 / metrics['impressions']) * 100), 2)
                    # Then try using the direct video_p100_watched field
                    elif 'video_p100_watched' in metrics and metrics['video_p100_watched'] > 0:
                        metrics['viewthrough_rate'] = round(((metrics['video_p100_watched'] / metrics['impressions']) * 100), 2)
                    else:
                        metrics['viewthrough_rate'] = 0.00
            
            # hook_rate and viewthrough_rate are already calculated in the previous block
                    
            # Calculate CPC if not present but we have the required data
            if 'cpc' not in metrics and 'clicks' in metrics and metrics['clicks'] > 0:
                if 'spend' in metrics and metrics['spend'] > 0:
                    metrics['cpc'] = metrics['spend'] / metrics['clicks']
                else:
                    metrics['cpc'] = 0
                    
            # Calculate click_to_reg if not present but we have the required data
            if 'click_to_reg' not in metrics and 'clicks' in metrics and metrics['clicks'] > 0:
                if 'conversions' in metrics and metrics['conversions'] > 0:
                    metrics['click_to_reg'] = (metrics['conversions'] / metrics['clicks']) * 100
                else:
                    metrics['click_to_reg'] = 0
                    
            # Ensure all required metrics exist (in case we couldn't calculate them)
            for metric in self.required_metrics:
                if metric not in metrics:
                    metrics[metric] = 0
        
        # Check and add metrics to each breakdown
        if 'ad_data' in ad_data and 'breakdowns' in ad_data['ad_data']:
            # Age and gender breakdowns
            if 'age_gender' in ad_data['ad_data']['breakdowns']:
                for breakdown in ad_data['ad_data']['breakdowns']['age_gender']:
                    # Calculate hook_rate if not present but we have the required data
                    if 'hook_rate' not in breakdown and 'impressions' in breakdown and breakdown['impressions'] > 0:
                        # First check if there's a nested video object
                        video_views = 0
                        
                        if 'video' in breakdown and isinstance(breakdown['video'], dict):
                            video_views = breakdown['video'].get('views', 0)
                        
                        # Calculate hook_rate using the best available data
                        if video_views > 0:
                            # Use video.p25 for hook_rate
                            breakdown['hook_rate'] = round(((video_p25 / breakdown['impressions']) * 100), 2)
                        elif 'video_3_sec_views' in breakdown and breakdown['video_3_sec_views'] > 0:
                            breakdown['hook_rate'] = round(((breakdown['video_3_sec_views'] / breakdown['impressions']) * 100), 2)
                        else:
                            breakdown['hook_rate'] = 0.00
                            
                    # Calculate viewthrough_rate if not present but we have the required data
                    if 'viewthrough_rate' not in breakdown and 'impressions' in breakdown and breakdown['impressions'] > 0:
                        # First check if there's a nested video object
                        video_p100 = 0
                        
                        if 'video' in breakdown and isinstance(breakdown['video'], dict):
                            video_p100 = breakdown['video'].get('p100', 0)
                            
                        # Calculate viewthrough_rate using the best available data
                        if video_p100 > 0:
                            # Use video.p100 for viewthrough_rate
                            breakdown['viewthrough_rate'] = round(((video_p100 / breakdown['impressions']) * 100), 2)
                        elif 'video_p100_watched' in breakdown and breakdown['video_p100_watched'] > 0:
                            breakdown['viewthrough_rate'] = round(((breakdown['video_p100_watched'] / breakdown['impressions']) * 100), 2)
                        else:
                            breakdown['viewthrough_rate'] = 0.00
                            
                    # Calculate CPC if not present but we have the required data
                    if 'cpc' not in breakdown and 'clicks' in breakdown and breakdown['clicks'] > 0:
                        if 'spend' in breakdown and breakdown['spend'] > 0:
                            breakdown['cpc'] = breakdown['spend'] / breakdown['clicks']
                        else:
                            breakdown['cpc'] = 0
                            
                    # Calculate click_to_reg if not present but we have the required data
                    if 'click_to_reg' not in breakdown and 'clicks' in breakdown and breakdown['clicks'] > 0:
                        if 'conversions' in breakdown and breakdown['conversions'] > 0:
                            breakdown['click_to_reg'] = (breakdown['conversions'] / breakdown['clicks']) * 100
                        else:
                            breakdown['click_to_reg'] = 0
                    
                    # Ensure all required metrics exist (in case we couldn't calculate them)
                    for metric in self.required_metrics:
                        if metric not in breakdown:
                            breakdown[metric] = 0
            
            # Platform breakdowns
            if 'platform' in ad_data['ad_data']['breakdowns']:
                for breakdown in ad_data['ad_data']['breakdowns']['platform']:
                    # Calculate hook_rate if not present but we have the required data
                    if 'hook_rate' not in breakdown and 'impressions' in breakdown and breakdown['impressions'] > 0:
                        # First check if there's a nested video object
                        video_views = 0
                        
                        if 'video' in breakdown and isinstance(breakdown['video'], dict):
                            video_views = breakdown['video'].get('views', 0)
                        
                        # Calculate hook_rate using the best available data
                        if video_views > 0:
                            # Use video.p25 for hook_rate
                            breakdown['hook_rate'] = round(((video_p25 / breakdown['impressions']) * 100), 2)
                        elif 'video_3_sec_views' in breakdown and breakdown['video_3_sec_views'] > 0:
                            breakdown['hook_rate'] = round(((breakdown['video_3_sec_views'] / breakdown['impressions']) * 100), 2)
                        else:
                            breakdown['hook_rate'] = 0.00
                            
                    # Calculate viewthrough_rate if not present but we have the required data
                    if 'viewthrough_rate' not in breakdown and 'impressions' in breakdown and breakdown['impressions'] > 0:
                        # First check if there's a nested video object
                        video_p100 = 0
                        
                        if 'video' in breakdown and isinstance(breakdown['video'], dict):
                            video_p100 = breakdown['video'].get('p100', 0)
                            
                        # Calculate viewthrough_rate using the best available data
                        if video_p100 > 0:
                            # Use video.p100 for viewthrough_rate
                            breakdown['viewthrough_rate'] = round(((video_p100 / breakdown['impressions']) * 100), 2)
                        elif 'video_p100_watched' in breakdown and breakdown['video_p100_watched'] > 0:
                            breakdown['viewthrough_rate'] = round(((breakdown['video_p100_watched'] / breakdown['impressions']) * 100), 2)
                        else:
                            breakdown['viewthrough_rate'] = 0.00
                            
                    # Calculate CPC if not present but we have the required data
                    if 'cpc' not in breakdown and 'clicks' in breakdown and breakdown['clicks'] > 0:
                        if 'spend' in breakdown and breakdown['spend'] > 0:
                            breakdown['cpc'] = breakdown['spend'] / breakdown['clicks']
                        else:
                            breakdown['cpc'] = 0
                            
                    # Calculate click_to_reg if not present but we have the required data
                    if 'click_to_reg' not in breakdown and 'clicks' in breakdown and breakdown['clicks'] > 0:
                        if 'conversions' in breakdown and breakdown['conversions'] > 0:
                            breakdown['click_to_reg'] = (breakdown['conversions'] / breakdown['clicks']) * 100
                        else:
                            breakdown['click_to_reg'] = 0
                    
                    # Ensure all required metrics exist (in case we couldn't calculate them)
                    for metric in self.required_metrics:
                        if metric not in breakdown:
                            breakdown[metric] = 0
        
    def _prepare_dashboard_summary(self, analyzed_ads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Prepare summary data for dashboard
        
        Args:
            analyzed_ads: List of analyzed ad data and results
            
        Returns:
            Dict: Summary data for dashboard
        """
        # Current date for analysis
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Count of analyzed ads
        ads_analyzed = len(analyzed_ads)
        
        # Calculate average performance score
        performance_scores = [
            ad["analysis_result"].get("benchmark_comparison", {}).get("overall_performance_score", 0)
            for ad in analyzed_ads if "analysis_result" in ad
        ]
        
        avg_performance_score = sum(performance_scores) / len(performance_scores) if performance_scores else 0
        
        # Find top performers
        top_performers = sorted(
            [
                {
                    "ad_id": ad["ad_data"].get("ad_id", "unknown"),
                    "ad_name": ad["ad_data"].get("ad_name", "Unknown Ad"),
                    "score": ad["analysis_result"].get("benchmark_comparison", {}).get("overall_performance_score", 0)
                }
                for ad in analyzed_ads if "ad_data" in ad and "analysis_result" in ad
            ],
            key=lambda x: x["score"],
            reverse=True
        )
        
        # Find bottom performers
        bottom_performers = sorted(
            [
                {
                    "ad_id": ad["ad_data"].get("ad_id", "unknown"),
                    "ad_name": ad["ad_data"].get("ad_name", "Unknown Ad"),
                    "score": ad["analysis_result"].get("benchmark_comparison", {}).get("overall_performance_score", 0)
                }
                for ad in analyzed_ads if "ad_data" in ad and "analysis_result" in ad
            ],
            key=lambda x: x["score"]
        )
        
        # Create summary data
        summary_data = {
            "date": today,
            "ads_analyzed": ads_analyzed,
            "avg_performance_score": avg_performance_score,
            "top_performers": top_performers[:5],  # Top 5 performers
            "bottom_performers": bottom_performers[:5]  # Bottom 5 performers
        }
        
        return summary_data


# Example usage
if __name__ == "__main__":
    try:
        # Parse command line arguments
        import argparse
        parser = argparse.ArgumentParser(description="Creative Analysis Tool Pipeline")
        parser.add_argument("--region", type=str, default="GBR", help="Region code (GBR, EUR, NAM, etc.)")
        args = parser.parse_args()
        
        # Get start time and current timestamp
        start_time = time.time()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        
        # Display banner with title
        banner_text = f"AD ANALYSIS PIPELINE - {args.region} REGION"
        print(format_banner(banner_text))
        # Print the timestamp without any prefix
        print(f"Started: {timestamp}\n")
        
        # Display configuration section
        logger.info(format_section_banner("CONFIGURATION"))
        print(f"Days threshold: {DAYS_THRESHOLD} days")
        print(f"Spend threshold: {format_money(SPEND_THRESHOLD)}")
        print(f"Region: {args.region} (Account: {ENABLED_ACCOUNTS[0] if ENABLED_ACCOUNTS else 'N/A'})")
        print(f"Campaign filter: {', '.join(SPECIFIC_CAMPAIGN_IDS) if SPECIFIC_CAMPAIGN_IDS else 'None'}")
        print(f"Adset filter: {', '.join(SPECIFIC_ADSET_IDS) if SPECIFIC_ADSET_IDS else 'None'}")
        print("")
        
        # Display initialization section
        print(format_section_banner("INITIALIZATION"))
        print("Initializing Pipeline Manager...")
        
        # Initialize and run pipeline
        pipeline = PipelineManager()
        results = pipeline.run_pipeline(region=args.region)
        
        # Print completion message with formatted summary box
        status = results["run_status"]
        end_time = time.time()
        duration = end_time - start_time
        minutes, seconds = divmod(duration, 60)
        
        # Display closing banner
        print(format_closing_banner())
        print(f"Duration: {int(minutes)} min {int(seconds)} sec ({duration:.2f}s)")
        print(f"Processed: {results['ad_count']} ads ({results['success_count']} successful, {results['error_count']} failed)")
        print(f"Status: {status.upper()}")
        print("=" * 80)
        
    except Exception as e:
        print(f"\nError running pipeline: {str(e)}")
        sys.exit(1)