// 更新任务列表
function updateTasks() {
    $.get('/action/tasks', function(tasks) {
        $('#taskContainer').empty();
        tasks.forEach(function(task) {
            let taskHtml = `
                <div class="task-item">
                    <div class="task-header">
                        <div class="task-info">
                            <div><strong>任务ID:</strong> ${task.task_id}</div>
                            <div><strong>状态:</strong> <span class="status-badge ${task.status === '完成' ? 'status-complete' : 'status-processing'}">${task.status}</span></div>
                            <div><strong>创建时间:</strong> ${task.create_time}</div>
                        </div>
                    </div>
                    <div class="file-info">
                        <div class="file-item">
                            <span class="file-label">视频文件：</span>
                            <span class="file-name">${task.video_name}</span>
                        </div>
                        <div class="file-item">
                            <span class="file-label">音频文件：</span>
                            <span class="file-name">${task.audio_name}</span>
                        </div>
                    </div>
                    <div class="log-container" id="log-${task.task_id}"></div>
                    ${task.output_file ? `
                        <div class="download-actions">
                            <a href="${task.output_file}" class="download-btn" download>下载视频</a>
                            <span class="copy-link-btn" onclick="showDownloadLink('${task.output_file}')">复制下载链接</span>
                        </div>
                    ` : ''}
                </div>
            `;
            $('#taskContainer').append(taskHtml);
            
            // 获取任务状态和日志
            pollTaskStatus(task.task_id);
        });
    });
}

// 轮询任务状态
function pollTaskStatus(taskId) {
    $.get(`/task_status/${taskId}`, function(response) {
        if (response.error) return;
        
        $(`#log-${taskId}`).html(response.log.join('<br>'));
        
        if (response.status === "处理中") {
            setTimeout(() => pollTaskStatus(taskId), 2000);
        }
    });
}

// 页面加载完成后执行
$(document).ready(function() {
    // 处理表单提交
    $('#uploadForm').submit(function(e) {
        e.preventDefault();
        
        let formData = new FormData(this);
        
        $.ajax({
            url: '/upload',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                alert('任务已提交，任务ID: ' + response.task_id);
                updateTasks();
            },
            error: function(xhr) {
                alert('提交失败: ' + xhr.responseJSON.error);
            }
        });
    });

    // 页面加载时更新任务列表
    updateTasks();
    
    // 定期更新任务列表
    setInterval(updateTasks, 5000);
}); 