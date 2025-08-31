#!/usr/bin/env python3
"""
Debug MVP Script

This script tests each stage of the ad analysis pipeline:
1. Pull benchmarks for an account
2. Pull ad data (recent ads with sufficient spend or fallback)
3. Perform analysis against benchmarks
4. Log results to a JSON file

Usage:
    python debug_mvp.py [--region REGION] [--days DAYS] [--spend SPEND] [--limit LIMIT]
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import required components
from src.meta_api_client import MetaApiClient
from src.data_validator import DataValidator
from src.performance_analyzer import PerformanceAnalyzer
from src.sheets_formatter import SheetsFormatter
# Insight generator removed - will be replaced with AI
from config.settings import SPEND_THRESHOLD, DAYS_THRESHOLD

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_account_benchmarks(client: MetaApiClient, days: int = 30) -> Dict[str, Any]:
    """
    Get account-level benchmark metrics
    
    Args:
        client: Initialized MetaApiClient
        days: Number of days to analyze
        
    Returns:
        Dict: Benchmarks for the account
    """
    logger.info(f"Getting account benchmarks for the past {days} days")
    
    try:
        # Get account insights using client
        account_metrics = client.get_account_insights(days=days)
        
        if not account_metrics:
            logger.warning("No metrics data available for benchmark calculation")
            return {}
            
        logger.info("Successfully retrieved account metrics for benchmark calculation")
        
        # Create benchmark dictionary
        benchmarks = {
            "ctr": account_metrics.get('ctr', 1.5),
            "cpa": account_metrics.get('cost_per_conversion', 25.0),
            "roas": account_metrics.get('roas', 3.0),
            "cpm": account_metrics.get('cpm', 15.0),
            "conversion_rate": account_metrics.get('conversion_rate', 2.0),
            "hook_rate": account_metrics.get('hook_rate', 5.0),
            "viewthrough_rate": account_metrics.get('viewthrough_rate', 1.2)
        }
        
        # Log benchmark values
        for key, value in benchmarks.items():
            logger.info(f"Benchmark {key}: {value}")
            
        return benchmarks
        
    except Exception as e:
        logger.error(f"Error retrieving account benchmarks: {str(e)}")
        return {}

def get_ad_data(client: MetaApiClient, days: int, min_spend: float, limit: int) -> List[Dict[str, Any]]:
    """
    Get ad data with fallback mechanisms
    
    Args:
        client: Initialized MetaApiClient
        days: Number of days to analyze
        min_spend: Minimum spend threshold
        limit: Maximum number of ads to retrieve
        
    Returns:
        List[Dict]: List of ad data
    """
    logger.info(f"Finding ads with minimum spend of £{min_spend} over the past {days} days")
    
    try:
        # Step 1: Try to find ads with sufficient spend over the past N days
        eligible_ads = client.find_ads_with_spend(
            days=days,
            min_spend=min_spend,
            limit=limit
        )
        
        # Fallback mechanism if no ads found
        if not eligible_ads:
            logger.warning("No ads found with sufficient spend, trying alternative methods...")
            
            # Try looking for ads created exactly 7 days ago
            logger.info("Trying to find ads created exactly 7 days ago...")
            eligible_ads = client.get_eligible_ads(days_threshold=7)
            
            # If still no results, try any recent ads
            if not eligible_ads:
                logger.warning("No ads created exactly 7 days ago, trying any recent ads...")
                eligible_ads = client.get_any_recent_ads(days=30, limit=limit)
        
        if not eligible_ads:
            logger.error("No eligible ads found for analysis")
            return []
            
        logger.info(f"Found {len(eligible_ads)} eligible ads for analysis")
        
        # Get complete ad data for each eligible ad
        logger.info("Getting complete ad data for analysis...")
        complete_ads_data = []
        
        for ad in eligible_ads[:min(5, len(eligible_ads))]:  # Limit to 5 ads for testing
            ad_id = ad.get('ad_id')
            try:
                logger.info(f"Getting complete data for ad {ad_id}")
                ad_data = client.get_complete_ad_data(ad_id, days=days)
                
                if ad_data:
                    complete_ads_data.append(ad_data)
                    logger.info(f"Successfully retrieved complete data for ad {ad_id}")
                else:
                    logger.warning(f"No data returned for ad {ad_id}")
            except Exception as e:
                logger.error(f"Error getting complete data for ad {ad_id}: {str(e)}")
        
        return complete_ads_data
        
    except Exception as e:
        logger.error(f"Error getting ad data: {str(e)}")
        return []

def analyze_ads(ads_data: List[Dict[str, Any]], benchmarks: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Analyze ads using performance analyzer and insight generator
    
    Args:
        ads_data: List of ad data
        benchmarks: Benchmark metrics
        
    Returns:
        List[Dict]: List of analyzed ads with insights
    """
    logger.info(f"Analyzing {len(ads_data)} ads against benchmarks")
    
    try:
        # Initialize components
        validator = DataValidator()
        analyzer = PerformanceAnalyzer()  # Initialize without benchmarks file
        
        # Set benchmarks in the analyzer directly
        analyzer.benchmarks = {"benchmarks": benchmarks}
        
        # Process each ad
        analyzed_ads = []
        
        for ad_data in ads_data:
            ad_id = ad_data.get('ad_id', 'unknown')
            
            try:
                # Validate the ad data
                validation_result = validator.validate_ad(ad_data)
                if not validation_result['valid']:
                    logger.warning(f"Ad {ad_id} failed validation: {validation_result.get('reason', 'Unknown reason')}")
                    continue
                
                logger.info(f"Ad {ad_id} passed validation")
                
                # Analyze performance
                analysis_result = analyzer.analyze_performance(ad_data)
                
                # Insights generation removed - will be replaced with AI
                # Add placeholder insights
                analysis_result['insights'] = {
                    "summary": ["Data analysis complete. Insights will be generated by AI."],
                    "formatted_text": "Data analysis complete. Insights will be generated by AI."
                }
                
                # Add demographics field if it doesn't exist (for new formatter)
                if "creative" not in ad_data:
                    ad_data["creative"] = {}
                    
                if "breakdowns" not in ad_data:
                    ad_data["breakdowns"] = {}
                    
                # Add to analyzed ads
                analyzed_ads.append({
                    "ad_data": ad_data,
                    "analysis_result": analysis_result
                })
                
                logger.info(f"Successfully analyzed ad {ad_id}")
                
            except Exception as e:
                logger.error(f"Error analyzing ad {ad_id}: {str(e)}")
        
        logger.info(f"Completed analysis of {len(analyzed_ads)} ads")
        return analyzed_ads
        
    except Exception as e:
        logger.error(f"Error during ad analysis: {str(e)}")
        return []

