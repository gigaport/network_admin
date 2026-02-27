(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
})((function () {
    'use strict';

    var vipTable = null;

    function cleanHostname(name) {
        return (name || '').replace(/\.nextrade\.co\.kr$/i, '');
    }

    function updateSummary(data) {
        var devices = {};
        var vlans = {};
        var activeCount = 0;

        data.forEach(function(r) {
            if (r.device_id) devices[r.device_id] = true;
            if (r.vlan) vlans[r.vlan] = true;
            if (r.main && r.main.toLowerCase() === 'y') activeCount++;
        });

        var activeRate = data.length > 0 ? ((activeCount / data.length) * 100).toFixed(1) + '%' : '0%';

        $('#stat_total').text(data.length.toLocaleString());
        $('#stat_devices').text(Object.keys(devices).length);
        $('#stat_vlans').text(Object.keys(vlans).length);
        $('#stat_active').text(activeRate);

        renderDeviceBarChart(data);
        renderMismatchList(data);
    }

    function renderMismatchList(data) {
        var mismatches = [];
        data.forEach(function(r) {
            var ips = r.ip || [];
            var hostname = r.hostname || '';
            if (typeof ips === 'string') ips = [ips];

            ips.forEach(function(ip) {
                var clean = ip.split('/')[0].trim();
                var parts = clean.split('.');
                if (parts.length === 4 && parts[3] === '1') {
                    if (!cleanHostname(hostname).endsWith('_01')) {
                        mismatches.push({
                            ip: clean,
                            hostname: hostname,
                            device_ip: r.device_ip || '',
                            vlan: r.vlan || ''
                        });
                    }
                }
            });
        });

        $('#stat_mismatch_count').text(mismatches.length + '건');

        if (mismatches.length === 0) {
            $('#mismatchList').html('<div style="font-size: 0.7rem; color: rgba(255,255,255,0.6);"><i class="fas fa-check-circle me-1" style="color: #4ade80;"></i>불일치 항목 없음</div>');
            return;
        }

        var html = '';
        mismatches.forEach(function(m) {
            html += '<div style="display: flex; align-items: center; padding: 5px 8px; margin-bottom: 4px; border-radius: 6px; background: rgba(255,255,255,0.08);">' +
                '<div style="flex: 1; min-width: 0;">' +
                '<div style="font-size: 0.7rem; color: #fca5a5; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">' +
                '<span style="color: #fbbf24;">' + m.ip + '</span>' +
                ' <i class="fas fa-arrow-right" style="font-size: 0.5rem; color: rgba(255,255,255,0.4); margin: 0 4px;"></i> ' +
                '<span style="color: #fca5a5;">' + cleanHostname(m.hostname) + '</span>' +
                '</div>' +
                '<div style="font-size: 0.55rem; color: rgba(255,255,255,0.4);">' +
                '접속IP: ' + m.device_ip + ' / VLAN: ' + m.vlan +
                '</div>' +
                '</div>' +
                '</div>';
        });
        $('#mismatchList').html(html);
    }

    function renderDeviceBarChart(data) {
        var deviceCounts = {};
        data.forEach(function(r) {
            var name = cleanHostname(r.hostname) || r.device_ip || '-';
            deviceCounts[name] = (deviceCounts[name] || 0) + 1;
        });

        var sorted = Object.keys(deviceCounts).sort(function(a, b) {
            return deviceCounts[b] - deviceCounts[a];
        });

        // VIP 3건 이상만 표시
        var filtered = sorted.filter(function(n) { return deviceCounts[n] >= 3; });
        var top = filtered.length > 0 ? filtered : sorted.slice(0, 10);
        var max = top.length > 0 ? deviceCounts[top[0]] : 1;
        var colors = ['#6366f1', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#06b6d4'];

        var html = '';
        top.forEach(function(name, i) {
            var count = deviceCounts[name];
            var widthPct = Math.max(8, Math.round((count / max) * 100));
            var color = colors[i % colors.length];

            html += '<div style="display: flex; align-items: center; margin-bottom: 5px;">' +
                '<div style="width: 140px; min-width: 140px; font-size: 0.65rem; color: rgba(255,255,255,0.7); text-align: right; padding-right: 10px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="' + name + '">' + name + '</div>' +
                '<div style="flex: 1; height: 18px; background: rgba(255,255,255,0.06); border-radius: 4px; overflow: hidden;">' +
                '<div style="width: ' + widthPct + '%; height: 100%; background: ' + color + '; border-radius: 4px; display: flex; align-items: center; justify-content: flex-end; padding-right: 6px; transition: width 0.4s ease;">' +
                '<span style="font-size: 0.6rem; font-weight: 700; color: #fff;">' + count + '</span>' +
                '</div>' +
                '</div>' +
                '</div>';
        });

        var otherCount = sorted.length - top.length;
        if (otherCount > 0) {
            $('#stat_device_label').text(top.length + '개 표시 / ' + sorted.length + '개 장비');
        } else {
            $('#stat_device_label').text(sorted.length + '개 장비');
        }

        $('#deviceBarChart').html(html);
    }

    var initTable = function() {
        var data_back = document.getElementById("back_data");
        var currentPath = data_back ? data_back.dataset.submenu : 'interface_vip';

        vipTable = $('#vip_table').DataTable({
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
                paginate: { first: "처음", last: "마지막", next: "다음", previous: "이전" },
                emptyTable: "검색 결과가 없습니다",
                zeroRecords: "검색 결과가 없습니다",
                loadingRecords: " "
            },
            dom: '<"row align-items-center"<"col-sm-12 col-md-3"l><"col-sm-12 col-md-9 d-flex justify-content-end align-items-center gap-2"fB>>' +
                 '<"row"<"col-sm-12"tr>>' +
                 '<"row"<"col-sm-12 col-md-5"i><"col-sm-12 col-md-7"p>>',
            buttons: [
                { extend: 'excel', text: '<i class="fa-solid fa-file-excel me-2"></i>Excel', className: 'btn btn-success btn-sm', title: 'VIP_정보_' + new Date().toISOString().slice(0, 10), exportOptions: { columns: ':visible', modifier: { page: 'all' } } },
                { extend: 'csv', text: '<i class="fa-solid fa-file-csv me-2"></i>CSV', className: 'btn btn-info btn-sm', title: 'VIP_정보_' + new Date().toISOString().slice(0, 10), exportOptions: { columns: ':visible', modifier: { page: 'all' } } },
                { extend: 'copy', text: '<i class="fa-solid fa-copy me-2"></i>복사', className: 'btn btn-secondary btn-sm', exportOptions: { columns: ':visible', modifier: { page: 'all' } } }
            ],
            ajax: {
                url: '/information/init',
                type: 'GET',
                data: { sub_menu: currentPath },
                dataSrc: function(json) {
                    if (json.data) { updateSummary(json.data); return json.data; }
                    return [];
                },
                error: function(xhr, error, thrown) {
                    console.error('AJAX Error:', error, thrown);
                    showAlert('데이터 로드 중 오류가 발생했습니다.', 'danger');
                }
            },
            columns: [
                { data: 'device_id' }, { data: 'device_ip' }, { data: 'hostname' },
                { data: 'vlan' }, { data: 'ip' }, { data: 'main' }
            ],
            columnDefs: [
                { targets: 0, width: '5%', className: 'text-center py-2 align-middle', render: function(data, type) { if (type === 'export') return data; if (!data && data !== 0) return '-'; return '<span class="badge badge-phoenix badge-phoenix-secondary">' + data + '</span>'; } },
                { targets: 1, width: '13%', className: 'text-center py-2 align-middle', render: function(data, type) { if (type === 'export') return data; if (!data) return '-'; return '<span style="color: #0ea5e9; font-weight: 500;">' + data + '</span>'; } },
                { targets: 2, width: '18%', className: 'text-center py-2 align-middle', render: function(data, type) { if (type === 'export') return data; if (!data) return '-'; return '<span class="fw-bold" style="color: #1e293b;">' + cleanHostname(data) + '</span>'; } },
                { targets: 3, width: '10%', className: 'text-center py-2 align-middle', render: function(data, type) { if (type === 'export') return data; if (!data) return '-'; return '<span class="badge badge-phoenix badge-phoenix-info">' + data + '</span>'; } },
                { targets: 4, width: '40%', className: 'text-start py-2 align-middle', render: function(data, type) { if (type === 'export') return data; if (!data) return '<span style="color: #cbd5e1;">-</span>'; return '<span style="color: #059669; font-weight: 600;">' + data + '</span>'; } },
                { targets: 5, width: '10%', className: 'text-center py-2 align-middle', render: function(data, type) { if (type === 'export') return data; if (data && data.toLowerCase() === 'y') return '<span class="badge badge-phoenix badge-phoenix-success">Active</span>'; return '<span class="badge badge-phoenix badge-phoenix-secondary">Standby</span>'; } }
            ],
            initComplete: function() {
                var overlay = document.getElementById('pageLoadingOverlay');
                if (overlay) { overlay.style.opacity = '0'; setTimeout(function() { overlay.remove(); }, 400); }

                $('#vip_table tfoot th').each(function() {
                    var title = $(this).text();
                    $(this).css({'font-size': '0.7rem', 'white-space': 'nowrap'});
                    $(this).html('<input type="text" class="form-control form-control-sm" placeholder="' + title + ' 검색" style="font-size:0.65rem; padding:2px 4px;" />');
                });
                vipTable.columns().every(function() {
                    var that = this;
                    $('input', this.footer()).on('keyup change', function() {
                        if (that.search() !== this.value) that.search(this.value).draw();
                    });
                });
            }
        });

        $('#summaryCards > div > div').css('transition', 'transform 0.25s ease, box-shadow 0.25s ease');
        $('#summaryCards > div > div').on('mouseenter', function() {
            $(this).css({ 'transform': 'translateY(-4px) scale(1.02)', 'box-shadow': '0 8px 25px rgba(0,0,0,0.2)' });
        }).on('mouseleave', function() {
            $(this).css({ 'transform': 'translateY(0) scale(1)', 'box-shadow': '' });
        });
    };

    window.refreshTable = function() {
        var spinner = $('<div class="position-fixed top-50 start-50 translate-middle" style="z-index: 10000;"><div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;"><span class="visually-hidden">Loading...</span></div></div>');
        $('body').append(spinner);
        $('#vip_table tfoot input').val('');
        if (vipTable) { vipTable.columns().search(''); vipTable.ajax.reload(function() { spinner.remove(); }, false); }
        else { spinner.remove(); }
    };

    function showAlert(message, type) {
        var icons = { success: 'fa-check-circle', danger: 'fa-exclamation-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle' };
        var colors = { success: '#10b981', danger: '#ef4444', warning: '#f59e0b', info: '#3b82f6' };
        var titles = { success: '완료', danger: '오류', warning: '알림', info: '안내' };
        if (!$('#toastContainer').length) { $('body').append('<div id="toastContainer" class="toast-container position-fixed top-0 end-0 p-3" style="z-index: 9999;"></div>'); }
        var toastId = 'toast_' + Date.now();
        var toastHtml = '<div id="' + toastId + '" class="toast align-items-center border-0 shadow-lg" role="alert" data-bs-delay="3000" style="border-radius: 10px; overflow: hidden; border-left: 4px solid ' + (colors[type] || colors.info) + ' !important;"><div class="toast-header border-0" style="padding: 10px 14px;"><i class="fas ' + (icons[type] || icons.info) + ' me-2" style="color: ' + (colors[type] || colors.info) + '; font-size: 0.9rem;"></i><strong class="me-auto" style="font-size: 0.8rem; color: #1e293b;">' + (titles[type] || titles.info) + '</strong><button type="button" class="btn-close" data-bs-dismiss="toast" style="font-size: 0.55rem;"></button></div><div class="toast-body" style="padding: 0 14px 12px; font-size: 0.78rem; color: #475569;">' + message + '</div></div>';
        $('#toastContainer').append(toastHtml);
        var toastEl = document.getElementById(toastId);
        var toast = new bootstrap.Toast(toastEl);
        toast.show();
        toastEl.addEventListener('hidden.bs.toast', function() { $(toastEl).remove(); });
    }

    $(document).ready(function() { initTable(); });
}));
