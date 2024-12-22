from flask import Blueprint, render_template, request, jsonify
import os
import subprocess
import uuid
from datetime import datetime
import shutil
import json
import platform

bp = Blueprint('action', __name__)

# 存储生成任务信息
action_tasks = {}

class ActionTask:
    def __init__(self, task_id, video_path, audio_path):
        self.task_id = task_id
        self.video_path = video_path
        self.video_name = os.path.basename(video_path)
        self.audio_path = audio_path
        self.audio_name = os.path.basename(audio_path)
        self.status = "处理中"
        self.log = []
        self.output_file = None
        self.create_time = datetime.now()

def get_file_extension(filename):
    """获取文件扩展名（小写）"""
    return os.path.splitext(filename)[1].lower()

def convert_video_to_mp4(input_path, output_path):
    """将视频转换为MP4格式"""
    try:
        subprocess.run([
            'ffmpeg', '-i', input_path,
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-y',
            output_path
        ], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"视频转换错误: {e.stderr.decode()}")
        return False

def convert_audio_to_wav(input_path, output_path):
    """将音频转换为WAV格式"""
    try:
        subprocess.run([
            'ffmpeg', '-i', input_path,
            '-vn',
            '-acodec', 'pcm_s16le',
            '-ar', '44100',
            '-ac', '2',
            '-y',
            output_path
        ], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"音频转换错误: {e.stderr.decode()}")
        return False

@bp.route('/action')
def action():
    return render_template('action.html')

@bp.route('/action/upload', methods=['POST'])
def upload():
    if 'video' not in request.files or 'audio' not in request.files:
        return jsonify({'error': '请上传视频和音频文件'}), 400
        
    video = request.files['video']
    audio = request.files['audio']
    
    # 获取文件扩展名
    video_ext = get_file_extension(video.filename)
    audio_ext = get_file_extension(audio.filename)
    
    # 生成唯一任务ID
    task_id = str(uuid.uuid4())
    
    # 创建上传目录
    upload_dir = os.path.join('static', 'action_uploads', task_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    # 保存原始文件
    original_video_path = os.path.join(upload_dir, 'original_' + video.filename)
    original_audio_path = os.path.join(upload_dir, 'original_' + audio.filename)
    
    video.save(original_video_path)
    audio.save(original_audio_path)
    
    # 转换后的文件路径
    converted_video_path = os.path.join(upload_dir, f'{task_id}.mp4')
    converted_audio_path = os.path.join(upload_dir, f'{task_id}.wav')
    
    # 处理视频文件
    if video_ext == '.mp4':
        # 如果已经是MP4格式，直接复制
        shutil.copy2(original_video_path, converted_video_path)
        task_log = "视频已经是MP4格式，无需转换"
    else:
        # 需要转换为MP4格式
        if not convert_video_to_mp4(original_video_path, converted_video_path):
            shutil.rmtree(upload_dir)  # 清理临时文件
            return jsonify({'error': '视频格式转换失败'}), 400
        task_log = "视频已转换为MP4格式"
    
    # 处理音频文件
    if audio_ext == '.wav':
        # 如果已经是WAV格式，直接复制
        shutil.copy2(original_audio_path, converted_audio_path)
        task_log += "\n音频已经是WAV格式，无需转换"
    else:
        # 需要转换为WAV格式
        if not convert_audio_to_wav(original_audio_path, converted_audio_path):
            shutil.rmtree(upload_dir)  # 清理临时文件
            return jsonify({'error': '音频格式转换失败'}), 400
        task_log += "\n音频已转换为WAV格式"
    
    # 创建新任务
    task = ActionTask(task_id, converted_video_path, converted_audio_path)
    task.log.append(f"原始视频文件: {video.filename}")
    task.log.append(f"原始音频文件: {audio.filename}")
    task.log.append(task_log)
    action_tasks[task_id] = task
    
    # 调用外部生成项目
    try:
        # 从配置文件读取TANGO路径
        config_file = os.path.join('config', 'system_setting.json')
        with open(config_file, 'r') as f:
            config = json.load(f)
            
        if platform.system() == 'Windows':
            tango_path = config.get('windows_tango_path', '')
            # Windows 环境下，使用 cmd 激活 conda 环境并执行命令
            cmd = f'cmd /c "cd /d {tango_path} && conda activate tango && python inference.py --audio_path {converted_audio_path} --video_path {converted_video_path} --save_path {upload_dir}"'
        else:
            tango_path = config.get('linux_tango_path', '')
            # Linux/macOS 环境下，先进入目录，然后激活环境并执行命令
            cmd = f'cd {tango_path} && source /root/miniconda3/etc/profile.d/conda.sh && conda activate tango && python inference.py --audio_path {converted_audio_path} --video_path {converted_video_path} --save_path {upload_dir}'
            
        if not tango_path:
            raise Exception("TANGO路径未配置")
            
        # 使用 shell=True 来执行完整的命令字符串
        subprocess.Popen(cmd, shell=True)
        
    except Exception as e:
        task.log.append(f"启动任务失败: {str(e)}")
        task.status = "失败"
        return jsonify({'error': str(e)}), 500
    
    return jsonify({'task_id': task_id})

@bp.route('/action/tasks')
def get_tasks():
    task_list = []
    for task in action_tasks.values():
        task_list.append({
            'task_id': task.task_id,
            'status': task.status,
            'video_name': task.video_name,
            'audio_name': task.audio_name,
            'create_time': task.create_time.strftime('%Y-%m-%d %H:%M:%S'),
            'output_file': task.output_file
        })
    return jsonify(task_list)

@bp.route('/action/task_status/<task_id>')
def task_status(task_id):
    task = action_tasks.get(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    return jsonify({
        'status': task.status,
        'log': task.log,
        'output_file': task.output_file
    }) 