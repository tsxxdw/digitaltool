// 全局变量来存储轮询间隔
const POLLING_INTERVAL = 10000;      // 10秒
const COMPLETED_POLLING_INTERVAL = null;  // 已完成的任务不再轮询

// 更新任务列表
function updateTasks() {
    $.get('/action/tasks', function(tasks) {
        $('#taskContainer').empty();
        tasks.forEach(function(task) {
            let queueInfo = task.queue_position ? 
                `<div class="queue-info">队列位置: ${task.queue_position}</div>` : '';
                
            let taskHtml = `
                <div class="task-item">
                    <div class="task-header">
                        <div class="task-info">
                            <div><strong>任务ID:</strong> ${task.task_id}</div>
                            <div><strong>状态:</strong> <span class="status-badge ${getStatusClass(task.status)}">${task.status}</span></div>
                            <div><strong>创建时间:</strong> ${task.create_time}</div>
                            ${queueInfo}
                        </div>
                    </div>
                    <div class="file-info">
                        <div class="file-item">
                            ${task.video_name}
                        </div>
                        <div class="file-item">
                            ${task.audio_name}
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
            
            // 获取任务状态和日志（页面刷新模式）
            pollTaskStatus(task.task_id, true);
        });
        
        // 只有存在进行中的任务时才继续轮询
        const hasActiveTasks = tasks.some(task => 
            task.status !== "完成" && task.status !== "失败"
        );
        if (hasActiveTasks) {
            setTimeout(updateTasks, POLLING_INTERVAL);
        }
    });
}

// 轮询任务状态
function pollTaskStatus(taskId, isRefresh = false) {
    const url = isRefresh 
        ? `/action/task_status/${taskId}?refresh=true`
        : `/action/task_status/${taskId}`;

    $.get(url, function(response) {
        if (response.error) return;
        
        const logContainer = $(`#log-${taskId}`);
        
        // 如果是页面刷新，清空并显示完整的历史日志
        if (isRefresh) {
            logContainer.empty();
            response.log.forEach(log => {
                logContainer.append(`<div class="log-line">${log}</div>`);
            });
        }
        // 否则只添加新的日志
        else if (response.new_logs && response.new_logs.length > 0) {
            response.new_logs.forEach(log => {
                logContainer.append(`<div class="log-line">${log}</div>`);
            });
        }
        
        // 滚动到底部
        logContainer.scrollTop(logContainer[0].scrollHeight);
        
        // 只有任务正在进行中时才继续轮询
        if (response.status !== "完成" && response.status !== "失败") {
            setTimeout(() => pollTaskStatus(taskId, false), POLLING_INTERVAL);
        }
    }).fail(function(xhr) {
        console.error('获取任务状态失败:', xhr);
    });
}

// 页面加载完成后执行
$(document).ready(function() {
    updateTasks();

    // 监听表单提交
    $('#uploadForm').on('submit', function(e) {
        e.preventDefault(); // 阻止表单默认提交行为
        
        // 检查是否选择了文件
        const videoFile = $('#video')[0].files[0];
        const audioFile = $('#audio')[0].files[0];
        
        if (!videoFile || !audioFile) {
            alert('请选择视频和音频文件');
            return false;
        }

        // 创建 FormData 对象
        const formData = new FormData();
        formData.append('video', videoFile);
        formData.append('audio', audioFile);

        // 禁用提交按钮
        $('#submitBtn').prop('disabled', true);

        // 发送 AJAX 请求
        $.ajax({
            url: '/action/upload',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                if (response.task_id) {
                    // 清空表单
                    $('#uploadForm')[0].reset();
                    // 更新任务列表
                    updateTasks();
                } else {
                    alert('上传失败：' + (response.error || '未知错误'));
                }
            },
            error: function(xhr) {
                alert('上传失败：' + (xhr.responseJSON?.error || '服务器错误'));
            },
            complete: function() {
                // 重新启用提交按钮
                $('#submitBtn').prop('disabled', false);
            }
        });

        return false;
    });

    // 显示下载链接
    window.showDownloadLink = function(url) {
        const modal = $('#linkModal');
        $('#downloadLink').text(window.location.origin + '/' + url);
        modal.show();
    }

    // 复制下载链接
    window.copyDownloadLink = function() {
        const linkText = $('#downloadLink').text();
        navigator.clipboard.writeText(linkText).then(function() {
            alert('链接已复制到剪贴板');
        }).catch(function(err) {
            console.error('复制失败:', err);
            alert('复制失败，请手动复制');
        });
    }

    // 关闭模态框
    $('.close').click(function() {
        $('#linkModal').hide();
    });
    
    // 点击模态框外部关闭
    $(window).click(function(e) {
        if (e.target == document.getElementById('linkModal')) {
            $('#linkModal').hide();
        }
    });
}); 

function getStatusClass(status) {
    switch(status) {
        case '等待中':
            return 'status-waiting';
        case '处理中':
            return 'status-processing';
        case '完成':
            return 'status-complete';
        case '失败':
            return 'status-failed';
        default:
            return '';
    }
} 