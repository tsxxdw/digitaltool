$(document).ready(function() {
    // 页签切换功能
    $('.tab-btn').click(function() {
        $('.tab-btn').removeClass('active');
        $(this).addClass('active');
        
        const tabId = $(this).data('tab');
        $('.tab-content').removeClass('active');
        $(`#${tabId}`).addClass('active');
    });

    // 页面加载时获取现有设置
    $.get('/system_setting/get', function(data) {
        // Linux 设置
        $('#linux_tango_path').val(data.linux_tango_path || '');
        $('#linux_musetalk_path').val(data.linux_musetalk_path || '');
        
        // Windows 设置
        $('#windows_tango_path').val(data.windows_tango_path || '');
        $('#windows_musetalk_path').val(data.windows_musetalk_path || '');
    });

    // 处理 Linux 设置表单提交
    $('#linuxSettingsForm').submit(function(e) {
        e.preventDefault();
        saveSettings('linux');
    });

    // 处理 Windows 设置表单提交
    $('#windowsSettingsForm').submit(function(e) {
        e.preventDefault();
        saveSettings('windows');
    });

    function saveSettings(platform) {
        const formData = {
            platform: platform,
            settings: {
                tango_path: $(`#${platform}_tango_path`).val(),
                musetalk_path: $(`#${platform}_musetalk_path`).val()
            }
        };
        
        // 禁用提交按钮
        const submitButton = $(`#${platform}SettingsForm button[type="submit"]`);
        submitButton.prop('disabled', true);
        submitButton.text('保存中...');
        
        $.ajax({
            url: '/system_setting/save',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(formData),
            success: function(response) {
                // 显示成功消息
                const successMessage = $('<div class="success-message">设置已保存</div>');
                $('body').append(successMessage);
                successMessage.fadeIn();
                
                // 3秒后隐藏消息
                setTimeout(function() {
                    successMessage.fadeOut(function() {
                        successMessage.remove();
                    });
                }, 3000);
            },
            error: function(xhr) {
                alert('保存失败: ' + xhr.responseJSON.error);
            },
            complete: function() {
                // 恢复提交按钮
                submitButton.prop('disabled', false);
                submitButton.text(`保存 ${platform.charAt(0).toUpperCase() + platform.slice(1)} 设置`);
            }
        });
    }
}); 