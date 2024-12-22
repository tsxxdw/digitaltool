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
    $.get(`/action/task_status/${taskId}`, function(response) {
        if (response.error) return;
        
        const logContainer = $(`#log-${taskId}`);
        
        // 添加新的日志
        if (response.new_logs && response.new_logs.length > 0) {
            response.new_logs.forEach(log => {
                logContainer.append(`<div class="log-line">${log}</div>`);
            });
            // 滚动到底部
            logContainer.scrollTop(logContainer[0].scrollHeight);
        }
        
        // 如果任务还在处理中，继续轮询
        if (response.status === "处理中") {
            setTimeout(() => pollTaskStatus(taskId), 1000);
        } else {
            // 任务完成或失败时，更新状态
            updateTasks();
        }
    }).fail(function(xhr) {
        console.error('获取任务状态失败:', xhr);
    });
}

// 页面加载完成后执行
$(document).ready(function() {
    $('#uploadForm').submit(function(e) {
        e.preventDefault();
        
        const formData = new FormData(this);
        const submitButton = $(this).find('button[type="submit"]');
        
        // 禁用提交按钮
        submitButton.prop('disabled', true);
        submitButton.text('上传中...');
        
        $.ajax({
            url: '/action/upload',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                alert('上传成功，任务ID: ' + response.task_id);
                updateTasks();
            },
            error: function(xhr) {
                let errorMessage = '上传失败';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMessage += ': ' + xhr.responseJSON.error;
                }
                alert(errorMessage);
            },
            complete: function() {
                // 恢复提交按钮
                submitButton.prop('disabled', false);
                submitButton.text('开始生成');
            }
        });
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

    // 页面加载时更新任务列表
    updateTasks();
    
    // 定期更新任务列表
    setInterval(updateTasks, 50000);
}); 