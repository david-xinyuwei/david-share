"""
Quick Demo - Run this file to test Sora-2 features

This demo will:
1. Create a video of a puppy playing in snow
2. Remix it to change snow to a beach
3. Download both versions for comparison
"""

from sora_client_en import SoraVideoClient

# ========== Configuration ==========
# Replace with your actual credentials
API_KEY = "YOUR_API_KEY_HERE"
BASE_URL = "https://your-resource.openai.azure.com/openai/v1"

# Create client
client = SoraVideoClient(api_key=API_KEY, base_url=BASE_URL)


def demo_create():
    """Demo: Create a video"""
    print("\n" + "="*60)
    print("Demo 1: Create Video")
    print("="*60)
    
    result = client.create_video(
        prompt="A golden retriever puppy playing in the snow",
        size="720x1280",
        seconds="4"
    )
    
    video_id = result["id"]
    print(f"✅ Video creation started, ID: {video_id}")
    
    # Wait for completion
    info = client.wait_until_complete(video_id)
    
    if info:
        client.download_video(video_id, "demo_puppy.mp4")
        print(f"\n🎉 Done! Video saved as demo_puppy.mp4")
        return video_id
    
    return None


def demo_remix(original_id):
    """Demo: Remix a video"""
    print("\n" + "="*60)
    print("Demo 2: Remix Video")
    print("="*60)
    
    result = client.remix_video(
        video_id=original_id,
        prompt="Change the snow to a sunny beach with sand"
    )
    
    remix_id = result["id"]
    print(f"✅ Remix started, new ID: {remix_id}")
    print(f"   Source video: {result.get('remixed_from_video_id')}")
    
    # Wait for completion
    info = client.wait_until_complete(remix_id)
    
    if info:
        client.download_video(remix_id, "demo_puppy_beach.mp4")
        print(f"\n🎉 Done! Remixed video saved as demo_puppy_beach.mp4")


if __name__ == "__main__":
    print("="*60)
    print("🎬 Azure Sora-2 Quick Demo")
    print("="*60)
    print("\n⚠️ Please configure API_KEY and BASE_URL in the code first")
    
    if API_KEY == "YOUR_API_KEY_HERE":
        print("\n❌ Please set API_KEY and BASE_URL")
        print("   1. Open demo_en.py")
        print("   2. Update API_KEY and BASE_URL at the top")
        print("   3. Run this file again")
    else:
        # Run demo
        video_id = demo_create()
        
        if video_id:
            demo_remix(video_id)
            
            print("\n" + "="*60)
            print("✅ Demo Complete!")
            print("="*60)
            print("\nGenerated files:")
            print("  1. demo_puppy.mp4 - Original video (snow)")
            print("  2. demo_puppy_beach.mp4 - Remixed video (beach)")
            print("\n💡 Compare these two videos - the puppy's actions are")
            print("   identical, but the background is completely different!")
