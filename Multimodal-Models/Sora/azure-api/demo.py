"""
Interactive Demo - Azure Sora-2 Video Generation and Remix
"""

from sora_client import SoraVideoClient


def get_user_input():
    """Get API credentials and prompts from user"""
    print("="*70)
    print("🎬 Azure Sora-2 Interactive Demo")
    print("="*70)
    
    # Get API credentials
    print("\n📋 Step 1: Configure API Credentials")
    print("-" * 70)
    api_key = input("Enter your API Key: ").strip()
    
    print("\nEnter your Base URL")
    print("Example: https://your-resource.openai.azure.com/openai/v1")
    base_url = input("Base URL: ").strip()
    
    # Get original video prompt
    print("\n" + "="*70)
    print("🎨 Step 2: Create Original Video")
    print("-" * 70)
    print("Enter a prompt to generate your video")
    print("Example: A golden retriever puppy playing in the snow")
    original_prompt = input("\nOriginal video prompt: ").strip()
    
    # Get video duration
    print("\nSelect video duration (seconds):")
    print("  1. 4 seconds")
    print("  2. 8 seconds")
    print("  3. 12 seconds")
    duration_choice = input("Enter choice (1/2/3) [default: 1]: ").strip()
    
    duration_map = {"1": "4", "2": "8", "3": "12", "": "4"}
    seconds = duration_map.get(duration_choice, "4")
    
    return api_key, base_url, original_prompt, seconds


def create_video(client, prompt, seconds="4"):
    """Create original video"""
    print("\n" + "="*70)
    print("📹 Creating Video...")
    print("-" * 70)
    print(f"Prompt: {prompt}")
    print(f"Duration: {seconds} seconds")
    
    result = client.create_video(
        prompt=prompt,
        size="720x1280",
        seconds=seconds
    )
    
    video_id = result["id"]
    print("\n✅ Video creation started successfully")
    print(f"   Video ID: {video_id}")
    
    # Wait for completion
    print("\n⏳ Waiting for video generation to complete...")
    info = client.wait_until_complete(video_id)
    
    if info:
        filename = "original_video.mp4"
        client.download_video(video_id, filename)
        print(f"\n🎉 Success! Video saved as '{filename}'")
        return video_id, filename
    
    return None, None


def remix_video(client, original_id, original_filename):
    """Remix the video"""
    print("\n" + "="*70)
    print("🎨 Step 3: Remix Video")
    print("-" * 70)
    print(f"Original video: {original_filename}")
    print(f"Video ID: {original_id}")
    
    print("\nEnter a remix prompt to transform the video")
    print("Example: Change the snow to a sunny beach with sand")
    print("Note: The motion and composition will be preserved")
    remix_prompt = input("\nRemix prompt: ").strip()
    
    if not remix_prompt:
        print("\n⚠️  No remix prompt provided. Skipping remix.")
        return
    
    print("\n" + "="*70)
    print("🔄 Remixing Video...")
    print("-" * 70)
    print(f"Remix prompt: {remix_prompt}")
    
    result = client.remix_video(
        video_id=original_id,
        prompt=remix_prompt
    )
    
    remix_id = result["id"]
    print("\n✅ Remix started successfully")
    print(f"   New Video ID: {remix_id}")
    print(f"   Source Video ID: {result.get('remixed_from_video_id')}")
    
    # Wait for completion
    print("\n⏳ Waiting for remix to complete...")
    info = client.wait_until_complete(remix_id)
    
    if info:
        filename = "remixed_video.mp4"
        client.download_video(remix_id, filename)
        print(f"\n🎉 Success! Remixed video saved as '{filename}'")
        return filename
    
    return None


if __name__ == "__main__":
    try:
        # Get user input
        api_key, base_url, original_prompt, seconds = get_user_input()
        
        # Create client
        client = SoraVideoClient(api_key=api_key, base_url=base_url)
        
        # Create original video
        video_id, original_filename = create_video(
            client, original_prompt, seconds
        )
        
        if not video_id:
            print("\n❌ Failed to create video. Exiting.")
            exit(1)
        
        # Remix video
        remixed_filename = remix_video(client, video_id, original_filename)
        
        # Summary
        print("\n" + "="*70)
        print("✅ Demo Completed Successfully!")
        print("="*70)
        print("\nGenerated Files:")
        print(f"  1. {original_filename} - Original video")
        if remixed_filename:
            print(f"  2. {remixed_filename} - Remixed video")
            print("\n💡 Compare the two videos - same motion, different scene!")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user.")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