def log_results(analyzed_ads: List[Dict[str, Any]], region: str) -> str:
    """
    Log results to JSON and CSV files
    
    Args:
        analyzed_ads: List of analyzed ads with insights
        region: Region code
        
    Returns:
        str: Path to the output file
    """
    if not analyzed_ads:
        logger.warning("No analyzed ads to log")
        return ""
    
    try:
        # Create output directory if it doesn't exist
        output_dir = project_root / "tests" / "output"
        output_dir.mkdir(exist_ok=True)
        
        # Create timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create output file paths
        json_path = output_dir / f"ad_analysis_{region}_{timestamp}.json"
        
        # Write results to JSON file
        with open(json_path, 'w') as f:
            json.dump(analyzed_ads, f, indent=2, default=str)
        
        logger.info(f"Results logged to {json_path}")
        
        # Also export to CSV using SheetsFormatter
        try:
            # Initialize formatter with our output directory
            formatter = SheetsFormatter(output_dir=str(output_dir))
            
            # Format the data according to new specifications
            formatted_ads = formatter.format_ad_data_for_sheets(analyzed_ads)
            
            # Export to CSV for local testing
            csv_path = formatter.export_to_csv(formatted_ads, f"ad_analysis_{region}_{timestamp}.csv")
            
            logger.info(f"Formatted results exported to CSV: {csv_path}")
        except Exception as csv_error:
            logger.error(f"Error exporting to CSV: {str(csv_error)}")
        
        return str(json_path)
        
    except Exception as e:
        logger.error(f"Error logging results: {str(e)}")
        return ""

