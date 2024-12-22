from flask import Blueprint, render_template, request, jsonify
import os
import subprocess
import uuid
from datetime import datetime

bp = Blueprint('sync', __name__)

# 存储生成任务信息
sync_tasks = {}

class SyncTask:
    def __init__(self, task_id, trained_video, audio_path):
        self.task_id = task_id
        self.trained_video = trained_video
        self.audio_path = audio_path
        self.status = "处理中"
        self.log = []
        self.output_file = None
        self.create_time = datetime.now()

@bp.route('/sync')
def sync():
    # 获取所有已训练的视频文件
    trained_videos = []
    train_uploads_dir = os.path.join('static', 'train_uploads')
    if os.path.exists(train_uploads_dir):
        for task_id in os.listdir(train_uploads_dir):
            model_dir = os.path.join(train_uploads_dir, task_id, 'model')
            if os.path.exists(model_dir):
                trained_videos.append({
                    'task_id': task_id,
                    'path': os.path.join(train_uploads_dir, task_id)
                })
    
    return render_template('sync.html', trained_videos=trained_videos)

@bp.route('/sync/upload', methods=['POST'])
def upload():
    if 'audio' not in request.files or 'trained_video' not in request.form:
        return jsonify({'error': '请选择训练好的视频和上传新的音频文件'}), 400
        
    audio = request.files['audio']
    trained_video = request.form['trained_video']
    
    # 验证训练好的视频是否存在
    if not os.path.exists(trained_video):
        return jsonify({'error': '所选视频不存在'}), 400
    
    # 生成唯一任务ID
    task_id = str(uuid.uuid4())
    
    # 创建上传目录
    upload_dir = os.path.join('static', 'sync_uploads', task_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    # 保存音频文件
    audio_path = os.path.join(upload_dir, audio.filename)
    audio.save(audio_path)
    
    # 创建新任务
    task = SyncTask(task_id, trained_video, audio_path)
    sync_tasks[task_id] = task
    
    # 调用外部生成项目
    external_project_path = "/path/to/external/project"
    subprocess.Popen([
        'python',
        os.path.join(external_project_path, 'main.py'),  # 替换为实际的入口脚本
        '--mode', 'generate',
        '--trained_video', trained_video,
        '--audio', audio_path,
        '--output_dir', upload_dir,
        '--task_id', task_id
    ])
    
    return jsonify({'task_id': task_id})

@bp.route('/sync/task_status/<task_id>')
def task_status(task_id):
    task = sync_tasks.get(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    
    return jsonify({
        'status': task.status,
        'log': task.log,
        'output_file': task.output_file,
        'create_time': task.create_time.strftime('%Y-%m-%d %H:%M:%S')
    })

@bp.route('/sync/tasks')
def get_tasks():
    task_list = []
    for task in sync_tasks.values():
        task_list.append({
            'task_id': task.task_id,
            'status': task.status,
            'create_time': task.create_time.strftime('%Y-%m-%d %H:%M:%S'),
            'output_file': task.output_file
        })
    return jsonify(task_list) 