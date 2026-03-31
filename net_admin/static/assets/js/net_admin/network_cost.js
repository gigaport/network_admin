(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
})((function () {
    'use strict';

    var costData = [];

    function formatPrice(val) {
        if (!val && val !== 0) return '-';
        return Number(val).toLocaleString() + '원';
    }

    function getGroupKey(item) {
        if (item.provider === 'KTC') return 'KTC';
        if (item.provider === 'LGU') return 'LGU';
        if (item.provider === 'SKB') return 'SKB';
        if (item.provider === '세종') return 'SEJONG';
        if (item.provider === '코스콤') return 'KOSCOM';
        return 'ETC';
    }

    function getProviderBadge(provider) {
        var colors = {
            'KTC': '#3b82f6',
            'LGU': '#10b981',
            'SKB': '#ef4444',
            '세종': '#8b5cf6',
            '코스콤': '#0891b2',
            '기타': '#78716c'
        };
        var color = colors[provider] || '#f59e0b';
        return '<span style="display: inline-block; padding: 2px 10px; border-radius: 6px; font-size: 0.7rem; font-weight: 600; color: #fff; background: ' + color + ';">' + provider + '</span>';
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

            // 왼쪽: 코드 + 통신사 배지 + 회선종류 + 비용기준 + 설명
            html += '    <div class="col-md-8">';
            html += '      <div class="d-flex align-items-center gap-3">';
            html += '        <span style="display: inline-block; padding: 3px 8px; border-radius: 5px; font-size: 0.68rem; font-weight: 600; color: #334155; background: #e2e8f0; letter-spacing: 0.3px; min-width: 80px; text-align: center;">' + (item.code || '-') + '</span>';
            html += '        ' + getProviderBadge(item.provider);
            if (item.circuit_type) {
                var ctColor = '#475569', ctBg = '#f1f5f9', ctBorder = '#e2e8f0';
                if (item.circuit_type === '회원사') { ctColor = '#0369a1'; ctBg = '#e0f2fe'; ctBorder = '#7dd3fc'; }
                else if (item.circuit_type === '정보이용사') { ctColor = '#9333ea'; ctBg = '#f3e8ff'; ctBorder = '#c084fc'; }
                html += '        <span style="display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.65rem; font-weight: 500; color: ' + ctColor + '; background: ' + ctBg + '; border: 1px solid ' + ctBorder + ';">' + item.circuit_type + '</span>';
            }
            html += '        <div style="min-width: 0; flex: 1;">';
            html += '          <div class="fw-bold" style="font-size: 0.9rem; color: #1e293b;">' + (item.cost_standart || '-') + '</div>';
            html += '          <div class="text-muted" style="font-size: 0.75rem;">' + (item.description || '-') + '</div>';
            html += '        </div>';
            html += '      </div>';
            html += '    </div>';

            // 원가
            html += '    <div class="col-md-2">';
            html += '      <div class="text-muted" style="font-size: 0.65rem; font-weight: 600; margin-bottom: 2px;">원가</div>';
            html += '      <div class="fw-bold" style="font-size: 0.95rem; color: #0f172a; letter-spacing: -0.3px;">' + formatPrice(item.cost_price) + '</div>';
            html += '    </div>';

            // 버튼
            html += '    <div class="col-md-2 text-end">';
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

    function calcAvg(items) {
        if (!items.length) return '-';
        var sum = 0;
        items.forEach(function(item) { sum += (item.cost_price || 0); });
        return Number(Math.round(sum / items.length)).toLocaleString() + '원';
    }

    function updateStats() {
        var ktItems = [], lguItems = [], skbItems = [], sejongItems = [], koscomItems = [], etcItems = [];
        costData.forEach(function(item) {
            var g = getGroupKey(item);
            if (g === 'KTC') ktItems.push(item);
            else if (g === 'LGU') lguItems.push(item);
            else if (g === 'SKB') skbItems.push(item);
            else if (g === 'SEJONG') sejongItems.push(item);
            else if (g === 'KOSCOM') koscomItems.push(item);
            else etcItems.push(item);
        });
        $('#stat_total').text(costData.length);
        $('#stat_kt').text(ktItems.length);
        $('#stat_lgu').text(lguItems.length);
        $('#stat_skb').text(skbItems.length);
        $('#stat_sejong').text(sejongItems.length);
        $('#stat_koscom').text(koscomItems.length);
        $('#stat_etc').text(etcItems.length);
        $('#stat_total_avg').text('평균 ' + calcAvg(costData));
        $('#stat_kt_avg').text('평균 ' + calcAvg(ktItems));
        $('#stat_lgu_avg').text('평균 ' + calcAvg(lguItems));
        $('#stat_skb_avg').text('평균 ' + calcAvg(skbItems));
        $('#stat_sejong_avg').text('평균 ' + calcAvg(sejongItems));
        $('#stat_koscom_avg').text('평균 ' + calcAvg(koscomItems));
        $('#stat_etc_avg').text('평균 ' + calcAvg(etcItems));
    }

    // 비용기준 커스텀 정렬 순서
    var costStandartOrder = ['서울', '서울_KTC_IDC', '경기도_01', '경기도_02', '경기도_03'];

    function sortByCostStandart(items) {
        return items.sort(function(a, b) {
            var ai = costStandartOrder.indexOf(a.cost_standart);
            var bi = costStandartOrder.indexOf(b.cost_standart);
            if (ai === -1) ai = 9999;
            if (bi === -1) bi = 9999;
            if (ai !== bi) return ai - bi;
            return (a.cost_standart || '').localeCompare(b.cost_standart || '');
        });
    }

    window.loadNetworkCost = function() {
        fetch('/network_cost/get_network_cost')
            .then(function(res) { return res.json(); })
            .then(function(result) {
                if (result.success && result.data) {
                    costData = result.data;
                    updateStats();

                    var groups = { 'KTC': [], 'LGU': [], 'SKB': [], 'SEJONG': [], 'KOSCOM': [], 'ETC': [] };
                    costData.forEach(function(item) {
                        groups[getGroupKey(item)].push(item);
                    });

                    renderGroup('KTC', sortByCostStandart(groups['KTC']));
                    renderGroup('LGU', sortByCostStandart(groups['LGU']));
                    renderGroup('SKB', sortByCostStandart(groups['SKB']));
                    renderGroup('SEJONG', sortByCostStandart(groups['SEJONG']));
                    renderGroup('KOSCOM', sortByCostStandart(groups['KOSCOM']));
                    renderGroup('ETC', sortByCostStandart(groups['ETC']));
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
        $('#add_cost_price').val(0);
        $('#addFormCard').slideDown(200);
    };

    window.hideAddForm = function() {
        $('#addFormCard').slideUp(200);
    };

    window.saveAdd = function() {
        var data = {
            provider: $('#add_provider').val(),
            circuit_type: $('#add_circuit_type').val().trim(),
            cost_standart: $('#add_cost_standart').val().trim(),
            cost_price: parseInt($('#add_cost_price').val()) || 0,
            description: $('#add_description').val().trim()
        };

        if (!data.provider || !data.cost_standart) {
            showAlert('통신사, 비용기준은 필수 입력항목입니다.', 'warning');
            return;
        }

        fetch('/network_cost/create_network_cost', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(function(res) { return res.json(); })
        .then(function(result) {
            if (result.success) {
                showAlert('추가가 완료되었습니다.', 'success');
                hideAddForm();
                loadNetworkCost();
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
        var item = costData.find(function(d) { return d.id === id; });
        if (!item) return;

        $('#edit_id').val(item.id);
        $('#edit_code').val(item.code || '');
        $('#edit_provider').val(item.provider);
        $('#edit_circuit_type').val(item.circuit_type || '');
        $('#edit_cost_standart').val(item.cost_standart);
        $('#edit_cost_price').val(item.cost_price);
        $('#edit_description').val(item.description);

        var modal = new bootstrap.Modal(document.getElementById('editModal'));
        modal.show();
    };

    window.saveEdit = function() {
        var data = {
            id: parseInt($('#edit_id').val()),
            provider: $('#edit_provider').val(),
            circuit_type: $('#edit_circuit_type').val().trim(),
            cost_standart: $('#edit_cost_standart').val().trim(),
            cost_price: parseInt($('#edit_cost_price').val()) || 0,
            description: $('#edit_description').val().trim()
        };

        if (!data.provider || !data.cost_standart) {
            showAlert('통신사, 비용기준은 필수 입력항목입니다.', 'warning');
            return;
        }

        fetch('/network_cost/update_network_cost', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(function(res) { return res.json(); })
        .then(function(result) {
            if (result.success) {
                showAlert('수정이 완료되었습니다.', 'success');
                bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
                loadNetworkCost();
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
        var item = costData.find(function(d) { return d.id === id; });
        if (!item) return;

        if (!confirm('"' + item.provider + ' - ' + (item.cost_standart || '') + '" 항목을 삭제하시겠습니까?')) {
            return;
        }

        fetch('/network_cost/delete_network_cost', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: id })
        })
        .then(function(res) { return res.json(); })
        .then(function(result) {
            if (result.success) {
                showAlert('삭제가 완료되었습니다.', 'success');
                loadNetworkCost();
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
        loadNetworkCost();
    });

}));
