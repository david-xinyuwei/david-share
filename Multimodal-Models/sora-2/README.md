# Azure Sora-2 Video Generation and Remix Guide
A Python client library for Azure OpenAI's Sora-2 video generation API, featuring video creation from text prompts and the powerful Remix capability to modify existing videos while preserving their core structure.

a beautiful gril in a car
https://github.com/user-attachments/assets/1765d958-6e13-473c-aa0d-ef4052cee0ac

Transform the scene to golden hour sunset with warm orange lighting
https://github.com/user-attachments/assets/c5d0571b-2e3a-4d64-ba05-c8d057f16fdb

A hot air balloon floating over mountains at sunset
https://github.com/user-attachments/assets/41ed7ab4-d299-4d43-abcc-e776085dd627

Change the sunset to early morning with soft sunrise light
https://github.com/user-attachments/assets/d291077f-4a70-42cb-ae39-fb2098e1ee1e



## 📦 Installation

```bash
pip install requests
```

## 🔑 API Configuration

1. Get your Azure OpenAI resource information:
   - API Key
   - Endpoint URL

2. Configure in your code:
```python
client = SoraVideoClient(
    api_key="YOUR_API_KEY",  # Replace with your API Key
    base_url="https://your-resource.openai.azure.com/openai/v1"  # Replace with your endpoint
)
```

## 🚀 Quick Start

### Running the Interactive Demo

```bash
python demo.py
```

The demo will guide you through:
1. **API Configuration**: Enter your API key and base URL
2. **Video Creation**: Input your prompt and select duration (4/8/12 seconds)
3. **Video Remix**: Transform your video with a remix prompt

Output files:
- `original_video.mp4` - Your original video
- `remixed_video.mp4` - The remixed version

### 1️⃣ Creating Videos Programmatically

```python
from sora_client import SoraVideoClient

# Initialize client
client = SoraVideoClient(
    api_key="YOUR_API_KEY",
    base_url="https://your-resource.openai.azure.com/openai/v1"
)

# Create video
result = client.create_video(
    prompt="A cute cat playing with a ball in a sunny garden",
    size="720x1280",  # Portrait, or "1280x720" for landscape
    seconds="4"  # Options: "4", "8", "12"
)

video_id = result["id"]

# Wait for completion
client.wait_until_complete(video_id)

# Download video
client.download_video(video_id, "my_video.mp4")
```

### 2️⃣ Remixing Videos

```python
# Remix an existing video
remixed = client.remix_video(
    video_id="video_xxxxx",  # Original video ID
    prompt="Change the background to a beach with sunset"  # Transformation instruction
)

remix_id = remixed["id"]

# Wait for completion and download
client.wait_until_complete(remix_id)
client.download_video(remix_id, "remixed_video.mp4")
```

## 📝 API Parameters

### `create_video()` Parameters

| Parameter | Type | Description | Options |
|-----------|------|-------------|---------|
| `prompt` | string | Video description (English works best) | - |
| `size` | string | Video resolution | `"720x1280"` (Portrait)<br>`"1280x720"` (Landscape) |
| `seconds` | string | Video duration | `"4"`, `"8"`, `"12"` |

### `remix_video()` Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `video_id` | string | Original video ID |
| `prompt` | string | Transformation instruction (describe what to change) |

**Remix Features:**
- ✅ Preserves original composition, motion, and camera movement
- ✅ Automatically inherits size and duration from original
- ✨ Only modifies specified details (colors, lighting, specific elements, etc.)

## 💡 Remix Best Practices

### ✅ Recommended Remix Usage

1. **Color Adjustments**
   ```python
   "Change the color palette to warm tones"
   "Make everything more vibrant and colorful"
   ```

2. **Lighting Changes**
   ```python
   "Change from night to daytime with bright sunlight"
   "Add dramatic sunset lighting"
   ```

3. **Element Replacement**
   ```python
   "Change the red car to a blue car"
   "Replace the cat with a dog"
   ```

4. **Style Tweaks**
   ```python
   "Add cinematic film grain"
   "Make it look like a watercolor painting"
   ```

### ⚠️ Important Notes

- **Change one aspect at a time** for best results
- **Avoid complete transformations** (e.g., changing entire scene layout)
- More specific prompts yield more precise results

## 📂 Complete Example

### Creating and Remixing a Video

```python
from sora_client import SoraVideoClient

client = SoraVideoClient(
    api_key="YOUR_API_KEY",
    base_url="https://your-resource.openai.azure.com/openai/v1"
)

# 1. Create original video (night scene)
print("Creating original video...")
original = client.create_video(
    prompt="A robot walking in a futuristic city at night",
    size="1280x720",
    seconds="8"
)

original_id = original["id"]
client.wait_until_complete(original_id)
client.download_video(original_id, "robot_night.mp4")

# 2. Remix to daytime scene
print("\nRemixing to daytime scene...")
remixed = client.remix_video(
    video_id=original_id,
    prompt="Change to bright daytime with blue sky and sunshine"
)

remix_id = remixed["id"]
client.wait_until_complete(remix_id)
client.download_video(remix_id, "robot_day.mp4")

print("\n✅ Complete!")
print("Compare robot_night.mp4 and robot_day.mp4")
print("The robot's motion is identical, but lighting is different")
```

## 🎯 Video Status Values

| Status | Description |
|--------|-------------|
| `queued` | Waiting in queue |
| `in_progress` | Generating |
| `completed` | Finished |
| `failed` | Failed |
| `cancelled` | Cancelled |

## 📞 Support

For questions, please refer to:
- [Azure OpenAI Documentation](https://learn.microsoft.com/azure/ai-foundry/openai/concepts/video-generation)
- [Sora API Reference](https://platform.openai.com/docs/guides/video-generation)

## ⚖️ Limitations

- Maximum 2 concurrent video generation tasks
- Videos available for download for 24 hours after generation
- Remix requires original video to be in `completed` status
