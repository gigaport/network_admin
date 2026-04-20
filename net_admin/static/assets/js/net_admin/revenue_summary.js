(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
})((function () {
    'use strict';
    function _isDark() { return document.documentElement.getAttribute('data-bs-theme') === 'dark'; }
    function T(l, d) { return _isDark() ? d : l; }

    var revenueTable = null;
    var allDetails = [];
    var chartTop5 = null;
    var chartOrdMpr = null;
    var chartSubType = null;
    var chartTrend = null;
    var currentMonth = ''; // '' = 전체(누적)

    // 금액 포맷
    function formatPrice(val) {
        if (val === null || val === undefined || val === '') return '-';
        return Number(val).toLocaleString() + '원';
    }

    // 요약 통계 업데이트
    var _savedTrend = null;
    var _pendingRevSummary = null;

    function fmtCompact(v) {
        if (v === 0) return '0';
        var s = v >= 0 ? '+' : '';
        if (Math.abs(v) >= 100000000) return s + (v / 100000000).toFixed(1) + '억';
        if (Math.abs(v) >= 10000) return s + (v / 10000).toFixed(0) + '만';
        return s + v.toLocaleString();
    }

    function updateSummary(summary) {
        if (!_savedTrend) {
            _pendingRevSummary = summary;
        }

        var memberSet = {};
        summary.forEach(function(r) { memberSet[r.member_code] = true; });
        var totalMembers = Object.keys(memberSet).length;
        var grandTotal = 0, ordTotal = 0, mprTotal = 0;
        summary.forEach(function(r) {
            grandTotal += Number(r.grand_total) || 0;
            ordTotal += Number(r.ord_total) || 0;
            mprTotal += Number(r.mpr_total) || 0;
        });
        $('#stat_members').text(totalMembers.toLocaleString());

        // 작년 12월 대비 증감 계산
        var baseLine = null;
        if (_savedTrend && _savedTrend.length > 0) {
            var lastYear = String(Number(_savedTrend[_savedTrend.length - 1].month.substring(0, 4)) - 1);
            for (var ti = 0; ti < _savedTrend.length; ti++) {
                if (_savedTrend[ti].month === lastYear + '-12') {
                    baseLine = _savedTrend[ti];
                    break;
                }
            }
        }

        if (baseLine) {
            var bGrand = Number(baseLine.grand_total) || 0;
            var bOrd = Number(baseLine.ord_total) || 0;
            var bMpr = Number(baseLine.mpr_total) || 0;
            var gDiff = grandTotal - bGrand, oDiff = ordTotal - bOrd, mDiff = mprTotal - bMpr;
            var gPct = bGrand > 0 ? ((gDiff / bGrand) * 100).toFixed(1) : '0.0';
            var oPct = bOrd > 0 ? ((oDiff / bOrd) * 100).toFixed(1) : '0.0';
            var mPct = bMpr > 0 ? ((mDiff / bMpr) * 100).toFixed(1) : '0.0';

            var diffColor = function(v) { return v >= 0 ? '#dc2626' : '#2563eb'; };
            $('#stat_grand_total').html(grandTotal.toLocaleString() + '원 <span style="font-size:0.72rem;color:' + diffColor(gDiff) + ';font-weight:600;">(' + fmtCompact(gDiff) + ', ' + (gDiff >= 0 ? '+' : '') + gPct + '%)</span>');
            $('#stat_ord_total').html(ordTotal.toLocaleString() + '원 <span style="font-size:0.72rem;color:' + diffColor(oDiff) + ';font-weight:600;">(' + fmtCompact(oDiff) + ', ' + (oDiff >= 0 ? '+' : '') + oPct + '%)</span>');
            $('#stat_mpr_total').html(mprTotal.toLocaleString() + '원 <span style="font-size:0.72rem;color:' + diffColor(mDiff) + ';font-weight:600;">(' + fmtCompact(mDiff) + ', ' + (mDiff >= 0 ? '+' : '') + mPct + '%)</span>');
        } else {
            $('#stat_grand_total').text(grandTotal.toLocaleString() + '원');
            $('#stat_ord_total').text(ordTotal.toLocaleString() + '원');
            $('#stat_mpr_total').text(mprTotal.toLocaleString() + '원');
        }

        renderCharts(summary, ordTotal, mprTotal);
    }

    // 차트 렌더링
    function renderCharts(summary, ordTotal, mprTotal) {
        // 기존 차트 파괴
        if (chartTop5) chartTop5.destroy();
        if (chartOrdMpr) chartOrdMpr.destroy();
        // chartSubType 삭제됨

        var isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
        var textColor = isDark ? '#cbd5e1' : '#475569';
        var gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';

        // 1. 매출 TOP 5 (가로 막대, ORD/MPR 스택)
        var sorted = summary.slice().sort(function(a, b) { return (Number(b.grand_total) || 0) - (Number(a.grand_total) || 0); });
        var top5 = sorted.slice(0, 5);
        var top5Labels = top5.map(function(r) { return r.company_name; });
        var top5Ord = top5.map(function(r) { return Number(r.ord_total) || 0; });
        var top5Mpr = top5.map(function(r) { return Number(r.mpr_total) || 0; });

        chartTop5 = new Chart(document.getElementById('chartTop5').getContext('2d'), {
            type: 'bar',
            data: {
                labels: top5Labels,
                datasets: [
                    {
                        label: 'ORD',
                        data: top5Ord,
                        backgroundColor: 'rgba(37, 99, 235, 0.8)',
                        borderRadius: 4,
                        barPercentage: 0.6
                    },
                    {
                        label: 'MPR',
                        data: top5Mpr,
                        backgroundColor: 'rgba(245, 158, 11, 0.8)',
                        borderRadius: 4,
                        barPercentage: 0.6
                    }
                ]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { color: textColor, font: { size: 11 }, boxWidth: 12, padding: 12 }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) { return ctx.dataset.label + ': ' + Number(ctx.raw).toLocaleString() + '원'; }
                        }
                    }
                },
                scales: {
                    x: {
                        stacked: true,
                        grid: { color: gridColor },
                        ticks: { color: textColor, font: { size: 10 }, callback: function(v) { return (v / 10000).toLocaleString() + '만'; } }
                    },
                    y: {
                        stacked: true,
                        grid: { display: false },
                        ticks: { color: textColor, font: { size: 11 } }
                    }
                }
            }
        });

        // 2. ORD vs MPR 매출 비율 (도넛)
        var ordPct = (ordTotal + mprTotal) > 0 ? ((ordTotal / (ordTotal + mprTotal)) * 100).toFixed(1) : '0';
        var centerTextPlugin = {
            id: 'centerText',
            afterDraw: function(chart) {
                var ctx = chart.ctx;
                var centerX = (chart.chartArea.left + chart.chartArea.right) / 2;
                var centerY = (chart.chartArea.top + chart.chartArea.bottom) / 2;
                ctx.save();
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.font = '700 1.3rem -apple-system, sans-serif';
                ctx.fillStyle = isDark ? '#e2e8f0' : '#1e293b';
                ctx.fillText(chart._centerValue || '', centerX, centerY - 8);
                ctx.font = '500 0.68rem -apple-system, sans-serif';
                ctx.fillStyle = '#94a3b8';
                ctx.fillText(chart._centerLabel || '', centerX, centerY + 14);
                ctx.restore();
            }
        };

        chartOrdMpr = new Chart(document.getElementById('chartOrdMpr').getContext('2d'), {
            type: 'doughnut',
            plugins: [centerTextPlugin],
            data: {
                labels: ['ORD', 'MPR'],
                datasets: [{
                    data: [ordTotal, mprTotal],
                    backgroundColor: ['rgba(37, 99, 235, 0.6)', 'rgba(245, 158, 11, 0.55)'],
                    borderWidth: 2,
                    borderColor: isDark ? '#1e293b' : '#fff',
                    hoverOffset: 8,
                    spacing: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '72%',
                animation: { animateRotate: true, duration: 800 },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: textColor, font: { size: 11 }, padding: 14, boxWidth: 8, boxHeight: 8, usePointStyle: true, pointStyle: 'circle' }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(15,23,42,0.9)',
                        cornerRadius: 8,
                        padding: 10,
                        callbacks: {
                            label: function(ctx) {
                                var total = ordTotal + mprTotal;
                                var pct = total > 0 ? ((ctx.raw / total) * 100).toFixed(1) : 0;
                                return ' ' + ctx.label + ': ' + Number(ctx.raw).toLocaleString() + '원 (' + pct + '%)';
                            }
                        }
                    }
                }
            }
        });
        chartOrdMpr._centerValue = ordPct + '%';
        chartOrdMpr._centerLabel = 'ORD 비율';

    }

    // 상세 모달 표시
    function showDetailModal(memberCode, companyName, summaryRow) {
        var details = allDetails.filter(function(d) { return d.member_code === memberCode; });

        $('#detailSubtitle').text(companyName + ' (' + memberCode + ')');
        $('#modal_ord_total').text(formatPrice(summaryRow.ord_total));
        $('#modal_mpr_total').text(formatPrice(summaryRow.mpr_total));
        $('#modal_grand_total').text(formatPrice(summaryRow.grand_total));

        var html = '';
        details.forEach(function(d) {
            var usageBadge = d.usage === 'ORD'
                ? '<span class="badge badge-phoenix badge-phoenix-primary">ORD</span>'
                : '<span class="badge badge-phoenix badge-phoenix-warning">MPR</span>';
            html += '<tr>' +
                '<td class="text-center py-2">' + (d.datacenter_code || '-') + '</td>' +
                '<td class="text-center py-2">' + usageBadge + '</td>' +
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

    // 알림 표시
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
                    title: '회원사 매출내역_' + new Date().toISOString().slice(0,10),
                    exportOptions: { columns: ':visible', modifier: { page: 'all' } }
                },
                {
                    extend: 'csv',
                    text: '<i class="fa-solid fa-file-csv me-2"></i>CSV',
                    className: 'btn btn-info btn-sm',
                    title: '회원사 매출내역_' + new Date().toISOString().slice(0,10),
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
                url: '/revenue_summary/get_revenue_summary',
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
                { data: 'ord_count' },
                { data: 'ord_total' },
                { data: 'mpr_count' },
                { data: 'mpr_total' },
                { data: 'total_count' },
                { data: 'grand_total' }
            ],
            columnDefs: [
                {
                    targets: 0, // 회원번호
                    width: '6%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-info">' + data + '</span>';
                    }
                },
                {
                    targets: 1, // 회원사코드
                    width: '7%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-primary">' + data + '</span>';
                    }
                },
                {
                    targets: 2, // 회사명
                    width: '11%',
                    className: 'text-center py-2 align-middle'
                },
                {
                    targets: 3, // 가입유형
                    width: '7%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-secondary">' + data + '</span>';
                    }
                },
                {
                    targets: 4, // PB
                    width: '5%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (data === true || data === 'true' || data === 't') {
                            return '<span class="badge badge-phoenix badge-phoenix-danger">PB</span>';
                        }
                        return '-';
                    }
                },
                {
                    targets: 5, // Phase
                    width: '5%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-success">' + data + '</span>';
                    }
                },
                {
                    targets: 6, // ORD회선수
                    width: '6%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        return (data || 0).toLocaleString();
                    }
                },
                {
                    targets: 7, // ORD매출
                    width: '9%',
                    className: 'text-end py-2 align-middle',
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return '<span style="color: #1e293b; font-weight: 600;">' + Number(data).toLocaleString() + '원</span>';
                    }
                },
                {
                    targets: 8, // MPR회선수
                    width: '6%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        return (data || 0).toLocaleString();
                    }
                },
                {
                    targets: 9, // MPR매출
                    width: '9%',
                    className: 'text-end py-2 align-middle',
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return '<span style="color: #1e293b; font-weight: 600;">' + Number(data).toLocaleString() + '원</span>';
                    }
                },
                {
                    targets: 10, // 총회선수
                    width: '6%',
                    className: 'text-center py-2 align-middle fw-bold',
                    render: function(data) {
                        return (data || 0).toLocaleString();
                    }
                },
                {
                    targets: 11, // 총매출
                    width: '10%',
                    className: 'text-end py-2 align-middle',
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return '<span style="color: #059669; font-weight: 700; font-size: 0.85rem;">' + Number(data).toLocaleString() + '원</span>';
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
                var allData = api.rows({ search: 'applied' }).data();
                if (!allData.length) return;

                var totalOrdCount = 0, totalOrdAmount = 0, totalMprCount = 0, totalMprAmount = 0, totalCount = 0, grandTotal = 0;
                allData.each(function(row) {
                    totalOrdCount += Number(row.ord_count) || 0;
                    totalOrdAmount += Number(row.ord_total) || 0;
                    totalMprCount += Number(row.mpr_count) || 0;
                    totalMprAmount += Number(row.mpr_total) || 0;
                    totalCount += Number(row.total_count) || 0;
                    grandTotal += Number(row.grand_total) || 0;
                });

                // 기존 합계 행 제거 후 재삽입
                $('#revenueTable tbody tr.grand-total-row').remove();
                var grandRow = '<tr class="grand-total-row" style="background: #1e293b !important; pointer-events: none;">' +
                    '<td colspan="6" class="text-start py-2 align-middle" style="font-size: 0.85rem; font-weight: 800; color: #fff; padding-left: 14px !important;">' +
                    '<i class="fas fa-coins me-1" style="font-size: 0.7rem; opacity: 0.8;"></i>전체 합계 (' + allData.length + '개 회원사)</td>' +
                    '<td class="text-center py-2 align-middle" style="font-weight: 700; color: #93c5fd;">' + totalOrdCount.toLocaleString() + '</td>' +
                    '<td class="text-end py-2 align-middle" style="font-weight: 700; color: #93c5fd;">' + totalOrdAmount.toLocaleString() + '원</td>' +
                    '<td class="text-center py-2 align-middle" style="font-weight: 700; color: #fcd34d;">' + totalMprCount.toLocaleString() + '</td>' +
                    '<td class="text-end py-2 align-middle" style="font-weight: 700; color: #fcd34d;">' + totalMprAmount.toLocaleString() + '원</td>' +
                    '<td class="text-center py-2 align-middle" style="font-weight: 700; color: #f1f5f9;">' + totalCount.toLocaleString() + '</td>' +
                    '<td class="text-end py-2 align-middle" style="font-size: 0.9rem; font-weight: 800; color: #6ee7b7; padding-right: 12px !important;">' + grandTotal.toLocaleString() + '원</td>' +
                    '</tr>';
                $('#revenueTable tbody').append(grandRow);
            },
            initComplete: function() {
                // tfoot 개별 열 검색
                this.api().columns().every(function() {
                    var column = this;
                    var header = $(column.footer());
                    var title = header.text().trim();
                    header.html('<input type="text" class="form-control form-control-sm text-center" placeholder="' + title + '" style="font-size:0.65rem; min-width:50px;" />');
                    $('input', header).on('keyup change', function() {
                        if (column.search() !== this.value) {
                            column.search(this.value).draw();
                        }
                    }).on('click', function(e) {
                        e.stopPropagation();
                    });
                });
            }
        });

        // 행 클릭 시 상세 모달 (합계 행 제외)
        $('#revenueTable tbody').on('click', 'tr:not(.grand-total-row)', function() {
            var data = revenueTable.row(this).data();
            if (data) {
                showDetailModal(data.member_code, data.company_name, data);
            }
        });

        // 행 호버 스타일
        $('#revenueTable tbody').on('mouseenter', 'tr', function() {
            $(this).css('cursor', 'pointer');
        });
    };

    // 월 필터 초기화 (최근 12개월)
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

    // 월 변경 이벤트
    function onMonthChange() {
        var ym = document.getElementById('monthFilter').value;
        currentMonth = ym;
        document.getElementById('btnDownloadPdf').disabled = !ym;

        if (!ym) {
            // 전체(누적) → 기존 API + 추이 차트는 현재 월 기준으로 로드
            revenueTable.ajax.url('/revenue_summary/get_revenue_summary').load();
            loadTrendOnly();
        } else {
            // 월별 → 새 API
            loadMonthlyData(ym);
        }
    }

    // 추이 차트만 로드 (전체 모드에서 현재 월 기준)
    function loadTrendOnly() {
        var now = new Date();
        var ym = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
        $.ajax({
            url: '/revenue_summary/get_revenue_monthly',
            data: { year_month: ym },
            type: 'GET',
            success: function(json) {
                if (json.success && json.trend) {
                    renderTrendChart(json.trend);
                }
            }
        });
    }

    // 월별 데이터 로드
    function loadMonthlyData(yearMonth) {
        var overlay = document.getElementById('pageLoadingOverlay');
        if (overlay) { overlay.style.display = 'flex'; overlay.style.opacity = '1'; }

        $.ajax({
            url: '/revenue_summary/get_revenue_monthly',
            data: { year_month: yearMonth },
            type: 'GET',
            success: function(json) {
                if (json.success) {
                    allDetails = json.details || [];
                    updateSummary(json.summary);
                    renderTrendChart(json.trend);

                    // DataTable 갱신
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

    // 12개월 추이 차트
    function renderTrendChart(trend) {
        _savedTrend = trend;
        // trend 로드 후 대기 중인 summary 재실행
        if (_pendingRevSummary) {
            updateSummary(_pendingRevSummary);
            _pendingRevSummary = null;
        }
        if (chartTrend) chartTrend.destroy();
        if (!trend || !trend.length) return;

        var isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
        var textColor = isDark ? '#cbd5e1' : '#475569';
        var gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';

        var labels = trend.map(function(t) { return t.month; });
        var ordData = trend.map(function(t) { return Number(t.ord_total) || 0; });
        var mprData = trend.map(function(t) { return Number(t.mpr_total) || 0; });
        var totalData = trend.map(function(t) { return Number(t.grand_total) || 0; });

        // 전월 대비 증감률/증감값 계산
        var changeLabels = totalData.map(function(v, i) {
            if (i === 0) return '';
            var prev = totalData[i - 1];
            if (!prev || prev === 0) return '';
            var diff = v - prev;
            var pct = ((diff / prev) * 100).toFixed(1);
            var diffStr = diff >= 0 ? '+' : '';
            if (Math.abs(diff) >= 100000000) diffStr += (diff / 100000000).toFixed(1) + '억';
            else if (Math.abs(diff) >= 10000) diffStr += (diff / 10000).toFixed(0) + '만';
            else diffStr += diff.toLocaleString();
            return (diff >= 0 ? '+' : '') + pct + '% (' + diffStr + ')';
        });

        var changePlugin = {
            id: 'changeLabel',
            afterDatasetsDraw: function(chart) {
                var meta = chart.getDatasetMeta(2); // 합계 데이터셋
                if (!meta || meta.hidden) return;
                var ctx = chart.ctx;
                ctx.save();
                ctx.textAlign = 'center';
                ctx.font = '800 0.82rem -apple-system, sans-serif';
                meta.data.forEach(function(point, i) {
                    if (!changeLabels[i]) return;
                    var isUp = totalData[i] >= (totalData[i - 1] || 0);
                    // 배경 라운드 박스
                    var text = changeLabels[i];
                    var tw = ctx.measureText(text).width;
                    var px = point.x, py = point.y - 16;
                    ctx.fillStyle = isUp ? 'rgba(239, 68, 68, 0.08)' : 'rgba(59, 130, 246, 0.08)';
                    ctx.beginPath();
                    ctx.roundRect(px - tw / 2 - 6, py - 8, tw + 12, 18, 4);
                    ctx.fill();
                    // 텍스트
                    ctx.fillStyle = isUp ? 'rgba(220, 38, 38, 0.9)' : 'rgba(37, 99, 235, 0.9)';
                    ctx.fillText(text, px, py);
                });
                ctx.restore();
            }
        };

        var ctx = document.getElementById('chartTrend').getContext('2d');
        chartTrend = new Chart(ctx, {
            type: 'line',
            plugins: [changePlugin],
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'ORD 매출',
                        data: ordData,
                        borderColor: 'rgba(37, 99, 235, 0.9)',
                        backgroundColor: 'rgba(37, 99, 235, 0.05)',
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        borderWidth: 1.2
                    },
                    {
                        label: 'MPR 매출',
                        data: mprData,
                        borderColor: 'rgba(245, 158, 11, 0.9)',
                        backgroundColor: 'rgba(245, 158, 11, 0.05)',
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        borderWidth: 1.2
                    },
                    {
                        label: '합계',
                        data: totalData,
                        borderColor: 'rgba(16, 185, 129, 0.9)',
                        backgroundColor: 'transparent',
                        borderDash: [6, 3],
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 4,
                        borderWidth: 1.2
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: { padding: { top: 25, right: 60 } },
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { color: textColor, font: { size: 11 }, boxWidth: 14, padding: 15 }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                return ctx.dataset.label + ': ' + Number(ctx.raw).toLocaleString() + '원';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: gridColor },
                        ticks: { color: textColor, font: { size: 10 } }
                    },
                    y: {
                        beginAtZero: false,
                        grid: { color: gridColor },
                        ticks: {
                            color: textColor,
                            font: { size: 10 },
                            callback: function(v) { return (v / 10000).toLocaleString() + '만'; }
                        }
                    }
                }
            }
        });

        // 월별 매출 추이 테이블
        var tbody = document.getElementById('monthlyTrendBody');
        if (tbody && trend && trend.length) {
            var reversed = trend.slice().reverse();
            var html = '';
            function fmtDiff(v) {
                if (v === 0) return '';
                var s = v >= 0 ? '+' : '';
                if (Math.abs(v) >= 100000000) return s + (v / 100000000).toFixed(1) + '억';
                if (Math.abs(v) >= 10000) return s + (v / 10000).toFixed(0) + '만';
                return s + v.toLocaleString();
            }

            reversed.forEach(function(t, i) {
                var ord = Number(t.ord_total) || 0;
                var mpr = Number(t.mpr_total) || 0;
                var total = Number(t.grand_total) || 0;
                var hasPrev = i < reversed.length - 1;
                var prevOrd = hasPrev ? (Number(reversed[i + 1].ord_total) || 0) : 0;
                var prevMpr = hasPrev ? (Number(reversed[i + 1].mpr_total) || 0) : 0;
                var prevTotal = hasPrev ? (Number(reversed[i + 1].grand_total) || 0) : 0;

                var ordDiff = hasPrev ? ord - prevOrd : 0;
                var mprDiff = hasPrev ? mpr - prevMpr : 0;
                var totalDiff = hasPrev ? total - prevTotal : 0;
                var totalPct = prevTotal > 0 ? ((totalDiff / prevTotal) * 100).toFixed(1) : '0.0';

                var ordSub = hasPrev && ordDiff !== 0 ? ' <span style="font-size:0.6rem;color:' + (ordDiff >= 0 ? '#dc2626' : '#2563eb') + ';">(' + fmtDiff(ordDiff) + ')</span>' : '';
                var mprSub = hasPrev && mprDiff !== 0 ? ' <span style="font-size:0.6rem;color:' + (mprDiff >= 0 ? '#dc2626' : '#2563eb') + ';">(' + fmtDiff(mprDiff) + ')</span>' : '';
                var totalSub = hasPrev && totalDiff !== 0 ? ' <span style="font-size:0.6rem;color:' + (totalDiff >= 0 ? '#dc2626' : '#2563eb') + ';">(' + fmtDiff(totalDiff) + ')</span>' : '';

                var diffStr = '';
                if (hasPrev) {
                    var arrow = totalDiff >= 0 ? '<span style="color:#dc2626;">▲</span>' : '<span style="color:#2563eb;">▼</span>';
                    diffStr = arrow + ' ' + (totalDiff >= 0 ? '+' : '') + totalPct + '%';
                }
                html += '<tr class="trend-row" data-month="' + t.month + '" style="border-bottom:1px solid #f5f5f5; cursor:pointer; transition: background 0.15s;" onmouseenter="this.style.background=\'#f8fafc\'" onmouseleave="this.style.background=\'\'">' +
                    '<td class="text-center py-2" style="font-weight:600; color:' + T('#475569','#94a3b8') + ';">' + t.month + '</td>' +
                    '<td class="py-2" style="color:' + T('#1e293b','#e2e8f0') + '; font-weight:600;">' + ord.toLocaleString() + '원' + ordSub + '</td>' +
                    '<td class="py-2" style="color:' + T('#1e293b','#e2e8f0') + '; font-weight:600;">' + mpr.toLocaleString() + '원' + mprSub + '</td>' +
                    '<td class="py-2" style="color:#059669; font-weight:700;">' + total.toLocaleString() + '원' + totalSub + '</td>' +
                    '<td class="text-center py-2" style="font-size:0.78rem; font-weight:600;">' + diffStr + '</td>' +
                    '</tr>';
            });
            tbody.innerHTML = html;

            // 행 클릭 → 변동 내역 펼침
            tbody.querySelectorAll('.trend-row').forEach(function(row) {
                row.addEventListener('click', function() {
                    var month = this.getAttribute('data-month');
                    var existing = this.nextElementSibling;
                    if (existing && existing.classList.contains('diff-detail-row')) {
                        existing.remove();
                        return;
                    }
                    // 기존 열린 상세 닫기
                    tbody.querySelectorAll('.diff-detail-row').forEach(function(r) { r.remove(); });

                    var detailRow = document.createElement('tr');
                    detailRow.className = 'diff-detail-row';
                    detailRow.innerHTML = '<td colspan="5" style="padding:12px 16px; background:#fafbfc;"><div style="text-align:center; color:#94a3b8; font-size:0.78rem;"><span class="spinner-border spinner-border-sm me-1" style="width:0.6rem;height:0.6rem;"></span>변동 내역 조회 중...</div></td>';
                    this.parentNode.insertBefore(detailRow, this.nextSibling);

                    fetch('/revenue_summary/get_revenue_monthly_diff?year_month=' + month)
                        .then(function(r) { return r.json(); })
                        .then(function(data) {
                            if (!data.success) {
                                detailRow.innerHTML = '<td colspan="5" style="padding:12px; color:#dc2626; font-size:0.78rem;">조회 실패</td>';
                                return;
                            }
                            var dhtml = '<td colspan="5" style="padding:0; background:#fafbfc;">';
                            if (data.added.length === 0 && data.removed.length === 0) {
                                dhtml += '<div style="padding:12px 16px; color:#94a3b8; font-size:0.78rem; text-align:center;">전월 대비 변동 없음</div>';
                            } else {
                                dhtml += '<table class="table table-sm mb-0" style="font-size:0.75rem; background:transparent;">';
                                if (data.added.length > 0) {
                                    dhtml += '<tr><td colspan="6" style="padding:8px 16px; font-weight:700; color:#059669; font-size:0.72rem; background:rgba(16,185,129,0.06);">▲ 추가 (' + data.added.length + '건)</td></tr>';
                                    data.added.forEach(function(a) {
                                        dhtml += '<tr style="border-bottom:1px solid #f0f0f0;">' +
                                            '<td style="padding:4px 16px; color:' + T('#475569','#94a3b8') + ';">' + (a.company_name || a.member_code) + '</td>' +
                                            '<td style="color:' + (a.usage === 'ORD' ? '#7c3aed' : '#6366f1') + '; font-weight:600;">' + a.usage + '</td>' +
                                            '<td>' + a.product + '</td>' +
                                            '<td>' + a.bandwidth + '</td>' +
                                            '<td>' + a.provider + '</td>' +
                                            '<td style="text-align:right; font-weight:600; color:#dc2626;">' + Number(a.price).toLocaleString() + '원</td></tr>';
                                    });
                                }
                                if (data.removed.length > 0) {
                                    dhtml += '<tr><td colspan="6" style="padding:8px 16px; font-weight:700; color:#dc2626; font-size:0.72rem; background:rgba(239,68,68,0.06);">▼ 제거 (' + data.removed.length + '건)</td></tr>';
                                    data.removed.forEach(function(a) {
                                        dhtml += '<tr style="border-bottom:1px solid #f0f0f0; opacity:0.6;">' +
                                            '<td style="padding:4px 16px; color:' + T('#475569','#94a3b8') + ';">' + (a.company_name || a.member_code) + '</td>' +
                                            '<td style="color:#94a3b8;">' + a.usage + '</td>' +
                                            '<td>' + a.product + '</td>' +
                                            '<td>' + a.bandwidth + '</td>' +
                                            '<td>' + a.provider + '</td>' +
                                            '<td style="text-align:right; color:#94a3b8;">' + Number(a.price).toLocaleString() + '원</td></tr>';
                                    });
                                }
                                dhtml += '</table>';
                            }
                            dhtml += '</td>';
                            detailRow.innerHTML = dhtml;
                        })
                        .catch(function() {
                            detailRow.innerHTML = '<td colspan="5" style="padding:12px; color:#dc2626; font-size:0.78rem;">조회 실패</td>';
                        });
                });
            });
        }
    }

    // PDF 다운로드
    window.downloadPdf = function() {
        if (!currentMonth) {
            showAlert('PDF 다운로드는 월을 선택한 후 가능합니다.', 'warning');
            return;
        }
        showAlert(currentMonth + ' 보고서 PDF를 생성 중...', 'info');
        window.open('/revenue_summary/download_revenue_pdf?year_month=' + currentMonth, '_blank');
    };

    // 새로고침
    window.refreshTable = function() {
        if (revenueTable) {
            var ym = document.getElementById('monthFilter').value;
            if (ym) {
                loadMonthlyData(ym);
            } else {
                revenueTable.ajax.url('/revenue_summary/get_revenue_summary').load();
            }
            showAlert('데이터를 새로고침했습니다.', 'success');
        }
    };

    // 초기화
    document.addEventListener('DOMContentLoaded', function() {
        initMonthFilter();
        initTable();
        // 전체 모드에서도 추이 차트 표시
        loadTrendOnly();
    });

}));
