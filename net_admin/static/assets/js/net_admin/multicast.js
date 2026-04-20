(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
})((function () {
    'use strict';

    var multicastTable = null;
    var countdownInterval = null;
    var countdown = 60;

    function updateFreshness(meta) {
        var el = document.getElementById('updatedTime');
        if (!el || !meta) return;

        var collectedAt = meta.collected_at;
        var status = meta.status;
        var successDevices = meta.success_devices || 0;
        var totalDevices = meta.total_devices || 0;
        var preservedFrom = meta.preserved_from;

        var ageText = '';
        var bgColor = '';
        var icon = '';
        if (collectedAt) {
            var collected = new Date(collectedAt.replace(' ', 'T'));
            var diffMin = Math.round((new Date() - collected) / 60000);
            if (diffMin < 1) ageText = '방금 전';
            else if (diffMin < 60) ageText = diffMin + '분 전';
            else if (diffMin < 1440) ageText = Math.floor(diffMin / 60) + '시간 전';
            else ageText = Math.floor(diffMin / 1440) + '일 전';
        }

        if (status === 'success') { bgColor = '#059669'; icon = 'fa-check-circle'; }
        else if (status === 'partial') { bgColor = '#d97706'; icon = 'fa-exclamation-triangle'; }
        else { bgColor = '#dc2626'; icon = 'fa-times-circle'; }

        var label = '<i class="fas ' + icon + ' me-1"></i>';
        if (status === 'failed' && preservedFrom) {
            label += '수집실패 · 과거 데이터 유지 (' + preservedFrom + ')';
        } else {
            label += '수집: ' + ageText + ' (' + successDevices + '/' + totalDevices + '대)';
        }

        el.innerHTML = label;
        el.className = 'badge';
        el.style.cssText = 'font-size:0.7rem; font-weight:500; padding:3px 10px; border-radius:6px; color:#fff; background:' + bgColor + ';';

        if (collectedAt) {
            var diffMin2 = Math.round((new Date() - new Date(collectedAt.replace(' ', 'T'))) / 60000);
            if (diffMin2 > 5 && status !== 'failed') {
                el.style.background = '#d97706';
                el.innerHTML = '<i class="fas fa-clock me-1"></i>수집: ' + ageText + ' (' + successDevices + '/' + totalDevices + '대)';
            }
        }
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function updateSummary(data) {
        var total = data.length;
        var normalCount = 0;
        var alertCount = 0;

        data.forEach(function(r) {
            if (r.check_result_badge && r.check_result_badge.type === 'success') {
                normalCount++;
            } else {
                alertCount++;
            }
        });

        $('#stat_total').text(total);
        $('#stat_normal').text(normalCount);
        $('#stat_alert').text(alertCount);
    }

    function startAutoRefresh() {
        countdown = 60;
        updateCountdownDisplay();

        if (countdownInterval) clearInterval(countdownInterval);
        countdownInterval = setInterval(function() {
            countdown--;
            updateCountdownDisplay();
            if (countdown <= 0) {
                countdown = 60;
                if (multicastTable) {
                    multicastTable.ajax.reload(null, false);
                }
            }
        }, 1000);
    }

    function updateCountdownDisplay() {
        $('#stat_countdown').text(countdown + '초');
    }

    var initTable = function() {
        var data_back = document.getElementById("back_data");
        var currentPath = data_back ? data_back.dataset.submenu : 'pr_multicast';

        multicastTable = $('#multicast_table').DataTable({
            responsive: false,
            paging: true,
            pageLength: 100,
            searching: true,
            ordering: true,
            order: [],
            language: {
                search: "검색:",
                lengthMenu: "페이지당 _MENU_ 개씩 표시",
                info: "전체 _TOTAL_개 중 _START_-_END_개 표시",
                infoEmpty: "데이터가 없습니다",
                infoFiltered: "(전체 _MAX_개 중 필터링됨)",
                paginate: {
                    first: "처음",
                    last: "마지막",
                    next: "다음",
                    previous: "이전"
                },
                emptyTable: "데이터가 없습니다",
                zeroRecords: "검색 결과가 없습니다",
                loadingRecords: " "
            },
            dom: '<"row align-items-center"<"col-sm-12 col-md-3"l><"col-sm-12 col-md-9 d-flex justify-content-end align-items-center gap-2"fB>>' +
                 '<"row"<"col-sm-12"tr>>' +
                 '<"row"<"col-sm-12 col-md-5"i><"col-sm-12 col-md-7"p>>',
            buttons: [
                {
                    extend: 'excel',
                    text: '<i class="fa-solid fa-file-excel me-2"></i>Excel',
                    className: 'btn btn-success btn-sm',
                    title: '멀티캐스트_시세_' + new Date().toISOString().slice(0, 10),
                    exportOptions: { columns: ':visible', modifier: { page: 'all' } }
                },
                {
                    extend: 'csv',
                    text: '<i class="fa-solid fa-file-csv me-2"></i>CSV',
                    className: 'btn btn-info btn-sm',
                    title: '멀티캐스트_시세_' + new Date().toISOString().slice(0, 10),
                    exportOptions: { columns: ':visible', modifier: { page: 'all' } }
                },
                {
                    extend: 'copy',
                    text: '<i class="fa-solid fa-copy me-2"></i>복사',
                    className: 'btn btn-secondary btn-sm',
                    exportOptions: { columns: ':visible', modifier: { page: 'all' } }
                }
            ],
            ajax: {
                url: '/multicast/init',
                type: 'GET',
                data: { sub_menu: currentPath },
                dataSrc: function(json) {
                    // 새 형식: {"data": [...], "_meta": {...}} 또는 기존 배열 형식 호환
                    var rows = Array.isArray(json) ? json : (json.data || []);
                    var meta = json._meta || null;

                    if (rows.length > 0) {
                        updateSummary(rows);
                        if (currentPath === 'pr_info_multicast') {
                            $('#updatedTime').html('<i class="fas fa-info-circle me-1"></i>실시간 정보');
                        } else if (meta) {
                            updateFreshness(meta);
                        } else if (rows[0].updated_time) {
                            $('#updatedTime').html('<i class="fas fa-clock me-1"></i>최종: ' + rows[0].updated_time);
                        }
                    } else {
                        updateSummary([]);
                        if (meta) { updateFreshness(meta); }
                    }
                    return rows;
                },
                error: function(xhr, error, thrown) {
                    console.error('AJAX Error:', error, thrown);
                    showAlert('데이터 로드 중 오류가 발생했습니다.', 'danger');
                }
            },
            columns: [
                { data: 'member_no' },
                { data: 'member_code' },
                { data: 'member_name' },
                { data: 'device_name' },
                { data: 'device_os' },
                { data: 'products' },
                { data: 'received_products' },
                { data: 'pim_rp' },
                { data: 'product_cnt' },
                { data: 'mroute_cnt' },
                { data: 'oif_cnt' },
                { data: 'min_update' },
                { data: 'checked_at' },
                { data: 'connected_server_cnt' },
                { data: 'org_output' },
                { data: 'check_result' }
            ],
            columnDefs: [
                {
                    targets: 0, // member_no
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return data;
                        if (!data && data !== 0) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-secondary">' + data + '</span>';
                    }
                },
                {
                    targets: 1, // member_code
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return data;
                        if (!data) return '-';
                        return '<span class="fw-bold">' + escapeHtml(data) + '</span>';
                    }
                },
                {
                    targets: 2, // member_name
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (type === 'export') return data;
                        if (!data) return '-';
                        var badge = row.check_result_badge || {};
                        var colorMap = { success: '#10b981', danger: '#ef4444', warning: '#f59e0b' };
                        var color = colorMap[badge.type] || '#64748b';
                        return '<span class="fw-bold" style="color: ' + color + ';">' + escapeHtml(data) + '</span>';
                    }
                },
                {
                    targets: 3, // device_name
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return data;
                        if (!data) return '-';
                        return '<span style="color: #1e293b;">' + escapeHtml(data) + '</span>';
                    }
                },
                {
                    targets: 4, // device_os
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return data;
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-info">' + escapeHtml(data) + '</span>';
                    }
                },
                {
                    targets: 5, // products (신청_시세상품)
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') {
                            if (Array.isArray(data)) return data.join(',');
                            return data || '';
                        }
                        if (!data || (Array.isArray(data) && data.length === 0)) return '-';
                        var arr = Array.isArray(data) ? data : [data];
                        return arr.map(function(p) {
                            return '<span class="badge badge-phoenix badge-phoenix-info me-1" style="font-size:0.72rem;">' + escapeHtml(p) + '</span>';
                        }).join('');
                    }
                },
                {
                    targets: 6, // received_products (수신_시세상품) - 신청 리스트 전부 표시, 누락은 빨강
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        var received = Array.isArray(data) ? data : (data ? [data] : []);
                        var applied = Array.isArray(row.products) ? row.products : (row.products ? [row.products] : []);
                        if (type === 'export') {
                            return applied.map(function(p) {
                                return p + (received.indexOf(p) >= 0 ? '(O)' : '(X)');
                            }).concat(received.filter(function(p) { return applied.indexOf(p) < 0; }).map(function(p) { return p + '(+)'; })).join(',');
                        }
                        if (applied.length === 0 && received.length === 0) return '<span style="color:#cbd5e1;">-</span>';
                        var html = applied.map(function(p) {
                            var ok = received.indexOf(p) >= 0;
                            var cls = ok ? 'success' : 'danger';
                            return '<span class="badge badge-phoenix badge-phoenix-' + cls + ' me-1" style="font-size:0.72rem;">' + escapeHtml(p) + '</span>';
                        }).join('');
                        // 신청엔 없지만 실제 수신중인 상품 (warning 뱃지로 보조 표시)
                        var extras = received.filter(function(p) { return applied.indexOf(p) < 0; });
                        if (extras.length > 0) {
                            html += extras.map(function(p) {
                                return '<span class="badge badge-phoenix badge-phoenix-warning me-1" style="font-size:0.72rem;" title="신청 없이 수신중">' + escapeHtml(p) + '</span>';
                            }).join('');
                        }
                        return html;
                    }
                },
                {
                    targets: 7, // pim_rp
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return data;
                        if (!data) return '-';
                        return '<span style="font-size: 0.8rem;">' + escapeHtml(data) + '</span>';
                    }
                },
                {
                    targets: 8, // product_cnt
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (type === 'export') return data;
                        var badge = row.check_result_badge || {};
                        var colorMap = { success: '#10b981', danger: '#ef4444', warning: '#f59e0b' };
                        var color = colorMap[badge.type] || '#64748b';
                        return '<span class="fw-bold" style="color: ' + color + '; font-size: 1rem;">' + (data != null ? data : '-') + '</span>';
                    }
                },
                {
                    targets: 9, // mroute_cnt
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (type === 'export') return data;
                        var badge = row.check_result_badge || {};
                        var colorMap = { success: '#10b981', danger: '#ef4444', warning: '#f59e0b' };
                        var color = colorMap[badge.type] || '#64748b';
                        return '<span class="fw-bold" style="color: ' + color + '; font-size: 1rem;">' + (data != null ? data : '-') + '</span>';
                    }
                },
                {
                    targets: 10, // oif_cnt
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (type === 'export') return data;
                        var badge = row.check_result_badge || {};
                        var colorMap = { success: '#10b981', danger: '#ef4444', warning: '#f59e0b' };
                        var color = colorMap[badge.type] || '#64748b';
                        return '<span class="fw-bold" style="color: ' + color + '; font-size: 1rem;">' + (data != null ? data : '-') + '</span>';
                    }
                },
                {
                    targets: 11, // min_update
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return data;
                        return data || '-';
                    }
                },
                {
                    targets: 12, // checked_at
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return data;
                        return '<span style="font-size: 0.78rem; font-weight: 700; color: #0ea5e9; background: #f0f9ff; padding: 2px 8px; border-radius: 4px;">' + (data || '-') + '</span>';
                    }
                },
                {
                    targets: 13, // connected_server_cnt
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (type === 'export') return data;
                        var badge = row.check_result_badge || {};
                        var colorMap = { success: '#10b981', danger: '#ef4444', warning: '#f59e0b' };
                        var color = colorMap[badge.type] || '#64748b';
                        return '<span class="fw-bold" style="color: ' + color + ';">' + (data != null ? data : '-') + '</span>';
                    }
                },
                {
                    targets: 14, // org_output - mroute button
                    orderable: false,
                    searchable: false,
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return '';
                        return '<button class="btn btn-phoenix-primary btn-sm btn-mroute" style="font-size: 0.8rem; padding: 2px 8px;">mroute</button>';
                    }
                },
                {
                    targets: 15, // check_result - badge
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (type === 'export') return data;
                        var badge = row.check_result_badge || {};
                        var iconHtml = badge.icon ? ' <span class="ms-1 ' + badge.icon + '" data-fa-transform="shrink-2"></span>' : '';
                        return '<span class="badge badge-phoenix badge-phoenix-' + (badge.type || 'secondary') + '">' +
                            escapeHtml(data || '-') + iconHtml + '</span>';
                    }
                }
            ],
            initComplete: function() {
                var overlay = document.getElementById('pageLoadingOverlay');
                if (overlay) {
                    overlay.style.opacity = '0';
                    setTimeout(function() { overlay.remove(); }, 400);
                }

                // tfoot 검색 필드
                $('#multicast_table tfoot th').each(function(i) {
                    var title = $(this).text();
                    $(this).css({'font-size': '0.75rem', 'white-space': 'nowrap'});
                    $(this).html('<input type="text" class="form-control form-control-sm" placeholder="' + title + '" style="font-size:0.75rem; padding:3px 5px; min-width: 50px;" />');
                });

                multicastTable.columns().every(function() {
                    var that = this;
                    $('input', this.footer()).on('keyup change', function() {
                        if (that.search() !== this.value) {
                            that.search(this.value).draw();
                        }
                    });
                });

                startAutoRefresh();
            }
        });

        // 요약 카드 호버
        $('#summaryCards > div > div').css('transition', 'transform 0.25s ease, box-shadow 0.25s ease');
        $('#summaryCards > div > div').on('mouseenter', function() {
            $(this).css({ 'transform': 'translateY(-4px) scale(1.02)', 'box-shadow': '0 8px 25px rgba(0,0,0,0.2)' });
        }).on('mouseleave', function() {
            $(this).css({ 'transform': 'translateY(0) scale(1)', 'box-shadow': '' });
        });

        // mroute 모달 (이벤트 위임) - org_output은 DB에 저장하지 않고 on-demand로 조회
        $('#multicast_table tbody').on('click', '.btn-mroute', function() {
            var row = multicastTable.row($(this).closest('tr'));
            var data = row.data();
            if (!data) return;

            $('#modal_title').text(data.device_name || '-');
            var parts = [];
            if (data.member_code) parts.push(data.member_code);
            if (data.member_name) parts.push(data.member_name);
            if (data.device_os) parts.push(data.device_os);
            $('#modal_subtitle').text(parts.join(' · '));
            $('#btn_copy_output').html('<i class="fas fa-copy me-1"></i>복사');
            $('#modal_output').text('mroute 정보를 불러오는 중...');

            var modalEl = document.getElementById('modal_mroute');
            var modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
            modal.show();

            var data_back = document.getElementById("back_data");
            var currentPath = data_back ? data_back.dataset.submenu : 'pr_multicast';
            var marketMap = { pr_multicast: 'pr_members', ts_multicast: 'ts_members', pr_info_multicast: 'pr_information' };
            var marketType = marketMap[currentPath] || 'pr_members';

            // org_output이 data에 이미 있으면(fallback 경로) 그대로 사용, 아니면 API 호출
            if (data.org_output) {
                var out = String(data.org_output).replace(/\\r\\n/g, '\n').replace(/\\n/g, '\n').replace(/\\r/g, '\n');
                $('#modal_output').text(out);
                return;
            }

            $.ajax({
                url: '/' + currentPath + '/mroute_output',
                type: 'GET',
                data: { market_type: marketType, device_name: data.device_name },
                success: function(resp) {
                    if (resp && resp.success) {
                        var out = String(resp.output || '').replace(/\\r\\n/g, '\n').replace(/\\n/g, '\n').replace(/\\r/g, '\n');
                        // HTML-escape 되어 저장된 경우 디코딩
                        out = $('<textarea/>').html(out).text();
                        $('#modal_output').text(out || '(출력 없음)');
                    } else {
                        $('#modal_output').text('mroute 정보를 불러올 수 없습니다: ' + (resp && resp.error ? resp.error : 'Unknown error'));
                    }
                },
                error: function(xhr) {
                    $('#modal_output').text('mroute 조회 실패 (HTTP ' + xhr.status + ')');
                }
            });
        });

        // 복사 버튼
        $(document).on('click', '#btn_copy_output', function() {
            var text = $('#modal_output').text();
            var btn = $(this);
            navigator.clipboard.writeText(text).then(function() {
                btn.html('<i class="fas fa-check me-1"></i>복사됨');
                btn.css({ 'background': 'rgba(16,185,129,0.2)', 'color': '#10b981', 'border-color': 'rgba(16,185,129,0.3)' });
                setTimeout(function() {
                    btn.html('<i class="fas fa-copy me-1"></i>복사');
                    btn.css({ 'background': 'rgba(255,255,255,0.08)', 'color': '#a5b4fc', 'border-color': 'rgba(255,255,255,0.12)' });
                }, 2000);
            });
        });
    };

    window.refreshTable = function() {
        var spinner = $('<div class="position-fixed top-50 start-50 translate-middle" style="z-index: 10000;">' +
            '<div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">' +
            '<span class="visually-hidden">Loading...</span>' +
            '</div></div>');
        $('body').append(spinner);

        $('#multicast_table tfoot input').val('');
        if (multicastTable) {
            multicastTable.columns().search('');
            multicastTable.ajax.reload(function() {
                spinner.remove();
                countdown = 60;
                updateCountdownDisplay();
            }, false);
        } else {
            spinner.remove();
        }
    };

    function showAlert(message, type) {
        var icons = { success: 'fa-check-circle', danger: 'fa-exclamation-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle' };
        var colors = { success: '#10b981', danger: '#ef4444', warning: '#f59e0b', info: '#3b82f6' };
        var titles = { success: '완료', danger: '오류', warning: '알림', info: '안내' };
        var icon = icons[type] || icons.info;
        var color = colors[type] || colors.info;
        var title = titles[type] || titles.info;

        if (!$('#toastContainer').length) {
            $('body').append('<div id="toastContainer" class="toast-container position-fixed top-0 end-0 p-3" style="z-index: 9999;"></div>');
        }

        var toastId = 'toast_' + Date.now();
        var toastHtml = '<div id="' + toastId + '" class="toast align-items-center border-0 shadow-lg" role="alert" data-bs-delay="3000" style="border-radius: 10px; overflow: hidden; border-left: 4px solid ' + color + ' !important;">' +
            '<div class="toast-header border-0" style="padding: 10px 14px;">' +
            '<i class="fas ' + icon + ' me-2" style="color: ' + color + '; font-size: 0.9rem;"></i>' +
            '<strong class="me-auto" style="font-size: 0.8rem; color: #1e293b;">' + title + '</strong>' +
            '<button type="button" class="btn-close" data-bs-dismiss="toast" style="font-size: 0.55rem;"></button>' +
            '</div>' +
            '<div class="toast-body" style="padding: 0 14px 12px; font-size: 0.78rem; color: #475569;">' + message + '</div>' +
            '</div>';

        $('#toastContainer').append(toastHtml);
        var toastEl = document.getElementById(toastId);
        var toast = new bootstrap.Toast(toastEl);
        toast.show();
        toastEl.addEventListener('hidden.bs.toast', function() { $(toastEl).remove(); });
    }

    $(document).ready(function() {
        initTable();
    });

}));
