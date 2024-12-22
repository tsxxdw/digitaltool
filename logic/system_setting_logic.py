from flask import Blueprint, render_template, request, jsonify
import json
import os
import platform

bp = Blueprint('system_setting', __name__)

SETTINGS_FILE = 'system_setting.json'

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

@bp.route('/system_setting/save', methods=['POST'])
def save_settings():
    try:
        data = request.get_json()
        platform_type = data['platform']
        settings = data['settings']
        
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
        
        # 验证路径是否存在
        if platform.system() == 'Linux' and platform_type == 'linux':
            if not os.path.exists(settings['tango_path']):
                return jsonify({'error': 'Linux TANGO路径不存在'}), 400
            if not os.path.exists(settings['musetalk_path']):
                return jsonify({'error': 'Linux MUSETALK路径不存在'}), 400
        elif platform.system() == 'Windows' and platform_type == 'windows':
            if not os.path.exists(settings['tango_path']):
                return jsonify({'error': 'Windows TANGO路径不存在'}), 400
            if not os.path.exists(settings['musetalk_path']):
                return jsonify({'error': 'Windows MUSETALK路径不存在'}), 400
            
        # 保存所有设置到文件
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(current_settings, f, indent=4)
            
        return jsonify({'message': '设置已保存'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500 