from flask import Blueprint, render_template, request, jsonify
import os
import subprocess
import uuid
from datetime import datetime
import threading
import json
import platform
import shutil

bp = Blueprint('sync', __name__)

# 存储生成任务信息
sync_tasks = {}

# 添加配置文件路径
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_FILE = os.path.join(ROOT_DIR, 'config', 'system_setting.json')

class SyncTask:
    def __init__(self, task_id, trained_video_id, audio_name, person_name):
        self.task_id = task_id
        self.trained_video_id = trained_video_id
        self.audio_name = audio_name
        self.person_name = person_name
        self.status = "等待中"
        self.create_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.output_file = None
        self.log = []
        self.progress = 0

def update_yaml_audio_path(yaml_path, new_audio_path):
    """更新YAML文件中的音频路径"""
    try:
        # 获取当前项目的根目录
        current_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        # 转换为绝对路径
        absolute_audio_path = os.path.abspath(os.path.join(current_dir, new_audio_path))
        
        with open(yaml_path, 'r', encoding='utf-8') as f:
            yaml_content = f.readlines()
            
        new_yaml_content = []
        for line in yaml_content:
            if 'audio_0:' in line:
                # 保持缩进
                indent = len(line) - len(line.lstrip())
                new_yaml_content.append(' ' * indent + f'audio_0: {absolute_audio_path}\n')
            else:
                new_yaml_content.append(line)
                
        with open(yaml_path, 'w', encoding='utf-8') as f:
            f.writelines(new_yaml_content)
            
    except Exception as e:
        raise Exception(f"更新YAML文件失败: {str(e)}")

@bp.route('/sync')
def sync():
    # 获取所有已训练的视频文件
    trained_videos = []
    yaml_dir = os.path.join('static', 'sync', 'yaml')
    
    if os.path.exists(yaml_dir):
        for file in os.listdir(yaml_dir):
            if file.endswith('.txt'):
                task_id = file[:-4]  # 移除.txt后缀
                txt_path = os.path.join(yaml_dir, file)
                yaml_path = os.path.join(yaml_dir, f"{task_id}.yaml")
                
                # 确保对应的yaml文件存在
                if os.path.exists(yaml_path):
                    try:
                        with open(txt_path, 'r', encoding='utf-8') as f:
                            name = f.read().strip()
                        trained_videos.append({
                            'id': task_id,
                            'name': name
                        })
                    except Exception as e:
                        print(f"读取{txt_path}失败: {str(e)}")
    
    return render_template('sync.html', trained_videos=trained_videos)

@bp.route('/sync/upload', methods=['POST'])
def upload():
    try:
        if 'audio' not in request.files or 'trained_video' not in request.form:
            return jsonify({'error': '请选择训练好的视频和上传新的音频文件'})
            
        audio = request.files['audio']
        trained_video_id = request.form['trained_video']
        
        # 验证训练文件是否存在
        yaml_path = os.path.join('static', 'sync', 'yaml', f'{trained_video_id}.yaml')
        txt_path = os.path.join('static', 'sync', 'yaml', f'{trained_video_id}.txt')
        
        if not os.path.exists(yaml_path):
            return jsonify({'error': '所选视频的训练数据不存在'})
            
        # 读取训练对象名称
        with open(txt_path, 'r', encoding='utf-8') as f:
            person_name = f.read().strip()
            
        # 生成任务ID
        task_id = generate_task_id()
        
        # 创建输出目录
        out_dir = os.path.join('static', 'sync', 'out')
        os.makedirs(out_dir, exist_ok=True)
        
        # 保存并转换音频文件
        original_audio_path = os.path.join(out_dir, f"{task_id}_original_{audio.filename}")
        converted_audio_path = os.path.join(out_dir, f"{task_id}.wav")
        audio.save(original_audio_path)
        
        # 转换音频为WAV格式
        try:
            if original_audio_path.lower().endswith('.wav'):
                shutil.copy2(original_audio_path, converted_audio_path)
            else:
                cmd = f'ffmpeg -i "{original_audio_path}" "{converted_audio_path}"'
                subprocess.run(cmd, shell=True, check=True)
        except Exception as e:
            if os.path.exists(original_audio_path):
                os.remove(original_audio_path)
            return jsonify({'error': f'音频转换失败: {str(e)}'})
            
        # 生成输出视频文件名
        output_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{generate_random_string(4)}.mp4"
        output_path = os.path.join(out_dir, output_filename)
        
        # 创建任务
        task = SyncTask(task_id, trained_video_id, audio.filename, person_name)
        sync_tasks[task_id] = task
        
        # 读取配置文件
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            
        # 获取绝对路径
        yaml_path_abs = os.path.abspath(yaml_path)
        output_path_abs = os.path.abspath(output_path)

        # 获取MUSETALK路径
        MUSETALK = config.get('windows_musetalk_path' if platform.system() == 'Windows' else 'linux_musetalk_path', '')
        if not MUSETALK:
            raise Exception("MUSETALK路径未配置")

        # 根据操作系统构建命令
        if platform.system() == 'Windows':
            cmd = f'cmd /c "cd /d {MUSETALK} && conda activate musetalk && python -m tsxxdw.realtime_inference --inference_config {yaml_path_abs} --save_path {output_path_abs}"'
        else:
            cmd = f'cd {MUSETALK} && source /root/miniconda3/etc/profile.d/conda.sh && conda activate musetalk && python -m tsxxdw.realtime_inference --inference_config {yaml_path_abs} --save_path {output_path_abs}"'

        # 打印命令用于调试
        print("执行的命令：")
        print(cmd)
        print("文件路径：")
        print(f"YAML文件: {yaml_path_abs}")
        print(f"输出文件: {output_path_abs}")

        # 添加到任务日志
        task.log.append(f"执行的命令：\n{cmd}")
        task.log.append(f"YAML文件: {yaml_path_abs}")
        task.log.append(f"输出文件: {output_path_abs}")

        # 更新yaml文件中的音频路径
        try:
            update_yaml_audio_path(yaml_path_abs, converted_audio_path)
        except Exception as e:
            return jsonify({'error': str(e)})

        # 启动生成进程
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding='utf-8',
            errors='replace'
        )
        
        # 启动监控线程
        monitor_thread = threading.Thread(
            target=monitor_process,
            args=(process, task, output_path_abs),
            daemon=True
        )
        monitor_thread.start()
        
        # 清理原始音频文件
        if os.path.exists(original_audio_path):
            os.remove(original_audio_path)
            
        return jsonify({
            'task_id': task_id,
            'message': '任务已创建'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)})

