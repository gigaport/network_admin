(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
})((function () {
    'use strict';

    var lldpTable = null;

    // 요약 통계 업데이트
    function updateSummary(data) {
        var devices = {};
        var remoteDevices = {};

        data.forEach(function(r) {
            if (r.hostname) devices[r.hostname] = true;
            if (r.remote_hostname) remoteDevices[r.remote_hostname] = true;
        });

        var deviceCount = Object.keys(devices).length;
        $('#stat_total').text(data.length.toLocaleString());
        $('#stat_devices').text(deviceCount);
        $('#stat_remote_devices').text(Object.keys(remoteDevices).length);
        $('#stat_avg_if').text(deviceCount > 0 ? Math.round(data.length / deviceCount) : '-');

        // 장비별 LLDP 수 바 차트
        renderDeviceBarChart(data);
    }

    function renderDeviceBarChart(data) {
        var deviceCounts = {};
        data.forEach(function(r) {
            var name = r.hostname || '-';
            deviceCounts[name] = (deviceCounts[name] || 0) + 1;
        });

        var sorted = Object.keys(deviceCounts).sort(function(a, b) {
            return deviceCounts[b] - deviceCounts[a];
        });

        var top = sorted.slice(0, 20);
        var max = top.length > 0 ? deviceCounts[top[0]] : 1;
        var colors = ['#6366f1', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#06b6d4', '#84cc16', '#e11d48', '#7c3aed', '#0d9488', '#dc2626', '#a855f7', '#0891b2', '#16a34a', '#d97706', '#be123c'];

        var html = '';
        top.forEach(function(name, i) {
            var count = deviceCounts[name];
            var heightPct = Math.max(15, Math.round((count / max) * 100));
            var color = colors[i % colors.length];
            var shortName = name.length > 16 ? name.substring(0, 16) + '..' : name;

            html += '<div class="text-center" style="flex: 1; min-width: 40px;">';
            html += '  <div style="font-size: 0.6rem; color: #fff; font-weight: 700; margin-bottom: 3px;">' + count + '</div>';
            html += '  <div style="height: ' + heightPct + '%; min-height: 12px; background: ' + color + '; border-radius: 4px 4px 0 0; opacity: 0.85; transition: opacity 0.2s;" onmouseenter="this.style.opacity=1" onmouseleave="this.style.opacity=0.85"></div>';
            html += '  <div style="font-size: 0.5rem; color: rgba(255,255,255,0.6); margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="' + name + '">' + shortName + '</div>';
            html += '</div>';
        });

        if (sorted.length > 20) {
            $('#stat_device_label').text('TOP 20 / ' + sorted.length + '개');
        } else {
            $('#stat_device_label').text(sorted.length + '개 장비');
        }

        $('#deviceBarChart').html(html);
    }

    var initTable = function() {
        var data_back = document.getElementById("back_data");
        var currentPath = data_back ? data_back.dataset.submenu : 'info_lldp';

        lldpTable = $('#interface_table').DataTable({
            responsive: true,
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
                emptyTable: "검색 결과가 없습니다",
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
                    title: 'LLDP_정보_' + new Date().toISOString().slice(0, 10),
                    exportOptions: {
                        columns: ':visible',
                        modifier: { page: 'all' }
                    }
                },
                {
                    extend: 'csv',
                    text: '<i class="fa-solid fa-file-csv me-2"></i>CSV',
                    className: 'btn btn-info btn-sm',
                    title: 'LLDP_정보_' + new Date().toISOString().slice(0, 10),
                    exportOptions: {
                        columns: ':visible',
                        modifier: { page: 'all' }
                    }
                },
                {
                    extend: 'copy',
                    text: '<i class="fa-solid fa-copy me-2"></i>복사',
                    className: 'btn btn-secondary btn-sm',
                    exportOptions: {
                        columns: ':visible',
                        modifier: { page: 'all' }
                    }
                }
            ],
            ajax: {
                url: '/information/init',
                type: 'GET',
                data: { sub_menu: currentPath },
                dataSrc: function(json) {
                    if (json.data) {
                        updateSummary(json.data);
                        return json.data;
                    }
                    return [];
                },
                error: function(xhr, error, thrown) {
                    console.error('AJAX Error:', error, thrown);
                    showAlert('데이터 로드 중 오류가 발생했습니다.', 'danger');
                }
            },
            columns: [
                { data: 'device_id' },
                { data: 'device_ip' },
                { data: 'hostname' },
                { data: 'local_ifname' },
                { data: 'local_ifdesc' },
                { data: 'remote_hostname' },
                { data: 'remote_port' }
            ],
            columnDefs: [
                {
                    targets: 0, // 장비ID
                    width: '4%',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return data;
                        if (!data && data !== 0) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-secondary">' + data + '</span>';
                    }
                },
                {
                    targets: 1, // 장비접속IP
                    width: '10%',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return data;
                        if (!data) return '-';
                        return '<span style="color: #0ea5e9; font-weight: 500;">' + data + '</span>';
                    }
                },
                {
                    targets: 2, // 장비시스템명
                    width: '15%',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return data;
                        if (!data) return '-';
                        return '<span class="fw-bold" style="color: #1e293b;">' + data + '</span>';
                    }
                },
                {
                    targets: 3, // 인터페이스명
                    width: '12%',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return data;
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-primary">' + data + '</span>';
                    }
                },
                {
                    targets: 4, // 인터페이스설명
                    width: '26%',
                    className: 'text-start py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return data;
                        if (!data) return '<span style="color: #cbd5e1;">-</span>';
                        return '<span style="color: #059669; font-weight: 600;">' + data + '</span>';
                    }
                },
                {
                    targets: 5, // 원격장비호스트네임
                    width: '20%',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return data;
                        if (!data) return '<span style="color: #cbd5e1;">-</span>';
                        return '<span class="fw-bold" style="color: #7c3aed;">' + data + '</span>';
                    }
                },
                {
                    targets: 6, // 원격포트
                    width: '13%',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type) {
                        if (type === 'export') return data;
                        if (!data) return '<span style="color: #cbd5e1;">-</span>';
                        return '<span class="badge badge-phoenix badge-phoenix-warning">' + data + '</span>';
                    }
                }
            ],
            initComplete: function() {
                var overlay = document.getElementById('pageLoadingOverlay');
                if (overlay) {
                    overlay.style.opacity = '0';
                    setTimeout(function() { overlay.remove(); }, 400);
                }

                // tfoot 검색 필드 추가
                $('#interface_table tfoot th').each(function(i) {
                    var title = $(this).text();
                    $(this).css({'font-size': '0.7rem', 'white-space': 'nowrap'});
                    $(this).html('<input type="text" class="form-control form-control-sm" placeholder="' + title + ' 검색" style="font-size:0.65rem; padding:2px 4px;" />');
                });

                lldpTable.columns().every(function() {
                    var that = this;
                    $('input', this.footer()).on('keyup change', function() {
                        if (that.search() !== this.value) {
                            that.search(this.value).draw();
                        }
                    });
                });
            }
        });

        // 요약 카드 호버 애니메이션
        $('#summaryCards > div > div').css('transition', 'transform 0.25s ease, box-shadow 0.25s ease');
        $('#summaryCards > div > div').on('mouseenter', function() {
            $(this).css({ 'transform': 'translateY(-4px) scale(1.02)', 'box-shadow': '0 8px 25px rgba(0,0,0,0.2)' });
        }).on('mouseleave', function() {
            $(this).css({ 'transform': 'translateY(0) scale(1)', 'box-shadow': '' });
        });
    };

    window.refreshTable = function() {
        var spinner = $('<div class="position-fixed top-50 start-50 translate-middle" style="z-index: 10000;">' +
            '<div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">' +
            '<span class="visually-hidden">Loading...</span>' +
            '</div></div>');
        $('body').append(spinner);

        // 검색 필터 초기화
        $('#interface_table tfoot input').val('');
        if (lldpTable) {
            lldpTable.columns().search('');
            lldpTable.ajax.reload(function() {
                spinner.remove();
            }, false);
        } else {
            spinner.remove();
        }
    };

    function showAlert(message, type) {
        var icons = {
            success: 'fa-check-circle',
            danger: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };
        var colors = {
            success: '#10b981',
            danger: '#ef4444',
            warning: '#f59e0b',
            info: '#3b82f6'
        };
        var titles = {
            success: '완료',
            danger: '오류',
            warning: '알림',
            info: '안내'
        };
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

        toastEl.addEventListener('hidden.bs.toast', function() {
            $(toastEl).remove();
        });
    }

    $(document).ready(function() {
        initTable();
    });

}));
