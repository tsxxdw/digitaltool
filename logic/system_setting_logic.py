from flask import Blueprint, render_template, request, jsonify
import json
import os
import platform
import re

bp = Blueprint('system_setting', __name__)

# 创建config目录（如果不存在）
CONFIG_DIR = 'config'
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)

# 修改配置文件路径
SETTINGS_FILE = os.path.join(CONFIG_DIR, 'system_setting.json')

@bp.route('/system_setting')
def system_setting():
    return render_template('system_setting.html')

@bp.route('/system_setting/get')
def get_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return jsonify(json.load(f))
    return jsonify({
        'linux_tango_path': '',
        'linux_musetalk_path': '',
        'windows_tango_path': '',
        'windows_musetalk_path': ''
    })

def validate_windows_path(path):
    """验证Windows路径格式"""
    try:
        # 允许使用正斜杠或反斜杠
        # 允许网络路径（以\\开头）
        # 路径可以是相对路径或绝对路径
        path = path.strip()
        
        # 如果是空路径，返回False
        if not path:
            return False
            
        # 检查基本的Windows路径格式
        # 允许以下格式：
        # C:\path\to\something
        # C:/path/to/something
        # \\server\share\path
        # ./relative/path
        # ../relative/path
        # relative\path
        
        # 将所有正斜杠转换为反斜杠进行检查
        normalized_path = path.replace('/', '\\')
        
        # 检查是否包含完全不允许的字符
        invalid_chars = '<>"|?*'
        if any(char in normalized_path for char in invalid_chars):
            return False
            
        return True
        
    except Exception as e:
        print(f"Path validation error: {str(e)}")  # 添加调试信息
        return False

@bp.route('/system_setting/save', methods=['POST'])
def save_settings():
    try:
        data = request.get_json()
        platform_type = data['platform']
        settings = data['settings']
        
        print(f"Received settings: {settings}")  # 添加调试信息
        
        # 读取现有设置
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                current_settings = json.load(f)
        else:
            current_settings = {
                'linux_tango_path': '',
                'linux_musetalk_path': '',
                'windows_tango_path': '',
                'windows_musetalk_path': ''
            }
        
        # 更新对应平台的设置
        current_settings[f'{platform_type}_tango_path'] = settings['tango_path']
        current_settings[f'{platform_type}_musetalk_path'] = settings['musetalk_path']
        
        # 根据不同平台进行验证
        if platform_type == 'linux':
            # Linux路径验证
            if platform.system() == 'Linux':
                if not os.path.exists(settings['tango_path']):
                    return jsonify({'error': 'Linux TANGO路径不存在'}), 400
                if not os.path.exists(settings['musetalk_path']):
                    return jsonify({'error': 'Linux MUSETALK路径不存在'}), 400
        else:
            # Windows路径验证
            if not validate_windows_path(settings['tango_path']):
                print(f"Invalid Windows TANGO path: {settings['tango_path']}")  # 添加调试信息
                return jsonify({'error': f"Windows TANGO路径格式无效: {settings['tango_path']}"}), 400
            if not validate_windows_path(settings['musetalk_path']):
                print(f"Invalid Windows MUSETALK path: {settings['musetalk_path']}")  # 添加调试信息
                return jsonify({'error': f"Windows MUSETALK路径格式无效: {settings['musetalk_path']}"}), 400
            
        # 确保config目录存在
        os.makedirs(CONFIG_DIR, exist_ok=True)
            
        # 保存所有设置到文件
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(current_settings, f, indent=4, ensure_ascii=False)
            
        return jsonify({'message': '设置已保存'})
    except Exception as e:
        print(f"Save settings error: {str(e)}")  # 添加调试信息
        return jsonify({'error': str(e)}), 500