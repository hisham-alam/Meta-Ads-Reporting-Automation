#!/usr/bin/env python3
"""
Sheets Formatter

This module handles formatting and processing ad data for Google Sheets output and CSV export.
It prepares data according to the specific formatting requirements for both formats.
"""

import logging
import pandas as pd
import os
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SheetsFormatter:
    """
    Formats ad data for Google Sheets and CSV export with specific formatting rules
    """
    
    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the SheetsFormatter
        
        Args:
            output_dir: Directory to save CSV files (defaults to current directory)
        """
        self.output_dir = output_dir or os.getcwd()
        logger.info(f"SheetsFormatter initialized with output directory: {self.output_dir}")
    
    def format_ad_data_for_sheets(self, ads_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format raw ad data for Google Sheets with specific formatting rules
        
        Args:
            ads_data: List of ad data dictionaries
            
        Returns:
            List[Dict]: Formatted ad data ready for Google Sheets insertion
        """
        logger.info(f"Formatting {len(ads_data)} ads for Google Sheets")
        formatted_ads = []
        
        for ad_data in ads_data:
            # Extract relevant data
            ad_info = ad_data.get("ad_data", {})
            analysis = ad_data.get("analysis_result", {})
            
            # Skip if missing essential data
            if not ad_info or not analysis:
                logger.warning(f"Skipping ad with missing data")
                continue
            
            metrics = ad_info.get("metrics", {})
            creative = ad_info.get("creative", {})
            
            # Basic ad information
            launched = ad_info.get("created_time", "")
            if launched and "T" in launched:
                # Format date from ISO to MM/DD/YYYY
                try:
                    date_obj = datetime.strptime(launched.split("T")[0], "%Y-%m-%d")
                    launched = date_obj.strftime("%m/%d/%Y")
                except ValueError:
                    pass
                    
            ad_name = ad_info.get("ad_name", "")
            ad_link = creative.get("video_url") or creative.get("image_url") or ""
            
            # Determine creative angle (could be extended with more sophisticated logic)
            creative_angle = "Unknown"  # Default value
            # This would ideally be derived from ad data or provided by user
            
            # Determine status and action based on performance
            performance_score = analysis.get("benchmark_comparison", {}).get("overall_performance_score", 0)
            
            if performance_score >= 20:
                status = "Winning"
                action = "Scale"
            elif performance_score <= -20:
                status = "Losing" 
                action = "Stop"
            else:
                status = "Average"
                action = "Monitor"
            
            # Use CPA as CPR (Cost Per Registration) value
            cpr_value = metrics.get("cpr", 0) or metrics.get("cpa", 0)
            
            # Remove percentage change calculation as it's no longer needed
            cpr_percent_change = 0  # Set to 0 for backward compatibility
            
            # Extract or create demographics insights
            demographics = []
            if "breakdowns" in ad_info and "age_gender" in ad_info["breakdowns"]:
                age_gender_data = ad_info["breakdowns"]["age_gender"]
                
                # Find best performing demographics
                if age_gender_data:
                    # Sort by CPR (lower is better) if we have conversions
                    convertors = [segment for segment in age_gender_data if segment.get("conversions", 0) > 0]
                    if convertors:
                        best_demo = sorted(convertors, key=lambda x: x.get("cpr", float("inf")))[0]
                        demo_text = f"Strong performance with {best_demo.get('gender', 'Unknown')} {best_demo.get('age', '18-65')}."
                        demographics.append(demo_text)
                    
                    # Also look for high engagement demographics
                    engaged = sorted(age_gender_data, key=lambda x: x.get("ctr", 0), reverse=True)[0]
                    if engaged:
                        demo_text = f"Consistent engagement from {engaged.get('gender', 'Unknown')} {engaged.get('age', '18-65')}."
                        demographics.append(demo_text)
            
            # If no demographics data was found, use placeholder
            if not demographics:
                demographics = ["No significant demographic patterns identified."]
            
            # Extract or create AI analysis insights
            # In a real implementation, these would come from an AI system
            ai_analysis = []
            if "insights" in analysis:
                insights = analysis.get("insights", {})
                if "summary" in insights and insights["summary"]:
                    ai_analysis = insights["summary"]
            
            # If no AI insights were found, use placeholder
            if not ai_analysis:
                ai_analysis = ["Awaiting AI analysis."]
            
            # Extract more metrics from the data
            spend = metrics.get("spend", 0)  # Ad spend
            impressions = metrics.get("impressions", 0)
            clicks = metrics.get("clicks", 0)  # Number of clicks
            conversions = metrics.get("conversions", 0)  # Number of conversions
            
            # Percentage metrics - calculate if not directly provided
            # CTR - Use value directly from API as it's already in percentage form
            ctr = metrics.get("ctr", 0)
            # Only calculate if we don't have a value and have necessary data
            if ctr == 0 and impressions > 0 and clicks > 0:
                ctr = (clicks / impressions)
                
            # Hook rate - Get directly from metrics if it exists, otherwise calculate
            hook_rate = metrics.get("hook_rate", 0)  
            if hook_rate == 0:  # If not available in metrics, try to calculate
                # First try with video nested object
                if "video" in metrics and isinstance(metrics["video"], dict):
                    video_metrics = metrics["video"]
                    p25_views = video_metrics.get("p25", 0)
                    if impressions > 0 and p25_views > 0:
                        hook_rate = round(((p25_views / impressions) * 100), 2)
                # Then try with direct video metrics
                elif "video_3_sec_views" in metrics and impressions > 0 and metrics["video_3_sec_views"] > 0:
                    hook_rate = round(((metrics["video_3_sec_views"] / impressions) * 100), 2)
                
            # Viewthrough rate - Get directly from metrics if it exists, otherwise calculate
            viewthrough_rate = metrics.get("viewthrough_rate", 0)  
            if viewthrough_rate == 0:  # If not available in metrics, try to calculate
                # First try with video nested object
                if "video" in metrics and isinstance(metrics["video"], dict):
                    video_metrics = metrics["video"]
                    p100_views = video_metrics.get("p100", 0)
                    if impressions > 0 and p100_views > 0:
                        viewthrough_rate = round(((p100_views / impressions) * 100), 2)
                # Then try with direct video metrics
                elif "video_p100_watched" in metrics and impressions > 0 and metrics["video_p100_watched"] > 0:
                    viewthrough_rate = round(((metrics["video_p100_watched"] / impressions) * 100), 2)
                
            ctr_destination = metrics.get("ctr_destination", 0)  # Destination CTR
            
            # Cost metrics - extract if available or calculate
            cpm = metrics.get("cpm", 0)
            if cpm == 0 and impressions > 0:
                cpm = (spend / impressions) * 1000
                
            cpc = metrics.get("cpc", 0)
            if cpc == 0 and clicks > 0:
                cpc = spend / clicks
            
            # Create formatted ad entry
            formatted_ad = {
                "launched": launched,
                "ad_name": ad_name,
                "ad_link": ad_link,
                "creative_angle": creative_angle,
                "status": status,
                "action": action,
                "spend": spend,
                "impressions": impressions,
                "clicks": clicks,
                "conversions": conversions,
                "ctr": ctr,
                "cpm": cpm,
                "cpc": cpc,
                "hook_rate": hook_rate,
                "viewthrough_rate": viewthrough_rate,
                "ctr_destination": ctr_destination,
                "cpr_value": cpr_value,
                "cpr_percent_change": cpr_percent_change,
                "demographics": demographics,
                "ai_analysis": ai_analysis
            }
            
            formatted_ads.append(formatted_ad)
        
        logger.info(f"Successfully formatted {len(formatted_ads)} ads for Google Sheets")
        return formatted_ads
    
    def create_sheets_formulas(self, formatted_ads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert formatted ad data into Google Sheets formulas
        
        Args:
            formatted_ads: List of formatted ad data dictionaries
            
        Returns:
            List[Dict]: Ad data with Google Sheets formula strings
        """
        sheets_ready_ads = []
        
        for ad in formatted_ads:
            # Create hyperlink formula for ad name
            ad_name = ad.get("ad_name", "")
            ad_link = ad.get("ad_link", "")
            hyperlink_formula = f'=HYPERLINK("{ad_link}", "{ad_name}")' if ad_link else ad_name
            
            # Format CPR value (use cpa value if cpr_value doesn't exist)
            cpr_value = ad.get("cpr_value", 0) or ad.get("cpa", 0)
            
            # Format demographics and AI analysis as bulleted lists
            demographics = ad.get("demographics", [])
            demographics_str = "\n".join(f"• {item}" for item in demographics)
            
            ai_analysis = ad.get("ai_analysis", [])
            ai_analysis_str = "\n".join(f"• {item}" for item in ai_analysis)
            
            # Create sheets-ready ad entry
            sheets_ad = ad.copy()
            sheets_ad["ad_name_formula"] = hyperlink_formula
            
            # Format all metrics correctly
            # Spend
            spend = ad.get("spend", 0)
            sheets_ad["spend_formatted"] = f"£{spend:.2f}"
            
            # CPM
            cpm = ad.get("cpm", 0)
            if cpm == 0 and ad.get("impressions", 0) > 0:
                # Calculate CPM if not provided but we have impressions
                cpm = (spend / ad.get("impressions", 1)) * 1000
            sheets_ad["cpm_formatted"] = f"£{cpm:.2f}"
            
            # CPC
            cpc = ad.get("cpc", 0)
            if cpc == 0 and ad.get("clicks", 0) > 0:
                # Calculate CPC if not provided but we have clicks
                cpc = spend / ad.get("clicks", 1)
            sheets_ad["cpc_formatted"] = f"£{cpc:.2f}"
            
            # CPR (cost per registration/conversion)
            # Use cpa value as cpr value since they're the same metric
            cpr_value = ad.get("cpr_value", 0) or ad.get("cpa", 0)
            sheets_ad["cpr_formatted"] = f"£{cpr_value:.2f}"
            
            # Format percentage metrics
            ctr = ad.get("ctr", 0)
            hook_rate = ad.get("hook_rate", 0)
            viewthrough_rate = ad.get("viewthrough_rate", 0)
            
            sheets_ad["ctr_formatted"] = f"{ctr:.2f}%"
            # Format hook rate and viewthrough rate
            # These values should now always be numbers, not strings
            sheets_ad["hook_rate_formatted"] = f"{hook_rate:.2f}%" if hook_rate is not None else ""
            sheets_ad["viewthrough_rate_formatted"] = f"{viewthrough_rate:.2f}%" if viewthrough_rate is not None else ""
            
            sheets_ad["demographics_formatted"] = demographics_str
            sheets_ad["ai_analysis_formatted"] = ai_analysis_str
            
            sheets_ready_ads.append(sheets_ad)
        
        return sheets_ready_ads
    
    def export_to_csv(self, formatted_ads: List[Dict[str, Any]], filename: Optional[str] = None) -> str:
        """
        Export formatted ad data to CSV
        
        Args:
            formatted_ads: List of formatted ad data
            filename: Optional filename override
            
        Returns:
            str: Path to the exported CSV file
        """
        if not formatted_ads:
            logger.warning("No ad data to export to CSV")
            return ""
        
        # Create a copy of the formatted ads with adjusted CPR format (combined value and percentage)
        csv_ready_ads = []
        for ad in formatted_ads:
            csv_ad = ad.copy()
            # Format CPR value (use cpa value if cpr_value doesn't exist)
            cpr_value = ad.get("cpr_value", 0) or ad.get("cpa", 0) or ad.get("cpr", 0)
            csv_ad["cpr"] = f"£{cpr_value:.2f}"
            
            # Format percentages
            csv_ad["ctr"] = f"{ad.get('ctr', 0):.2f}%"
            csv_ad["hook_rate"] = f"{ad.get('hook_rate', 0):.2f}%"
            csv_ad["viewthrough_rate"] = f"{ad.get('viewthrough_rate', 0):.2f}%"
            csv_ad["ctr_destination"] = f"{ad.get('ctr_destination', 0):.2f}%"
            
            # Format impressions with thousands separator
            csv_ad["impressions"] = f"{ad.get('impressions', 0):,}"
            
            # Remove now redundant fields
            if "cpr_value" in csv_ad:
                del csv_ad["cpr_value"]
            if "cpr_percent_change" in csv_ad:
                del csv_ad["cpr_percent_change"]
                
            csv_ready_ads.append(csv_ad)
        
        # Create DataFrame from formatted ads
        df = pd.DataFrame(csv_ready_ads)
        
        # Format lists as strings for CSV
        if "demographics" in df.columns:
            df["demographics"] = df["demographics"].apply(lambda x: "\n".join(x) if isinstance(x, list) else str(x))
        
        if "ai_analysis" in df.columns:
            df["ai_analysis"] = df["ai_analysis"].apply(lambda x: "\n".join(x) if isinstance(x, list) else str(x))
        
        # Create output filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = filename or f"ad_analysis_{timestamp}.csv"
        output_path = os.path.join(self.output_dir, filename)
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Write to CSV
        df.to_csv(output_path, index=False)
        logger.info(f"Ad data exported to CSV: {output_path}")
        
        return output_path
    
    def format_for_sheets_api(self, sheets_ready_ads: List[Dict[str, Any]]) -> List[List[Any]]:
        """
        Format ads data into a 2D array format for the Google Sheets API
        
        Args:
            sheets_ready_ads: List of sheets-ready ad data
            
        Returns:
            List[List[Any]]: 2D array of values for Google Sheets
        """
        # Define column order - matching SheetsManager.AD_DETAILS_COLUMNS
        columns = [
            "launched", "ad_name_formula", "creative_angle", "status", 
            "action", "spend_formatted", "cpm_formatted", "hook_rate_formatted",
            "viewthrough_rate_formatted", "ctr_formatted", "cpc_formatted", "cpr_formatted", 
            "demographics_formatted", "ai_analysis_formatted"
        ]
        
        # Create 2D array
        rows = []
        
        # Add header row - matching SheetsManager.AD_DETAILS_COLUMNS
        headers = [
            "Launch Date", "Ad Name", "Creative Angle", "Status", 
            "Action", "Spend", "CPM", "Hook Rate", 
            "VT Rate", "CTR", "CPC", "CPR", 
            "Demographics", "AI Analysis"
        ]
        rows.append(headers)
        
        # Add data rows
        for ad in sheets_ready_ads:
            row = [ad.get(col, "") for col in columns]
            rows.append(row)
        
        return rows


# Example usage
if __name__ == "__main__":
    formatter = SheetsFormatter()
    print("SheetsFormatter initialized for testing")