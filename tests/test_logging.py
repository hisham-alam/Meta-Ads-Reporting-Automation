#!/usr/bin/env python3
"""
Test script to debug Google Sheets integration.

This script:
1. Loads existing ad data from the tests/output directory
2. Initializes the SheetsManager
3. Updates Google Sheets with the ad data
4. Prints the URL to access the Google Sheet
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import components
from src.sheets_manager import SheetsManager

def main():
    # Load ad data from the most recent JSON file in tests/output
    output_dir = project_root / "tests" / "output"
    json_files = list(output_dir.glob("ad_analysis_*.json"))
    if not json_files:
        print("No ad analysis files found in tests/output directory")
        return
    
    # Get the most recent file
    latest_file = sorted(json_files, key=os.path.getmtime)[-1]
    print(f"Using ad data from: {latest_file}")
    
    # Load the JSON data
    with open(latest_file, 'r') as f:
        analyzed_ads = json.load(f)
    
    region = "GBR"  # Default region
    if "_" in latest_file.stem:
        # Extract region from filename (e.g., ad_analysis_GBR_20250814_234252.json)
        parts = latest_file.stem.split("_")
        if len(parts) > 2:
            region = parts[2]
    
    print(f"Using region: {region}")
    print(f"Found {len(analyzed_ads)} ads to process")
    
    try:
        # Initialize SheetsManager
        print("Initializing SheetsManager...")
        sheets_manager = SheetsManager(region=region)
        
        # Update Google Sheets
        print("Updating Google Sheets with ad details...")
        sheets_results = sheets_manager.update_ad_details_batch(analyzed_ads)
        
        # Create dashboard summary
        print("Creating dashboard summary...")
        summary_data = prepare_dashboard_summary(analyzed_ads)
        sheets_manager.update_dashboard(summary_data)
        
        # Get spreadsheet URL
        spreadsheet_url = sheets_manager.get_spreadsheet_url()
        
        print("\nGoogle Sheets updated successfully!")
        print(f"Access the spreadsheet at: {spreadsheet_url}")
        
    except Exception as e:
        print(f"Error updating Google Sheets: {str(e)}")
        import traceback
        print(traceback.format_exc())

def prepare_dashboard_summary(analyzed_ads):
    """
    Prepare summary data for dashboard
    
    Args:
        analyzed_ads: List of analyzed ad data
        
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

if __name__ == "__main__":
    main()