def run_pipeline(region: str = "GBR", days: int = DAYS_THRESHOLD, 
                min_spend: float = SPEND_THRESHOLD, limit: int = 5) -> Dict[str, Any]:
    """
    Run the complete analysis pipeline
    
    Args:
        region: Region code
        days: Number of days to analyze
        min_spend: Minimum spend threshold
        limit: Maximum number of ads to process
        
    Returns:
        Dict: Pipeline run results
    """
    start_time = datetime.now()
    
    logger.info(f"Starting pipeline execution for region {region}")
    logger.info(f"Parameters: days={days}, min_spend={min_spend}, limit={limit}")
    
    # Initialize result stats
    run_stats = {
        "run_id": f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "region": region,
        "days_analyzed": days,
        "min_spend": min_spend,
        "ad_limit": limit,
        "start_time": start_time.isoformat(),
        "run_status": "in_progress"
    }
    
    try:
        # Step 1: Initialize Meta API client
        logger.info(f"Initializing Meta API client for region {region}")
        client = MetaApiClient(region=region)
        
        # Test connection
        logger.info("Testing Meta API connection")
        if not client.test_connection():
            run_stats["run_status"] = "failed"
            run_stats["error"] = "Failed to connect to Meta API"
            logger.error("Failed to connect to Meta API")
            return run_stats
        
        # Step 2: Get account benchmarks
        logger.info("Getting account benchmarks")
        benchmarks = get_account_benchmarks(client, days)
        
        if not benchmarks:
            logger.warning("Using default benchmarks due to missing account benchmarks")
            # Use default benchmarks if we couldn't get account benchmarks
            benchmarks = {
                "ctr": 1.5,
                "cpa": 25.0,
                "roas": 3.0,
                "cpm": 15.0,
                "conversion_rate": 2.0,
                "hook_rate": 5.0,
                "viewthrough_rate": 1.2
            }
        
        run_stats["benchmarks"] = benchmarks
        
        # Step 3: Get ad data
        logger.info("Getting ad data")
        ads_data = get_ad_data(client, days, min_spend, limit)
        
        if not ads_data:
            run_stats["run_status"] = "failed"
            run_stats["error"] = "No eligible ads found for analysis"
            logger.error("No eligible ads found for analysis")
            return run_stats
        
        run_stats["ads_found"] = len(ads_data)
        
        # Step 4: Analyze ads
        logger.info("Analyzing ads")
        analyzed_ads = analyze_ads(ads_data, benchmarks)
        
        if not analyzed_ads:
            run_stats["run_status"] = "failed"
            run_stats["error"] = "Failed to analyze any ads"
            logger.error("Failed to analyze any ads")
            return run_stats
        
        run_stats["ads_analyzed"] = len(analyzed_ads)
        
        # Step 5: Log results
        logger.info("Logging results")
        output_path = log_results(analyzed_ads, region)
        
        if not output_path:
            run_stats["run_status"] = "completed_with_errors"
            run_stats["error"] = "Failed to log results"
            logger.error("Failed to log results")
        else:
            run_stats["output_path"] = output_path
            run_stats["run_status"] = "completed"
        
        # Record end time and duration
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        run_stats["end_time"] = end_time.isoformat()
        run_stats["duration_seconds"] = duration
        
        logger.info(f"Pipeline execution completed in {duration:.2f} seconds")
        
        return run_stats
        
    except Exception as e:
        import traceback
        logger.error(f"Error during pipeline execution: {str(e)}")
        logger.error(traceback.format_exc())
        
        run_stats["run_status"] = "failed"
        run_stats["error"] = str(e)
        
        return run_stats

def print_summary(run_stats: Dict[str, Any]) -> None:
    """Print a summary of the pipeline run"""
    print("\n" + "=" * 50)
    print(f"PIPELINE RUN SUMMARY")
    print("=" * 50)
    
    status = run_stats.get("run_status", "unknown")
    status_display = {
        "completed": "✅ COMPLETED",
        "completed_with_errors": "⚠️ COMPLETED WITH ERRORS",
        "failed": "❌ FAILED"
    }.get(status, status.upper())
    
    print(f"\nStatus: {status_display}")
    print(f"Region: {run_stats.get('region', 'unknown')}")
    
    # Print timing information
    start_time = run_stats.get('start_time')
    duration = run_stats.get('duration_seconds', 0)
    print(f"Duration: {duration:.2f} seconds")
    
    # Print count information
    print(f"\nAds found: {run_stats.get('ads_found', 0)}")
    print(f"Ads analyzed: {run_stats.get('ads_analyzed', 0)}")
    
    # Print error if any
    if "error" in run_stats:
        print(f"\nError: {run_stats['error']}")
    
    # Print output path if available
    if "output_path" in run_stats:
        print(f"\nOutput saved to: {run_stats['output_path']}")
        
        # Check for CSV file
        csv_path = run_stats['output_path'].replace('.json', '.csv')
        if os.path.exists(csv_path):
            print(f"CSV export saved to: {csv_path}")
    
    print("\n" + "=" * 50)

