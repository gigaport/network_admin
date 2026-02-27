(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
})((function () {
    'use strict';

    var multicastTable = null;
    var countdownInterval = null;
    var countdown = 60;

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
                    if (json && json.length > 0) {
                        updateSummary(json);
                        if (currentPath === 'pr_info_multicast') {
                            $('#updatedTime').html('<i class="fas fa-info-circle me-1"></i>실시간 정보');
                        } else if (json[0].updated_time) {
                            $('#updatedTime').html('<i class="fas fa-clock me-1"></i>최종: ' + json[0].updated_time);
                        }
                    } else {
                        updateSummary([]);
                    }
                    return json || [];
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
                { data: 'pim_rp' },
                { data: 'product_cnt' },
                { data: 'mroute_cnt' },
                { data: 'oif_cnt' },
                { data: 'min_update' },
                { data: 'bfd_nbr' },
                { data: 'rpf_nbr' },
                { data: 'connected_server_cnt' },
                { data: 'alarm' },
                { data: 'member_note' },
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
                    targets: 5, // products
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return data;
                        if (!data) return '-';
                        return '<span style="color: #0ea5e9; font-weight: 500; font-size: 0.8rem;">' + escapeHtml(data) + '</span>';
                    }
                },
                {
                    targets: 6, // pim_rp
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return data;
                        if (!data) return '-';
                        return '<span style="font-size: 0.8rem;">' + escapeHtml(data) + '</span>';
                    }
                },
                {
                    targets: 7, // product_cnt
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
                    targets: 8, // mroute_cnt
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
                    targets: 9, // oif_cnt
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
                    targets: 10, // min_update
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return data;
                        return data || '-';
                    }
                },
                {
                    targets: 11, // bfd_nbr
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return data;
                        return data || '-';
                    }
                },
                {
                    targets: 12, // rpf_nbr
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return data;
                        if (!data) return '-';
                        return '<span style="font-size: 0.8rem;">' + escapeHtml(data) + '</span>';
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
                    targets: 14, // alarm
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (type === 'export') return data;
                        var icon = row.alarm_icon || '';
                        if (icon) {
                            return '<span class="fa-solid ' + icon + ' text-primary me-1"></span>' + escapeHtml(data || '');
                        }
                        return data || '-';
                    }
                },
                {
                    targets: 15, // member_note
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return data;
                        if (!data) return '<span style="color: #cbd5e1;">-</span>';
                        return '<span style="font-size: 0.8rem;">' + escapeHtml(data) + '</span>';
                    }
                },
                {
                    targets: 16, // org_output - mroute button
                    orderable: false,
                    searchable: false,
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return '';
                        return '<button class="btn btn-phoenix-primary btn-sm btn-mroute" style="font-size: 0.8rem; padding: 2px 8px;">mroute</button>';
                    }
                },
                {
                    targets: 17, // check_result - badge
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

        // mroute 모달 (이벤트 위임)
        $('#multicast_table tbody').on('click', '.btn-mroute', function() {
            var row = multicastTable.row($(this).closest('tr'));
            var data = row.data();
            if (data) {
                var output = String(data.org_output || '').replace(/\\r\\n/g, '\n').replace(/\\n/g, '\n').replace(/\\r/g, '\n');
                $('#modal_output').text(output);
                $('#modal_title').text(data.device_name || '-');

                var parts = [];
                if (data.member_code) parts.push(data.member_code);
                if (data.member_name) parts.push(data.member_name);
                if (data.device_os) parts.push(data.device_os);
                $('#modal_subtitle').text(parts.join(' · '));

                // 복사 버튼 초기화
                $('#btn_copy_output').html('<i class="fas fa-copy me-1"></i>복사');

                var modalEl = document.getElementById('modal_mroute');
                var modal = bootstrap.Modal.getInstance(modalEl) || new bootstrap.Modal(modalEl);
                modal.show();
            }
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
