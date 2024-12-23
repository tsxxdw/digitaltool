from flask import Blueprint, render_template, request, jsonify
import os
import json
import uuid
import shutil
import subprocess
from datetime import datetime
import threading
import time
import queue
from pathlib import Path
import platform

bp = Blueprint('train', __name__)

# 获取项目根目录路径
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# 配置文件路径
CONFIG_FILE = os.path.join(ROOT_DIR, 'config/train_data_config.json')
SYSTEM_SETTINGS_FILE = os.path.join(ROOT_DIR, 'config/system_setting.json')
TRAIN_DIR = os.path.join(ROOT_DIR, 'static/train')

# 确保目录存在
os.makedirs('config', exist_ok=True)
os.makedirs(TRAIN_DIR, exist_ok=True)

# 任务队列和锁
task_queue = []
task_lock = threading.Lock()
current_task = None

def load_system_settings():
    """加载系统设置"""
    try:
        with open(SYSTEM_SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            os_type = platform.system()
            if os_type == "Windows":
                return settings.get('windows_musetalk_path', '')
            else:
                return settings.get('linux_musetalk_path', '')
    except Exception as e:
        print(f"加载系统设置失败: {str(e)}")
        return ''

# 获取对应操作系统的 MUSETALK 路径
MUSETALK = load_system_settings()
if not MUSETALK:
    print("警告: 未在 system_setting.json 中找到对应操作系统的 MUSETALK 路径配置")

class TrainTask:
    def __init__(self, task_id, name, video_name, audio_name):
        self.task_id = task_id
        self.name = name
        self.video_name = video_name
        self.audio_name = audio_name
        
        # 使用绝对路径
        task_dir = os.path.join(TRAIN_DIR, task_id)
        self.new_video_name = os.path.abspath(os.path.join(task_dir, f"{task_id}.mp4"))  # 完整的视频文件路径
        self.new_audio_name = os.path.abspath(os.path.join(task_dir, f"{task_id}.wav"))  # 完整的音频文件路径
        self.yaml_file = os.path.abspath(os.path.join(task_dir, f"{task_id}.yaml"))
        self.log_file = os.path.abspath(os.path.join(task_dir, f"{task_id}.log"))
        
        self.status = "等待中"
        self.create_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.process = None
        
    def to_dict(self):
        return {
            "name": self.name,
            "yaml_file": self.yaml_file,
            "status": self.status,
            "log_file": self.log_file,
            "create_time": self.create_time,
            "video_name": self.video_name,
            "audio_name": self.audio_name,
            "new_video_name": self.new_video_name,  # 现在是完整的绝对路径
            "new_audio_name": self.new_audio_name   # 现在是完整的绝对路径
        }

def load_config():
    """加载配置文件"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_config(config):
    """保存配置文件"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

def generate_task_id():
    """生成任务ID"""
    now = datetime.now()
    random_str = str(uuid.uuid4())[:4]
    return f"{now.strftime('%Y%m%d%H%M%S')}_{random_str}"

def convert_video(input_file, output_path):
    """转换视频为MP4格式"""
    # 保存上传的文件
    temp_path = os.path.join(os.path.dirname(output_path), "temp_" + input_file.filename)
    input_file.save(temp_path)
    
    try:
        if temp_path.lower().endswith('.mp4'):
            shutil.copy2(temp_path, output_path)
        else:
            cmd = f'ffmpeg -i "{temp_path}" -c:v libx264 -preset medium -crf 23 "{output_path}"'
            subprocess.run(cmd, shell=True, check=True)
    finally:
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)

def convert_audio(input_file, output_path):
    """转换音频为WAV格式"""
    # 保存上传的文件
    temp_path = os.path.join(os.path.dirname(output_path), "temp_" + input_file.filename)
    input_file.save(temp_path)
    
    try:
        if temp_path.lower().endswith('.wav'):
            shutil.copy2(temp_path, output_path)
        else:
            cmd = f'ffmpeg -i "{temp_path}" "{output_path}"'
            subprocess.run(cmd, shell=True, check=True)
    finally:
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)

def create_yaml_file(task_id, new_video_name, new_audio_name):
    """创建YAML配置文件"""
    yaml_content = f"""{task_id}:
  preparation: True
  bbox_shift: 5
  video_path: {new_video_name}
  audio_clips:
    audio_0: {new_audio_name}
"""
    yaml_path = os.path.join(TRAIN_DIR, task_id, f"{task_id}.yaml")
    with open(yaml_path, 'w', encoding='utf-8') as f:
        f.write(yaml_content)

def get_command(yaml_path):
    """根据操作系统生成对应的命令"""
    if not MUSETALK:
        raise ValueError("MUSETALK 路径未配置")
        
    os_type = platform.system()
    
    if os_type == "Windows":
        # Windows 环境下，使用 cmd 激活 conda 环境并执行命令
        return f'cmd /c "cd /d {MUSETALK} && conda activate musetalk && python -m scripts.realtime_inference --inference_config {yaml_path}"'
    else:
        # Linux/macOS 环境下，先进入目录，然后激活环境并执行命令
        return f'cd {MUSETALK} && source /root/miniconda3/etc/profile.d/conda.sh && conda activate musetalk && python -m scripts.realtime_inference --inference_config {yaml_path}'

