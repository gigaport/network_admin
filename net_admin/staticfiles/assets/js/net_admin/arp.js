(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
})((function () {
    'use strict';

    var arpTable = null;

    function updateFreshness(meta) {
        var el = document.getElementById('freshnessIndicator');
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
        el.style.cssText = 'display:inline-block; font-size:0.7rem; font-weight:500; padding:3px 10px; border-radius:6px; color:#fff; background:' + bgColor + ';';

        if (collectedAt) {
            var diffMin2 = Math.round((new Date() - new Date(collectedAt.replace(' ', 'T'))) / 60000);
            if (diffMin2 > 5 && status !== 'failed') {
                el.style.background = '#d97706';
                el.innerHTML = '<i class="fas fa-clock me-1"></i>수집: ' + ageText + ' (' + successDevices + '/' + totalDevices + '대)';
            }
        }
    }

    function updateSummary(data) {
        var devices = {};
        var uniqueIps = {};
        var uniqueMacs = {};

        data.forEach(function(r) {
            if (r.device_name) devices[r.device_name] = true;
            if (r.arp_ip) uniqueIps[r.arp_ip] = true;
            if (r.link_layer_address) uniqueMacs[r.link_layer_address] = true;
        });

        $('#stat_total').text(data.length.toLocaleString());
        $('#stat_devices').text(Object.keys(devices).length);
        $('#stat_unique_ip').text(Object.keys(uniqueIps).length.toLocaleString());
        $('#stat_unique_mac').text(Object.keys(uniqueMacs).length.toLocaleString());

        renderDeviceBarChart(data);
    }

    function renderDeviceBarChart(data) {
        var deviceCounts = {};
        data.forEach(function(r) {
            var name = r.device_name || '-';
            deviceCounts[name] = (deviceCounts[name] || 0) + 1;
        });

        var sorted = Object.keys(deviceCounts).sort(function(a, b) { return deviceCounts[b] - deviceCounts[a]; });
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

        if (sorted.length > 20) { $('#stat_device_label').text('TOP 20 / ' + sorted.length + '개'); }
        else { $('#stat_device_label').text(sorted.length + '개 장비'); }
        $('#deviceBarChart').html(html);
    }

    var initTable = function() {
        var data_back = document.getElementById("back_data");
        var currentPath = data_back ? data_back.dataset.submenu : 'pr_info_arp';
        var pageTitle = currentPath.includes('ts_') ? '테스트_ARP_' : '본가동_ARP_';

        arpTable = $('#data_table').DataTable({
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
                { extend: 'excel', text: '<i class="fa-solid fa-file-excel me-2"></i>Excel', className: 'btn btn-success btn-sm', title: pageTitle + new Date().toISOString().slice(0, 10), exportOptions: { columns: ':visible', modifier: { page: 'all' } } },
                { extend: 'csv', text: '<i class="fa-solid fa-file-csv me-2"></i>CSV', className: 'btn btn-info btn-sm', title: pageTitle + new Date().toISOString().slice(0, 10), exportOptions: { columns: ':visible', modifier: { page: 'all' } } },
                { extend: 'copy', text: '<i class="fa-solid fa-copy me-2"></i>복사', className: 'btn btn-secondary btn-sm', exportOptions: { columns: ':visible', modifier: { page: 'all' } } }
            ],
            ajax: {
                url: '/information/init',
                type: 'GET',
                data: { sub_menu: currentPath },
                dataSrc: function(json) {
                    if (json._meta) { updateFreshness(json._meta); }
                    if (json.data) { updateSummary(json.data); return json.data; }
                    return [];
                },
                error: function(xhr, error, thrown) {
                    console.error('AJAX Error:', error, thrown);
                    showAlert('데이터 로드 중 오류가 발생했습니다.', 'danger');
                }
            },
            columns: [
                { data: 'device_name' }, { data: 'device_ip' }, { data: 'device_os' },
                { data: 'interface' }, { data: 'arp_ip' }, { data: 'link_layer_address' }, { data: 'origin' }
            ],
            columnDefs: [
                { targets: 0, width: '15%', className: 'text-center py-2 align-middle', render: function(data, type) { if (type === 'export') return data; if (!data) return '-'; return '<span class="fw-bold" style="color: #1e293b;">' + data + '</span>'; } },
                { targets: 1, width: '10%', className: 'text-center py-2 align-middle', render: function(data, type) { if (type === 'export') return data; if (!data) return '-'; return '<span style="color: #0ea5e9; font-weight: 500;">' + data + '</span>'; } },
                { targets: 2, width: '10%', className: 'text-center py-2 align-middle', render: function(data, type) { if (type === 'export') return data; if (!data) return '-'; return '<span class="badge badge-phoenix badge-phoenix-secondary">' + data + '</span>'; } },
                { targets: 3, width: '15%', className: 'text-center py-2 align-middle', render: function(data, type) { if (type === 'export') return data; if (!data) return '-'; return '<span class="fw-bold" style="color: #059669;">' + data + '</span>'; } },
                { targets: 4, width: '20%', className: 'text-center py-2 align-middle', render: function(data, type) { if (type === 'export') return data; if (!data) return '-'; return '<span class="fw-semibold" style="color: #7c3aed;">' + data + '</span>'; } },
                { targets: 5, width: '20%', className: 'text-center py-2 align-middle', render: function(data, type) { if (type === 'export') return data; if (!data) return '-'; return '<code style="color: #0ea5e9;">' + data + '</code>'; } },
                { targets: 6, width: '10%', className: 'text-center py-2 align-middle', render: function(data, type) {
                    if (type === 'export') return data; if (!data) return '-';
                    var origin = (data || '').toLowerCase();
                    if (origin === 'dynamic') return '<span class="badge badge-phoenix badge-phoenix-info">dynamic</span>';
                    if (origin === 'static') return '<span class="badge badge-phoenix badge-phoenix-success">static</span>';
                    return '<span class="badge badge-phoenix badge-phoenix-secondary">' + data + '</span>';
                } }
            ],
            initComplete: function() {
                var overlay = document.getElementById('pageLoadingOverlay');
                if (overlay) { overlay.style.opacity = '0'; setTimeout(function() { overlay.remove(); }, 400); }

                $('#data_table tfoot th').each(function() {
                    var title = $(this).text();
                    $(this).css({'font-size': '0.7rem', 'white-space': 'nowrap'});
                    $(this).html('<input type="text" class="form-control form-control-sm" placeholder="' + title + ' 검색" style="font-size:0.65rem; padding:2px 4px;" />');
                });
                arpTable.columns().every(function() {
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
        $('#data_table tfoot input').val('');
        if (arpTable) { arpTable.columns().search(''); arpTable.ajax.reload(function() { spinner.remove(); }, false); }
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
