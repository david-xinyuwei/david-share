import requests
import json
import time


class SoraVideoClient:
    """Azure Sora-2 视频生成客户端"""
    
    def __init__(self, api_key, base_url):
        """
        初始化客户端
        
        Args:
            api_key: Azure OpenAI API Key
            base_url: API Endpoint (例如: https://<your-resource>.openai.azure.com/openai/v1)
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Content-Type": "application/json",
            "api-key": api_key
        }
    
    def create_video(self, prompt, size="720x1280", seconds="4"):
        """
        创建视频
        
        Args:
            prompt: 视频描述提示词
            size: 视频分辨率 (可选: "720x1280", "1280x720")
            seconds: 视频时长 (可选: "4", "8", "12")
        
        Returns:
            dict: 包含 video_id 的响应
        """
        url = f"{self.base_url}/videos"
        data = {
            "model": "sora-2",
            "prompt": prompt,
            "size": size,
            "seconds": seconds
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError:
            # Print detailed error information
            error_detail = ""
            try:
                error_detail = response.json()
            except Exception:
                error_detail = response.text
            print("\n❌ API Error Details:")
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {error_detail}")
            raise
    
    def remix_video(self, video_id, prompt):
        """
        Remix 视频 - 修改已有视频的细节
        
        Args:
            video_id: 原始视频 ID
            prompt: 修改指令（描述要改变的内容）
        
        Returns:
            dict: 包含新 video_id 的响应
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
        查询视频生成状态
        
        Args:
            video_id: 视频 ID
        
        Returns:
            dict: 包含状态信息的响应
        """
        url = f"{self.base_url}/videos/{video_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def wait_until_complete(self, video_id, check_interval=20):
        """
        等待视频生成完成
        
        Args:
            video_id: 视频 ID
            check_interval: 检查间隔（秒）
        
        Returns:
            dict: 完成后的视频信息，失败返回 None
        """
        print(f"⏳ 等待视频生成... (ID: {video_id})")
        
        while True:
            info = self.get_status(video_id)
            status = info.get("status")
            progress = info.get("progress", 0)
            
            print(f"   状态: {status:15} | 进度: {progress}%")
            
            if status == "completed":
                print("✅ 生成完成！")
                return info
            elif status in ["failed", "cancelled"]:
                print(f"❌ 生成失败: {status}")
                return None
            
            time.sleep(check_interval)
    
    def download_video(self, video_id, filename):
        """
        下载视频
        
        Args:
            video_id: 视频 ID
            filename: 保存的文件名
        
        Returns:
            bool: 下载是否成功
        """
        url = f"{self.base_url}/videos/{video_id}/content"
        
        response = requests.get(url, headers=self.headers, stream=True)
        response.raise_for_status()
        
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"✅ 视频已保存: {filename}")
        return True


# ========== 使用示例 ==========

def example_create_video():
    """示例 1: 创建视频"""
    
    # 初始化客户端
    client = SoraVideoClient(
        api_key="YOUR_API_KEY",
        base_url="https://<your-resource>.openai.azure.com/openai/v1"
    )
    
    # 创建视频
    print("【创建视频】")
    result = client.create_video(
        prompt="A cute cat playing with a ball in a sunny garden",
        size="720x1280",
        seconds="4"
    )
    
    video_id = result["id"]
    print(f"视频 ID: {video_id}\n")
    
    # 等待完成
    info = client.wait_until_complete(video_id)
    
    if info:
        # 下载视频
        client.download_video(video_id, "my_video.mp4")


def example_remix_video():
    """示例 2: Remix 视频"""
    
    client = SoraVideoClient(
        api_key="YOUR_API_KEY",
        base_url="https://<your-resource>.openai.azure.com/openai/v1"
    )
    
    # 假设已有一个视频 ID
    original_video_id = "video_xxxxx"
    
    # Remix 视频
    print("【Remix 视频】")
    result = client.remix_video(
        video_id=original_video_id,
        prompt="Change the background to a beach with sunset"
    )
    
    remix_id = result["id"]
    print(f"新视频 ID: {remix_id}")
    print(f"源视频 ID: {result.get('remixed_from_video_id')}\n")
    
    # 等待完成
    info = client.wait_until_complete(remix_id)
    
    if info:
        # 下载 Remix 视频
        client.download_video(remix_id, "remixed_video.mp4")


def example_complete_workflow():
    """示例 3: 完整工作流 - 创建 + Remix"""
    
    client = SoraVideoClient(
        api_key="YOUR_API_KEY",
        base_url="https://<your-resource>.openai.azure.com/openai/v1"
    )
    
    # 步骤 1: 创建原始视频
    print("="*60)
    print("步骤 1: 创建原始视频")
    print("="*60)
    
    original = client.create_video(
        prompt="A robot walking in a futuristic city at night",
        size="1280x720",
        seconds="8"
    )
    
    original_id = original["id"]
    print(f"原始视频 ID: {original_id}\n")
    
    # 等待原始视频完成
    if not client.wait_until_complete(original_id):
        return
    
    # 下载原始视频
    client.download_video(original_id, "original.mp4")
    
    # 步骤 2: Remix 视频
    print("\n" + "="*60)
    print("步骤 2: Remix 视频")
    print("="*60)
    
    remixed = client.remix_video(
        video_id=original_id,
        prompt="Change to bright daytime with blue sky and sunshine"
    )
    
    remix_id = remixed["id"]
    print(f"Remix 视频 ID: {remix_id}\n")
    
    # 等待 Remix 完成
    if not client.wait_until_complete(remix_id):
        return
    
    # 下载 Remix 视频
    client.download_video(remix_id, "remixed.mp4")
    
    print("\n" + "="*60)
    print("✅ 完成！")
    print("="*60)
    print("生成文件:")
    print("  - original.mp4 (夜晚场景)")
    print("  - remixed.mp4 (白天场景)")


if __name__ == "__main__":
    # 运行示例
    print("请选择要运行的示例:")
    print("1. 创建视频")
    print("2. Remix 视频")
    print("3. 完整工作流（创建 + Remix）")
    print("\n请修改代码中的 API_KEY 和 base_url 后运行相应的函数")
    
    # 取消注释以运行示例
    # example_create_video()
    # example_remix_video()
    # example_complete_workflow()
