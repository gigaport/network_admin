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

    function formatNumberInput(el) {
        var raw = el.value.replace(/[^\d]/g, '');
        if (raw === '') { el.value = ''; return; }
        el.value = Number(raw).toLocaleString();
    }

    function getRawNumber(selector) {
        return parseInt($(selector).val().replace(/[^\d]/g, '')) || 0;
    }

    function getGroupKey(item) {
        if (item.phase === 1) return '1';
        if (item.phase === 2) return '2';
        return '0';
    }

    function getUsageBadge(usage) {
        var styles = {
            'MPR': { color: '#3b82f6', bg: 'rgba(59,130,246,0.12)' },
            'ORD': { color: '#10b981', bg: 'rgba(16,185,129,0.12)' },
            'PB_ORD_PRD': { color: '#ef4444', bg: 'rgba(239,68,68,0.12)' },
            'PB_ORD_DEV': { color: '#ef4444', bg: 'rgba(239,68,68,0.12)' },
            'MGT': { color: '#8b5cf6', bg: 'rgba(139,92,246,0.12)' },
            '장비사용료': { color: '#f97316', bg: 'rgba(249,115,22,0.12)' },
            '회선설치비': { color: '#06b6d4', bg: 'rgba(6,182,212,0.12)' }
        };
        var s = styles[usage] || { color: '#eab308', bg: 'rgba(234,179,8,0.12)' };
        return '<span style="display:inline-block; padding:3px 10px; border-radius:4px; font-size:0.8rem; font-weight:600; color:' + s.color + '; background:' + s.bg + '; line-height:1.4; white-space:nowrap;">' + usage + '</span>';
    }

    function renderGroup(groupId, items) {
        var container = $('#group_' + groupId);

        if (!items.length) {
            if (groupId === '0') $('#group_0_card').hide();
            container.html('<div style="padding:24px; text-align:center; color:var(--fee-text-light); font-size:0.85rem;">등록된 항목이 없습니다.</div>');
            return;
        }
        if (groupId === '0') $('#group_0_card').show();

        var html = '';
        items.forEach(function(item, idx) {
            var borderTop = idx > 0 ? 'border-top:1px solid var(--fee-border-light);' : '';
            var desc = item.description || '-';
            var sub = [];
            if (item.bandwidth) sub.push(item.bandwidth);
            if (item.additional_circuit) sub.push('추가회선');
            var subText = sub.length ? sub.join(' · ') : '';

            html += '<div class="fee-item" style="padding:12px 14px; ' + borderTop + ' cursor:pointer; transition:background 0.15s;" ';
            html += 'onclick="if(!$(event.target).closest(\'.fee-btn\').length) showEditModal(' + item.id + ')">';

            // Line 1: fee_code + price + buttons
            html += '<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">';
            html += '<span style="font-family:\'SF Mono\',SFMono-Regular,Consolas,monospace; font-size:0.85rem; color:#6366f1; font-weight:500; letter-spacing:0.2px;">' + (item.fee_code || '-') + '</span>';
            html += '<div style="display:flex; align-items:center; gap:8px;">';
            html += '<span style="font-size:0.92rem; font-weight:600; color:var(--fee-text-heading); white-space:nowrap;">' + formatPrice(item.price) + '</span>';
            html += '<div class="fee-actions" style="display:flex; gap:2px;">';
            html += '<button onclick="showEditModal(' + item.id + ')" class="fee-btn" style="width:26px; height:26px; border:none; border-radius:4px; background:transparent; color:var(--fee-text-light); cursor:pointer; display:inline-flex; align-items:center; justify-content:center; padding:0; transition:color 0.15s;" onmouseenter="this.style.color=\'#6366f1\'" onmouseleave="this.style.color=\'\'" title="수정">';
            html += '<i class="fas fa-pen" style="font-size:0.62rem;"></i></button>';
            html += '<button onclick="deleteItem(' + item.id + ')" class="fee-btn" style="width:26px; height:26px; border:none; border-radius:4px; background:transparent; color:var(--fee-text-light); cursor:pointer; display:inline-flex; align-items:center; justify-content:center; padding:0; transition:color 0.15s;" onmouseenter="this.style.color=\'#dc2626\'" onmouseleave="this.style.color=\'\'" title="삭제">';
            html += '<i class="fas fa-trash-alt" style="font-size:0.62rem;"></i></button>';
            html += '</div>';
            html += '</div>';
            html += '</div>';

            // Line 2: usage badge + description + sub info
            html += '<div style="display:flex; align-items:center; gap:6px;">';
            html += getUsageBadge(item.usage);
            html += '<span style="font-size:0.88rem; font-weight:600; color:var(--fee-text-desc); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">' + desc + '</span>';
            if (subText) {
                html += '<span style="font-size:0.8rem; color:var(--fee-text-light); white-space:nowrap;">· ' + subText + '</span>';
            }
            html += '</div>';

            html += '</div>';
        });

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
        $('#stat_phase1_cnt').text(phase1 + '건');
        $('#stat_phase2_cnt').text(phase2 + '건');
        $('#stat_etc_cnt').text(etc + '건');
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
        $('#add_price').val('0');
        $('#add_phase').val(1);
        $('#addFormCard').slideDown(200);
    };

    window.hideAddForm = function() {
        $('#addFormCard').slideUp(200);
    };

    window.saveAdd = function() {
        var data = {
            fee_code: $('#add_fee_code').val().trim(),
            usage: $('#add_usage').val().trim(),
            description: $('#add_description').val().trim(),
            price: getRawNumber('#add_price'),
            phase: parseInt($('#add_phase').val()) || 0,
            bandwidth: $('#add_bandwidth').val().trim() || null,
            additional_circuit: $('#add_additional_circuit').is(':checked')
        };

        if (!data.fee_code || !data.usage || !data.description) {
            showAlert('요금코드, 용도, 설명은 필수 입력항목입니다.', 'warning');
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
        $('#edit_fee_code').val(item.fee_code || '');
        $('#edit_usage').val(item.usage);
        $('#edit_description').val(item.description);
        $('#edit_price').val(item.price ? Number(item.price).toLocaleString() : '0');
        $('#edit_phase').val(item.phase);
        $('#edit_bandwidth').val(item.bandwidth || '');
        $('#edit_additional_circuit').prop('checked', item.additional_circuit);

        var modal = new bootstrap.Modal(document.getElementById('editModal'));
        modal.show();
    };

    window.saveEdit = function() {
        var data = {
            id: parseInt($('#edit_id').val()),
            fee_code: $('#edit_fee_code').val().trim(),
            usage: $('#edit_usage').val().trim(),
            description: $('#edit_description').val().trim(),
            price: getRawNumber('#edit_price'),
            phase: parseInt($('#edit_phase').val()) || 0,
            bandwidth: $('#edit_bandwidth').val().trim() || null,
            additional_circuit: $('#edit_additional_circuit').is(':checked')
        };

        if (!data.fee_code || !data.usage || !data.description) {
            showAlert('요금코드, 용도, 설명은 필수 입력항목입니다.', 'warning');
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
        // 금액 입력필드 콤마 포맷
        $(document).on('input', '.fee-price-input', function() {
            formatNumberInput(this);
        });

        loadFeeSchedule();
    });

}));
