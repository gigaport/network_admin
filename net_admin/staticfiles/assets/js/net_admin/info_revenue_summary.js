(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
})((function () {
    'use strict';

    var revenueTable = null;
    var allDetails = [];
    var chartTop5 = null;
    var chartSubType = null;
    var chartTrend = null;
    var currentMonth = '';

    function formatPrice(val) {
        if (val === null || val === undefined || val === '') return '-';
        return Number(val).toLocaleString() + '원';
    }

    function updateSummary(summary) {
        var memberSet = {};
        var subTypeSet = {};
        var mkdTotal = 0, mkdCount = 0;
        summary.forEach(function(r) {
            memberSet[r.member_code] = true;
            mkdTotal += Number(r.mkd_total) || 0;
            mkdCount += Number(r.mkd_count) || 0;
            var st = r.subscription_type || '미분류';
            subTypeSet[st] = true;
        });
        $('#stat_members').text(Object.keys(memberSet).length.toLocaleString());
        $('#stat_mkd_count').text(mkdCount.toLocaleString() + '건');
        $('#stat_mkd_total').text(mkdTotal.toLocaleString() + '원');
        $('#stat_sub_types').text(Object.keys(subTypeSet).length + '개');

        renderCharts(summary, mkdTotal);
    }

    function renderCharts(summary, mkdTotal) {
        if (chartTop5) chartTop5.destroy();
        if (chartSubType) chartSubType.destroy();

        var isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
        var textColor = isDark ? '#cbd5e1' : '#475569';
        var gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';

        // 1. 매출 TOP 5 (가로 막대)
        var memberMap = {};
        summary.forEach(function(r) {
            var mc = r.member_code;
            if (!memberMap[mc]) memberMap[mc] = { name: r.company_name || mc, total: 0 };
            memberMap[mc].total += Number(r.mkd_total) || 0;
        });
        var members = Object.values(memberMap);
        members.sort(function(a, b) { return b.total - a.total; });
        var top5 = members.slice(0, 5);

        chartTop5 = new Chart(document.getElementById('chartTop5').getContext('2d'), {
            type: 'bar',
            data: {
                labels: top5.map(function(r) { return r.name; }),
                datasets: [{
                    label: 'MKD 매출',
                    data: top5.map(function(r) { return r.total; }),
                    backgroundColor: 'rgba(16, 185, 129, 0.8)',
                    borderRadius: 4,
                    barPercentage: 0.6
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) { return 'MKD: ' + Number(ctx.raw).toLocaleString() + '원'; }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: gridColor },
                        ticks: { color: textColor, font: { size: 10 }, callback: function(v) { return (v / 10000).toLocaleString() + '만'; } }
                    },
                    y: {
                        grid: { display: false },
                        ticks: { color: textColor, font: { size: 11 } }
                    }
                }
            }
        });

        // 2. 가입유형별 매출 (도넛)
        var subTypeMap = {};
        summary.forEach(function(r) {
            var st = r.subscription_type || '미분류';
            if (!subTypeMap[st]) subTypeMap[st] = 0;
            subTypeMap[st] += Number(r.mkd_total) || 0;
        });
        var subTypeLabels = Object.keys(subTypeMap);
        var subTypeData = subTypeLabels.map(function(k) { return subTypeMap[k]; });
        var subTypeColors = [
            'rgba(16, 185, 129, 0.85)', 'rgba(99, 102, 241, 0.85)',
            'rgba(236, 72, 153, 0.85)', 'rgba(14, 165, 233, 0.85)',
            'rgba(245, 158, 11, 0.85)', 'rgba(139, 92, 246, 0.85)'
        ];

        chartSubType = new Chart(document.getElementById('chartSubType').getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: subTypeLabels,
                datasets: [{
                    data: subTypeData,
                    backgroundColor: subTypeColors.slice(0, subTypeLabels.length),
                    borderWidth: 2,
                    borderColor: isDark ? '#1e293b' : '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '62%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: textColor, font: { size: 11 }, padding: 12, boxWidth: 12 }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                var total = subTypeData.reduce(function(a, b) { return a + b; }, 0);
                                var pct = total > 0 ? ((ctx.raw / total) * 100).toFixed(1) : 0;
                                return ctx.label + ': ' + Number(ctx.raw).toLocaleString() + '원 (' + pct + '%)';
                            }
                        }
                    }
                }
            }
        });
    }

    function showDetailModal(memberCode, companyName, summaryRow) {
        var details = allDetails.filter(function(d) { return d.member_code === memberCode; });

        $('#detailSubtitle').text(companyName + ' (' + memberCode + ')');
        $('#modal_mkd_count').text((summaryRow.mkd_count || 0) + '건');
        $('#modal_mkd_total').text(formatPrice(summaryRow.mkd_total));

        var html = '';
        details.forEach(function(d) {
            html += '<tr>' +
                '<td class="text-center py-2">' + (d.datacenter_code || '-') + '</td>' +
                '<td class="text-center py-2"><span class="badge badge-phoenix badge-phoenix-success">MKD</span></td>' +
                '<td class="text-center py-2">' + (d.product || '-') + '</td>' +
                '<td class="text-center py-2">' + (d.bandwidth || '-') + '</td>' +
                '<td class="text-center py-2">' + (d.additional_circuit ? 'Y' : 'N') + '</td>' +
                '<td class="text-center py-2">' + (d.phase || '-') + '</td>' +
                '<td class="text-center py-2">' + (d.provider || '-') + '</td>' +
                '<td class="text-center py-2">' + (d.circuit_id || '-') + '</td>' +
                '<td class="text-center py-2">' + (d.fee_description || '-') + '</td>' +
                '<td class="text-center py-2 fw-bold">' + formatPrice(d.fee_price) + '</td>' +
                '</tr>';
        });
        if (!html) {
            html = '<tr><td colspan="10" class="text-center py-3 text-muted">상세 데이터가 없습니다.</td></tr>';
        }
        $('#detailTableBody').html(html);
        new bootstrap.Modal(document.getElementById('detailModal')).show();
    }

    function showAlert(message, type) {
        type = type || 'info';
        var alertHtml = '<div class="alert alert-' + type + ' alert-dismissible fade show position-fixed" role="alert" ' +
            'style="top: 80px; right: 20px; z-index: 9999; min-width: 300px; box-shadow: 0 4px 15px rgba(0,0,0,0.15); border-radius: 10px;">' +
            message +
            '<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>';
        $('body').append(alertHtml);
        setTimeout(function() { $('.alert').fadeOut(400, function() { $(this).remove(); }); }, 3000);
    }

    var initTable = function() {
        revenueTable = $('#revenueTable').DataTable({
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
                {
                    extend: 'excel',
                    text: '<i class="fa-solid fa-file-excel me-2"></i>Excel',
                    className: 'btn btn-success btn-sm',
                    title: '정보이용사 매출내역_' + new Date().toISOString().slice(0,10),
                    exportOptions: { columns: ':visible', modifier: { page: 'all' } }
                },
                {
                    extend: 'csv',
                    text: '<i class="fa-solid fa-file-csv me-2"></i>CSV',
                    className: 'btn btn-info btn-sm',
                    title: '정보이용사 매출내역_' + new Date().toISOString().slice(0,10),
                    exportOptions: { columns: ':visible', modifier: { page: 'all' } }
                }
            ],
            ajax: {
                url: '/info_revenue_summary/get_info_revenue_summary',
                type: 'GET',
                dataSrc: function(json) {
                    if (json.success) {
                        allDetails = json.details || [];
                        updateSummary(json.summary);
                        return json.summary;
                    } else {
                        showAlert('데이터 로드 실패: ' + json.error, 'danger');
                        return [];
                    }
                },
                error: function(xhr, error, thrown) {
                    console.error('AJAX Error:', error, thrown);
                    showAlert('데이터 로드 중 오류가 발생했습니다.', 'danger');
                }
            },
            columns: [
                { data: 'member_number' },
                { data: 'member_code' },
                { data: 'company_name' },
                { data: 'subscription_type' },
                { data: 'is_pb' },
                { data: 'phase' },
                { data: 'mkd_count' },
                { data: 'mkd_total' }
            ],
            columnDefs: [
                {
                    targets: 0,
                    width: '8%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-info">' + data + '</span>';
                    }
                },
                {
                    targets: 1,
                    width: '8%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-primary">' + data + '</span>';
                    }
                },
                {
                    targets: 2,
                    width: '14%',
                    className: 'text-center py-2 align-middle'
                },
                {
                    targets: 3,
                    width: '8%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-secondary">' + data + '</span>';
                    }
                },
                {
                    targets: 4,
                    width: '6%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (data === true || data === 'true' || data === 't') {
                            return '<span class="badge badge-phoenix badge-phoenix-danger">PB</span>';
                        }
                        return '-';
                    }
                },
                {
                    targets: 5,
                    width: '6%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-success">' + data + '</span>';
                    }
                },
                {
                    targets: 6,
                    width: '8%',
                    className: 'text-center py-2 align-middle fw-bold',
                    render: function(data) {
                        return (data || 0).toLocaleString();
                    }
                },
                {
                    targets: 7,
                    width: '12%',
                    className: 'text-end py-2 align-middle',
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return '<span style="color: #059669; font-weight: 700; font-size: 0.8rem;">' + Number(data).toLocaleString() + '원</span>';
                    }
                }
            ],
            drawCallback: function(settings) {
                var overlay = document.getElementById('pageLoadingOverlay');
                if (overlay) {
                    overlay.style.opacity = '0';
                    setTimeout(function() { overlay.style.display = 'none'; }, 400);
                }

                var api = this.api();
                var data = api.rows({ page: 'current' }).data();
                if (!data.length) return;

                var totalCount = 0, grandTotal = 0;
                data.each(function(row) {
                    totalCount += Number(row.mkd_count) || 0;
                    grandTotal += Number(row.mkd_total) || 0;
                });

                $('#revenueTable tbody tr.grand-total-row').remove();
                var grandRow = '<tr class="grand-total-row" style="background: #1e293b !important; pointer-events: none;">' +
                    '<td colspan="6" class="text-start py-2 align-middle" style="font-size: 0.85rem; font-weight: 800; color: #fff; padding-left: 14px !important;">' +
                    '<i class="fas fa-coins me-1" style="font-size: 0.7rem; opacity: 0.8;"></i>전체 합계 (' + data.length + '개 정보이용사)</td>' +
                    '<td class="text-center py-2 align-middle" style="font-weight: 700; color: #93c5fd;">' + totalCount.toLocaleString() + '</td>' +
                    '<td class="text-end py-2 align-middle" style="font-size: 0.9rem; font-weight: 800; color: #fbbf24; padding-right: 12px !important;">' + grandTotal.toLocaleString() + '원</td>' +
                    '</tr>';
                $('#revenueTable tbody').append(grandRow);
            },
            initComplete: function() {
                this.api().columns().every(function() {
                    var column = this;
                    var header = $(column.footer());
                    var title = header.text().trim();
                    header.html('<input type="text" class="form-control form-control-sm text-center" placeholder="' + title + '" style="font-size:0.65rem; min-width:50px;" />');
                    $('input', header).on('keyup change', function() {
                        if (column.search() !== this.value) {
                            column.search(this.value).draw();
                        }
                    }).on('click', function(e) { e.stopPropagation(); });
                });
            }
        });

        $('#revenueTable tbody').on('click', 'tr:not(.grand-total-row)', function() {
            var data = revenueTable.row(this).data();
            if (data) showDetailModal(data.member_code, data.company_name, data);
        });
        $('#revenueTable tbody').on('mouseenter', 'tr', function() { $(this).css('cursor', 'pointer'); });
    };

    function initMonthFilter() {
        var sel = document.getElementById('monthFilter');
        var now = new Date();
        for (var i = 0; i < 12; i++) {
            var d = new Date(now.getFullYear(), now.getMonth() - i, 1);
            var ym = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
            var label = d.getFullYear() + '년 ' + (d.getMonth() + 1) + '월';
            var opt = document.createElement('option');
            opt.value = ym;
            opt.textContent = label;
            sel.appendChild(opt);
        }
        sel.addEventListener('change', onMonthChange);
    }

    function onMonthChange() {
        var ym = document.getElementById('monthFilter').value;
        currentMonth = ym;
        document.getElementById('btnDownloadPdf').disabled = !ym;
        if (!ym) {
            revenueTable.ajax.url('/info_revenue_summary/get_info_revenue_summary').load();
            loadTrendOnly();
        } else {
            loadMonthlyData(ym);
        }
    }

    function loadTrendOnly() {
        var now = new Date();
        var ym = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
        $.ajax({
            url: '/info_revenue_summary/get_info_revenue_monthly',
            data: { year_month: ym },
            type: 'GET',
            success: function(json) {
                if (json.success && json.trend) renderTrendChart(json.trend);
            }
        });
    }

    function loadMonthlyData(yearMonth) {
        var overlay = document.getElementById('pageLoadingOverlay');
        if (overlay) { overlay.style.display = 'flex'; overlay.style.opacity = '1'; }

        $.ajax({
            url: '/info_revenue_summary/get_info_revenue_monthly',
            data: { year_month: yearMonth },
            type: 'GET',
            success: function(json) {
                if (json.success) {
                    allDetails = json.details || [];
                    updateSummary(json.summary);
                    renderTrendChart(json.trend);
                    revenueTable.clear();
                    revenueTable.rows.add(json.summary);
                    revenueTable.draw();
                } else {
                    showAlert('월별 데이터 로드 실패: ' + json.error, 'danger');
                }
                if (overlay) { overlay.style.opacity = '0'; setTimeout(function() { overlay.style.display = 'none'; }, 400); }
            },
            error: function(xhr, error) {
                console.error('Monthly AJAX Error:', error);
                showAlert('월별 데이터 로드 중 오류가 발생했습니다.', 'danger');
                if (overlay) { overlay.style.opacity = '0'; setTimeout(function() { overlay.style.display = 'none'; }, 400); }
            }
        });
    }

    function renderTrendChart(trend) {
        if (chartTrend) chartTrend.destroy();
        if (!trend || !trend.length) return;

        var isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
        var textColor = isDark ? '#cbd5e1' : '#475569';
        var gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';

        var labels = trend.map(function(t) { return t.month; });
        var mkdData = trend.map(function(t) { return Number(t.mkd_total) || 0; });

        chartTrend = new Chart(document.getElementById('chartTrend').getContext('2d'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'MKD 매출',
                    data: mkdData,
                    borderColor: 'rgba(16, 185, 129, 0.9)',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { color: textColor, font: { size: 11 }, boxWidth: 14, padding: 15 }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) { return ctx.dataset.label + ': ' + Number(ctx.raw).toLocaleString() + '원'; }
                        }
                    }
                },
                scales: {
                    x: { grid: { color: gridColor }, ticks: { color: textColor, font: { size: 10 } } },
                    y: {
                        grid: { color: gridColor },
                        ticks: { color: textColor, font: { size: 10 }, callback: function(v) { return (v / 10000).toLocaleString() + '만'; } }
                    }
                }
            }
        });
    }

    window.downloadPdf = function() {
        if (!currentMonth) {
            showAlert('PDF 다운로드는 월을 선택한 후 가능합니다.', 'warning');
            return;
        }
        showAlert(currentMonth + ' 보고서 PDF를 생성 중...', 'info');
        window.open('/info_revenue_summary/download_info_revenue_pdf?year_month=' + currentMonth, '_blank');
    };

    window.refreshTable = function() {
        if (revenueTable) {
            var ym = document.getElementById('monthFilter').value;
            if (ym) {
                loadMonthlyData(ym);
            } else {
                revenueTable.ajax.url('/info_revenue_summary/get_info_revenue_summary').load();
            }
            showAlert('데이터를 새로고침했습니다.', 'success');
        }
    };

    document.addEventListener('DOMContentLoaded', function() {
        initMonthFilter();
        initTable();
        loadTrendOnly();
    });

}));
