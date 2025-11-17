# Azure Sora-2 Video Generation and Remix SDK

A Python client library for Azure OpenAI's Sora-2 video generation API, featuring video creation from text prompts and the powerful Remix capability to modify existing videos while preserving their core structure.

## ✨ Features

- **Video Creation**: Generate videos from text prompts with customizable resolution and duration
- **Remix Videos**: Modify specific aspects of existing videos (lighting, colors, elements) while maintaining the original motion and composition
- **Async Status Polling**: Automatic polling with progress tracking
- **Simple Download**: Easy video file download and saving

## 🚀 Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Basic Usage

```python
from sora_client import SoraVideoClient

# Initialize client
client = SoraVideoClient(
    api_key="YOUR_API_KEY",
    base_url="https://your-resource.openai.azure.com/openai/v1"
)

# Create a video
result = client.create_video(
    prompt="A cute cat playing with a ball in a sunny garden",
    size="720x1280",
    seconds="4"
)

# Wait for completion
video_id = result["id"]
client.wait_until_complete(video_id)

# Download the video
client.download_video(video_id, "my_video.mp4")
```

## 🎨 Remix Feature

The Remix feature allows you to modify specific aspects of an existing video while preserving its core elements like motion, composition, and camera movement.

### Example

```python
# Original video: A robot walking at night
original = client.create_video(
    prompt="A robot walking in a futuristic city at night",
    size="1280x720",
    seconds="8"
)

original_id = original["id"]
client.wait_until_complete(original_id)

# Remix: Change to daytime while keeping the robot's motion
remixed = client.remix_video(
    video_id=original_id,
    prompt="Change to bright daytime with blue sky and sunshine"
)

remix_id = remixed["id"]
client.wait_until_complete(remix_id)

# Download both versions
client.download_video(original_id, "robot_night.mp4")
client.download_video(remix_id, "robot_day.mp4")
```

**What Remix preserves:**
- ✅ Original motion and animation
- ✅ Camera angles and movements
- ✅ Scene composition and framing
- ✅ Object positions and trajectories

**What you can change:**
- ✨ Lighting conditions (night → day, sunset, etc.)
- ✨ Color palette and tones
- ✨ Individual elements (colors, materials, objects)
- ✨ Visual style (cinematic, artistic effects)

## 📖 API Reference

### SoraVideoClient

#### `__init__(api_key, base_url)`

Initialize the Sora video client.

**Parameters:**
- `api_key` (str): Your Azure OpenAI API key
- `base_url` (str): API endpoint URL (e.g., `https://your-resource.openai.azure.com/openai/v1`)

#### `create_video(prompt, size="720x1280", seconds="4")`

Create a new video from a text prompt.

**Parameters:**
- `prompt` (str): Text description of the video to generate
- `size` (str): Video resolution
  - `"720x1280"` - Portrait (default)
  - `"1280x720"` - Landscape
- `seconds` (str): Video duration - `"4"`, `"8"`, or `"12"`

**Returns:** dict with video information including `id`

#### `remix_video(video_id, prompt)`

Remix an existing video with modifications.

**Parameters:**
- `video_id` (str): ID of the original completed video
- `prompt` (str): Description of the changes to apply

**Returns:** dict with new video information

#### `get_status(video_id)`

Get the current status of a video generation job.

**Parameters:**
- `video_id` (str): Video ID

**Returns:** dict with status information

#### `wait_until_complete(video_id, check_interval=20)`

Wait for a video to complete generation.

**Parameters:**
- `video_id` (str): Video ID to wait for
- `check_interval` (int): Seconds between status checks (default: 20)

**Returns:** dict with completion info, or None if failed

#### `download_video(video_id, filename)`

Download a completed video.

**Parameters:**
- `video_id` (str): Video ID
- `filename` (str): Local filename to save to

**Returns:** bool indicating success

## 💡 Best Practices

### For Creating Videos

1. **Be specific**: Include details about subject, action, setting, lighting, and camera movement
2. **Single focus**: Keep prompts focused on one main idea
3. **Use English**: English prompts generally produce the best results

### For Remixing Videos

1. **One change at a time**: Modify one aspect (lighting, color, or single element) for best results
2. **Be precise**: Clear, specific instructions yield better fidelity
3. **Avoid drastic changes**: Don't try to completely restructure the scene
4. **Good examples**:
   - ✅ "Change to daytime with bright sunlight"
   - ✅ "Make the car red instead of blue"
   - ✅ "Add warm golden hour lighting"
   - ❌ "Completely change the scene to a beach"

## 🎬 Demo

Run the included demo to see creation and remix in action:

```bash
# Edit demo.py to add your API credentials
python demo.py
```

This will:
1. Create a video of a puppy playing in snow
2. Remix it to change the snow to a beach
3. Download both versions for comparison

## 📊 Video Status States

| Status | Description |
|--------|-------------|
| `queued` | Job is queued for processing |
| `in_progress` | Video is being generated |
| `completed` | Video is ready for download |
| `failed` | Generation failed |
| `cancelled` | Job was cancelled |

## ⚠️ Limitations

- Maximum 2 concurrent video generation jobs
- Videos are available for download for 24 hours after creation
- Remix requires the source video to be in `completed` status
- Video size and duration are inherited from the original video when remixing

## 📝 Examples

See `sora_client.py` for complete examples including:
- `example_create_video()` - Basic video creation
- `example_remix_video()` - Remixing an existing video
- `example_complete_workflow()` - Full creation + remix workflow

## 🔗 Resources

- [Azure OpenAI Documentation](https://learn.microsoft.com/azure/ai-foundry/openai/concepts/video-generation)
- [Sora API Reference](https://platform.openai.com/docs/guides/video-generation)

## 📄 License

MIT License - Feel free to use this in your projects!

## 🤝 Contributing

Issues and pull requests are welcome!
