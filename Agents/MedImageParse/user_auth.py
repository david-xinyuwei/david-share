"""
用户认证和管理模块
支持多用户、密码修改、独立配置
"""
import json
import hashlib
from pathlib import Path
from typing import Dict, Optional

# 用户数据文件路径
USERS_FILE = Path.home() / ".medimageparse_users.json"

class UserManager:
    """用户管理类"""
    
    def __init__(self):
        self.users = self._load_users()
    
    def _load_users(self) -> Dict:
        """加载用户数据"""
        if USERS_FILE.exists():
            try:
                with open(USERS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return self._create_default_users()
        return self._create_default_users()
    
    def _create_default_users(self) -> Dict:
        """创建默认管理员账户"""
        default_users = {
            "admin": {
                "password_hash": self._hash_password("admin123"),
                "role": "admin",  # admin 或 user
                "config": {
                    "endpoint_url_2d": "",
                    "api_key_2d": "",
                    "endpoint_url_3d": "",
                    "api_key_3d": "",
                    "model_type": "MedImageParse (2D)"
                }
            }
        }
        self._save_users(default_users)
        return default_users
    
    def _save_users(self, users: Dict = None):
        """保存用户数据"""
        try:
            data_to_save = users if users is not None else self.users
            with open(USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving users: {e}")
            return False
    
    def _hash_password(self, password: str) -> str:
        """密码哈希"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def authenticate(self, username: str, password: str) -> bool:
        """验证用户名和密码"""
        if username not in self.users:
            return False
        
        password_hash = self._hash_password(password)
        return self.users[username]["password_hash"] == password_hash
    
    def change_password(self, username: str, old_password: str, new_password: str) -> tuple[bool, str]:
        """修改密码"""
        # 验证旧密码
        if not self.authenticate(username, old_password):
            return False, "原密码错误 / Old password incorrect"
        
        # 验证新密码强度
        if len(new_password) < 6:
            return False, "新密码至少6位 / New password must be at least 6 characters"
        
        # 更新密码
        self.users[username]["password_hash"] = self._hash_password(new_password)
        
        if self._save_users():
            return True, "密码修改成功 / Password changed successfully"
        else:
            return False, "保存失败 / Save failed"
    
    def add_user(self, username: str, password: str, role: str = "user") -> tuple[bool, str]:
        """添加新用户（仅管理员可用）"""
        # 检查用户名是否已存在
        if username in self.users:
            return False, "用户名已存在 / Username already exists"
        
        # 验证用户名
        if len(username) < 3:
            return False, "用户名至少3位 / Username must be at least 3 characters"
        
        # 验证密码强度
        if len(password) < 6:
            return False, "密码至少6位 / Password must be at least 6 characters"
        
        # 创建新用户
        self.users[username] = {
            "password_hash": self._hash_password(password),
            "role": role,
            "config": {
                "endpoint_url_2d": "",
                "api_key_2d": "",
                "endpoint_url_3d": "",
                "api_key_3d": "",
                "model_type": "MedImageParse (2D)"
            }
        }
        
        if self._save_users():
            return True, f"用户 {username} 创建成功 / User {username} created successfully"
        else:
            return False, "保存失败 / Save failed"
    
    def delete_user(self, username: str) -> tuple[bool, str]:
        """删除用户（仅管理员可用，不能删除自己）"""
        if username == "admin":
            return False, "不能删除管理员账户 / Cannot delete admin account"
        
        if username not in self.users:
            return False, "用户不存在 / User does not exist"
        
        del self.users[username]
        
        if self._save_users():
            return True, f"用户 {username} 已删除 / User {username} deleted"
        else:
            return False, "删除失败 / Delete failed"
    
    def get_user_config(self, username: str) -> Dict:
        """获取用户配置"""
        if username in self.users:
            return self.users[username].get("config", {})
        return {}
    
    def save_user_config(self, username: str, config: Dict) -> bool:
        """保存用户配置"""
        if username in self.users:
            self.users[username]["config"] = config
            return self._save_users()
        return False
    
    def is_admin(self, username: str) -> bool:
        """检查是否是管理员"""
        if username in self.users:
            return self.users[username].get("role") == "admin"
        return False
    
    def list_users(self) -> list:
        """列出所有用户（仅用户名和角色）"""
        return [
            {"username": username, "role": data.get("role", "user")}
            for username, data in self.users.items()
        ]
