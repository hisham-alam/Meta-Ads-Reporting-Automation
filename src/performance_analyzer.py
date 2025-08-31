#!/usr/bin/env python3
"""
Performance Analyzer

This module analyzes ad performance data by comparing metrics to benchmarks,
identifying top performing segments, and calculating performance ratings.
"""

import logging
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
from pathlib import Path

# Import settings from config
from config.settings import DAYS_THRESHOLD

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PerformanceAnalyzer:
    """Analyzes ad performance against benchmarks"""
    
    def __init__(self, meta_client=None):
        """
        Initialize the performance analyzer
        
        Args:
            meta_client: Meta API client instance for fetching account metrics
        """
        self.meta_client = meta_client
        self.benchmarks = None
        logger.info("Performance analyzer initialized - will calculate benchmarks when needed")
    
    def calculate_benchmarks(self, meta_client=None, days=DAYS_THRESHOLD):
        """
        Calculate benchmarks from actual Meta account data
        
        Args:
            meta_client: Meta API client instance (uses instance from init if None)
            days: Number of days of data to include
            
        Returns:
            Dict: Benchmark data
        """
        # Use provided client or instance client
        client = meta_client or self.meta_client
        
        if not client:
            logger.warning("No Meta API client available - cannot calculate benchmarks")
            # We need to return some minimal structure for the analyzer to function
            return {
                "market": "Unknown",
                "benchmarks": {}
            }
            
        logger.info(f"Calculating benchmarks from account data over past {days} days")
        
        try:
            # Get account-level metrics for benchmarks
            account_insights = client.get_account_insights(days=days)
            
            if not account_insights:
                logger.warning("No account insights available for benchmarking")
                return {"market": "Unknown", "benchmarks": {}}
                
            # Extract key metrics for benchmarking
            benchmarks = {
                "market": client.region,
                "benchmarks": {
                    # Extract metrics that exist in the account data
                    "ctr": account_insights.get("ctr", 0),
                    "cpm": account_insights.get("cpm", 0),
                    "cpa": account_insights.get("cost_per_conversion", 0),
                    "roas": account_insights.get("roas", 0),
                    "conversion_rate": account_insights.get("conversion_rate", 0),
                    "hook_rate": account_insights.get("hook_rate", 0),
                    "viewthrough_rate": account_insights.get("viewthrough_rate", 0)
                },
                # We could add segment benchmarks from more detailed account data if needed
                "segments": {}
            }
            
            # Log the benchmark values we calculated
            benchmark_str = ", ".join([f"{k}: {v:.2f}" for k, v in benchmarks["benchmarks"].items()])
            logger.info(f"Generated dynamic benchmarks from account data: {benchmark_str}")
            
            # Save the benchmarks
            self.benchmarks = benchmarks
            return benchmarks
            
        except Exception as e:
            logger.exception(f"Error calculating benchmarks: {str(e)}")
            # Return minimal structure so the analyzer can function
            return {"market": "Error", "benchmarks": {}}
    
    def compare_to_benchmarks(self, ad_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare ad metrics to benchmarks
        
        Args:
            ad_data: Ad performance data
            
        Returns:
            Dict: Performance comparison data
        """
        logger.info(f"Comparing ad {ad_data.get('ad_id', 'unknown')} to benchmarks")
        
        # If we don't have benchmarks yet and have a Meta client, calculate them now
        if not self.benchmarks and self.meta_client:
            self.benchmarks = self.calculate_benchmarks(self.meta_client)
        
        metrics = ad_data.get('metrics', {})
        benchmark_metrics = self.benchmarks.get('benchmarks', {}) if self.benchmarks else {}
        
        # Calculate percentage difference for each key metric
        comparison = {}
        
        # CTR comparison (higher is better)
        if 'ctr' in metrics and 'ctr' in benchmark_metrics and benchmark_metrics['ctr'] > 0:
            comparison['ctr_vs_benchmark'] = ((metrics['ctr'] / benchmark_metrics['ctr']) - 1) * 100
        else:
            comparison['ctr_vs_benchmark'] = 0
        
        # CPA comparison (lower is better, so invert the calculation)
        if 'cpa' in metrics and 'cpa' in benchmark_metrics and benchmark_metrics['cpa'] > 0 and metrics['cpa'] > 0:
            comparison['cpa_vs_benchmark'] = ((benchmark_metrics['cpa'] / metrics['cpa']) - 1) * 100
        else:
            comparison['cpa_vs_benchmark'] = 0
        
        # ROAS comparison (higher is better)
        if 'roas' in metrics and 'roas' in benchmark_metrics and benchmark_metrics['roas'] > 0:
            comparison['roas_vs_benchmark'] = ((metrics['roas'] / benchmark_metrics['roas']) - 1) * 100
        else:
            comparison['roas_vs_benchmark'] = 0
        
        # CPM comparison (lower is better, so invert the calculation)
        if 'cpm' in metrics and 'cpm' in benchmark_metrics and benchmark_metrics['cpm'] > 0 and metrics['cpm'] > 0:
            comparison['cpm_vs_benchmark'] = ((benchmark_metrics['cpm'] / metrics['cpm']) - 1) * 100
        else:
            comparison['cpm_vs_benchmark'] = 0
            
        # Hook Rate comparison (higher is better)
        if 'hook_rate' in metrics and 'hook_rate' in benchmark_metrics and benchmark_metrics['hook_rate'] > 0:
            comparison['hook_rate_vs_benchmark'] = ((metrics['hook_rate'] / benchmark_metrics['hook_rate']) - 1) * 100
        else:
            comparison['hook_rate_vs_benchmark'] = 0
            
        # Viewthrough Rate comparison (higher is better)
        if 'viewthrough_rate' in metrics and 'viewthrough_rate' in benchmark_metrics and benchmark_metrics['viewthrough_rate'] > 0:
            comparison['viewthrough_rate_vs_benchmark'] = ((metrics['viewthrough_rate'] / benchmark_metrics['viewthrough_rate']) - 1) * 100
        else:
            comparison['viewthrough_rate_vs_benchmark'] = 0
        
        # Calculate overall performance score
        # Weighted average of all metrics, with more weight on conversion metrics
        weights = {
            'ctr_vs_benchmark': 0.10,
            'cpa_vs_benchmark': 0.30,
            'roas_vs_benchmark': 0.30,
            'cpm_vs_benchmark': 0.10,
            'hook_rate_vs_benchmark': 0.10,
            'viewthrough_rate_vs_benchmark': 0.10
        }
        
        weighted_score = sum(comparison.get(metric, 0) * weight 
                            for metric, weight in weights.items())
        
        # Determine performance rating
        if weighted_score >= 20:
            rating = "Above Average"
        elif weighted_score <= -20:
            rating = "Below Average"
        else:
            rating = "Average"
        
        # Calculate performance stability score (0-100)
        # Higher score means more stable and reliable performance
        metrics_availability = sum(1 for metric in ['ctr', 'cpa', 'roas', 'cpm', 'hook_rate', 'viewthrough_rate'] 
                                  if metric in metrics and metrics[metric] > 0)
        stability_score = (metrics_availability / 6) * 100
        
        # Return comparison results
        result = {
            'metrics_vs_benchmark': comparison,
            'overall_performance_score': weighted_score,
            'performance_rating': rating,
            'stability_score': stability_score
        }
        
        logger.info(f"Performance analysis complete for ad {ad_data.get('ad_id', 'unknown')}, "
                   f"rating: {rating}, score: {weighted_score:.1f}")
        
        return result
    
    def analyze_segments(self, ad_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze demographic segments for an ad
        
        Args:
            ad_data: Ad performance data with breakdowns
            
        Returns:
            Dict: Segment analysis results
        """
        logger.info(f"Analyzing segments for ad {ad_data.get('ad_id', 'unknown')}")
        
        if 'breakdowns' not in ad_data or 'age_gender' not in ad_data['breakdowns']:
            logger.warning("No demographic breakdowns available for analysis")
            return {
                'best_segments': [],
                'worst_segments': [],
                'segment_performance': {}
            }
        
        age_gender_data = ad_data['breakdowns']['age_gender']
        
        # Analyze each segment
        segment_analysis = []
        for segment in age_gender_data:
            # Format segment name
            segment_name = f"{segment.get('age', 'unknown')} {segment.get('gender', 'unknown')}"
            segment_name = segment_name.lower().replace('-', ' ').replace('_', ' ').replace('+', ' plus')
            
            # Get benchmark for this segment if available
            segment_benchmarks = self.benchmarks.get('segments', {}).get(segment_name, {}) if self.benchmarks else {}
            
            # Calculate segment metrics
            analysis = {
                'segment_name': segment_name,
                'display_name': f"{segment.get('age', 'Unknown')} {segment.get('gender', 'Unknown')}",
                'metrics': {
                    'spend': segment.get('spend', 0),
                    'impressions': segment.get('impressions', 0),
                    'clicks': segment.get('clicks', 0),
                    'conversions': segment.get('conversions', 0),
                }
            }
            
            # Calculate derived metrics
            if analysis['metrics']['impressions'] > 0:
                analysis['metrics']['ctr'] = (analysis['metrics']['clicks'] / analysis['metrics']['impressions'])
                analysis['metrics']['cpm'] = (analysis['metrics']['spend'] / analysis['metrics']['impressions']) * 1000
            else:
                analysis['metrics']['ctr'] = 0
                analysis['metrics']['cpm'] = 0
                
            if analysis['metrics']['conversions'] > 0:
                analysis['metrics']['cpa'] = analysis['metrics']['spend'] / analysis['metrics']['conversions']
                
                # Calculate conversion rate
                if analysis['metrics']['clicks'] > 0:
                    analysis['metrics']['conversion_rate'] = (analysis['metrics']['conversions'] / analysis['metrics']['clicks']) * 100
                else:
                    analysis['metrics']['conversion_rate'] = 0
            else:
                analysis['metrics']['cpa'] = 0
                analysis['metrics']['conversion_rate'] = 0
            
            # Compare to segment benchmarks if available
            if segment_benchmarks:
                comparison = {}
                
                # CTR comparison
                if 'ctr' in segment_benchmarks and segment_benchmarks['ctr'] > 0:
                    comparison['ctr_vs_benchmark'] = ((analysis['metrics']['ctr'] / segment_benchmarks['ctr']) - 1) * 100
                else:
                    comparison['ctr_vs_benchmark'] = 0
                
                # CPA comparison (lower is better)
                if 'cpa' in segment_benchmarks and segment_benchmarks['cpa'] > 0 and analysis['metrics']['cpa'] > 0:
                    comparison['cpa_vs_benchmark'] = ((segment_benchmarks['cpa'] / analysis['metrics']['cpa']) - 1) * 100
                else:
                    comparison['cpa_vs_benchmark'] = 0
                
                # Add comparison to analysis
                analysis['comparison'] = comparison
                
                # Calculate segment score (weighted average of metrics)
                weights = {'ctr_vs_benchmark': 0.3, 'cpa_vs_benchmark': 0.7}  # More weight on CPA
                segment_score = sum(comparison.get(metric, 0) * weight 
                                  for metric, weight in weights.items())
                analysis['segment_score'] = segment_score
                
            else:
                # No benchmark available, score based on overall performance
                analysis['segment_score'] = 0
            
            segment_analysis.append(analysis)
        
        # Sort segments by score (highest first)
        sorted_segments = sorted(segment_analysis, key=lambda x: x.get('segment_score', 0), reverse=True)
        
        # Get best and worst performing segments
        best_segments = sorted_segments[:3] if len(sorted_segments) >= 3 else sorted_segments
        worst_segments = sorted_segments[-3:] if len(sorted_segments) >= 3 else sorted_segments
        worst_segments.reverse()  # Reverse to get worst first
        
        # Calculate contribution to overall performance
        total_spend = sum(segment.get('metrics', {}).get('spend', 0) for segment in segment_analysis)
        total_conversions = sum(segment.get('metrics', {}).get('conversions', 0) for segment in segment_analysis)
        
        for segment in segment_analysis:
            if total_spend > 0:
                segment['spend_contribution'] = (segment.get('metrics', {}).get('spend', 0) / total_spend) * 100
            else:
                segment['spend_contribution'] = 0
                
            if total_conversions > 0:
                segment['conversion_contribution'] = (segment.get('metrics', {}).get('conversions', 0) / total_conversions) * 100
            else:
                segment['conversion_contribution'] = 0
        
        # Format results
        segment_performance = {}
        for segment in segment_analysis:
            segment_performance[segment['segment_name']] = segment
        
        result = {
            'best_segments': [s['segment_name'] for s in best_segments],
            'worst_segments': [s['segment_name'] for s in worst_segments],
            'segment_performance': segment_performance
        }
        
        logger.info(f"Segment analysis complete for ad {ad_data.get('ad_id', 'unknown')}, "
                   f"best segment: {result['best_segments'][0] if result['best_segments'] else 'None'}")
        
        return result
    
    def analyze_performance(self, ad_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform comprehensive performance analysis on an ad
        
        Args:
            ad_data: Ad performance data
            
        Returns:
            Dict: Complete analysis results
        """
        logger.info(f"Starting comprehensive analysis for ad {ad_data.get('ad_id', 'unknown')}")
        
        # Ensure benchmarks are calculated if possible
        if not self.benchmarks and self.meta_client:
            self.benchmarks = self.calculate_benchmarks(self.meta_client)
        
        # Compare to benchmarks
        benchmark_comparison = self.compare_to_benchmarks(ad_data)
        
        # Analyze segments
        segment_analysis = self.analyze_segments(ad_data)
        
        # Combine results
        analysis = {
            'ad_id': ad_data.get('ad_id', 'unknown'),
            'ad_name': ad_data.get('ad_name', 'Unknown Ad'),
            'campaign_name': ad_data.get('campaign_name', 'Unknown Campaign'),
            'benchmark_comparison': benchmark_comparison,
            'segment_analysis': segment_analysis,
            'analysis_date': datetime.now().strftime('%Y-%m-%d')
        }
        
        # Add additional fields for reporting
        analysis['performance_rating'] = benchmark_comparison.get('performance_rating', 'Unknown')
        analysis['performance_score'] = benchmark_comparison.get('overall_performance_score', 0)
        analysis['best_segment'] = segment_analysis.get('best_segments', ['Unknown'])[0] if segment_analysis.get('best_segments') else 'Unknown'
        
        logger.info(f"Comprehensive analysis complete for ad {ad_data.get('ad_id', 'unknown')}")
        
        return analysis

# Example usage
if __name__ == "__main__":
    # Sample ad data for testing
    sample_ad = {
        "ad_id": "12345",
        "ad_name": "Test Ad",
        "campaign_name": "Test Campaign",
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
                {"age": "25-34", "gender": "female", "spend": 25.0, "impressions": 5000, "clicks": 100, "conversions": 6},
                {"age": "18-24", "gender": "male", "spend": 15.0, "impressions": 3000, "clicks": 50, "conversions": 2},
                {"age": "35-44", "gender": "female", "spend": 20.0, "impressions": 4000, "clicks": 45, "conversions": 3}
            ]
        }
    }
    
    analyzer = PerformanceAnalyzer()
    result = analyzer.analyze_performance(sample_ad)
    
    print(f"Ad: {result['ad_name']}")
    print(f"Performance Rating: {result['performance_rating']}")
    print(f"Performance Score: {result['performance_score']:.1f}")
    print(f"Best Segment: {result['best_segment']}")