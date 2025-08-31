#!/usr/bin/env python3
"""
Sheets Manager

This module handles all interactions with Google Sheets for the Creative Analysis Tool,
including creating and updating spreadsheets with ad performance data and insights.
"""

import logging
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Import our custom formatter
from src.sheets_formatter import SheetsFormatter

# Import settings from config
import sys

# Add project root to path if running as script
if __name__ == "__main__":
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.insert(0, project_root)

from config.settings import SHEETS_SPREADSHEET_ID, CONFIG_DIR

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SheetsManager:
    """Manages Google Sheets operations for Creative Analysis Tool"""
    
    # Base tab names for the spreadsheet
    DASHBOARD_TAB = "Dashboard"
    AD_DETAILS_TAB = "Ad Details"
    SEGMENTS_TAB = "Segments"
    
    # Valid regions
    VALID_REGIONS = ["ASI", "EUR", "LAT", "PAC", "GBR", "NAM"]
    
    # Column definitions for each tab
    DASHBOARD_COLUMNS = [
        "Date", "Ads Analyzed", "Avg Performance Score", "Top Performer", 
        "Score", "Bottom Performer", "Score"
    ]
    
    AD_DETAILS_COLUMNS = [
        "Launch Date", "Ad Name", "Creative Angle", "Status", 
        "Action", "Spend", "CPM", "Hook Rate", 
        "VT Rate", "CTR", "CPC", "CPR", 
        "Demographics", "AI Analysis"
    ]
    
    SEGMENTS_COLUMNS = [
        "Ad ID", "Ad Name", "Segment", "Spend (£)", "Impressions", "Clicks",
        "Conversions", "CTR (%)", "CPA (£)", "Performance (%)"
    ]
    
    def __init__(
        self,
        spreadsheet_id: Optional[str] = SHEETS_SPREADSHEET_ID,
        credentials_path: Optional[str] = None,
        region: str = "GBR",
        output_dir: Optional[str] = None
    ):
        """
        Initialize the Sheets Manager
        
        Args:
            spreadsheet_id: ID of the Google Sheet to use (from settings or .env)
            credentials_path: Path to service account credentials file
            region: Region code (ASI, EUR, LAT, PAC, GBR, NAM)
        """
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = credentials_path
        
        # Set region and validate it
        if region not in self.VALID_REGIONS:
            logger.warning(f"Invalid region: {region}, defaulting to GBR")
            region = "GBR"
        self.region = region
        
        # Initialize the formatter
        self.formatter = SheetsFormatter(output_dir=output_dir)
        
        # Initialize sheets client
        self.service = self._authenticate()
        
        # Create or validate spreadsheet
        if not self.spreadsheet_id:
            logger.info("No spreadsheet ID provided, creating a new spreadsheet")
            self.spreadsheet_id = self._create_spreadsheet("Creative Performance Analysis")
        
        logger.info(f"Sheets Manager initialized with spreadsheet ID: {self.spreadsheet_id} for region {self.region}")
        
        # Ensure required tabs exist
        self._ensure_tabs_exist()
    
    def _authenticate(self):
        """
        Authenticate with Google Sheets API
        
        Returns:
            Google Sheets API service
        
        Raises:
            Exception: If authentication fails
        """
        try:
            # Import needed here to ensure it's in scope
            import os
            from google.oauth2 import service_account
            
            # If credentials file is provided, use service account
            if self.credentials_path:
                credentials = Credentials.from_service_account_file(
                    self.credentials_path,
                    scopes=['https://www.googleapis.com/auth/spreadsheets']
                )
                service = build('sheets', 'v4', credentials=credentials)
                logger.info("Authenticated with service account")
            # Try using the credentials file in the config directory
            elif os.path.exists(os.path.join(CONFIG_DIR, 'sheets-api-key.json')):
                credentials = Credentials.from_service_account_file(
                    os.path.join(CONFIG_DIR, 'sheets-api-key.json'),
                    scopes=['https://www.googleapis.com/auth/spreadsheets']
                )
                service = build('sheets', 'v4', credentials=credentials)
                logger.info("Authenticated with service account from config directory")
            
            # Otherwise use application default credentials
            else:

                # Try to use GOOGLE_APPLICATION_CREDENTIALS environment variable
                credentials = None
                
                try:
                    credentials = service_account.Credentials.from_service_account_info(
                        info=json.loads(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '{}')),
                        scopes=['https://www.googleapis.com/auth/spreadsheets']
                    )
                except (json.JSONDecodeError, TypeError):
                    # If not a valid JSON string, try as a file path
                    if os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
                        try:
                            credentials = service_account.Credentials.from_service_account_file(
                                os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'),
                                scopes=['https://www.googleapis.com/auth/spreadsheets']
                            )
                        except Exception as e:
                            logger.warning(f"Could not load credentials from file: {e}")
                
                # Fall back to application default credentials
                if not credentials:
                    from google.auth import default
                    credentials, _ = default(scopes=['https://www.googleapis.com/auth/spreadsheets'])
                    logger.info("Using application default credentials")
                
                service = build('sheets', 'v4', credentials=credentials)
            
            return service
            
        except Exception as e:
            logger.exception(f"Authentication failed: {str(e)}")
            raise
    
    def _create_spreadsheet(self, title: str) -> str:
        """
        Create a new Google Sheet
        
        Args:
            title: Title of the new spreadsheet
            
        Returns:
            str: ID of the created spreadsheet
            
        Raises:
            Exception: If spreadsheet creation fails
        """
        try:
            spreadsheet = {
                'properties': {
                    'title': title
                }
            }
            
            request = self.service.spreadsheets().create(body=spreadsheet)
            response = request.execute()
            
            spreadsheet_id = response['spreadsheetId']
            logger.info(f"Created new spreadsheet with ID: {spreadsheet_id}")
            
            return spreadsheet_id
            
        except Exception as e:
            logger.exception(f"Failed to create spreadsheet: {str(e)}")
            raise
    
    def _get_region_tab_name(self, base_tab: str) -> str:
        """
        Get the region-specific tab name
        
        Args:
            base_tab: Base tab name
            
        Returns:
            str: Region name for Ad Details tab, region_tab for others
        """
        # For Ad Details tab, use just the region name
        if base_tab == self.AD_DETAILS_TAB:
            return self.region
        
        # For other tabs (Dashboard, Segments), use region prefix
        return f"{self.region}_{base_tab}"
    
    def _ensure_tabs_exist(self) -> None:
        """
        Ensure that the region tab exists in the spreadsheet, creating it if not
        
        Raises:
            Exception: If tab creation fails
        """
        try:
            # Get existing sheets
            sheet_metadata = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            sheets = sheet_metadata.get('sheets', [])
            existing_titles = [sheet.get('properties', {}).get('title') for sheet in sheets]
            
            # Get region tab name (for Ad Details, this is just the region name)
            region_tab = self._get_region_tab_name(self.AD_DETAILS_TAB)  # This will return just the region name
            
            # Check if region tab exists and create if not
            requests = []
            if region_tab not in existing_titles:
                requests.append({
                    'addSheet': {
                        'properties': {
                            'title': region_tab
                        }
                    }
                })
            
            # Execute batch update if region tab needs to be created
            if requests:
                body = {'requests': requests}
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body=body
                ).execute()
                logger.info(f"Created {region_tab} tab for region {self.region}")
            
            # Initialize columns for region tab if not already populated
            self._initialize_columns(region_tab, self.AD_DETAILS_COLUMNS)
            
        except Exception as e:
            logger.exception(f"Failed to ensure tabs exist for region {self.region}: {str(e)}")
            raise
    
    def _initialize_columns(self, tab_name: str, columns: List[str]) -> None:
        """
        Initialize column headers for a tab if not already populated
        
        Args:
            tab_name: Name of the tab to initialize
            columns: List of column headers
            
        Raises:
            Exception: If initialization fails
        """
        try:
            # Check if headers already exist
            range_name = f"{tab_name}!A1:{chr(65 + len(columns) - 1)}1"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [[]])
            
            # If no headers or incomplete headers, update them
            if not values or not values[0] or len(values[0]) < len(columns):
                body = {
                    'values': [columns]
                }
                
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                    valueInputOption='RAW',
                    body=body
                ).execute()
                
                # Format header row
                self._format_header_row(tab_name, len(columns))
                logger.info(f"Initialized column headers for tab {tab_name}")
            
        except Exception as e:
            logger.exception(f"Failed to initialize columns for tab {tab_name}: {str(e)}")
            raise
    
    def _format_header_row(self, tab_name: str, num_columns: int) -> None:
        """
        Format the header row with bold text and background color
        
        Args:
            tab_name: Name of the tab to format
            num_columns: Number of columns in the header
            
        Raises:
            Exception: If formatting fails
        """
        try:
            # Get sheet ID for the tab
            sheet_metadata = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            sheets = sheet_metadata.get('sheets', [])
            sheet_id = None
            
            for sheet in sheets:
                if sheet.get('properties', {}).get('title') == tab_name:
                    sheet_id = sheet.get('properties', {}).get('sheetId')
                    break
            
            if not sheet_id:
                logger.warning(f"Could not find sheet ID for tab {tab_name}")
                return
            
            # Apply formatting
            requests = [
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': 0,
                            'endRowIndex': 1,
                            'startColumnIndex': 0,
                            'endColumnIndex': num_columns
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'backgroundColor': {
                                    'red': 0.086,
                                    'green': 0.2,
                                    'blue': 0.0
                                },
                                'textFormat': {
                                    'bold': True,
                                    'foregroundColor': {
                                        'red': 0.624,
                                        'green': 0.91,
                                        'blue': 0.439
                                    }
                                }
                            }
                        },
                        'fields': 'userEnteredFormat(backgroundColor,textFormat)'
                    }
                },
                {
                    'updateDimensionProperties': {
                        'range': {
                            'sheetId': sheet_id,
                            'dimension': 'COLUMNS',
                            'startIndex': 0,
                            'endIndex': num_columns
                        },
                        'properties': {
                            'pixelSize': 150
                        },
                        'fields': 'pixelSize'
                    }
                },
                {
                    'updateDimensionProperties': {
                        'range': {
                            'sheetId': sheet_id,
                            'dimension': 'ROWS',
                            'startIndex': 0,
                            'endIndex': 1
                        },
                        'properties': {
                            'pixelSize': 30
                        },
                        'fields': 'pixelSize'
                    }
                }
            ]
            
            body = {'requests': requests}
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
            
        except Exception as e:
            logger.exception(f"Failed to format header row for tab {tab_name}: {str(e)}")
            raise
    
    def get_spreadsheet_id(self) -> str:
        """
        Get the ID of the Google Sheet
        
        Returns:
            str: Spreadsheet ID
        """
        return self.spreadsheet_id
    
    def get_spreadsheet_url(self) -> str:
        """
        Get the URL for the Google Sheet
        
        Returns:
            str: URL to access the spreadsheet
        """
        return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit"
    
    def update_dashboard(self, summary_data: Dict[str, Any]) -> bool:
        """
        Update the Dashboard tab with summary metrics
        
        Args:
            summary_data: Dictionary containing summary metrics
                - date: Analysis date (str in YYYY-MM-DD format)
                - ads_analyzed: Number of ads analyzed (int)
                - avg_performance_score: Average performance score (float)
                - top_performers: List of top performing ads [{"ad_id": str, "ad_name": str, "score": float}, ...]
                - bottom_performers: List of bottom performing ads [{"ad_id": str, "ad_name": str, "score": float}, ...]
                
        Returns:
            bool: True if update was successful
            
        Raises:
            Exception: If update fails
        """
        # Get region-specific dashboard tab name
        dashboard_tab = self._get_region_tab_name(self.DASHBOARD_TAB)
        logger.info(f"Updating {dashboard_tab} tab with summary metrics for region {self.region}")
        
        try:
            # Format data for dashboard row
            date_str = summary_data.get('date', datetime.now().strftime('%Y-%m-%d'))
            ads_analyzed = summary_data.get('ads_analyzed', 0)
            avg_performance_score = summary_data.get('avg_performance_score', 0)
            
            # Get top performer
            top_performers = summary_data.get('top_performers', [])
            top_performer = f"{top_performers[0].get('ad_name', 'Unknown')}" if top_performers else "None"
            top_score = top_performers[0].get('score', 0) if top_performers else 0
            
            # Get bottom performer
            bottom_performers = summary_data.get('bottom_performers', [])
            bottom_performer = f"{bottom_performers[0].get('ad_name', 'Unknown')}" if bottom_performers else "None"
            bottom_score = bottom_performers[0].get('score', 0) if bottom_performers else 0
            
            # Create row values
            row_values = [
                date_str,
                ads_analyzed,
                avg_performance_score,
                top_performer,
                top_score,
                bottom_performer,
                bottom_score
            ]
            
            # Find the next empty row in the Dashboard tab
            range_name = f"{dashboard_tab}!A:A"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            next_row = len(values) + 1
            
            # Check if today's date already exists in the first column
            today_row = None
            for i, row in enumerate(values):
                if row and row[0] == date_str:
                    today_row = i + 1  # 1-based indexing for Sheets API
                    break
            
            # Determine whether to insert a new row or update existing
            update_row = today_row if today_row else next_row
            range_name = f"{dashboard_tab}!A{update_row}:{chr(65 + len(row_values) - 1)}{update_row}"
            
            # Update or insert the row
            body = {
                'values': [row_values]
            }
            
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
            # If this is a new row, apply formatting
            if not today_row:
                self._format_dashboard_row(update_row)
            
            logger.info(f"Dashboard updated successfully at row {update_row}")
            
            # Update dashboard summary visualization (recent trend chart)
            self._update_dashboard_summary(dashboard_tab)
            
            return True
            
        except Exception as e:
            logger.exception(f"Failed to update Dashboard: {str(e)}")
            return False
    
    def _update_dashboard_summary(self, dashboard_tab: str) -> None:
        """
        Update the dashboard summary visualization (trend charts)
        
        This creates or updates charts showing performance trends over time
        
        Args:
            dashboard_tab: The dashboard tab name (with region prefix)
        """
        try:
            # Get sheet ID for dashboard tab
            sheet_metadata = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            sheets = sheet_metadata.get('sheets', [])
            sheet_id = None
            
            for sheet in sheets:
                if sheet.get('properties', {}).get('title') == dashboard_tab:
                    sheet_id = sheet.get('properties', {}).get('sheetId')
                    break
            
            if not sheet_id:
                logger.warning("Could not find dashboard sheet ID for charts")
                return
            
            # Check if charts already exist (to avoid duplicating them)
            charts_response = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id,
                ranges=[dashboard_tab],
                fields='sheets.charts'
            ).execute()
            
            dashboard_sheet = charts_response.get('sheets', [])[0]
            existing_charts = dashboard_sheet.get('charts', [])
            
            # If charts already exist, don't recreate them
            if existing_charts:
                logger.info("Dashboard charts already exist, skipping creation")
                return
            
            # Create performance trend chart
            requests = [
                {
                    'addChart': {
                        'chart': {
                            'spec': {
                                'title': 'Performance Trend',
                                'basicChart': {
                                    'chartType': 'LINE',
                                    'legendPosition': 'BOTTOM_LEGEND',
                                    'axis': [
                                        {
                                            'position': 'BOTTOM_AXIS',
                                            'title': 'Date'
                                        },
                                        {
                                            'position': 'LEFT_AXIS',
                                            'title': 'Performance Score'
                                        }
                                    ],
                                    'domains': [
                                        {
                                            'domain': {
                                                'sourceRange': {
                                                    'sources': [
                                                        {
                                                            'sheetId': sheet_id,
                                                            'startRowIndex': 1,  # Skip header row
                                                            'endRowIndex': 15,  # Show up to 14 days of data
                                                            'startColumnIndex': 0,  # Date column
                                                            'endColumnIndex': 1
                                                        }
                                                    ]
                                                }
                                            }
                                        }
                                    ],
                                    'series': [
                                        {
                                            'series': {
                                                'sourceRange': {
                                                    'sources': [
                                                        {
                                                            'sheetId': sheet_id,
                                                            'startRowIndex': 1,  # Skip header row
                                                            'endRowIndex': 15,  # Show up to 14 days of data
                                                            'startColumnIndex': 2,  # Avg performance score column
                                                            'endColumnIndex': 3
                                                        }
                                                    ]
                                                }
                                            },
                                            'targetAxis': 'LEFT_AXIS',
                                            'chartType': 'LINE'
                                        }
                                    ],
                                    'headerCount': 1
                                }
                            },
                            'position': {
                                'overlayPosition': {
                                    'anchorCell': {
                                        'sheetId': sheet_id,
                                        'rowIndex': 1,
                                        'columnIndex': 8  # Position chart to the right of data
                                    },
                                    'offsetXPixels': 10,
                                    'offsetYPixels': 10,
                                    'widthPixels': 600,
                                    'heightPixels': 400
                                }
                            }
                        }
                    }
                }
            ]
            
            # Execute batch update to add charts
            body = {'requests': requests}
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
            
            logger.info("Dashboard summary charts created successfully")
            
        except Exception as e:
            logger.exception(f"Failed to update dashboard summary: {str(e)}")
    
    def _format_dashboard_row(self, row_index: int) -> None:
        """
        Apply formatting to a dashboard row
        
        Args:
            row_index: The 1-based row index to format
        """
        try:
            # Get region-specific dashboard tab name
            dashboard_tab = self._get_region_tab_name(self.DASHBOARD_TAB)
            
            # Get sheet ID for dashboard tab
            sheet_metadata = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            sheets = sheet_metadata.get('sheets', [])
            sheet_id = None
            
            for sheet in sheets:
                if sheet.get('properties', {}).get('title') == dashboard_tab:
                    sheet_id = sheet.get('properties', {}).get('sheetId')
                    break
            
            if not sheet_id:
                logger.warning(f"Could not find sheet ID for tab {dashboard_tab}")
                return
            
            # Apply alternating row background
            background_color = {
                'red': 0.95,
                'green': 0.95,
                'blue': 0.95
            } if row_index % 2 == 0 else {
                'red': 1.0,
                'green': 1.0,
                'blue': 1.0
            }
            
            requests = [
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': row_index - 1,  # 0-based for API
                            'endRowIndex': row_index,
                            'startColumnIndex': 0,
                            'endColumnIndex': len(self.DASHBOARD_COLUMNS)
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'backgroundColor': background_color,
                                'horizontalAlignment': 'CENTER',
                                'verticalAlignment': 'MIDDLE',
                                'textFormat': {
                                    'bold': False
                                }
                            }
                        },
                        'fields': 'userEnteredFormat(backgroundColor,horizontalAlignment,verticalAlignment,textFormat)'
                    }
                },
                # Left-align text columns
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': row_index - 1,
                            'endRowIndex': row_index,
                            'startColumnIndex': 0,  # Date column
                            'endColumnIndex': 1
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'horizontalAlignment': 'LEFT',
                                'verticalAlignment': 'MIDDLE'
                            }
                        },
                        'fields': 'userEnteredFormat(horizontalAlignment,verticalAlignment)'
                    }
                },
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': row_index - 1,
                            'endRowIndex': row_index,
                            'startColumnIndex': 3,  # Top performer column
                            'endColumnIndex': 4
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'horizontalAlignment': 'LEFT',
                                'verticalAlignment': 'MIDDLE'
                            }
                        },
                        'fields': 'userEnteredFormat(horizontalAlignment,verticalAlignment)'
                    }
                },
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': row_index - 1,
                            'endRowIndex': row_index,
                            'startColumnIndex': 5,  # Bottom performer column
                            'endColumnIndex': 6
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'horizontalAlignment': 'LEFT',
                                'verticalAlignment': 'MIDDLE'
                            }
                        },
                        'fields': 'userEnteredFormat(horizontalAlignment,verticalAlignment)'
                    }
                }
            ]
            
            body = {'requests': requests}
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
            
        except Exception as e:
            logger.exception(f"Failed to format dashboard row: {str(e)}")
    
    def update_ad_details(self, ad_data: Dict[str, Any], analysis_result: Dict[str, Any]) -> bool:
        """
        Update the Ad Details tab with ad performance data
        
        Args:
            ad_data: Ad data from Meta API
            analysis_result: Performance analysis result
            
        Returns:
            bool: True if update was successful
            
        Raises:
            Exception: If update fails
        """
        # Get region-specific ad details tab name
        ad_details_tab = self._get_region_tab_name(self.AD_DETAILS_TAB)
        logger.info(f"Updating {ad_details_tab} tab for ad {ad_data.get('ad_id', 'unknown')} in region {self.region}")
        
        try:
            # Extract ad data fields
            ad_id = ad_data.get('ad_id', 'unknown')
            ad_name = ad_data.get('ad_name', 'Unknown Ad')
            campaign_name = ad_data.get('campaign_name', 'Unknown Campaign')
            
            # Format dates
            created_date = ad_data.get('created_time', '')
            if created_date and 'T' in created_date:
                # Extract just the date part if it's in ISO format
                created_date = created_date.split('T')[0]
                
            analysis_date = datetime.now().strftime('%Y-%m-%d')
            
            # Extract metrics
            metrics = ad_data.get('metrics', {})
            spend = metrics.get('spend', 0)
            impressions = metrics.get('impressions', 0)
            clicks = metrics.get('clicks', 0)
            conversions = metrics.get('conversions', 0)
            ctr = metrics.get('ctr', 0)
            cpa = metrics.get('cpa', 0)
            cpm = metrics.get('cpm', 0)
            # ROAS removed as per client request
            
            # Extract analysis data
            benchmark_comparison = analysis_result.get('benchmark_comparison', {})
            performance_vs_benchmark = benchmark_comparison.get('overall_performance_score', 0)
            performance_rating = benchmark_comparison.get('performance_rating', 'Average')
            
            # Get best segment
            segment_analysis = analysis_result.get('segment_analysis', {})
            best_segment = segment_analysis.get('best_segments', ['Unknown'])[0] if segment_analysis.get('best_segments') else 'Unknown'
            
            # Get creative preview URL
            creative = ad_data.get('creative', {}) or {}
            image_url = creative.get('image_url', '')
            
            # Format image URL as a clickable link formula in Google Sheets
            creative_preview = f'=HYPERLINK("{image_url}", "View Creative")' if image_url else ''
            
            # Create row values
            row_values = [
                ad_id,
                ad_name,
                campaign_name,
                created_date,
                analysis_date,
                spend,
                impressions,
                clicks,
                conversions,
                ctr,
                cpa,
                cpm,
                performance_vs_benchmark,
                performance_rating,
                best_segment,
                creative_preview
            ]
            
            # Find if the ad already exists in the Ad Details tab
            range_name = f"{ad_details_tab}!A:A"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            existing_row = None
            
            # Skip header row and search for ad ID
            for i, row in enumerate(values[1:], 2):  # Start from row 2 (index 1+1)
                if row and row[0] == ad_id:
                    existing_row = i
                    break
            
            # Determine whether to insert a new row or update existing
            next_row = len(values) + 1
            update_row = existing_row if existing_row else next_row
            range_name = f"{ad_details_tab}!A{update_row}:{chr(65 + len(row_values) - 1)}{update_row}"
            
            # Update or insert the row
            body = {
                'values': [row_values]
            }
            
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',  # Use USER_ENTERED for formulas to work
                body=body
            ).execute()
            
            # If this is a new row, apply formatting
            if not existing_row:
                self._format_ad_details_row(update_row, performance_vs_benchmark, ad_details_tab)
            
            logger.info(f"Ad details updated successfully for ad {ad_id} at row {update_row} in region {self.region}")
            return True
            
        except Exception as e:
            logger.exception(f"Failed to update ad details: {str(e)}")
            return False
    
    def _format_ad_details_row(self, row_index: int, performance_score: float, ad_details_tab: str = None) -> None:
        """
        Apply formatting to an ad details row based on performance
        
        Args:
            row_index: The 1-based row index to format
            performance_score: Performance score to determine formatting
            ad_details_tab: The ad details tab name (with region prefix)
        """
        try:
            # If ad_details_tab is not provided, get it from the region
            if ad_details_tab is None:
                ad_details_tab = self._get_region_tab_name(self.AD_DETAILS_TAB)
                
            # Get sheet ID for ad details tab
            sheet_metadata = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            sheets = sheet_metadata.get('sheets', [])
            sheet_id = None
            
            for sheet in sheets:
                if sheet.get('properties', {}).get('title') == ad_details_tab:
                    sheet_id = sheet.get('properties', {}).get('sheetId')
                    break
            
            if not sheet_id:
                logger.warning(f"Could not find sheet ID for tab {ad_details_tab}")
                return
            
            # Apply alternating row background
            background_color = {
                'red': 0.95,
                'green': 0.95,
                'blue': 0.95
            } if row_index % 2 == 0 else {
                'red': 1.0,
                'green': 1.0,
                'blue': 1.0
            }
            
            # Determine performance color (green for good, red for bad)
            performance_color = {}
            if performance_score >= 20:
                # Good performance - green
                performance_color = {'red': 0.0, 'green': 0.6, 'blue': 0.0}
            elif performance_score <= -20:
                # Poor performance - red
                performance_color = {'red': 0.8, 'green': 0.0, 'blue': 0.0}
            
            requests = [
                # Basic row formatting
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': row_index - 1,  # 0-based for API
                            'endRowIndex': row_index,
                            'startColumnIndex': 0,
                            'endColumnIndex': len(self.AD_DETAILS_COLUMNS)
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'backgroundColor': background_color,
                                'horizontalAlignment': 'CENTER',
                                'verticalAlignment': 'MIDDLE',
                                'textFormat': {
                                    'bold': False
                                }
                            }
                        },
                        'fields': 'userEnteredFormat(backgroundColor,horizontalAlignment,verticalAlignment,textFormat)'
                    }
                },
                # Left-align text columns
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': row_index - 1,
                            'endRowIndex': row_index,
                            'startColumnIndex': 0,  # Ad ID column
                            'endColumnIndex': 3  # Through Campaign column
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'horizontalAlignment': 'LEFT',
                                'verticalAlignment': 'MIDDLE'
                            }
                        },
                        'fields': 'userEnteredFormat(horizontalAlignment,verticalAlignment)'
                    }
                },
                # Left-align more text columns
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': row_index - 1,
                            'endRowIndex': row_index,
                            'startColumnIndex': 14,  # Rating column
                            'endColumnIndex': 16  # Through Best Segment
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'horizontalAlignment': 'LEFT',
                                'verticalAlignment': 'MIDDLE'
                            }
                        },
                        'fields': 'userEnteredFormat(horizontalAlignment,verticalAlignment)'
                    }
                }
            ]
            
            # Add performance score color if applicable
            if performance_color:
                requests.append({
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': row_index - 1,
                            'endRowIndex': row_index,
                            'startColumnIndex': 13,  # Performance vs Benchmark column
                            'endColumnIndex': 14
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'textFormat': {
                                    'foregroundColor': performance_color,
                                    'bold': True
                                }
                            }
                        },
                        'fields': 'userEnteredFormat(textFormat)'
                    }
                })
                
                # Also color the rating column
                requests.append({
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': row_index - 1,
                            'endRowIndex': row_index,
                            'startColumnIndex': 14,  # Rating column
                            'endColumnIndex': 15
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'textFormat': {
                                    'foregroundColor': performance_color,
                                    'bold': True
                                }
                            }
                        },
                        'fields': 'userEnteredFormat(textFormat)'
                    }
                })
            
            # Apply number formatting
            # Spend, CPA, CPM columns (currency format)
            currency_columns = [5, 10, 12]  # Spend, CPA, CPM
            for column_index in currency_columns:
                requests.append({
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': row_index - 1,
                            'endRowIndex': row_index,
                            'startColumnIndex': column_index,
                            'endColumnIndex': column_index + 1
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'numberFormat': {
                                    'type': 'CURRENCY',
                                    'pattern': '£#,##0.00'
                                }
                            }
                        },
                        'fields': 'userEnteredFormat(numberFormat)'
                    }
                })
            
            # Percentage formatting for CTR and Performance vs Benchmark
            percentage_columns = [9, 13]  # CTR, Performance vs Benchmark
            for column_index in percentage_columns:
                requests.append({
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': row_index - 1,
                            'endRowIndex': row_index,
                            'startColumnIndex': column_index,
                            'endColumnIndex': column_index + 1
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'numberFormat': {
                                    'type': 'PERCENT',
                                    'pattern': '0.00%'
                                }
                            }
                        },
                        'fields': 'userEnteredFormat(numberFormat)'
                    }
                })
            
            # Number formatting for impressions, clicks, conversions
            number_columns = [6, 7, 8]  # Impressions, Clicks, Conversions
            for column_index in number_columns:
                requests.append({
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': row_index - 1,
                            'endRowIndex': row_index,
                            'startColumnIndex': column_index,
                            'endColumnIndex': column_index + 1
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'numberFormat': {
                                    'type': 'NUMBER',
                                    'pattern': '#,##0'
                                }
                            }
                        },
                        'fields': 'userEnteredFormat(numberFormat)'
                    }
                })
            
            # ROAS formatting (decimal format)
            requests.append({
                'repeatCell': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': row_index - 1,
                        'endRowIndex': row_index,
                        'startColumnIndex': 11,  # ROAS column
                        'endColumnIndex': 12
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'numberFormat': {
                                'type': 'NUMBER',
                                'pattern': '0.0x'
                            }
                        }
                    },
                    'fields': 'userEnteredFormat(numberFormat)'
                }
            })
            
            body = {'requests': requests}
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
            
        except Exception as e:
            logger.exception(f"Failed to format ad details row: {str(e)}")
    
    def update_ad_details_batch(self, ads_data: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Batch update multiple ad records in the Ad Details tab
        
        Args:
            ads_data: List of dictionaries containing ad_data and analysis_result pairs
                [{"ad_data": {...}, "analysis_result": {...}}, ...]
                
        Returns:
            Tuple[int, int]: (success_count, error_count)
        """
        logger.info(f"Batch updating Ad Details for {len(ads_data)} ads")
        
        # Format the data according to new specifications
        formatted_ads = self.formatter.format_ad_data_for_sheets(ads_data)
        sheets_ready_ads = self.formatter.create_sheets_formulas(formatted_ads)
        
        # No longer exporting to CSV - Google Sheets only
        
        # Now update the Google Sheets with the formatted data
        success_count = 0
        error_count = 0
        
        # Get the Ad Details tab name for this region
        ad_details_tab = self._get_region_tab_name(self.AD_DETAILS_TAB)
        
        try:
            # Format data for sheets API
            rows_data = self.formatter.format_for_sheets_api(sheets_ready_ads)
            
            # Get sheet ID for this tab
            sheet_id = self._get_sheet_id(ad_details_tab)
            if not sheet_id:
                logger.error(f"Could not find sheet ID for {ad_details_tab}")
                return 0, len(ads_data)
            
            # Find the first empty row to append data
            # Get current data to determine where to append
            current_data_range = f"{ad_details_tab}!A:A"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=current_data_range
            ).execute()
            
            values = result.get('values', [])
            next_row = len(values) + 1
            if next_row == 1:  # No data exists yet, add header row
                next_row = 1
            else:  # Data exists, append after last row
                next_row = max(2, next_row)  # Make sure we start at row 2 at minimum
            
            # Write new data (including header if this is the first data)
            body = {
                'values': rows_data[1:] if next_row > 1 else rows_data  # Include header if first data
            }
            
            update_range = f"{ad_details_tab}!A{next_row}"  # Append after last row
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=update_range,
                valueInputOption='USER_ENTERED',  # For formulas to work
                body=body
            ).execute()
            
            # Apply formatting
            self._apply_special_formatting(sheet_id, len(sheets_ready_ads))
            
            success_count = len(sheets_ready_ads)
            logger.info(f"Ad details batch update complete: {success_count} ads updated")
            
        except Exception as e:
            logger.exception(f"Failed to batch update sheets: {str(e)}")
            error_count = len(sheets_ready_ads)
        
        return success_count, error_count
        
    def _get_sheet_id(self, tab_name: str) -> Optional[int]:
        """
        Get sheet ID for a specific tab name
        
        Args:
            tab_name: Tab name to find
            
        Returns:
            Optional[int]: Sheet ID or None if not found
        """
        try:
            sheet_metadata = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            sheets = sheet_metadata.get('sheets', [])
            
            for sheet in sheets:
                if sheet.get('properties', {}).get('title') == tab_name:
                    return sheet.get('properties', {}).get('sheetId')
            
            return None
        except Exception as e:
            logger.exception(f"Error getting sheet ID: {str(e)}")
            return None
            
    def _apply_special_formatting(self, sheet_id: int, row_count: int) -> None:
        """
        Apply special formatting for the new sheet format with hyperlinks, bullets, etc.
        
        Args:
            sheet_id: Sheet ID to format
            row_count: Number of new data rows to format
        """
        # Get the starting row for new data
        current_data_range = f"!A:A"  # Just look at column A to count rows
        result = self.service.spreadsheets().get(
            spreadsheetId=self.spreadsheet_id,
            includeGridData=False
        ).execute()
        
        # Find the sheet and get its properties
        start_row = 1  # Default to 1 if we can't determine existing rows
        for sheet in result.get('sheets', []):
            if sheet.get('properties', {}).get('sheetId') == sheet_id:
                # Get sheet dimensions
                grid_props = sheet.get('properties', {}).get('gridProperties', {})
                start_row = max(1, grid_props.get('rowCount', 1) - row_count)
                break
        try:
            requests = []
            
            # Set column widths appropriate for content
            requests.append({
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': sheet_id,
                        'dimension': 'COLUMNS',
                        'startIndex': 0,  # Date Launched
                        'endIndex': 1
                    },
                    'properties': {'pixelSize': 100},
                    'fields': 'pixelSize'
                }
            })
            
            requests.append({
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': sheet_id,
                        'dimension': 'COLUMNS',
                        'startIndex': 1,  # Ad Name
                        'endIndex': 2
                    },
                    'properties': {'pixelSize': 250},
                    'fields': 'pixelSize'
                }
            })
            
            # Make Demographics and AI Analysis columns wider
            requests.append({
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': sheet_id,
                        'dimension': 'COLUMNS',
                        'startIndex': 6,  # Demographics
                        'endIndex': 8     # Through AI Analysis
                    },
                    'properties': {'pixelSize': 300},
                    'fields': 'pixelSize'
                }
            })
            
            # Apply text wrapping to Demographics and AI Analysis
            requests.append({
                'repeatCell': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': 1,
                        'endRowIndex': row_count + 1,
                        'startColumnIndex': 6,
                        'endColumnIndex': 8
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'wrapStrategy': 'WRAP',
                            'verticalAlignment': 'MIDDLE',
                            'horizontalAlignment': 'LEFT'
                        }
                    },
                    'fields': 'userEnteredFormat(wrapStrategy,verticalAlignment,horizontalAlignment)'
                }
            })
            
            # Apply formatting for CPR column with mixed bold/regular text
            # Note: This can't be done directly in batch update - 
            # requires textFormatRuns which is implemented in the actual cell values
            
            # Set row heights taller for multiline content
            requests.append({
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': sheet_id,
                        'dimension': 'ROWS',
                        'startIndex': 1,
                        'endIndex': row_count + 1
                    },
                    'properties': {'pixelSize': 120},
                    'fields': 'pixelSize'
                }
            })
            
            # Set data validation for status column
            requests.append({
                'setDataValidation': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': 1,
                        'endRowIndex': 1000,  # Apply to all potential rows
                        'startColumnIndex': 3,  # Status column
                        'endColumnIndex': 4
                    },
                    'rule': {
                        'condition': {
                            'type': 'ONE_OF_LIST',
                            'values': [
                                {'userEnteredValue': 'Winning'},
                                {'userEnteredValue': 'Average'},
                                {'userEnteredValue': 'Losing'}
                            ]
                        },
                        'showCustomUi': True,
                        'strict': False
                    }
                }
            })
            
            # Set data validation for action column
            requests.append({
                'setDataValidation': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': 1,
                        'endRowIndex': 1000,  # Apply to all potential rows
                        'startColumnIndex': 4,  # Action column
                        'endColumnIndex': 5
                    },
                    'rule': {
                        'condition': {
                            'type': 'ONE_OF_LIST',
                            'values': [
                                {'userEnteredValue': 'Scale'},
                                {'userEnteredValue': 'Monitor'},
                                {'userEnteredValue': 'Stop'}
                            ]
                        },
                        'showCustomUi': True,
                        'strict': False
                    }
                }
            })
            
            # Set data validation for creative angle column
            requests.append({
                'setDataValidation': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': 1,
                        'endRowIndex': 1000,  # Apply to all potential rows
                        'startColumnIndex': 2,  # Creative angle column
                        'endColumnIndex': 3
                    },
                    'rule': {
                        'condition': {
                            'type': 'ONE_OF_LIST',
                            'values': [
                                {'userEnteredValue': 'Comparison'},
                                {'userEnteredValue': 'Testimonial'},
                                {'userEnteredValue': 'Educational'},
                                {'userEnteredValue': 'Problem-Solution'},
                                {'userEnteredValue': 'Lifestyle'},
                                {'userEnteredValue': 'Product Demo'}
                            ]
                        },
                        'showCustomUi': True,
                        'strict': False
                    }
                }
            })
            
            # Add conditional formatting for status column
            requests.append({
                'addConditionalFormatRule': {
                    'rule': {
                        'ranges': [{
                            'sheetId': sheet_id,
                            'startRowIndex': 1,
                            'endRowIndex': 1000,
                            'startColumnIndex': 3,  # Status column
                            'endColumnIndex': 4
                        }],
                        'booleanRule': {
                            'condition': {
                                'type': 'TEXT_EQ',
                                'values': [{'userEnteredValue': 'Winning'}]
                            },
                            'format': {
                                'textFormat': {
                                    'foregroundColor': {'red': 0.0, 'green': 0.6, 'blue': 0.0}  # Green color
                                }
                            }
                        }
                    },
                    'index': 0
                }
            })
            
            # Add conditional formatting for Average status
            requests.append({
                'addConditionalFormatRule': {
                    'rule': {
                        'ranges': [{
                            'sheetId': sheet_id,
                            'startRowIndex': 1,
                            'endRowIndex': 1000,
                            'startColumnIndex': 3,  # Status column
                            'endColumnIndex': 4
                        }],
                        'booleanRule': {
                            'condition': {
                                'type': 'TEXT_EQ',
                                'values': [{'userEnteredValue': 'Average'}]
                            },
                            'format': {
                                'textFormat': {
                                    'foregroundColor': {'red': 1.0, 'green': 0.65, 'blue': 0.0}  # Orange color
                                }
                            }
                        }
                    },
                    'index': 1
                }
            })
            
            # Add conditional formatting for Losing status
            requests.append({
                'addConditionalFormatRule': {
                    'rule': {
                        'ranges': [{
                            'sheetId': sheet_id,
                            'startRowIndex': 1,
                            'endRowIndex': 1000,
                            'startColumnIndex': 3,  # Status column
                            'endColumnIndex': 4
                        }],
                        'booleanRule': {
                            'condition': {
                                'type': 'TEXT_EQ',
                                'values': [{'userEnteredValue': 'Losing'}]
                            },
                            'format': {
                                'textFormat': {
                                    'foregroundColor': {'red': 0.8, 'green': 0.0, 'blue': 0.0}  # Red color
                                }
                            }
                        }
                    },
                    'index': 2
                }
            })
            
            # Execute batch update
            if requests:
                body = {'requests': requests}
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body=body
                ).execute()
                logger.info(f"Applied special formatting to {row_count} rows")
                
        except Exception as e:
            logger.exception(f"Failed to apply special formatting: {str(e)}")


# Example usage
if __name__ == "__main__":
    # Initialize the Sheets Manager with output directory for CSV files
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'tests', 'output')
    manager = SheetsManager(output_dir=output_dir)
    
    # Print spreadsheet URL
    print(f"Spreadsheet URL: {manager.get_spreadsheet_url()}")