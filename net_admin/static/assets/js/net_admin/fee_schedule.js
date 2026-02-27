(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
})((function () {
    'use strict';

    var feeData = [];

    function formatPrice(val) {
        if (!val && val !== 0) return '-';
        return Number(val).toLocaleString() + '원';
    }

    function getGroupKey(item) {
        if (item.phase === 1) return '1';
        if (item.phase === 2) return '2';
        return '0';
    }

    function getUsageBadge(usage) {
        var colors = {
            'MPR': '#3b82f6',
            'ORD': '#10b981'
        };
        var color = colors[usage] || '#f59e0b';
        return '<span style="display: inline-block; padding: 2px 10px; border-radius: 6px; font-size: 0.7rem; font-weight: 600; color: #fff; background: ' + color + ';">' + usage + '</span>';
    }

    function getPhaseBadge(phase) {
        if (phase === 1) return '<span style="display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 0.65rem; font-weight: 600; color: #fff; background: #6366f1;">Phase 1</span>';
        if (phase === 2) return '<span style="display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 0.65rem; font-weight: 600; color: #fff; background: #8b5cf6;">Phase 2</span>';
        return '<span style="display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 0.65rem; font-weight: 600; color: #fff; background: #94a3b8;">-</span>';
    }

    function renderGroup(groupId, items) {
        var container = $('#group_' + groupId);

        if (!items.length) {
            container.html('<div class="text-center py-4 text-muted" style="font-size: 0.85rem;">등록된 항목이 없습니다.</div>');
            return;
        }

        var html = '<div class="list-group list-group-flush">';

        items.forEach(function(item) {
            html += '<div class="list-group-item px-4 py-3" style="border-left: none; border-right: none; cursor: pointer;" data-id="' + item.id + '" onclick="if(!$(event.target).closest(\'button\').length) showEditModal(' + item.id + ')">';
            html += '  <div class="row align-items-center">';

            // 왼쪽: 용도 배지 + 요금키 + 설명
            html += '    <div class="col-md-4">';
            html += '      <div class="d-flex align-items-center gap-3">';
            html += '        ' + getUsageBadge(item.usage);
            html += '        <div>';
            html += '          <div class="fw-bold" style="font-size: 0.9rem; color: #1e293b;">' + (item.description || '-') + '</div>';
            html += '          <div class="text-muted" style="font-size: 0.75rem;">' + (item.description || '-') + '</div>';
            html += '        </div>';
            html += '      </div>';
            html += '    </div>';

            // 가운데: 요금 + 가입 Phase
            html += '    <div class="col-md-4">';
            html += '      <div class="d-flex gap-5 align-items-center">';
            html += '        <div style="min-width: 120px;">';
            html += '          <div class="text-muted" style="font-size: 0.65rem; font-weight: 600; margin-bottom: 2px;">요금</div>';
            html += '          <div class="fw-bold" style="font-size: 0.95rem; color: #0f172a; letter-spacing: -0.3px;">' + formatPrice(item.price) + '</div>';
            html += '        </div>';
            html += '        <div>';
            html += '          <div class="text-muted" style="font-size: 0.65rem; font-weight: 600; margin-bottom: 2px;">가입 Phase</div>';
            html += '          <div>' + getPhaseBadge(item.phase) + '</div>';
            html += '        </div>';
            html += '      </div>';
            html += '    </div>';

            // 오른쪽: 버튼
            html += '    <div class="col-md-4 text-end">';
            html += '      <button onclick="showEditModal(' + item.id + ')" style="width: 30px; height: 30px; border: none; border-radius: 8px; background: #f1f5f9; color: #64748b; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; transition: all 0.2s; margin-right: 4px;" onmouseenter="this.style.background=\'#e0e7ff\';this.style.color=\'#4f46e5\'" onmouseleave="this.style.background=\'#f1f5f9\';this.style.color=\'#64748b\'" title="수정">';
            html += '        <i class="fas fa-pen" style="font-size: 0.65rem;"></i>';
            html += '      </button>';
            html += '      <button onclick="deleteItem(' + item.id + ')" style="width: 30px; height: 30px; border: none; border-radius: 8px; background: #f1f5f9; color: #64748b; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; transition: all 0.2s;" onmouseenter="this.style.background=\'#fee2e2\';this.style.color=\'#dc2626\'" onmouseleave="this.style.background=\'#f1f5f9\';this.style.color=\'#64748b\'" title="삭제">';
            html += '        <i class="fas fa-trash-alt" style="font-size: 0.65rem;"></i>';
            html += '      </button>';
            html += '    </div>';

            html += '  </div>';
            html += '</div>';
        });

        html += '</div>';
        container.html(html);
    }

    function updateStats() {
        var phase1 = 0, phase2 = 0, etc = 0;
        feeData.forEach(function(item) {
            var g = getGroupKey(item);
            if (g === '1') phase1++;
            else if (g === '2') phase2++;
            else etc++;
        });
        $('#stat_total').text(feeData.length);
        $('#stat_phase1').text(phase1);
        $('#stat_phase2').text(phase2);
        $('#stat_etc').text(etc);
    }

    window.loadFeeSchedule = function() {
        fetch('/fee_schedule/get_fee_schedule')
            .then(function(res) { return res.json(); })
            .then(function(result) {
                if (result.success && result.data) {
                    feeData = result.data;
                    updateStats();

                    var groups = { '1': [], '2': [], '0': [] };
                    feeData.forEach(function(item) {
                        groups[getGroupKey(item)].push(item);
                    });

                    renderGroup('1', groups['1']);
                    renderGroup('2', groups['2']);
                    renderGroup('0', groups['0']);
                } else {
                    showAlert('데이터 로드 실패: ' + (result.error || ''), 'danger');
                }
            })
            .catch(function(err) {
                console.error('Error:', err);
                showAlert('데이터 로드 중 오류가 발생했습니다.', 'danger');
            });
    };

    window.showAddForm = function() {
        $('#addForm')[0].reset();
        $('#add_price').val(0);
        $('#add_phase').val(1);
        $('#addFormCard').slideDown(200);
    };

    window.hideAddForm = function() {
        $('#addFormCard').slideUp(200);
    };

    window.saveAdd = function() {
        var data = {
            usage: $('#add_usage').val().trim(),
            description: $('#add_description').val().trim(),
            price: parseInt($('#add_price').val()) || 0,
            phase: parseInt($('#add_phase').val()) || 0,
            bandwidth: $('#add_bandwidth').val().trim() || null,
            additional_circuit: $('#add_additional_circuit').is(':checked')
        };

        if (!data.usage || !data.description) {
            showAlert('용도, 설명은 필수 입력항목입니다.', 'warning');
            return;
        }

        fetch('/fee_schedule/create_fee_schedule', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(function(res) { return res.json(); })
        .then(function(result) {
            if (result.success) {
                showAlert('추가가 완료되었습니다.', 'success');
                hideAddForm();
                loadFeeSchedule();
            } else {
                showAlert('추가 실패: ' + result.error, 'danger');
            }
        })
        .catch(function(err) {
            console.error('Error:', err);
            showAlert('추가 중 오류가 발생했습니다.', 'danger');
        });
    };

    window.showEditModal = function(id) {
        var item = feeData.find(function(d) { return d.id === id; });
        if (!item) return;

        $('#edit_id').val(item.id);
        $('#edit_usage').val(item.usage);
        $('#edit_description').val(item.description);
        $('#edit_price').val(item.price);
        $('#edit_phase').val(item.phase);
        $('#edit_bandwidth').val(item.bandwidth || '');
        $('#edit_additional_circuit').prop('checked', item.additional_circuit);

        var modal = new bootstrap.Modal(document.getElementById('editModal'));
        modal.show();
    };

    window.saveEdit = function() {
        var data = {
            id: parseInt($('#edit_id').val()),
            usage: $('#edit_usage').val().trim(),
            description: $('#edit_description').val().trim(),
            price: parseInt($('#edit_price').val()) || 0,
            phase: parseInt($('#edit_phase').val()) || 0,
            bandwidth: $('#edit_bandwidth').val().trim() || null,
            additional_circuit: $('#edit_additional_circuit').is(':checked')
        };

        if (!data.usage || !data.description) {
            showAlert('용도, 설명은 필수 입력항목입니다.', 'warning');
            return;
        }

        fetch('/fee_schedule/update_fee_schedule', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(function(res) { return res.json(); })
        .then(function(result) {
            if (result.success) {
                showAlert('수정이 완료되었습니다.', 'success');
                bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
                loadFeeSchedule();
            } else {
                showAlert('수정 실패: ' + result.error, 'danger');
            }
        })
        .catch(function(err) {
            console.error('Error:', err);
            showAlert('수정 중 오류가 발생했습니다.', 'danger');
        });
    };

    window.deleteItem = function(id) {
        var item = feeData.find(function(d) { return d.id === id; });
        if (!item) return;

        if (!confirm('"' + item.usage + ' - ' + item.description + '" 항목을 삭제하시겠습니까?')) {
            return;
        }

        fetch('/fee_schedule/delete_fee_schedule', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: id })
        })
        .then(function(res) { return res.json(); })
        .then(function(result) {
            if (result.success) {
                showAlert('삭제가 완료되었습니다.', 'success');
                loadFeeSchedule();
            } else {
                showAlert('삭제 실패: ' + result.error, 'danger');
            }
        })
        .catch(function(err) {
            console.error('Error:', err);
            showAlert('삭제 중 오류가 발생했습니다.', 'danger');
        });
    };

    function showAlert(message, type) {
        var alertDiv = $('<div></div>')
            .addClass('alert alert-' + type + ' alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3')
            .css('zIndex', '9999')
            .html(message + '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>');

        $('body').append(alertDiv);

        setTimeout(function() {
            alertDiv.remove();
        }, 3000);
    }

    $(document).ready(function() {
        loadFeeSchedule();
    });

}));
