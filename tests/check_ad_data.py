#!/usr/bin/env python3
"""
Test script to validate ad data analysis and export functionality.

This script:
1. Fetches ad data from Meta API
2. Tests whether the required metrics are available
3. Performs performance analysis using the main script functions
4. Exports the results to a CSV file
5. Logs the process using the same format as the main script

It provides a way to test the analysis pipeline without running the full application.
"""

import os
import sys
import json
import csv
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Import required components
from src.meta_api_client import MetaApiClient
from src.data_validator import DataValidator
from src.performance_analyzer import PerformanceAnalyzer
# Insight generator removed - will be replaced with AI

# Set up logging with the same format as the main script
# Use config folder for log files
config_dir = os.path.join(project_root, 'config')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(config_dir, 'analysis_test.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def check_metrics_availability(ad_id=None):
    """Test whether required metrics can be accessed from Meta API"""
    client = MetaApiClient(
        ad_account_id="1042125899190941"  # Use the known working account ID for testing
    )
    
    print("\n=== META API METRICS AVAILABILITY TEST ===")
    
    # Test connection first
    print("\n1. Testing API Connection...")
    try:
        client.test_connection()
        print("✓ Connected successfully to Meta API")
    except Exception as e:
        print(f"✗ ERROR: Failed to connect to Meta API: {str(e)}")
        return False
    
    # Get account info
    print("\n2. Retrieving Account Information...")
    try:
        account_info = client.get_account_info()
        print("✓ Account information retrieved successfully")
        print(f"  Account Name: {account_info.get('name')}")
        print(f"  Currency: {account_info.get('currency')}")
    except Exception as e:
        print(f"✗ ERROR: Failed to get account info: {str(e)}")
        return False
    
    # Get recent ads to test with - using improved methods with proper limits
    print("\n3. Finding Suitable Ads for Testing...")
    try:
        # If an ad_id is provided, use it directly
        if ad_id:
            print(f"  Using provided ad ID: {ad_id}")
            # Get basic ad info
            ad_url = f"{client.base_url}/{ad_id}"
            ad_params = {
                "access_token": client.access_token,
                "fields": "id,name,campaign{id,name},adset{id,name},created_time,status"
            }
            try:
                ad_info = client._make_api_request(ad_url, ad_params)
                high_spend_ads = [{
                    "ad_id": ad_info.get('id'),
                    "ad_name": ad_info.get('name'),
                    "campaign_name": ad_info.get('campaign', {}).get('name'),
                    "created_time": ad_info.get('created_time'),
                    "status": ad_info.get('status')
                }]
                print(f"  Using ad '{high_spend_ads[0].get('ad_name')}' (ID: {ad_id}) for testing")
            except Exception as e:
                print(f"  Error getting ad info: {str(e)}")
                high_spend_ads = []
        else:
            # Use the new find_ads_with_spend method to find ads with sufficient spend
            from config.settings import SPEND_THRESHOLD, DAYS_THRESHOLD
            min_spend = SPEND_THRESHOLD
            
            print(f"  Looking for ads with minimum spend of £{min_spend} over the past {DAYS_THRESHOLD} days (excluding today)...")
            high_spend_ads = client.find_ads_with_spend(days=DAYS_THRESHOLD, min_spend=min_spend, limit=5)
            
            if not high_spend_ads:
                print("  No ads found with sufficient spend, trying ads from exactly 7 days ago...")
                eligible_ads = client.get_eligible_ads(days_threshold=7)
                
                if eligible_ads:
                    high_spend_ads = eligible_ads
                else:
                    print("  No ads found from exactly 7 days ago either, trying any recent ads...")
                    high_spend_ads = client.get_any_recent_ads(days=30, limit=3)
            
            if high_spend_ads:
                eligible_ads = high_spend_ads
        
        if not eligible_ads:
            print("✗ ERROR: No suitable ads found for testing")
            return False
        
        test_ad = eligible_ads[0]
        ad_id = test_ad.get('ad_id')
        
        print(f"✓ Found {len(eligible_ads)} suitable ads for testing")
        print(f"  Using ad '{test_ad.get('ad_name')}' (ID: {ad_id}) for testing")
        
        # Test required metrics
        print("\n4. Testing Required Metrics...")
        try:
            metrics = client.get_comprehensive_ad_metrics(ad_id, days=7)
            
            if not metrics:
                print(f"✗ ERROR: No metrics data found for ad {ad_id}")
                return False
                
            print("✓ Successfully retrieved metrics")
            
            # Calculate additional metrics for video ads
            impressions = metrics.get('impressions', 0)
            if impressions > 0:
                # Hook Rate: 3-second views / impressions
                three_sec_views = metrics.get('video_3_sec_views', 0)
                if three_sec_views:
                    hook_rate = (three_sec_views / impressions) * 100
                    metrics['hook_rate'] = hook_rate
                
                # Viewthrough Rate: 100% Views / Impressions
                p100_views = metrics.get('video_p100_watched', 0)
                if p100_views:
                    viewthrough_rate = (p100_views / impressions) * 100
                    metrics['viewthrough_rate'] = viewthrough_rate
            
            # Check which metrics are available
            available_metrics = 0
            total_metrics = 12  # Total number of metrics we're checking (added 2 new ones)
            
            metric_checks = [
                ("Date Launched", metrics.get('date_launched') is not None),
                ("Media Spend", metrics.get('spend') is not None),
                ("CPM", metrics.get('cpm') is not None),
                ("Impressions", metrics.get('impressions') is not None),
                ("3 Second Views", metrics.get('video_3_sec_views') is not None),
                ("100% Video Watches", metrics.get('video_p100_watched') is not None),
                ("Hook Rate", metrics.get('hook_rate') is not None),
                ("Viewthrough Rate", metrics.get('viewthrough_rate') is not None),
                ("CTR (Destination)", metrics.get('ctr_destination') is not None),
                ("CPC", metrics.get('cpc') is not None),
                ("Registrations", metrics.get('registrations') is not None),
                ("CPR", metrics.get('cpr') is not None)
            ]
            
            print("\n  Available Metrics:")
            for name, is_available in metric_checks:
                status = "✓" if is_available else "✗"
                if is_available:
                    available_metrics += 1
                print(f"  {status} {name}")
            
            print(f"\n  {available_metrics} of {total_metrics} metrics are available")
            
            # Show detailed ad data for visual inspection
            print("\n  DETAILED AD DATA:")
            print(f"  Ad Name: {test_ad.get('ad_name')}")
            print(f"  Ad ID: {ad_id}")
            print(f"  Campaign: {test_ad.get('campaign_name')}")
            print(f"  Created: {metrics.get('date_launched', 'Unknown')}")
            print(f"  Status: {test_ad.get('status', 'Unknown')}")
            
            print("\n  Performance Metrics (past 7 days):")
            print(f"  - Spend: £{metrics.get('spend', 0):.2f}")
            print(f"  - Impressions: {metrics.get('impressions', 0):,}")
            print(f"  - CPM: £{metrics.get('cpm', 0):.2f}")
            print(f"  - Clicks: {metrics.get('clicks', 0):,}")
            print(f"  - CPC: £{metrics.get('cpc', 0):.2f}")
            print(f"  - CTR: {metrics.get('ctr_destination', 0):.2f}%")
            
            print("\n  Video Metrics:")
            print(f"  - 3 Second Views: {metrics.get('video_3_sec_views', 0):,}")
            print(f"  - 100% Views: {metrics.get('video_p100_watched', 0):,}")
            if 'hook_rate' in metrics:
                print(f"  - Hook Rate: {metrics.get('hook_rate', 0):.2f}%")
            if 'viewthrough_rate' in metrics:
                print(f"  - Viewthrough Rate: {metrics.get('viewthrough_rate', 0):.2f}%")
            
            print("\n  Conversion Metrics:")
            print(f"  - Registrations: {metrics.get('registrations', 0):,}")
            if metrics.get('registrations', 0) > 0 and metrics.get('spend', 0) > 0:
                print(f"  - Cost Per Registration: £{metrics.get('cpr', 0):.2f}")
        except Exception as e:
            print(f"✗ ERROR: Problem getting metrics: {str(e)}")
            return False
        
        # Test demographic breakdowns
        print("\n5. Testing Demographic Breakdowns...")
        try:
            breakdowns = client.get_metrics_with_demographics(ad_id, days=7)
            
            if breakdowns:
                breakdown_types = []
                if 'age' in breakdowns:
                    breakdown_types.append("Age")
                if 'gender' in breakdowns:
                    breakdown_types.append("Gender")
                if 'age_gender' in breakdowns:
                    breakdown_types.append("Age+Gender")
                    
                print(f"✓ Successfully retrieved demographic breakdowns")
                print(f"  Available breakdown types: {', '.join(breakdown_types)}")
                
                # Display demographic breakdowns
                print("\n  DEMOGRAPHIC BREAKDOWN:")
                
                # Gender breakdown
                if 'gender' in breakdowns:
                    print("\n  Gender Breakdown:")
                    for item in breakdowns['gender']:
                        gender = item.get('gender', 'Unknown')
                        spend = item.get('spend', 0)
                        impressions = item.get('impressions', 0)
                        ctr = item.get('ctr_destination', 0)
                        registrations = item.get('registrations', 0)
                        
                        print(f"  - {gender}:")
                        print(f"    • Spend: £{spend:.2f}")
                        print(f"    • Impressions: {impressions:,}")
                        print(f"    • CTR: {ctr:.2f}%")
                        print(f"    • Registrations: {registrations:,}")
                        
                        # Calculate additional metrics if possible
                        if impressions > 0:
                            cpm = (spend / impressions) * 1000
                            print(f"    • CPM: £{cpm:.2f}")
                        
                        if registrations > 0:
                            cpr = spend / registrations
                            print(f"    • CPR: £{cpr:.2f}")
                
                # Age breakdown (top 5 age groups)
                if 'age' in breakdowns:
                    print("\n  Age Breakdown (top groups by spend):")
                    # Sort by spend and take top 5
                    sorted_ages = sorted(breakdowns['age'], key=lambda x: x.get('spend', 0), reverse=True)[:5]
                    for item in sorted_ages:
                        age = item.get('age', 'Unknown')
                        spend = item.get('spend', 0)
                        impressions = item.get('impressions', 0)
                        ctr = item.get('ctr_destination', 0)
                        registrations = item.get('registrations', 0)
                        
                        print(f"  - {age}:")
                        print(f"    • Spend: £{spend:.2f}")
                        print(f"    • Impressions: {impressions:,}")
                        print(f"    • CTR: {ctr:.2f}%")
                        print(f"    • Registrations: {registrations:,}")
                
                # Combined Age + Gender (top 3)
                if 'age_gender' in breakdowns:
                    print("\n  Top 3 Age+Gender Combinations (by spend):")
                    # Sort by spend and take top 3
                    sorted_combos = sorted(breakdowns['age_gender'], key=lambda x: x.get('spend', 0), reverse=True)[:3]
                    for item in sorted_combos:
                        age = item.get('age', 'Unknown')
                        gender = item.get('gender', 'Unknown')
                        spend = item.get('spend', 0)
                        impressions = item.get('impressions', 0)
                        ctr = item.get('ctr_destination', 0)
                        registrations = item.get('registrations', 0)
                        
                        print(f"  - {age} {gender}:")
                        print(f"    • Spend: £{spend:.2f}")
                        print(f"    • Impressions: {impressions:,}")
                        print(f"    • CTR: {ctr:.2f}%")
                        print(f"    • Registrations: {registrations:,}")
            else:
                print("✗ ERROR: Failed to retrieve demographic breakdowns")
                return False
        except Exception as e:
            print(f"✗ ERROR: Problem getting demographic breakdowns: {str(e)}")
            return False
        
        # Summary of what's available
        print("\n=== METRICS AVAILABILITY SUMMARY ===")
        
        availability = {
            "Date Launched": metrics.get('date_launched') is not None,
            "Media Spend": metrics.get('spend') is not None,
            "CPM": metrics.get('cpm') is not None,
            "Impressions": metrics.get('impressions') is not None,
            "3 Second Views": metrics.get('video_3_sec_views') is not None,
            "100% Video Watches": metrics.get('video_p100_watched') is not None,
            "CTR (Destination)": metrics.get('ctr_destination') is not None,
            "CPC": metrics.get('cpc') is not None,
            "Registrations": metrics.get('registrations') is not None,
            "CPR": metrics.get('cpr') is not None,
            "Age Breakdown": 'age' in breakdowns,
            "Gender Breakdown": 'gender' in breakdowns,
            "Age+Gender Breakdown": 'age_gender' in breakdowns,
        }
        
        # Count available metrics
        total_metrics = len(availability)
        available_metrics = sum(availability.values())
        availability_percentage = (available_metrics / total_metrics) * 100
        
        # Print summary
        print(f"\nOverall: {available_metrics} of {total_metrics} metrics available ({availability_percentage:.0f}%)")
        
        # Print result based on availability
        if availability_percentage > 80:
            print("\n✓ TEST PASSED - Most required metrics are available")
        elif availability_percentage > 50:
            print("\n! TEST PASSED WITH WARNINGS - Some metrics are unavailable")
        else:
            print("\n✗ TEST FAILED - Too many required metrics are unavailable")
        
        print("\n===============================================")
        
        return True
        
    except Exception as e:
        logger.error(f"Error during testing: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def analyze_and_export_to_csv(region: str = "GBR", limit: int = 5, ad_id=None):
    """
    Analyze ad data and export results to CSV using a two-step process:
    1. First find ads with sufficient spend from the past 7 days (excluding today)
    2. Then query each ad individually with proper rate limiting
    
    This approach is more robust than bulk operations for handling multiple ads.
    
    Args:
        region: Region code to analyze (default: GBR)
        limit: Maximum number of ads to analyze (default: 5)
        ad_id: Optional specific ad ID to analyze
    """
    logger.info(f"Starting ad data analysis and export test for region {region}")
    
    try:
        # Initialize components
        # Use the hardcoded account ID since environment variables aren't set
        meta_client = MetaApiClient(
            region=region,
            ad_account_id="1042125899190941"  # Use the known working account ID for testing
        )
        validator = DataValidator()
        analyzer = PerformanceAnalyzer()
        
        # Step 1: Verify API connection
        logger.info("Testing API connection...")
        if not meta_client.test_connection():
            logger.error("Failed to connect to Meta API")
            return False
        
        # Step 2: Get ads to analyze - either specific ad or bulk query
        from config.settings import SPEND_THRESHOLD
        min_spend = SPEND_THRESHOLD
        
        # If a specific ad ID is provided, use it directly
        if ad_id:
            logger.info(f"Using provided ad ID: {ad_id}")
            try:
                # Get complete ad data for the provided ID
                ad_data = meta_client.get_complete_ad_data(ad_id)
                if ad_data:
                    ads_data = [ad_data]
                    logger.info(f"Successfully retrieved data for ad {ad_id}: {ad_data.get('ad_name')}")
                else:
                    logger.error(f"Could not get data for ad {ad_id}")
                    ads_data = []
            except Exception as e:
                logger.error(f"Error getting data for ad {ad_id}: {str(e)}")
                ads_data = []
        else:
            # STEP 1: Find ads with sufficient spend from the past 7 days (excluding today)
            logger.info(f"Finding up to {limit} ads with minimum spend of £{min_spend} over the past 7 days (excluding today)...")
            
            try:
                # Use the new find_ads_with_spend method to get ads with sufficient spend
                from config.settings import DAYS_THRESHOLD
                
                found_ads = meta_client.find_ads_with_spend(
                    days=DAYS_THRESHOLD,     # Use the configured days threshold (default: 7)
                    min_spend=min_spend,     # Filter for ads with sufficient spend
                    limit=limit              # Limit the number of ads
                )
                
                logger.info(f"Found {len(found_ads)} ads with sufficient spend")
                
                if not found_ads:
                    logger.warning("No ads found with sufficient spend, trying fallback method...")
                    # Fallback to traditional method if find_ads_with_spend returns no results
                    # First, try to get ads created exactly 7 days ago
                    ads = meta_client.get_eligible_ads(days_threshold=7)
                    
                    # Process the traditional way if we got any results
                    if ads:
                        logger.info(f"Got {len(ads)} ads from eligible_ads method")
                        found_ads = ads[:min(3, limit)]  # Limit to avoid rate limiting
                
                # STEP 2: Query each ad individually with proper rate limiting
                logger.info("Querying individual ad data with proper rate limiting...")
                ads_data = []
                
                for ad in found_ads:
                    ad_id = ad.get('ad_id')
                    try:
                        logger.info(f"Getting complete data for ad {ad_id}...")
                        ad_data = meta_client.get_complete_ad_data(ad_id, days=DAYS_THRESHOLD)
                        if ad_data:
                            ads_data.append(ad_data)
                            logger.info(f"Successfully retrieved data for ad {ad_id}")
                        else:
                            logger.warning(f"No data returned for ad {ad_id}")
                    except Exception as e:
                        logger.error(f"Error getting data for ad {ad_id}: {str(e)}")
                        continue
            except Exception as e:
                logger.error(f"Error using bulk insights API: {str(e)}")
                ads_data = []
        
        if not ads_data:
            logger.error("No suitable ads found for analysis")
            return False
        
        logger.info(f"Successfully retrieved data for {len(ads_data)} ads for analysis")
        
        # Step 3: Prepare CSV file - use config folder
        csv_file_path = os.path.join(project_root, 'config', f'ad_analysis_{region}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        
        # Define CSV headers
        csv_headers = [
            "Ad ID", 
            "Ad Name", 
            "Campaign", 
            "Analysis Date",
            "Spend (£)",
            "Impressions",
            "Clicks",
            "CTR (%)",
            "CPA (£)",
            "ROAS",
            "Performance Score",
            "Rating",
            "Best Segment",
            "Key Insight"
        ]
        
        with open(csv_file_path, 'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(csv_headers)
            
            # Step 4: Process all ads - data is already retrieved via bulk operation
            analyzed_ads = []
            for ad_data in ads_data:
                ad_id = ad_data.get('ad_id')
                logger.info(f"Processing ad {ad_id}: {ad_data.get('ad_name')}")
                
                try:
                    # Validate the ad data
                    validation_result = validator.validate_ad(ad_data)
                    if not validation_result['valid']:
                        logger.warning(f"Ad {ad_id} failed validation: {validation_result['reason']}")
                        continue
                    
                    # Analyze performance
                    analysis_result = analyzer.analyze_performance(ad_data)
                    
                    # Insights generation removed - will be replaced with AI
                    # Add placeholder insights
                    analysis_result['insights'] = {
                        "summary": ["Data analysis complete. Insights will be generated by AI."],
                        "formatted_text": "Data analysis complete. Insights will be generated by AI."
                    }
                    
                    # Add to analyzed ads
                    analyzed_ads.append({
                        "ad_data": ad_data,
                        "analysis_result": analysis_result
                    })
                    
                    # Extract metrics for CSV
                    metrics = ad_data.get('metrics', {})
                    
                    # Get a key insight (first from summary)
                    key_insight = insights.get('summary', [''])[0] if insights.get('summary') else ''
                    
                    # Write to CSV
                    csv_writer.writerow([
                        ad_data.get('ad_id', 'unknown'),
                        ad_data.get('ad_name', 'Unknown Ad'),
                        ad_data.get('campaign_name', 'Unknown Campaign'),
                        analysis_result.get('analysis_date', ''),
                        metrics.get('spend', 0),
                        metrics.get('impressions', 0),
                        metrics.get('clicks', 0),
                        metrics.get('ctr', 0),
                        metrics.get('cpa', 0),
                        metrics.get('roas', 0),
                        analysis_result.get('performance_score', 0),
                        analysis_result.get('performance_rating', 'Unknown'),
                        analysis_result.get('best_segment', 'Unknown'),
                        key_insight
                    ])
                    
                    logger.info(f"Analysis complete for ad {ad_id}")
                    
                except Exception as e:
                    logger.error(f"Error analyzing ad {ad_id}: {str(e)}")
            
            logger.info(f"Successfully analyzed {len(analyzed_ads)} ads")
        
        logger.info(f"Results exported to {csv_file_path}")
        print(f"\nAnalysis results saved to: {csv_file_path}")
        
        # Create a detailed JSON output for debugging - use config folder
        json_file_path = os.path.join(project_root, 'config', f'ad_analysis_{region}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
        with open(json_file_path, 'w') as f:
            json.dump(analyzed_ads, f, indent=2, default=str)
        
        logger.info(f"Detailed results saved to {json_file_path}")
        print(f"Detailed JSON results saved to: {json_file_path}")
        
        return True
    
    except Exception as e:
        logger.exception(f"Error in analysis and export: {str(e)}")
        return False


if __name__ == "__main__":
    print("\nCREATIVE ANALYSIS TOOL TEST")
    print("============================\n")
    
    # Process command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Test the Creative Analysis Tool")
    parser.add_argument("--region", default="GBR", help="Region code (default: GBR)")
    parser.add_argument("--limit", type=int, default=5, help="Maximum number of ads to analyze")
    parser.add_argument("--ad_id", help="Specific ad ID to test with (bypasses ad search)")
    args = parser.parse_args()
    
    print("1. METRICS AVAILABILITY TEST")
    print("----------------------------")
    try:
        metrics_success = check_metrics_availability(ad_id=args.ad_id)
        if not metrics_success:
            print("\nMETRICS TEST FAILED")
    except Exception as e:
        print(f"\nMETRICS TEST FAILED WITH ERROR: {str(e)}")
    
    print("\n2. ANALYSIS AND EXPORT TEST")
    print("----------------------------")
    try:
        analysis_success = analyze_and_export_to_csv(
            region=args.region, 
            limit=args.limit,
            ad_id=args.ad_id
        )
        if not analysis_success:
            print("\nANALYSIS TEST FAILED")
            sys.exit(1)
    except Exception as e:
        print(f"\nANALYSIS TEST FAILED WITH ERROR: {str(e)}")
        sys.exit(1)