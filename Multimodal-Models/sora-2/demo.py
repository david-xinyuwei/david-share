"""
快速演示 - 运行这个文件来测试 Sora-2 功能
"""

from sora_client import SoraVideoClient

# ========== 配置区域 ==========
# 请替换为您的实际信息
API_KEY = "YOUR_API_KEY_HERE"
BASE_URL = "https://your-resource.openai.azure.com/openai/v1"

# 创建客户端
client = SoraVideoClient(api_key=API_KEY, base_url=BASE_URL)


def demo_create():
    """演示：创建视频"""
    print("\n" + "="*60)
    print("演示 1: 创建视频")
    print("="*60)
    
    result = client.create_video(
        prompt="A golden retriever puppy playing in the snow",
        size="720x1280",
        seconds="4"
    )
    
    video_id = result["id"]
    print(f"✅ 视频创建成功，ID: {video_id}")
    
    # 等待完成
    info = client.wait_until_complete(video_id)
    
    if info:
        client.download_video(video_id, "demo_puppy.mp4")
        print(f"\n🎉 完成！视频已保存为 demo_puppy.mp4")
        return video_id
    
    return None


def demo_remix(original_id):
    """演示：Remix 视频"""
    print("\n" + "="*60)
    print("演示 2: Remix 视频")
    print("="*60)
    
    result = client.remix_video(
        video_id=original_id,
        prompt="Change the snow to a sunny beach with sand"
    )
    
    remix_id = result["id"]
    print(f"✅ Remix 请求成功，新 ID: {remix_id}")
    print(f"   源视频: {result.get('remixed_from_video_id')}")
    
    # 等待完成
    info = client.wait_until_complete(remix_id)
    
    if info:
        client.download_video(remix_id, "demo_puppy_beach.mp4")
        print(f"\n🎉 完成！Remix 视频已保存为 demo_puppy_beach.mp4")


if __name__ == "__main__":
    print("="*60)
    print("🎬 Azure Sora-2 快速演示")
    print("="*60)
    print("\n⚠️ 请先在代码中配置 API_KEY 和 BASE_URL")
    
    if API_KEY == "YOUR_API_KEY_HERE":
        print("\n❌ 请先设置 API_KEY 和 BASE_URL")
        print("   1. 打开 demo.py")
        print("   2. 修改顶部的 API_KEY 和 BASE_URL")
        print("   3. 重新运行此文件")
    else:
        # 运行演示
        video_id = demo_create()
        
        if video_id:
            demo_remix(video_id)
            
            print("\n" + "="*60)
            print("✅ 演示完成！")
            print("="*60)
            print("\n生成的文件：")
            print("  1. demo_puppy.mp4 - 原始视频（雪地）")
            print("  2. demo_puppy_beach.mp4 - Remix 视频（沙滩）")
            print("\n💡 对比这两个视频，小狗的动作完全相同，但背景不同")
