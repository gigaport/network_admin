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
        // 원격장비별 연결 현황
        renderRemoteDeviceList(data);
    }

    function renderDeviceBarChart(data) {
        var isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
        var deviceCounts = {};
        data.forEach(function(r) {
            var name = r.hostname || '-';
            deviceCounts[name] = (deviceCounts[name] || 0) + 1;
        });

        var sorted = Object.keys(deviceCounts).sort(function(a, b) {
            return deviceCounts[b] - deviceCounts[a];
        });

        var top = sorted.slice(0, 15);
        var max = top.length > 0 ? deviceCounts[top[0]] : 1;
        var total = data.length;

        if (sorted.length > 15) {
            $('#stat_device_label').text('TOP 15 / ' + sorted.length + '개');
        } else {
            $('#stat_device_label').text(sorted.length + '개 장비');
        }

        var html = '';
        top.forEach(function(name, i) {
            var count = deviceCounts[name];
            var barW = Math.max(3, Math.round((count / max) * 100));
            var pct = total > 0 ? ((count / total) * 100).toFixed(1) : 0;

            html += '<div style="display:flex; align-items:center; gap:8px;">' +
                '<span style="min-width:14px; font-size:0.72rem; font-weight:600; color:#94a3b8; text-align:right;">' + (i + 1) + '</span>' +
                '<span style="min-width:130px; font-size:0.78rem; font-weight:600; color:' + (isDark ? '#e2e8f0' : '#1e293b') + '; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="' + name + '">' + name + '</span>' +
                '<div style="flex:1; height:8px; background:rgba(0,0,0,0.04); border-radius:4px; overflow:hidden;">' +
                '<div style="height:100%; width:' + barW + '%; background:rgba(99,102,241,0.45); border-radius:4px;"></div>' +
                '</div>' +
                '<span style="min-width:60px; text-align:right; font-size:0.75rem; font-weight:700; color:' + (isDark ? '#a5b4fc' : '#6366f1') + ';">' + count + ' <span style="font-weight:400;color:#94a3b8;font-size:0.6rem;">(' + pct + '%)</span></span>' +
                '</div>';
        });

        $('#deviceBarChart').html(html);
    }

    // 원격장비별 데이터 저장 (팝업용)
    var _remoteDeviceData = {};

    function renderRemoteDeviceList(data) {
        var isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
        // 원격 호스트네임별 집계
        var remoteMap = {};
        data.forEach(function(r) {
            var rh = r.remote_hostname || '';
            if (!rh) return;
            if (!remoteMap[rh]) remoteMap[rh] = { count: 0, localDevices: {}, connections: [] };
            remoteMap[rh].count++;
            if (r.hostname) remoteMap[rh].localDevices[r.hostname] = true;
            remoteMap[rh].connections.push({
                hostname: r.hostname || '-',
                device_ip: r.device_ip || '-',
                local_ifname: r.local_ifname || '-',
                local_ifdesc: r.local_ifdesc || '-',
                remote_port: r.remote_port || '-'
            });
        });

        _remoteDeviceData = remoteMap;

        var sorted = Object.keys(remoteMap).sort(function(a, b) {
            return remoteMap[b].count - remoteMap[a].count;
        });
        var top = sorted.slice(0, 15);
        var max = top.length > 0 ? remoteMap[top[0]].count : 1;

        if (sorted.length > 15) {
            $('#stat_remote_label').text('TOP 15 / ' + sorted.length + '개');
        } else {
            $('#stat_remote_label').text(sorted.length + '개 원격장비');
        }

        var html = '';
        top.forEach(function(name, i) {
            var info = remoteMap[name];
            var localCount = Object.keys(info.localDevices).length;
            var barW = Math.max(3, Math.round((info.count / max) * 100));

            html += '<div style="display:flex; align-items:center; gap:8px; cursor:pointer; padding:3px 0; border-radius:4px; transition:background 0.15s;" onmouseenter="this.style.background=\'' + (isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.02)') + '\'" onmouseleave="this.style.background=\'transparent\'" onclick="showRemoteDetail(\'' + name.replace(/'/g, "\\'") + '\')">' +
                '<span style="min-width:14px; font-size:0.72rem; font-weight:600; color:#94a3b8; text-align:right;">' + (i + 1) + '</span>' +
                '<span style="min-width:130px; font-size:0.78rem; font-weight:600; color:' + (isDark ? '#e2e8f0' : '#1e293b') + '; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="' + name + '">' + name + '</span>' +
                '<div style="flex:1; height:8px; background:rgba(0,0,0,0.04); border-radius:4px; overflow:hidden;">' +
                '<div style="height:100%; width:' + barW + '%; background:rgba(124,58,237,0.4); border-radius:4px;"></div>' +
                '</div>' +
                '<span style="min-width:80px; text-align:right; font-size:0.72rem;">' +
                '<span style="font-weight:700; color:' + (isDark ? '#c4b5fd' : '#7c3aed') + ';">' + info.count + '포트</span>' +
                ' <span style="color:#94a3b8;">· ' + localCount + '장비</span>' +
                '</span>' +
                '</div>';
        });

        $('#remoteDeviceList').html(html || '<div style="color:#94a3b8;font-size:0.8rem;text-align:center;padding:20px;">데이터 없음</div>');
    }

    // 원격장비 상세 팝업
    window.showRemoteDetail = function(remoteName) {
        var info = _remoteDeviceData[remoteName];
        if (!info) return;

        var conns = info.connections;
        // 로컬 장비별 그룹핑
        var grouped = {};
        conns.forEach(function(c) {
            if (!grouped[c.hostname]) grouped[c.hostname] = [];
            grouped[c.hostname].push(c);
        });

        var html = '<div style="max-height:500px; overflow-y:auto;">';

        // 요약 정보
        html += '<div style="display:flex; gap:20px; margin-bottom:16px; padding:12px 16px; background:#f8fafc; border-radius:8px;">';
        html += '<div><span style="font-size:0.72rem;color:#94a3b8;">총 연결 포트</span><div style="font-size:1.1rem;font-weight:700;color:#7c3aed;">' + conns.length + '</div></div>';
        html += '<div><span style="font-size:0.72rem;color:#94a3b8;">연결된 로컬 장비</span><div style="font-size:1.1rem;font-weight:700;color:#6366f1;">' + Object.keys(grouped).length + '</div></div>';
        html += '</div>';

        // 로컬 장비별 테이블
        var gKeys = Object.keys(grouped).sort();
        gKeys.forEach(function(hostname) {
            var items = grouped[hostname];
            html += '<div style="margin-bottom:14px;">';
            html += '<div style="font-size:0.82rem;font-weight:700;color:#1e293b;margin-bottom:6px;display:flex;align-items:center;gap:6px;">';
            html += '<span style="width:6px;height:6px;border-radius:50%;background:#6366f1;display:inline-block;"></span>';
            html += hostname + ' <span style="font-weight:400;color:#94a3b8;font-size:0.72rem;">(' + items.length + '포트)</span></div>';
            html += '<table class="table table-sm table-hover mb-0" style="font-size:0.8rem;">';
            html += '<thead><tr style="background:#f1f5f9;">';
            html += '<th class="py-1" style="color:#64748b;font-weight:600;">장비IP</th>';
            html += '<th class="py-1" style="color:#64748b;font-weight:600;">로컬 인터페이스</th>';
            html += '<th class="py-1" style="color:#64748b;font-weight:600;">인터페이스 설명</th>';
            html += '<th class="py-1" style="color:#64748b;font-weight:600;">원격 포트</th>';
            html += '</tr></thead><tbody>';
            items.forEach(function(c) {
                html += '<tr>';
                html += '<td class="py-1" style="color:#0ea5e9;font-weight:500;">' + c.device_ip + '</td>';
                html += '<td class="py-1"><span class="badge badge-phoenix badge-phoenix-primary" style="font-size:0.72rem;">' + c.local_ifname + '</span></td>';
                html += '<td class="py-1" style="color:#059669;font-weight:500;">' + c.local_ifdesc + '</td>';
                html += '<td class="py-1"><span class="badge badge-phoenix badge-phoenix-warning" style="font-size:0.72rem;">' + c.remote_port + '</span></td>';
                html += '</tr>';
            });
            html += '</tbody></table></div>';
        });

        html += '</div>';

        // 모달
        var modal = document.getElementById('lldpRemoteModal');
        if (!modal) {
            var md = document.createElement('div');
            md.innerHTML = '<div class="modal fade" id="lldpRemoteModal" tabindex="-1"><div class="modal-dialog modal-lg modal-dialog-centered"><div class="modal-content" style="border:none;border-radius:12px;overflow:hidden;">' +
                '<div class="modal-header py-2 px-3" style="background:#f8fafc;border-bottom:1px solid #e2e8f0;">' +
                '<h6 class="modal-title" id="lldpRemoteModalTitle" style="font-size:0.92rem;font-weight:700;"></h6>' +
                '<button type="button" class="btn-close" data-bs-dismiss="modal" style="font-size:0.6rem;"></button></div>' +
                '<div class="modal-body p-3" id="lldpRemoteModalBody"></div>' +
                '</div></div></div>';
            document.body.appendChild(md);
            modal = document.getElementById('lldpRemoteModal');
        }
        document.getElementById('lldpRemoteModalTitle').innerHTML = '<i class="fas fa-project-diagram me-2" style="color:#7c3aed;"></i>' + remoteName + ' 연결 상세';
        document.getElementById('lldpRemoteModalBody').innerHTML = html;
        new bootstrap.Modal(modal).show();
    };

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

        // (stat bar 스타일 - 호버 불필요)
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
