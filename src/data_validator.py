#!/usr/bin/env python3
"""
Data Validator

This module validates ad performance data before analysis.
It ensures data quality by checking for required fields,
verifying full data availability, and flagging anomalies.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional

# Import settings from config
from config.settings import SPEND_THRESHOLD, DAYS_THRESHOLD

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataValidator:
    """Validates ad performance data before analysis"""
    
    def __init__(self, spend_threshold: float = SPEND_THRESHOLD, days_threshold: int = DAYS_THRESHOLD):
        """
        Initialize the data validator
        
        Args:
            spend_threshold: Minimum spend amount to be considered valid
            days_threshold: Number of days required for analysis
        """
        self.spend_threshold = spend_threshold
        self.days_threshold = days_threshold
        logger.info(f"Data validator initialized with spend threshold: {spend_threshold}, days threshold: {days_threshold}")
    
    def validate_ad(self, ad_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate an ad's data (simplified interface used by check_ad_data.py)
        
        Args:
            ad_data: Ad performance data
            
        Returns:
            Dict[str, Any]: Validation result with valid flag and reason if invalid
        """
        is_valid, issues = self.validate_ad_data(ad_data)
        
        result = {
            "valid": is_valid
        }
        
        if not is_valid and issues:
            result["reason"] = issues[0]  # Return first issue as reason
        
        return result
    
    def validate_ad_data(self, ad_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate an ad's data for completeness and quality
        
        Args:
            ad_data: Ad performance data
            
        Returns:
            Tuple[bool, List[str]]: (is_valid, list_of_issues)
        """
        logger.info(f"Validating data for ad {ad_data.get('ad_id', 'unknown')}")
        
        issues = []
        is_valid = True
        
        # Check for required fields
        required_fields = self._check_required_fields(ad_data)
        if required_fields:
            issues.extend(required_fields)
            is_valid = False
        
        # Check spend threshold
        if not self._check_spend_threshold(ad_data):
            issues.append(f"Spend below threshold: {ad_data.get('metrics', {}).get('spend', 0)} < {self.spend_threshold}")
            is_valid = False
        
        # Check data timeframe
        if not self._check_timeframe(ad_data):
            issues.append(f"Insufficient data: Less than {self.days_threshold} days of data")
            is_valid = False
        
        # Check for anomalies
        anomalies = self._check_anomalies(ad_data)
        if anomalies:
            issues.extend(anomalies)
            # Anomalies don't necessarily invalidate data, but they are flagged
        
        if is_valid:
            logger.info(f"Data for ad {ad_data.get('ad_id', 'unknown')} is valid")
        else:
            logger.warning(f"Data for ad {ad_data.get('ad_id', 'unknown')} is invalid: {', '.join(issues)}")
        
        return is_valid, issues
    
    def _check_required_fields(self, ad_data: Dict[str, Any]) -> List[str]:
        """
        Check that all required fields are present in the data
        
        Args:
            ad_data: Ad performance data
            
        Returns:
            List[str]: List of missing required fields
        """
        missing_fields = []
        
        # Top level required fields
        for field in ['ad_id', 'ad_name', 'campaign_name', 'created_time', 'metrics']:
            if field not in ad_data or not ad_data[field]:
                missing_fields.append(f"Missing required field: {field}")
        
        # Metrics required fields
        if 'metrics' in ad_data:
            metrics = ad_data['metrics']
            for field in ['spend', 'impressions', 'clicks', 'conversions', 'ctr', 'cpm', 'cpa']:
                if field not in metrics:
                    missing_fields.append(f"Missing required metric: {field}")
        
        # Breakdowns required fields
        if 'breakdowns' in ad_data:
            breakdowns = ad_data['breakdowns']
            if 'age_gender' not in breakdowns or not breakdowns['age_gender']:
                missing_fields.append("Missing required breakdown: age_gender")
        else:
            missing_fields.append("Missing required section: breakdowns")
        
        return missing_fields
    
    def _check_spend_threshold(self, ad_data: Dict[str, Any]) -> bool:
        """
        Check if spend meets the threshold requirement
        
        Args:
            ad_data: Ad performance data
            
        Returns:
            bool: True if spend is greater than or equal to threshold
        """
        if 'metrics' not in ad_data:
            return False
            
        spend = ad_data['metrics'].get('spend', 0)
        return spend >= self.spend_threshold
    
    def _check_timeframe(self, ad_data: Dict[str, Any]) -> bool:
        """
        Check if ad has data for the required timeframe
        
        Args:
            ad_data: Ad performance data
            
        Returns:
            bool: True if data covers the required timeframe
        """
        if 'created_time' not in ad_data:
            return False
        
        try:
            # Parse created time
            created_time_str = ad_data['created_time']
            # Handle different date formats from Meta API
            if 'T' in created_time_str:
                created_time = datetime.strptime(created_time_str.split('T')[0], '%Y-%m-%d')
            else:
                created_time = datetime.strptime(created_time_str, '%Y-%m-%d')
            
            # Check if enough days have passed since creation
            today = datetime.now()
            days_since_creation = (today - created_time).days
            
            return days_since_creation >= self.days_threshold
            
        except Exception as e:
            logger.error(f"Error parsing created_time: {str(e)}")
            return False
    
    def _check_anomalies(self, ad_data: Dict[str, Any]) -> List[str]:
        """
        Check for data anomalies and unusual patterns
        
        Args:
            ad_data: Ad performance data
            
        Returns:
            List[str]: List of anomalies found
        """
        anomalies = []
        
        if 'metrics' in ad_data:
            metrics = ad_data['metrics']
            
            # Check for unusually high CTR (>10%)
            if metrics.get('ctr', 0) > 10.0:
                anomalies.append(f"Unusually high CTR: {metrics.get('ctr')}%")
            
            # Check for zero impressions but non-zero spend
            if metrics.get('impressions', 0) == 0 and metrics.get('spend', 0) > 0:
                anomalies.append("Zero impressions with non-zero spend")
            
            # Check for negative values
            for field in ['spend', 'impressions', 'clicks', 'conversions', 'ctr', 'cpm', 'cpa']:
                if field in metrics and metrics[field] < 0:
                    anomalies.append(f"Negative value for {field}: {metrics[field]}")
            
            # Check for impossible conversion rate (>100%)
            if metrics.get('clicks', 0) > 0 and metrics.get('conversions', 0) > metrics.get('clicks', 0):
                anomalies.append("Conversion count exceeds click count")
            
            # Check for extremely high ROAS (>20x)
            if metrics.get('roas', 0) > 20.0:
                anomalies.append(f"Unusually high ROAS: {metrics.get('roas')}")
        
        return anomalies
    
    def validate_multiple_ads(self, ads_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate multiple ads and return validation results
        
        Args:
            ads_data: List of ad performance data
            
        Returns:
            Dict: Validation results
        """
        logger.info(f"Validating {len(ads_data)} ads")
        
        valid_ads = []
        invalid_ads = []
        all_issues = {}
        
        for ad_data in ads_data:
            ad_id = ad_data.get('ad_id', 'unknown')
            is_valid, issues = self.validate_ad_data(ad_data)
            
            if is_valid:
                valid_ads.append(ad_data)
            else:
                invalid_ads.append(ad_id)
                all_issues[ad_id] = issues
        
        logger.info(f"Validation complete: {len(valid_ads)} valid ads, {len(invalid_ads)} invalid ads")
        
        return {
            "valid_ads": valid_ads,
            "invalid_ads": invalid_ads,
            "issues": all_issues,
            "total_ads": len(ads_data),
            "valid_count": len(valid_ads),
            "invalid_count": len(invalid_ads)
        }

# Example usage
if __name__ == "__main__":
    # Sample ad data for testing
    sample_ad = {
        "ad_id": "12345",
        "ad_name": "Test Ad",
        "campaign_name": "Test Campaign",
        "created_time": (datetime.now() - timedelta(days=8)).strftime('%Y-%m-%d'),
        "metrics": {
            "spend": 75.5,
            "impressions": 15000,
            "clicks": 225,
            "conversions": 12,
            "ctr": 1.5,
            "cpm": 5.03,
            "cpa": 6.29,
            "roas": 4.2
        },
        "breakdowns": {
            "age_gender": [
                {"age": "25-34", "gender": "female", "spend": 25.0, "conversions": 6}
            ]
        }
    }
    
    validator = DataValidator()
    is_valid, issues = validator.validate_ad_data(sample_ad)
    
    print(f"Ad valid: {is_valid}")
    if issues:
        print("Issues found:")
        for issue in issues:
            print(f"- {issue}")