from flask import Blueprint, render_template, request, jsonify
import os
import subprocess
import uuid
from datetime import datetime

bp = Blueprint('train', __name__)

# 存储训练任务信息
train_tasks = {}

class TrainTask:
    def __init__(self, task_id, video_path, audio_path):
        self.task_id = task_id
        self.video_path = video_path
        self.audio_path = audio_path
        self.status = "训练中"
        self.log = []
        self.create_time = datetime.now()

@bp.route('/train')
def train():
    return render_template('train.html')

@bp.route('/train/upload', methods=['POST'])
def upload():
    if 'video' not in request.files or 'audio' not in request.files:
        return jsonify({'error': '请上传视频和音频文件'}), 400
        
    video = request.files['video']
    audio = request.files['audio']
    
    # 生成唯一任务ID
    task_id = str(uuid.uuid4())
    
    # 创建上传目录
    upload_dir = os.path.join('static', 'train_uploads', task_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    # 保存上传的文件
    video_path = os.path.join(upload_dir, video.filename)
    audio_path = os.path.join(upload_dir, audio.filename)
    
    video.save(video_path)
    audio.save(audio_path)
    
    # 创建新任务
    task = TrainTask(task_id, video_path, audio_path)
    train_tasks[task_id] = task
    
    # 调用外部训练项目
    # 注意：这里需要替换为实际的Python项目路径和启动脚本
    external_project_path = "/path/to/external/project"
    subprocess.Popen([
        'python',
        os.path.join(external_project_path, 'main.py'),  # 替换为实际的入口脚本
        '--mode', 'train',
        '--video', video_path,
        '--audio', audio_path,
        '--output_dir', upload_dir,
        '--task_id', task_id
    ])
    
    return jsonify({'task_id': task_id})

@bp.route('/train/task_status/<task_id>')
def task_status(task_id):
    task = train_tasks.get(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    return jsonify({
        'status': task.status,
        'log': task.log,
        'create_time': task.create_time.strftime('%Y-%m-%d %H:%M:%S')
    })

@bp.route('/train/tasks')
def get_tasks():
    task_list = []
    for task in train_tasks.values():
        task_list.append({
            'task_id': task.task_id,
            'status': task.status,
            'create_time': task.create_time.strftime('%Y-%m-%d %H:%M:%S')
        })
    return jsonify(task_list) 