def detect_encoding(text):
    """检测文本编码"""
    if isinstance(text, str):
        return 'utf-8'
    
    # 尝试常见的编码
    encodings = ['utf-8', 'gbk', 'gb2312', 'ascii', 'iso-8859-1', 'utf-16', 'big5']
    
    # 首先尝试 chardet 检测
    try:
        import chardet
        result = chardet.detect(text)
        if result and result['encoding']:
            try:
                text.decode(result['encoding'])
                return result['encoding']
            except:
                pass
    except ImportError:
        pass

    # 如果 chardet 检测失败，尝试预定义的编码列表
    for encoding in encodings:
        try:
            text.decode(encoding)
            return encoding
        except:
            continue
            
    # 如果都失败了，使用 latin1（它能解码任何字节序列）
    return 'latin1'

def safe_decode(text):
    """安全解码文本"""
    if isinstance(text, str):
        return text
        
    encoding = detect_encoding(text)
    return text.decode(encoding)

def monitor_process(process, task, output_path):
    """监控进程输出"""
    task.status = "生成中"
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
            
        if line:
            # 使用safe_decode处理输出
            decoded_line = safe_decode(line)
            task.log.append(decoded_line.strip())
            print(decoded_line.strip())
            
            # 更新进度（如果有进度信息）
            if "Progress:" in decoded_line:
                try:
                    progress = int(decoded_line.split("Progress:")[1].strip().rstrip('%'))
                    task.progress = progress
                except:
                    pass
                    
    if process.returncode == 0:
        task.status = "已完成"
        task.output_file = os.path.relpath(output_path).replace('\\', '/')
    else:
        task.status = "生成失败"
        
@bp.route('/sync/tasks')
def get_tasks():
    """获取所有任务"""
    tasks_dict = {}
    for task_id, task in sync_tasks.items():
        tasks_dict[task_id] = {
            'id': task.task_id,
            'person_name': task.person_name,
            'audio_name': task.audio_name,
            'status': task.status,
            'progress': task.progress,
            'create_time': task.create_time,
            'output_file': task.output_file,
            'log': task.log
        }
    return jsonify(tasks_dict)

@bp.route('/sync/task_status/<task_id>')
def get_task_status(task_id):
    """获取单个任务状态"""
    if task_id not in sync_tasks:
        return jsonify({'error': '任务不存在'})
        
    task = sync_tasks[task_id]
    return jsonify({
        'status': task.status,
        'progress': task.progress,
        'output_file': task.output_file,
        'log': task.log
    }) 

def generate_random_string(length):
    """生成指定长度的随机字符串"""
    import random
    import string
    letters = string.ascii_letters
    return ''.join(random.choice(letters) for _ in range(length))

def generate_task_id():
    """生成任务ID: 年月日时分秒_4位随机字符"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_str = generate_random_string(4)
    return f"{timestamp}_{random_str}" 