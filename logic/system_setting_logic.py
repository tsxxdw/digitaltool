from flask import Blueprint, render_template, request, jsonify
import json
import os

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
        'tango_path': '',
        'musetalk_path': ''
    })

@bp.route('/system_setting/save', methods=['POST'])
def save_settings():
    try:
        settings = request.get_json()
        
        # 验证路径是否存在
        if not os.path.exists(settings['tango_path']):
            return jsonify({'error': 'TANGO路径不存在'}), 400
        if not os.path.exists(settings['musetalk_path']):
            return jsonify({'error': 'MUSETALK路径不存在'}), 400
            
        # 保存设置到文件
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=4)
            
        return jsonify({'message': '设置已保存'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500 