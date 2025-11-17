"""
Azure Sora-2 Video Generation and Remix Client

A Python SDK for Azure OpenAI's Sora-2 video generation API.

Features:
1. Create videos from text prompts
2. Remix existing videos (modify details while preserving structure)
3. Poll generation status with progress tracking
4. Download generated video files

Requirements:
pip install requests
"""

import requests
import json
import time


class SoraVideoClient:
    """Azure Sora-2 Video Generation Client"""
    
    def __init__(self, api_key, base_url):
        """
        Initialize the Sora video client
        
        Args:
            api_key: Azure OpenAI API Key
            base_url: API Endpoint (e.g., https://your-resource.openai.azure.com/openai/v1)
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Content-Type": "application/json",
            "api-key": api_key
        }
    
    def create_video(self, prompt, size="720x1280", seconds="4"):
        """
        Create a new video from text prompt
        
        Args:
            prompt: Text description of the desired video
            size: Video resolution (options: "720x1280", "1280x720")
            seconds: Video duration (options: "4", "8", "12")
        
        Returns:
            dict: Response containing video_id and metadata
        """
        url = f"{self.base_url}/videos"
        data = {
            "model": "sora-2",
            "prompt": prompt,
            "size": size,
            "seconds": seconds
        }
        
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()
    
    def remix_video(self, video_id, prompt):
        """
        Remix an existing video - modify specific aspects while preserving core structure
        
        Args:
            video_id: ID of the source video (must be completed)
            prompt: Description of the changes to apply
        
        Returns:
            dict: Response containing new video_id
        """
        url = f"{self.base_url}/videos/{video_id}/remix"
        data = {
            "prompt": prompt
        }
        
        response = requests.post(url, headers=self.headers, json=data)
        response.raise_for_status()
        return response.json()
    
    def get_status(self, video_id):
        """
        Query video generation status
        
        Args:
            video_id: Video ID to check
        
        Returns:
            dict: Status information including current state and progress
        """
        url = f"{self.base_url}/videos/{video_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def wait_until_complete(self, video_id, check_interval=20):
        """
        Wait for video generation to complete
        
        Args:
            video_id: Video ID to wait for
            check_interval: Seconds between status checks
        
        Returns:
            dict: Completion info if successful, None if failed
        """
        print(f"⏳ Waiting for video generation... (ID: {video_id})")
        
        while True:
            info = self.get_status(video_id)
            status = info.get("status")
            progress = info.get("progress", 0)
            
            print(f"   Status: {status:15} | Progress: {progress}%")
            
            if status == "completed":
                print("✅ Generation completed!")
                return info
            elif status in ["failed", "cancelled"]:
                print(f"❌ Generation failed: {status}")
                return None
            
            time.sleep(check_interval)
    
    def download_video(self, video_id, filename):
        """
        Download completed video to local file
        
        Args:
            video_id: Video ID to download
            filename: Local filename to save as
        
        Returns:
            bool: True if download successful
        """
        url = f"{self.base_url}/videos/{video_id}/content"
        
        response = requests.get(url, headers=self.headers, stream=True)
        response.raise_for_status()
        
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"✅ Video saved: {filename}")
        return True


# ========== Usage Examples ==========

def example_create_video():
    """Example 1: Create a video"""
    
    # Initialize client
    client = SoraVideoClient(
        api_key="YOUR_API_KEY",
        base_url="https://your-resource.openai.azure.com/openai/v1"
    )
    
    # Create video
    print("【Creating Video】")
    result = client.create_video(
        prompt="A cute cat playing with a ball in a sunny garden",
        size="720x1280",
        seconds="4"
    )
    
    video_id = result["id"]
    print(f"Video ID: {video_id}\n")
    
    # Wait for completion
    info = client.wait_until_complete(video_id)
    
    if info:
        # Download video
        client.download_video(video_id, "my_video.mp4")


def example_remix_video():
    """Example 2: Remix a video"""
    
    client = SoraVideoClient(
        api_key="YOUR_API_KEY",
        base_url="https://your-resource.openai.azure.com/openai/v1"
    )
    
    # Assume we have an existing video ID
    original_video_id = "video_xxxxx"
    
    # Remix the video
    print("【Remixing Video】")
    result = client.remix_video(
        video_id=original_video_id,
        prompt="Change the background to a beach with sunset"
    )
    
    remix_id = result["id"]
    print(f"New Video ID: {remix_id}")
    print(f"Source Video: {result.get('remixed_from_video_id')}\n")
    
    # Wait for completion
    info = client.wait_until_complete(remix_id)
    
    if info:
        # Download remixed video
        client.download_video(remix_id, "remixed_video.mp4")


def example_complete_workflow():
    """Example 3: Complete workflow - Create + Remix"""
    
    client = SoraVideoClient(
        api_key="YOUR_API_KEY",
        base_url="https://your-resource.openai.azure.com/openai/v1"
    )
    
    # Step 1: Create original video
    print("="*60)
    print("Step 1: Create Original Video")
    print("="*60)
    
    original = client.create_video(
        prompt="A robot walking in a futuristic city at night",
        size="1280x720",
        seconds="8"
    )
    
    original_id = original["id"]
    print(f"Original Video ID: {original_id}\n")
    
    # Wait for original video
    if not client.wait_until_complete(original_id):
        return
    
    # Download original
    client.download_video(original_id, "original.mp4")
    
    # Step 2: Remix the video
    print("\n" + "="*60)
    print("Step 2: Remix Video")
    print("="*60)
    
    remixed = client.remix_video(
        video_id=original_id,
        prompt="Change to bright daytime with blue sky and sunshine"
    )
    
    remix_id = remixed["id"]
    print(f"Remix Video ID: {remix_id}\n")
    
    # Wait for remix
    if not client.wait_until_complete(remix_id):
        return
    
    # Download remixed video
    client.download_video(remix_id, "remixed.mp4")
    
    print("\n" + "="*60)
    print("✅ Complete!")
    print("="*60)
    print("Generated files:")
    print("  - original.mp4 (night scene)")
    print("  - remixed.mp4 (daytime scene)")


if __name__ == "__main__":
    # Run examples
    print("Choose an example to run:")
    print("1. Create video")
    print("2. Remix video")
    print("3. Complete workflow (Create + Remix)")
    print("\nPlease update API_KEY and base_url in the code before running")
    
    # Uncomment to run examples
    # example_create_video()
    # example_remix_video()
    # example_complete_workflow()
