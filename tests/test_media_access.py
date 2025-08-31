#!/usr/bin/env python3
"""
Simple test script to retrieve media (video/image) from Meta API.

This script directly accesses a specified creative and video ID and outputs the media URLs.
"""

import os
import sys
import json

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Import Meta API client
from src.meta_api_client import MetaApiClient

def main():
    # Hardcoded IDs for testing
    CREATIVE_ID = "6579152089075"
    VIDEO_ID = "490342543326611"
    
    print(f"Testing Meta API media access")
    print("----------------------------")
    
    # Initialize Meta API client
    client = MetaApiClient(region="GBR")
    
    # Test connection
    if not client.test_connection():
        print("Failed to connect to Meta API")
        return False
    
    # Use hardcoded creative ID to get details
    print(f"\nAccessing creative details for creative_id: {CREATIVE_ID}")
    try:
        # Get creative directly from the creative ID (not the ad ID)
        creative_url = f"{client.base_url}/{CREATIVE_ID}"
        creative_params = {
            "access_token": client.access_token,
            "fields": "name,object_story_spec{link_data{message,name,description,link,caption,call_to_action},video_data{message,title,video_id,call_to_action}},asset_feed_spec{bodies,titles,descriptions,link_urls,videos},thumbnail_url,image_url,video_id,object_type"
        }
        
        creative_data = client._make_api_request(creative_url, creative_params)
        
        if creative_data:
            print(f"Successfully retrieved creative details")
            
            # Extract and print key information
            print("\nCreative Information:")
            print(f"Name: {creative_data.get('name', 'N/A')}")
            print(f"Type: {creative_data.get('object_type', 'N/A')}")
            
            # Check for image URL
            image_url = creative_data.get('image_url')
            if image_url:
                print(f"\nImage URL: {image_url}")
            
            # Check for video ID in creative data
            creative_video_id = creative_data.get('video_id')
            if creative_video_id:
                print(f"\nVideo ID from creative: {creative_video_id}")
            
            # Check for video data in object_story_spec
            object_story_spec = creative_data.get('object_story_spec', {})
            video_data = object_story_spec.get('video_data', {})
            if video_data:
                video_id_from_spec = video_data.get('video_id')
                if video_id_from_spec:
                    print(f"Video ID from object_story_spec: {video_id_from_spec}")
        else:
            print("No creative data found")
    
    except Exception as e:
        print(f"Error accessing creative: {str(e)}")
    
    # Use hardcoded video ID to get details
    print(f"\nAccessing video details for video_id: {VIDEO_ID}")
    try:
        video_url = f"{client.base_url}/{VIDEO_ID}"
        video_params = {
            "access_token": client.access_token,
            "fields": "source,permalink_url,title,description,thumbnails"
        }
        
        video_data = client._make_api_request(video_url, video_params)
        
        if video_data:
            print(f"Successfully retrieved video details")
            
            # Extract and print key information
            print("\nVideo Information:")
            print(f"Title: {video_data.get('title', 'N/A')}")
            print(f"Description: {video_data.get('description', 'N/A')}")
            
            # Check for video URLs
            video_url = video_data.get('source')
            if video_url:
                print(f"\nVideo URL: {video_url}")
            
            permalink = video_data.get('permalink_url')
            if permalink:
                print(f"Permalink: {permalink}")
            
            # Check for thumbnails
            thumbnails = video_data.get('thumbnails', {})
            if thumbnails and 'data' in thumbnails:
                thumb_data = thumbnails.get('data', [])
                if thumb_data and len(thumb_data) > 0:
                    print(f"\nThumbnail URL: {thumb_data[0].get('uri', 'N/A')}")
        else:
            print("No video data found")
    
    except Exception as e:
        print(f"Error accessing video: {str(e)}")
        # If it's a permission error, mention it specifically
        if "permission" in str(e).lower():
            print("\nThis appears to be a permission issue. The API token may not have the necessary permissions to access video details.")
            print("This is expected based on the errors you've seen before.")
    
    return True

if __name__ == "__main__":
    main()