def get_user_input():
    """Get configuration from user via terminal prompts"""
    # Print header
    print("\n" + "=" * 50)
    print("DEBUG MVP - AD ANALYSIS PIPELINE TEST")
    print("=" * 50)
    
    # Define valid regions
    valid_regions = ["GBR", "ASI", "EUR", "LAT", "NAM", "PAC"]
    
    # Get region
    region = "GBR"  # Default
    try:
        print(f"\nAvailable regions: {', '.join(valid_regions)}")
        region_input = input(f"Enter region code [{region}]: ").strip().upper()
        if region_input and region_input in valid_regions:
            region = region_input
        print(f"Using region: {region}")
    except KeyboardInterrupt:
        print("\nUsing default region: GBR")
    
    # Get days threshold
    days = DAYS_THRESHOLD  # Default from settings
    try:
        days_input = input(f"Enter days to analyze [{days}]: ").strip()
        if days_input and days_input.isdigit():
            days = int(days_input)
        print(f"Analyzing past {days} days")
    except KeyboardInterrupt:
        print(f"\nUsing default days: {days}")
    
    # Get spend threshold
    spend = SPEND_THRESHOLD  # Default from settings
    try:
        spend_input = input(f"Enter minimum spend threshold (£) [{spend}]: ").strip()
        if spend_input and spend_input.replace('.', '', 1).isdigit():
            spend = float(spend_input)
        print(f"Using spend threshold: £{spend}")
    except KeyboardInterrupt:
        print(f"\nUsing default spend threshold: £{spend}")
    
    # Get ad limit
    limit = 5  # Default
    try:
        limit_input = input(f"Enter maximum number of ads to process [{limit}]: ").strip()
        if limit_input and limit_input.isdigit():
            limit = int(limit_input)
        print(f"Processing up to {limit} ads")
    except KeyboardInterrupt:
        print(f"\nUsing default limit: {limit}")
    
    # Final confirmation
    try:
        print("\nConfiguration summary:")
        print(f"- Region: {region}")
        print(f"- Days to analyze: {days}")
        print(f"- Minimum spend: £{spend}")
        print(f"- Maximum ads: {limit}")
        
        confirm = input("\nRun pipeline with these settings? (y/n) [y]: ").strip().lower()
        if confirm and confirm != "y" and confirm != "yes":
            print("\nExiting without running pipeline")
            sys.exit(0)
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    
    return {
        "region": region,
        "days": days,
        "min_spend": spend,
        "limit": limit
    }

if __name__ == "__main__":
    # Check if arguments are provided (for backward compatibility)
    if len(sys.argv) > 1:
        # Use argparse for backward compatibility
        parser = argparse.ArgumentParser(description="Debug Ad Analysis Pipeline")
        parser.add_argument("region", nargs="?", default="GBR", help="Region code (default: GBR)")
        parser.add_argument("days", nargs="?", type=int, default=DAYS_THRESHOLD, help=f"Days to analyze (default: {DAYS_THRESHOLD})")
        parser.add_argument("spend", nargs="?", type=float, default=SPEND_THRESHOLD, help=f"Minimum spend threshold (default: {SPEND_THRESHOLD})")
        parser.add_argument("limit", nargs="?", type=int, default=5, help="Maximum number of ads to process (default: 5)")
        parser.add_argument("--non-interactive", action="store_true", help="Run with default settings without prompting")
        args = parser.parse_args()
        
        config = {
            "region": args.region,
            "days": args.days,
            "min_spend": args.spend,
            "limit": args.limit
        }
        
        print(f"\nRunning pipeline with command line arguments:")
        print(f"- Region: {config['region']}")
        print(f"- Days: {config['days']}")
        print(f"- Minimum spend: £{config['min_spend']}")
        print(f"- Maximum ads: {config['limit']}")
    else:
        # For testing - use default values to avoid interactive input
        use_defaults = True  # Change to False to use interactive mode
        
        if use_defaults:
            config = {
                "region": "GBR",
                "days": DAYS_THRESHOLD,
                "min_spend": SPEND_THRESHOLD,
                "limit": 5
            }
            print(f"\nRunning pipeline with default settings:")
            print(f"- Region: {config['region']}")
            print(f"- Days: {config['days']}")
            print(f"- Minimum spend: £{config['min_spend']}")
            print(f"- Maximum ads: {config['limit']}")
        else:
            # Get configuration from user via terminal
            config = get_user_input()
    
    # Run the pipeline
    print(f"\nRunning debug pipeline for {config['region']} region...\n")
    run_stats = run_pipeline(
        region=config['region'],
        days=config['days'],
        min_spend=config['min_spend'],
        limit=config['limit']
    )
    
    # Print summary
    print_summary(run_stats)