def process_task_queue():
    """处理任务队列"""
    global current_task
    while True:
        with task_lock:
            if not task_queue or current_task:
                time.sleep(10)  # 等待10秒后继续检查
                continue
            
            current_task = task_queue[0]
            config = load_config()
            task_info = config[current_task]
            
            # 更新状态为训练中
            task_info['status'] = "训练中"
            save_config(config)
            
            try:
                # 准备命令
                yaml_path = os.path.join(TRAIN_DIR, current_task, f"{current_task}.yaml")
                cmd = get_command(yaml_path)
                
                # 启动进程
                log_path = os.path.join(TRAIN_DIR, current_task, f"{current_task}.log")
                with open(log_path, 'a', encoding='utf-8') as log_file:
                    # 记录开始时间
                    start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    log_file.write(f"[{start_time}] 开始训练...\n")
                    log_file.flush()
                    
                    # 执行命令
                    process = subprocess.Popen(
                        cmd,
                        shell=True,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        text=True
                    )
                    
                    # 等待进程完成
                    return_code = process.wait()
                    
                    # 记录结束时间和状态
                    end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    if return_code == 0:
                        log_file.write(f"[{end_time}] 训练完成\n")
                    else:
                        log_file.write(f"[{end_time}] 训练失败，返回码: {return_code}\n")
                    log_file.flush()
                
                # 更新任务状态
                with task_lock:
                    config = load_config()
                    task_info = config[current_task]
                    task_info['status'] = "已完成" if return_code == 0 else "失败"
                    save_config(config)
                    
            except Exception as e:
                # 记录错误信息
                with open(log_path, 'a', encoding='utf-8') as log_file:
                    error_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    log_file.write(f"[{error_time}] 执行出错: {str(e)}\n")
                
                # 更新任务状态为失败
                with task_lock:
                    config = load_config()
                    task_info = config[current_task]
                    task_info['status'] = "失败"
                    save_config(config)
            
            finally:
                # 清理当前任务
                with task_lock:
                    task_queue.pop(0)
                    current_task = None

# 启动任务处理线程
threading.Thread(target=process_task_queue, daemon=True).start()

@bp.route('/train')
def train():
    return render_template('train.html')

@bp.route('/train/upload', methods=['POST'])
def upload():
    try:
        video = request.files['video']
        audio = request.files['audio']
        name = request.form['name']
        
        # 验证文件和名称
        if not video or not audio or not name:
            return jsonify({'error': '请提供所有必需的文件和信息'})
        
        if not name.replace(' ', '').isalnum():
            return jsonify({'error': '训练对象名称只能包含字母、数字、汉字'})
        
        # 生成任务ID和目录
        task_id = generate_task_id()
        task_dir = os.path.join(TRAIN_DIR, task_id)
        os.makedirs(task_dir, exist_ok=True)
        
        # 保存并转换文件
        video_path = os.path.join(task_dir, f"{task_id}.mp4")
        audio_path = os.path.join(task_dir, f"{task_id}.wav")
        
        try:
            convert_video(video, video_path)
            convert_audio(audio, audio_path)
        except Exception as e:
            shutil.rmtree(task_dir)
            return jsonify({'error': f'文件转换失败: {str(e)}'})
        
        # 创建任务对象
        task = TrainTask(task_id, name, video.filename, audio.filename)
        
        # 创建YAML文件
        create_yaml_file(task_id, task.new_video_name, task.new_audio_name)
        
        # 更新配置文件
        config = load_config()
        config[task_id] = task.to_dict()
        save_config(config)
        
        # 添加到任务队列
        with task_lock:
            task_queue.append(task_id)
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)})

@bp.route('/train/tasks')
def get_tasks():
    return jsonify(load_config())

@bp.route('/train/task_status/<task_id>')
def task_status(task_id):
    config = load_config()
    if task_id not in config:
        return jsonify({'error': '任务不存在'})
    
    task_info = config[task_id]
    log_path = os.path.join(TRAIN_DIR, task_id, task_info['log_file'])
    
    # 读取日志文件
    logs = []
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding='utf-8') as f:
            logs = f.readlines()
    
    # 如果是页面刷新
    is_refresh = request.args.get('refresh', 'false') == 'true'
    if is_refresh:
        return jsonify({
            'status': task_info['status'],
            'log': logs,
            'new_logs': []
        })
    else:
        # 获取新的日志（这里可以优化为只返回新的部分）
        return jsonify({
            'status': task_info['status'],
            'log': [],
            'new_logs': logs
        })

@bp.route('/train/update_name', methods=['POST'])
def update_name():
    task_id = request.form['task_id']
    new_name = request.form['name']
    
    if not new_name.replace(' ', '').isalnum():
        return jsonify({'error': '名称只能包含字母、数字、汉字'})
    
    config = load_config()
    if task_id not in config:
        return jsonify({'error': '任务不存在'})
    
    config[task_id]['name'] = new_name
    save_config(config)
    
    return jsonify({'success': True})

@bp.route('/train/delete_task', methods=['POST'])
def delete_task():
    task_id = request.form['task_id']
    
    config = load_config()
    if task_id not in config:
        return jsonify({'error': '任务不存在'})
    
    task_info = config[task_id]
    if task_info['status'] != "已完成":
        return jsonify({'error': '只能删除已完成的任务'})
    
    # 删除任务目录
    task_dir = os.path.join(TRAIN_DIR, task_id)
    if os.path.exists(task_dir):
        shutil.rmtree(task_dir)
    
    # 从配置文件中删除
    del config[task_id]
    save_config(config)
    
    return jsonify({'success': True}) 