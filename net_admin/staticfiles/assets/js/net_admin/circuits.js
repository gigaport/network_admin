(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
})((function () {
    'use strict';

    var circuitsTable = null;

    // 요약 통계 업데이트
    function updateSummary(data) {
        var members = {};
        var ktc = 0, lgu = 0, skb = 0, pr = 0, dr = 0, ts = 0, mg = 0;
        var ord = 0, mpr = 0, expiring = 0;
        var dc1 = 0, dc2 = 0, dc3 = 0, dcDr = 0;
        var today = new Date();
        var d90 = new Date(today.getTime() + 90 * 24 * 60 * 60 * 1000);
        data.forEach(function(r) {
            if (r.member_code) members[r.member_code] = true;
            if (r.provider === 'KTC') ktc++;
            else if (r.provider === 'LGU') lgu++;
            else if (r.provider === 'SKB') skb++;
            if (r.env === 'PR') pr++;
            else if (r.env === 'DR') dr++;
            else if (r.env === 'TS') ts++;
            else if (r.env === 'MG') mg++;
            if (r.usage === 'ORD') ord++;
            else if (r.usage === 'MPR') mpr++;
            if (r.datacenter_code === 'DC1') dc1++;
            else if (r.datacenter_code === 'DC2') dc2++;
            else if (r.datacenter_code === 'DC3') dc3++;
            else if (r.datacenter_code === 'DR') dcDr++;
            if (r.expiry_date) {
                var exp = new Date(r.expiry_date);
                if (exp >= today && exp <= d90) expiring++;
            }
        });
        $('#stat_total').text(data.length.toLocaleString());
        $('#stat_members').text(Object.keys(members).length.toLocaleString());
        $('#stat_kt').text(ktc); $('#stat_lgu').text(lgu); $('#stat_skb').text(skb);
        $('#stat_pr').text(pr); $('#stat_dr').text(dr); $('#stat_ts').text(ts); $('#stat_mg').text(mg);
        $('#stat_ord').text(ord); $('#stat_mpr').text(mpr);
        $('#stat_expiring').text(expiring);
        $('#stat_dc1').text(dc1); $('#stat_dc2').text(dc2); $('#stat_dc3').text(dc3); $('#stat_dc_dr').text(dcDr);

        // 최근 수정 내역 렌더링
        renderRecentChanges(data);
    }

    function renderRecentChanges(data) {
        var now = new Date();
        var thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);

        // updated_at 또는 created_at 기준으로 최근 항목 필터 + 정렬
        var recent = data.filter(function(r) {
            var ts = r.updated_at || r.created_at;
            if (!ts) return false;
            return new Date(ts) >= thirtyDaysAgo;
        }).sort(function(a, b) {
            var ta = new Date(a.updated_at || a.created_at || 0);
            var tb = new Date(b.updated_at || b.created_at || 0);
            return tb - ta;
        }).slice(0, 10);

        $('#stat_recent_count').text(recent.length + '건');

        if (!recent.length) {
            $('#recentChangesBody').html('<div class="text-center py-4 text-muted" style="font-size: 0.8rem;">최근 30일간 변경된 내역이 없습니다.</div>');
            return;
        }

        var html = '<div class="list-group list-group-flush">';
        recent.forEach(function(r, idx) {
            var ts = r.updated_at || r.created_at;
            var isNew = r.created_at === r.updated_at;
            var typeLabel = isNew ? '신규' : '수정';
            var typeColor = isNew ? '#10b981' : '#f59e0b';
            var typeBg = isNew ? 'rgba(16,185,129,0.1)' : 'rgba(245,158,11,0.1)';
            var typeIcon = isNew ? 'fa-plus-circle' : 'fa-pen';
            var timeAgo = getTimeAgo(ts);
            var bg = idx % 2 === 0 ? '#fff' : '#f8fafc';

            // 변경 상세 정보 조합
            var details = [];
            if (r.provider) details.push(r.provider);
            if (r.datacenter_code) details.push(r.datacenter_code);
            if (r.env) details.push(r.env);
            if (r.usage) details.push(r.usage);
            if (r.bandwidth) details.push(r.bandwidth);
            if (r.product) details.push(r.product);
            var detailStr = details.join(' / ');

            html += '<div class="list-group-item px-3 py-2 border-0" style="background:' + bg + ';">';

            // 1줄: 타입 + 회원사 + 시간
            html += '  <div class="d-flex align-items-center gap-2 mb-1">';
            html += '    <span style="display: inline-flex; align-items: center; gap: 3px; padding: 2px 7px; border-radius: 5px; font-size: 0.6rem; font-weight: 700; color: ' + typeColor + '; background: ' + typeBg + ';">';
            html += '      <i class="fas ' + typeIcon + '" style="font-size: 0.5rem;"></i>' + typeLabel;
            html += '    </span>';
            html += '    <span style="color: #6366f1; font-weight: 600; font-size: 0.7rem;">' + (r.member_code || '-') + '</span>';
            html += '    <span style="color: #475569; font-size: 0.7rem;">' + (r.company_name || '') + '</span>';
            html += '    <span style="color: #94a3b8; font-size: 0.6rem; margin-left: auto;">' + timeAgo + '</span>';
            html += '  </div>';

            // 2줄: 회선 상세
            html += '  <div style="padding-left: 4px; font-size: 0.65rem; color: #64748b;">';
            html += '    <span style="color: #94a3b8;">' + (r.circuit_id || '-') + '</span>';
            if (detailStr) {
                html += '    <span style="color: #cbd5e1; margin: 0 5px;">|</span>';
                html += '    <span>' + detailStr + '</span>';
            }
            html += '  </div>';

            html += '</div>';
        });
        html += '</div>';
        $('#recentChangesBody').html(html);
    }

    function getTimeAgo(dateStr) {
        if (!dateStr) return '-';
        var now = new Date();
        var date = new Date(dateStr);
        var diff = Math.floor((now - date) / 1000);

        if (diff < 60) return '방금 전';
        if (diff < 3600) return Math.floor(diff / 60) + '분 전';
        if (diff < 86400) return Math.floor(diff / 3600) + '시간 전';
        if (diff < 604800) return Math.floor(diff / 86400) + '일 전';
        return dateStr.substring(0, 10);
    }

    // subscriber_codes 목록 로드
    function loadMemberCodeOptions() {
        fetch('/subscriber_codes/get_codes')
            .then(function(res) { return res.json(); })
            .then(function(result) {
                if (result.success && result.data) {
                    var options = '<option value="">선택</option>';
                    result.data.forEach(function(s) {
                        options += '<option value="' + s.member_code + '">' + s.member_code + ' - ' + s.company_name + '</option>';
                    });
                    $('#create_member_code').html(options);
                    $('#edit_member_code').html(options);
                }
            })
            .catch(function(err) { console.error('회원사코드 목록 로드 실패:', err); });
    }


    // sise_products 목록 로드 (MPR용 캐시)
    var mprProductOptions = '<option value="">선택</option>';
    function loadProductOptions() {
        fetch('/sise_products/get_products')
            .then(function(res) { return res.json(); })
            .then(function(result) {
                if (result.success && result.data) {
                    mprProductOptions = '<option value="">선택</option>';
                    result.data.forEach(function(p) {
                        mprProductOptions += '<option value="' + p.product_name + '">' + p.product_name + '</option>';
                    });
                }
            })
            .catch(function(err) { console.error('상품 목록 로드 실패:', err); });
    }

    var allFeeData = [];

    function loadFeeCodeOptions() {
        fetch('/fee_schedule/get_fee_schedule')
            .then(function(res) { return res.json(); })
            .then(function(result) {
                if (result.success && result.data) {
                    allFeeData = result.data;
                    filterFeeCodeByUsage('', '#create_fee_code');
                    filterFeeCodeByUsage('', '#edit_fee_code');
                }
            })
            .catch(function(err) { console.error('요금코드 목록 로드 실패:', err); });
    }

    function filterFeeCodeByUsage(usage, selectId) {
        var html = '<option value="">선택</option>';
        allFeeData.forEach(function(f) {
            if (!usage || (f.fee_code && f.fee_code.indexOf(usage) === 0)) {
                var label = f.fee_code + ' (' + f.description + ' / ' + Number(f.price).toLocaleString() + '원)';
                html += '<option value="' + f.fee_code + '">' + label + '</option>';
            }
        });
        $(selectId).html(html);
    }

    // 용도에 따른 상품 옵션 변경
    function updateProductByUsage(usage, productSelect) {
        var options = '<option value="">선택</option>';
        if (usage === 'MPR') {
            options = mprProductOptions;
        } else if (usage === 'ORD') {
            var bandwidths = ['50M', '100M', '150M', '200M', '250M', '300M', '350M', '400M', '450M'];
            bandwidths.forEach(function(bw) {
                options += '<option value="' + bw + '">' + bw + '</option>';
            });
        } else if (usage === 'MGT') {
            options += '<option value="MGT">MGT</option>';
        } else if (usage === 'PB_ORD_PRD') {
            options = '<option value="50M" selected>50M</option>';
        } else if (usage === 'PB_ORD_DEV') {
            options = '<option value="공유(1G)" selected>공유(1G)</option>';
        }
        $(productSelect).html(options);
    }

    var allBandwidthOptions = '<option value="">선택</option>' +
        '<option value="10M">10M</option><option value="50M">50M</option>' +
        '<option value="100M">100M</option><option value="150M">150M</option>' +
        '<option value="200M">200M</option><option value="250M">250M</option>' +
        '<option value="300M">300M</option><option value="350M">350M</option>' +
        '<option value="400M">400M</option><option value="450M">450M</option>' +
        '<option value="공유(1G)">공유(1G)</option>';

    function updateBandwidthByUsage(usage, bwSelect) {
        if (usage === 'MPR') {
            $(bwSelect).html('<option value="100M">100M</option>').val('100M');
        } else if (usage === 'MGT') {
            $(bwSelect).html('<option value="10M">10M</option>').val('10M');
        } else if (usage === 'PB_ORD_PRD') {
            $(bwSelect).html('<option value="50M">50M</option>').val('50M');
        } else if (usage === 'PB_ORD_DEV') {
            $(bwSelect).html('<option value="공유(1G)">공유(1G)</option>').val('공유(1G)');
        } else {
            var current = $(bwSelect).val();
            $(bwSelect).html(allBandwidthOptions);
            if (current) $(bwSelect).val(current);
        }
    }

    // 용도에 따른 추가회선 체크박스 활성/비활성화
    function updateAdditionalCircuitByUsage(usage, checkboxId) {
        var isPB = (usage === 'PB_ORD_PRD' || usage === 'PB_ORD_DEV');
        var $cb = $(checkboxId);
        $cb.prop('disabled', isPB);
        if (isPB) $cb.prop('checked', false);
    }

    var initTable = function() {
        circuitsTable = $('#circuitsTable').DataTable({
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
                    title: '회선내역_' + new Date().toISOString().slice(0,10),
                    exportOptions: {
                        columns: ':visible',
                        modifier: { page: 'all' }
                    }
                },
                {
                    extend: 'csv',
                    text: '<i class="fa-solid fa-file-csv me-2"></i>CSV',
                    className: 'btn btn-info btn-sm',
                    title: '회선내역_' + new Date().toISOString().slice(0,10),
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
                url: '/circuits/get_circuits',
                type: 'GET',
                dataSrc: function(json) {
                    if (json.success) {
                        updateSummary(json.data);
                        return json.data;
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
                { data: 'member_code' },
                { data: 'member_number' },
                { data: 'company_name' },
                { data: 'datacenter_code' },
                { data: 'summary_address' },
                { data: 'provider' },
                { data: 'circuit_id' },
                { data: 'nni_id' },
                { data: 'env' },
                { data: 'usage' },
                { data: 'product' },
                { data: 'bandwidth' },
                { data: 'additional_circuit' },
                { data: 'phase' },
                { data: 'fee_price' },
                { data: 'cot_device' },
                { data: 'rt_device' },
                { data: 'contract_date' },
                { data: 'expiry_date' },
                { data: 'contract_period' },
                { data: 'report_number' },
                { data: 'comments' }
            ],
            columnDefs: [
                {
                    targets: 0, // 회원사코드
                    width: '4%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-primary">' + data + '</span>';
                    }
                },
                {
                    targets: 1, // 회원사넘버
                    width: '3%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-info">' + data + '</span>';
                    }
                },
                {
                    targets: 2, // 회사명
                    width: '5%',
                    className: 'text-center py-2 align-middle fw-semibold'
                },
                {
                    targets: 3, // DC코드
                    width: '3%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-warning">' + data + '</span>';
                    }
                },
                {
                    targets: 4, // 요약주소
                    width: '6%',
                    className: 'text-start py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span title="' + data + '">' + data + '</span>';
                    }
                },
                {
                    targets: 5, // 통신사
                    width: '3%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-secondary">' + data + '</span>';
                    }
                },
                {
                    targets: 6, // 회선ID
                    width: '6%',
                    className: 'text-center py-2 align-middle fw-semibold',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span title="' + data + '">' + data + '</span>';
                    }
                },
                {
                    targets: 7, // NNI ID
                    width: '5%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span title="' + data + '">' + data + '</span>';
                    }
                },
                {
                    targets: 8, // 환경
                    width: '3%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        var badgeClass = 'badge-phoenix-secondary';
                        if (data === 'PR') badgeClass = 'badge-phoenix-success';
                        else if (data === 'TS') badgeClass = 'badge-phoenix-info';
                        else if (data === 'DR') badgeClass = 'badge-phoenix-warning';
                        return '<span class="badge badge-phoenix ' + badgeClass + '">' + data + '</span>';
                    }
                },
                {
                    targets: 9, // 용도
                    width: '3%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) { return data || '-'; }
                },
                {
                    targets: 10, // 상품
                    width: '5%',
                    className: 'text-center py-2 align-middle fw-semibold',
                    render: function(data) { return data || '-'; }
                },
                {
                    targets: 11, // 대역폭
                    width: '3%',
                    className: 'text-center py-2 align-middle fw-semibold',
                    render: function(data) { return data || '-'; }
                },
                {
                    targets: 12, // 추가회선
                    width: '3%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (data === true) return '<span class="badge badge-phoenix badge-phoenix-info">추가</span>';
                        return '';
                    }
                },
                {
                    targets: 13, // 가입 Phase
                    width: '3%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        if (data === 1) return '<span class="badge badge-phoenix badge-phoenix-primary">Phase 1</span>';
                        if (data === 2) return '<span class="badge badge-phoenix badge-phoenix-info">Phase 2</span>';
                        return '<span class="badge badge-phoenix badge-phoenix-secondary">' + data + '</span>';
                    }
                },
                {
                    targets: 14, // 요금
                    width: '4%',
                    className: 'text-end py-2 align-middle fw-semibold',
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return Number(data).toLocaleString() + '원';
                    }
                },
                {
                    targets: 15, // COT장비
                    visible: false,
                    width: '6%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span title="' + data + '">' + data + '</span>';
                    }
                },
                {
                    targets: 16, // RT장비
                    visible: false,
                    width: '6%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span title="' + data + '">' + data + '</span>';
                    }
                },
                {
                    targets: 17, // 계약일
                    width: '5%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) { return data || '-'; }
                },
                {
                    targets: 18, // 만료일
                    width: '5%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) { return data || '-'; }
                },
                {
                    targets: 19, // 약정기간
                    width: '3%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) { return data || '-'; }
                },
                {
                    targets: 20, // 문서번호
                    width: '6%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) { return data || '-'; }
                },
                {
                    targets: 21, // 비고
                    width: '16%',
                    className: 'text-start py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        if (data.length > 30) {
                            return '<span title="' + data + '">' + data.substring(0, 30) + '...</span>';
                        }
                        return data;
                    }
                }
            ],
            initComplete: function() {
                var overlay = document.getElementById('pageLoadingOverlay');
                if (overlay) {
                    overlay.style.opacity = '0';
                    setTimeout(function() { overlay.remove(); }, 400);
                }
            }
        });

        // 행 클릭 커서
        $('#circuitsTable tbody').css('cursor', 'pointer');

        // tfoot의 각 열에 검색 입력 필드 추가 (contracts.js 패턴)
        $('#circuitsTable tfoot th').each(function(i) {
            var title = $(this).text();
            $(this).css({'font-size': '0.7rem', 'white-space': 'nowrap'});
            $(this).html('<input type="text" class="form-control form-control-sm" placeholder="' + title + ' 검색" style="font-size:0.65rem; padding:2px 4px;" />');
        });

        // 개별 열 검색 기능 적용
        circuitsTable.columns().every(function() {
            var that = this;
            $('input', this.footer()).on('keyup change', function() {
                if (that.search() !== this.value) {
                    that.search(this.value).draw();
                }
            });
        });

        // 행 클릭 시 상세보기 팝업
        $('#circuitsTable tbody').on('click', 'tr', function() {
            var data = circuitsTable.row(this).data();
            if (!data) return;
            showDetailModal(data);
        });
    };

    window.resetFilters = function() {
        $('#circuitsTable tfoot input').val('');
        if (circuitsTable) {
            circuitsTable.columns().search('').draw();
        }
    };

    window.refreshTable = function() {
        var spinner = $('<div class="position-fixed top-50 start-50 translate-middle" style="z-index: 10000;">' +
            '<div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">' +
            '<span class="visually-hidden">Loading...</span>' +
            '</div></div>');
        $('body').append(spinner);

        resetFilters();
        if (circuitsTable) {
            circuitsTable.ajax.reload(function() {
                spinner.remove();
            }, false);
        } else {
            spinner.remove();
            showAlert('테이블이 초기화되지 않았습니다.', 'danger');
        }
    };

    window.showCreateModal = function() {
        $('#createForm')[0].reset();
        var modal = new bootstrap.Modal(document.getElementById('createModal'));
        modal.show();
    };

    window.saveCreate = function(keepOpen) {
        var data = {
            member_code: $('#create_member_code').val().trim(),
            datacenter_code: $('input[name="create_datacenter_code"]:checked').val() || null,
            provider: $('input[name="create_provider"]:checked').val() || null,
            circuit_id: $('#create_circuit_id').val().trim() || null,
            nni_id: $('#create_nni_id').val().trim() || null,
            env: $('input[name="create_env"]:checked').val() || null,
            usage: $('#create_usage').val().trim() || null,
            product: $('#create_product').val().trim() || null,
            bandwidth: $('#create_bandwidth').val().trim() || null,
            additional_circuit: $('#create_additional_circuit').is(':checked'),
            cot_device: $('#create_cot_device').val().trim() || null,
            rt_device: $('#create_rt_device').val().trim() || null,
            phase: parseInt($('#create_phase').val()) || null,
            fee_code: $('#create_fee_code').val() || null,
            contract_date: $('#create_contract_date').val() || null,
            expiry_date: $('#create_expiry_date').val() || null,
            contract_period: $('#create_contract_period').val() || null,
            report_number: $('#create_report_number').val().trim() || null,
            comments: $('#create_comments').val().trim() || null
        };

        if (!data.member_code) {
            showAlert('회원사코드는 필수 입력항목입니다.', 'warning');
            return;
        }

        fetch('/circuits/create_circuit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(function(response) { return response.json(); })
        .then(function(result) {
            if (result.success) {
                showAlert('추가가 완료되었습니다.', 'success');
                refreshTable();
                if (keepOpen) {
                    // 회선별 고유값만 초기화 (회원사/DC/통신사/환경 등 공통값은 유지)
                    $('#create_circuit_id').val('');
                    $('#create_nni_id').val('');
                    $('#create_comments').val('');
                } else {
                    bootstrap.Modal.getInstance(document.getElementById('createModal')).hide();
                }
            } else {
                showAlert('추가 실패: ' + result.error, 'danger');
            }
        })
        .catch(function(error) {
            console.error('Error:', error);
            showAlert('추가 중 오류가 발생했습니다.', 'danger');
        });
    };

    function makeBadge(text, color, bg) {
        return '<span style="display:inline-block; padding:3px 10px; border-radius:4px; font-size:0.78rem; font-weight:600; color:' + color + '; background:' + bg + '; white-space:nowrap;">' + text + '</span>';
    }

    function showDetailModal(circuit) {
        $('#detail_id').val(circuit.id);

        var fields = [
            'member_code', 'member_number', 'company_name', 'datacenter_code',
            'summary_address', 'provider', 'circuit_id', 'nni_id',
            'env', 'usage', 'product', 'bandwidth',
            'cot_device', 'rt_device', 'lldp_cot_device', 'lldp_port',
            'lldp_rt_device', 'lldp_rt_port', 'contract_date', 'expiry_date',
            'contract_period', 'report_number', 'comments'
        ];
        fields.forEach(function(f) {
            var val = circuit[f];
            $('#detail_' + f).text(val !== null && val !== undefined && val !== '' ? val : '-');
        });
        $('#detail_additional_circuit').text(circuit.additional_circuit ? 'Y' : 'N');
        var phase = circuit.phase;
        $('#detail_phase').text(phase === 1 ? 'Phase 1' : phase === 2 ? 'Phase 2' : '-');
        $('#detail_fee_code').text(circuit.fee_code || '-');
        var fp = circuit.fee_price;
        var fpText = fp !== null && fp !== undefined ? Number(fp).toLocaleString() + '원' : '-';
        if (circuit.fee_description) fpText += ' (' + circuit.fee_description + ')';
        $('#detail_fee_price').text(fpText);

        var name = circuit.company_name || circuit.member_code || '';
        $('#detailSubtitle').text(name + (circuit.circuit_id ? ' / ' + circuit.circuit_id : ''));

        // 요약 배지
        var badges = '';
        var usageColors = { 'ORD': ['#059669','#f0fdf4'], 'MPR': ['#2563eb','#eff6ff'], 'MGT': ['#7c3aed','#f5f3ff'] };
        var uc = usageColors[circuit.usage] || ['#d97706','#fffbeb'];
        if (circuit.usage) badges += makeBadge(circuit.usage, uc[0], uc[1]);
        if (circuit.env) badges += makeBadge(circuit.env, '#0369a1', '#f0f9ff');
        if (phase === 1 || phase === 2) badges += makeBadge('Phase ' + phase, '#6d28d9', '#f5f3ff');
        if (circuit.provider) badges += makeBadge(circuit.provider, '#334155', '#f1f5f9');
        if (circuit.bandwidth) badges += makeBadge(circuit.bandwidth, '#0891b2', '#ecfeff');
        if (fp !== null && fp !== undefined) {
            badges += '<span style="margin-left:auto; font-size:0.95rem; font-weight:700; color:#0f172a;">' + Number(fp).toLocaleString() + '원</span>';
        }
        $('#detail_badges').html(badges);

        var modal = new bootstrap.Modal(document.getElementById('detailModal'));
        modal.show();
    }

    window.editFromDetail = function() {
        var id = parseInt($('#detail_id').val());
        var rowData = circuitsTable.rows().data().toArray();
        var circuit = rowData.find(function(item) { return item.id === id; });
        if (!circuit) return;

        bootstrap.Modal.getInstance(document.getElementById('detailModal')).hide();

        $('#edit_id').val(circuit.id);
        $('#edit_member_code').val(circuit.member_code);
        $('input[name="edit_datacenter_code"]').prop('checked', false);
        if (circuit.datacenter_code) $('input[name="edit_datacenter_code"][value="' + circuit.datacenter_code + '"]').prop('checked', true);
        $('input[name="edit_provider"]').prop('checked', false);
        if (circuit.provider) $('input[name="edit_provider"][value="' + circuit.provider + '"]').prop('checked', true);
        $('#edit_circuit_id').val(circuit.circuit_id);
        $('#edit_nni_id').val(circuit.nni_id);
        $('input[name="edit_env"]').prop('checked', false);
        if (circuit.env) $('input[name="edit_env"][value="' + circuit.env + '"]').prop('checked', true);
        $('#edit_usage').val(circuit.usage);
        updateProductByUsage(circuit.usage, '#edit_product');
        $('#edit_product').val(circuit.product);
        $('#edit_bandwidth').val(circuit.bandwidth);
        updateBandwidthByUsage(circuit.usage, '#edit_bandwidth');
        $('#edit_bandwidth').val(circuit.bandwidth);
        $('#edit_additional_circuit').prop('checked', circuit.additional_circuit);
        updateAdditionalCircuitByUsage(circuit.usage, '#edit_additional_circuit');
        $('#edit_cot_device').val(circuit.cot_device);
        $('#edit_rt_device').val(circuit.rt_device);
        $('#edit_phase').val(circuit.phase);
        filterFeeCodeByUsage(circuit.usage || '', '#edit_fee_code');
        $('#edit_fee_code').val(circuit.fee_code || '');
        $('#edit_contract_date').val(circuit.contract_date);
        $('#edit_expiry_date').val(circuit.expiry_date);
        $('#edit_contract_period').val(circuit.contract_period);
        $('#edit_report_number').val(circuit.report_number);
        $('#edit_comments').val(circuit.comments);

        document.getElementById('detailModal').addEventListener('hidden.bs.modal', function handler() {
            document.getElementById('detailModal').removeEventListener('hidden.bs.modal', handler);
            var editModal = new bootstrap.Modal(document.getElementById('editModal'));
            editModal.show();
        });
    };

    window.deleteFromDetail = function() {
        var id = parseInt($('#detail_id').val());
        var rowData = circuitsTable.rows().data().toArray();
        var circuit = rowData.find(function(item) { return item.id === id; });
        if (!circuit) return;

        var name = circuit.company_name ? circuit.company_name + ' (' + circuit.member_code + ')' : circuit.member_code;
        if (!confirm(name + '의 회선 (ID: ' + circuit.id + ')을 삭제하시겠습니까?')) {
            return;
        }

        fetch('/circuits/delete_circuit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: id })
        })
        .then(function(response) { return response.json(); })
        .then(function(result) {
            if (result.success) {
                bootstrap.Modal.getInstance(document.getElementById('detailModal')).hide();
                showAlert('삭제가 완료되었습니다.', 'success');
                refreshTable();
            } else {
                showAlert('삭제 실패: ' + result.error, 'danger');
            }
        })
        .catch(function(error) {
            console.error('Error:', error);
            showAlert('삭제 중 오류가 발생했습니다.', 'danger');
        });
    };

    window.saveEdit = function() {
        var data = {
            id: parseInt($('#edit_id').val()),
            member_code: $('#edit_member_code').val().trim(),
            datacenter_code: $('input[name="edit_datacenter_code"]:checked').val() || null,
            provider: $('input[name="edit_provider"]:checked').val() || null,
            circuit_id: $('#edit_circuit_id').val().trim() || null,
            nni_id: $('#edit_nni_id').val().trim() || null,
            env: $('input[name="edit_env"]:checked').val() || null,
            usage: $('#edit_usage').val().trim() || null,
            product: $('#edit_product').val().trim() || null,
            bandwidth: $('#edit_bandwidth').val().trim() || null,
            additional_circuit: $('#edit_additional_circuit').is(':checked'),
            cot_device: $('#edit_cot_device').val().trim() || null,
            rt_device: $('#edit_rt_device').val().trim() || null,
            phase: parseInt($('#edit_phase').val()) || null,
            fee_code: $('#edit_fee_code').val() || null,
            contract_date: $('#edit_contract_date').val() || null,
            expiry_date: $('#edit_expiry_date').val() || null,
            contract_period: $('#edit_contract_period').val() || null,
            report_number: $('#edit_report_number').val().trim() || null,
            comments: $('#edit_comments').val().trim() || null
        };

        if (!data.member_code) {
            showAlert('회원사코드는 필수 입력항목입니다.', 'warning');
            return;
        }

        fetch('/circuits/update_circuit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(function(response) { return response.json(); })
        .then(function(result) {
            if (result.success) {
                showAlert('수정이 완료되었습니다.', 'success');
                bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
                refreshTable();
            } else {
                showAlert('수정 실패: ' + result.error, 'danger');
            }
        })
        .catch(function(error) {
            console.error('Error:', error);
            showAlert('수정 중 오류가 발생했습니다.', 'danger');
        });
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

        // 토스트 컨테이너 생성 (없으면)
        if (!$('#toastContainer').length) {
            $('body').append('<div id="toastContainer" class="toast-container position-fixed top-0 end-0 p-3" style="z-index: 9999;"></div>');
        }

        var toastId = 'toast_' + Date.now();
        var toastHtml = '<div id="' + toastId + '" class="toast align-items-center border-0 shadow-lg" role="alert" aria-live="assertive" aria-atomic="true" data-bs-delay="3000" style="border-radius: 10px; overflow: hidden; border-left: 4px solid ' + color + ' !important;">' +
            '<div class="toast-header border-0" style="padding: 10px 14px;">' +
            '<i class="fas ' + icon + ' me-2" style="color: ' + color + '; font-size: 0.9rem;"></i>' +
            '<strong class="me-auto" style="font-size: 0.8rem; color: #1e293b;">' + title + '</strong>' +
            '<small class="text-muted" style="font-size: 0.65rem;">방금</small>' +
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

    // 회선 현황 분석 모달
    window.showAnalysisModal = function() {
        var data = circuitsTable.rows().data().toArray();
        if (!data.length) { showAlert('데이터가 없습니다.', 'warning'); return; }

        // 회원사별 집계
        var members = {};
        var productSet = {};
        data.forEach(function(r) {
            var key = r.member_code || '-';
            if (!members[key]) {
                members[key] = { company_name: r.company_name || '-', dc: {}, usage: {}, product: {}, total: 0 };
            }
            var m = members[key];
            m.total++;
            var dc = r.datacenter_code || '-';
            m.dc[dc] = (m.dc[dc] || 0) + 1;
            var u = r.usage || '-';
            m.usage[u] = (m.usage[u] || 0) + 1;
            var p = r.product || '-';
            m.product[p] = (m.product[p] || 0) + 1;
            productSet[p] = true;
        });

        var memberKeys = Object.keys(members).sort(function(a, b) {
            var na = members[a].total, nb = members[b].total;
            return nb - na;
        });
        var productOrder = ['NXTA-10', 'NXTA-05', 'NXTA-03', 'NXTB-10', 'NXTB-05', 'NXTB-03'];
        var products = productOrder.filter(function(p) { return productSet[p]; });
        Object.keys(productSet).forEach(function(p) {
            if (p !== '-' && products.indexOf(p) === -1) products.push(p);
        });

        // 셀 렌더 헬퍼
        function cell(val, isTotal) {
            if (!val) return '<td class="text-center py-2" style="color: #cbd5e1;">-</td>';
            if (isTotal) return '<td class="text-center py-2" style="font-weight: 700; color: #1e293b; background: #f1f5f9;">' + val + '</td>';
            return '<td class="text-center py-2" style="color: #334155;">' + val + '</td>';
        }

        // DC코드별
        var dcTotals = { DC1: 0, DC2: 0, DC3: 0, DR: 0, sum: 0 };
        var dcHtml = '';
        memberKeys.forEach(function(key) {
            var m = members[key];
            var dc1 = m.dc['DC1'] || 0, dc2 = m.dc['DC2'] || 0, dc3 = m.dc['DC3'] || 0, dr = m.dc['DR'] || 0;
            dcTotals.DC1 += dc1; dcTotals.DC2 += dc2; dcTotals.DC3 += dc3; dcTotals.DR += dr; dcTotals.sum += m.total;
            dcHtml += '<tr>';
            dcHtml += '<td class="text-center py-2 fw-semibold" style="color: #6366f1;">' + key + '</td>';
            dcHtml += '<td class="text-center py-2" style="color: #475569;">' + m.company_name + '</td>';
            dcHtml += cell(dc1) + cell(dc2) + cell(dc3) + cell(dr) + cell(m.total, true);
            dcHtml += '</tr>';
        });
        $('#analysisDcBody').html(dcHtml);
        $('#analysisDcFooter').html(
            '<td class="text-center py-2" colspan="2" style="color: #1e293b;">합계</td>' +
            cell(dcTotals.DC1, true) + cell(dcTotals.DC2, true) + cell(dcTotals.DC3, true) + cell(dcTotals.DR, true) +
            '<td class="text-center py-2" style="font-weight: 700; color: #fff; background: #475569;">' + dcTotals.sum + '</td>'
        );

        // 용도별
        var usageTotals = { ORD: 0, MPR: 0, MGT: 0, sum: 0 };
        var usageHtml = '';
        memberKeys.forEach(function(key) {
            var m = members[key];
            var ord = m.usage['ORD'] || 0, mpr = m.usage['MPR'] || 0, mgt = m.usage['MGT'] || 0;
            usageTotals.ORD += ord; usageTotals.MPR += mpr; usageTotals.MGT += mgt; usageTotals.sum += m.total;
            usageHtml += '<tr>';
            usageHtml += '<td class="text-center py-2 fw-semibold" style="color: #6366f1;">' + key + '</td>';
            usageHtml += '<td class="text-center py-2" style="color: #475569;">' + m.company_name + '</td>';
            usageHtml += cell(ord) + cell(mpr) + cell(mgt) + cell(m.total, true);
            usageHtml += '</tr>';
        });
        $('#analysisUsageBody').html(usageHtml);
        $('#analysisUsageFooter').html(
            '<td class="text-center py-2" colspan="2" style="color: #1e293b;">합계</td>' +
            cell(usageTotals.ORD, true) + cell(usageTotals.MPR, true) + cell(usageTotals.MGT, true) +
            '<td class="text-center py-2" style="font-weight: 700; color: #fff; background: #475569;">' + usageTotals.sum + '</td>'
        );

        // 상품별
        var prodColors = ['#6366f1','#0ea5e9','#10b981','#f59e0b','#ef4444','#8b5cf6','#ec4899','#14b8a6'];
        var headerHtml = '<th class="text-center py-2" style="color: #475569; font-weight: 700;">회원사코드</th>';
        headerHtml += '<th class="text-center py-2" style="color: #475569; font-weight: 700;">회사명</th>';
        var prodTotals = {};
        products.forEach(function(p, i) {
            prodTotals[p] = 0;
            headerHtml += '<th class="text-center py-2" style="color: ' + prodColors[i % prodColors.length] + '; font-weight: 700;">' + p + '</th>';
        });
        headerHtml += '<th class="text-center py-2" style="color: #1e293b; font-weight: 700; background: #e2e8f0;">합계</th>';
        $('#analysisProductHeader').html(headerHtml);

        var prodBodyHtml = '';
        var prodSum = 0;
        memberKeys.forEach(function(key) {
            var m = members[key];
            prodBodyHtml += '<tr>';
            prodBodyHtml += '<td class="text-center py-2 fw-semibold" style="color: #6366f1;">' + key + '</td>';
            prodBodyHtml += '<td class="text-center py-2" style="color: #475569;">' + m.company_name + '</td>';
            products.forEach(function(p) {
                var v = m.product[p] || 0;
                prodTotals[p] += v;
                prodBodyHtml += cell(v);
            });
            prodBodyHtml += cell(m.total, true);
            prodSum += m.total;
            prodBodyHtml += '</tr>';
        });
        $('#analysisProductBody').html(prodBodyHtml);
        var prodFooterHtml = '<td class="text-center py-2" colspan="2" style="color: #1e293b;">합계</td>';
        products.forEach(function(p) { prodFooterHtml += cell(prodTotals[p], true); });
        prodFooterHtml += '<td class="text-center py-2" style="font-weight: 700; color: #fff; background: #475569;">' + prodSum + '</td>';
        $('#analysisProductFooter').html(prodFooterHtml);

        // 통합 현황 (회원사 × DC코드 × 용도(환경별) / 주문회선(환경별) / 시세상품(환경별))
        var dcCodes = ['DC1', 'DC2', 'DC3', 'DR'];
        var usages = ['ORD', 'MPR', 'MGT'];
        var subEnvs = ['PR', 'TS', 'DR'];

        // 상품을 주문회선(대역폭)과 시세상품으로 분리
        var ordProducts = products.filter(function(p) { return /^\d+M$/.test(p); });
        var mprProducts = products.filter(function(p) { return p !== '-' && p !== 'MGT' && !/^\d+M$/.test(p); });
        // 주문회선 정렬 (숫자 기준)
        ordProducts.sort(function(a, b) { return parseInt(a) - parseInt(b); });

        // 회원사+DC별 집계 (용도×환경, 상품×환경 포함)
        var detail = {};
        data.forEach(function(r) {
            var mk = r.member_code || '-';
            var dc = r.datacenter_code || '-';
            var key = mk + '|' + dc;
            if (!detail[key]) {
                detail[key] = { member_code: mk, company_name: r.company_name || '-', dc: dc, ue: {}, pe: {}, total: 0 };
            }
            var d = detail[key];
            d.total++;
            var u = r.usage || '-';
            var e = r.env || '-';
            var p = r.product || '-';
            // 용도×환경
            if (!d.ue[u]) d.ue[u] = {};
            d.ue[u][e] = (d.ue[u][e] || 0) + 1;
            // 상품×환경
            if (!d.pe[p]) d.pe[p] = {};
            d.pe[p][e] = (d.pe[p][e] || 0) + 1;
        });

        // 헤더 (3행: 그룹 → 상품명 → 환경)
        var usageColCount = subEnvs.length * 2 + 1; // ORD(3) + MPR(3) + MGT(1)
        var ordColCount = ordProducts.length > 0 ? ordProducts.length * subEnvs.length : 0;
        var mprColCount = mprProducts.length > 0 ? mprProducts.length * subEnvs.length : 0;

        var detailHead = '<tr style="background: #1e293b;">';
        detailHead += '<th class="text-center py-2 text-white" rowspan="3" style="vertical-align: middle; font-weight: 700; border-right: 2px solid #475569;">회원사코드</th>';
        detailHead += '<th class="text-center py-2 text-white" rowspan="3" style="vertical-align: middle; font-weight: 700; border-right: 2px solid #475569;">회사명</th>';
        detailHead += '<th class="text-center py-2 text-white" rowspan="3" style="vertical-align: middle; font-weight: 700; border-right: 2px solid #475569;">DC</th>';
        detailHead += '<th class="text-center py-2" colspan="' + usageColCount + '" style="color: #93c5fd; font-weight: 700; border-right: 2px solid #475569; border-bottom: 1px solid #475569;">회선요약</th>';
        if (ordColCount > 0) {
            detailHead += '<th class="text-center py-2" colspan="' + ordColCount + '" style="color: #fbbf24; font-weight: 700; border-right: 2px solid #475569; border-bottom: 1px solid #475569;">주문회선</th>';
        }
        if (mprColCount > 0) {
            detailHead += '<th class="text-center py-2" colspan="' + mprColCount + '" style="color: #86efac; font-weight: 700; border-right: 2px solid #475569; border-bottom: 1px solid #475569;">시세상품</th>';
        }
        detailHead += '<th class="text-center py-2 text-white" rowspan="3" style="vertical-align: middle; font-weight: 700; background: #475569;">합계</th>';
        detailHead += '</tr>';

        // 2행: 용도명, 상품명
        var ordPColors = ['#fbbf24','#fcd34d','#fde68a','#fed7aa','#fdba74','#fb923c'];
        var mprPColors = ['#86efac','#6ee7b7','#5eead4','#67e8f9','#7dd3fc','#93c5fd','#a5b4fc','#c4b5fd'];
        detailHead += '<tr style="background: #334155;">';
        detailHead += '<th class="text-center py-1" colspan="' + subEnvs.length + '" style="color: #93c5fd; font-weight: 600; font-size: 0.7rem; border-bottom: 1px solid #475569; border-right: 1px solid #475569;">ORD</th>';
        detailHead += '<th class="text-center py-1" colspan="' + subEnvs.length + '" style="color: #67e8f9; font-weight: 600; font-size: 0.7rem; border-bottom: 1px solid #475569; border-right: 1px solid #475569;">MPR</th>';
        detailHead += '<th class="text-center py-1" rowspan="2" style="color: #6ee7b7; font-weight: 600; font-size: 0.7rem; vertical-align: middle; border-right: 2px solid #475569;">MGT</th>';
        ordProducts.forEach(function(p, i) {
            var borderR = i === ordProducts.length - 1 && mprProducts.length === 0 ? '2px solid #475569' : '1px solid #475569';
            if (i === ordProducts.length - 1) borderR = '2px solid #475569';
            detailHead += '<th class="text-center py-1" colspan="' + subEnvs.length + '" style="color: ' + ordPColors[i % ordPColors.length] + '; font-weight: 600; font-size: 0.7rem; border-bottom: 1px solid #475569; border-right: ' + borderR + ';">' + p + '</th>';
        });
        mprProducts.forEach(function(p, i) {
            var borderR = i === mprProducts.length - 1 ? '2px solid #475569' : '1px solid #475569';
            detailHead += '<th class="text-center py-1" colspan="' + subEnvs.length + '" style="color: ' + mprPColors[i % mprPColors.length] + '; font-weight: 600; font-size: 0.7rem; border-bottom: 1px solid #475569; border-right: ' + borderR + ';">' + p + '</th>';
        });
        detailHead += '</tr>';

        // 3행: 환경 서브 헤더
        var envColors = { PR: '#4ade80', TS: '#60a5fa', DR: '#fb923c' };
        detailHead += '<tr style="background: #475569;">';
        // ORD 환경
        subEnvs.forEach(function(e, i) {
            detailHead += '<th class="text-center py-1" style="color: ' + envColors[e] + '; font-weight: 600; font-size: 0.6rem;' + (i === subEnvs.length - 1 ? ' border-right: 1px solid #64748b;' : '') + '">' + e + '</th>';
        });
        // MPR 환경
        subEnvs.forEach(function(e, i) {
            detailHead += '<th class="text-center py-1" style="color: ' + envColors[e] + '; font-weight: 600; font-size: 0.6rem;' + (i === subEnvs.length - 1 ? ' border-right: 1px solid #64748b;' : '') + '">' + e + '</th>';
        });
        // MGT는 rowspan=2로 이미 처리
        // 주문회선별 환경
        ordProducts.forEach(function(p, pi) {
            var borderR = pi === ordProducts.length - 1 ? '2px solid #64748b' : '1px solid #64748b';
            subEnvs.forEach(function(e, ei) {
                detailHead += '<th class="text-center py-1" style="color: ' + envColors[e] + '; font-weight: 600; font-size: 0.6rem;' + (ei === subEnvs.length - 1 ? ' border-right: ' + borderR + ';' : '') + '">' + e + '</th>';
            });
        });
        // 시세상품별 환경
        mprProducts.forEach(function(p, pi) {
            var borderR = pi === mprProducts.length - 1 ? '2px solid #64748b' : '1px solid #64748b';
            subEnvs.forEach(function(e, ei) {
                detailHead += '<th class="text-center py-1" style="color: ' + envColors[e] + '; font-weight: 600; font-size: 0.6rem;' + (ei === subEnvs.length - 1 ? ' border-right: ' + borderR + ';' : '') + '">' + e + '</th>';
            });
        });
        detailHead += '</tr>';
        $('#analysisDetailHeader').html(detailHead);

        // 본문
        var allDetailProducts = ordProducts.concat(mprProducts);
        var detailBodyHtml = '';
        var detailTotals = { ue: {}, pe: {}, sum: 0 };
        usages.forEach(function(u) {
            detailTotals.ue[u] = {};
            subEnvs.forEach(function(e) { detailTotals.ue[u][e] = 0; });
            if (u === 'MGT') detailTotals.ue[u]._all = 0;
        });
        allDetailProducts.forEach(function(p) {
            detailTotals.pe[p] = {};
            subEnvs.forEach(function(e) { detailTotals.pe[p][e] = 0; });
        });

        var prevMember = '';
        var rowIdx = 0;
        var dcSortOrder = { 'DC1': 1, 'DC2': 2, 'DC3': 3, 'DR': 4 };
        var detailKeys = Object.keys(detail).sort(function(a, b) {
            var da = detail[a], db = detail[b];
            var totalA = members[da.member_code] ? members[da.member_code].total : 0;
            var totalB = members[db.member_code] ? members[db.member_code].total : 0;
            if (da.member_code !== db.member_code) {
                if (totalB !== totalA) return totalB - totalA;
                return da.member_code.localeCompare(db.member_code);
            }
            return (dcSortOrder[da.dc] || 99) - (dcSortOrder[db.dc] || 99);
        });

        var memberRowCount = {};
        detailKeys.forEach(function(key) {
            var mk = detail[key].member_code;
            memberRowCount[mk] = (memberRowCount[mk] || 0) + 1;
        });

        detailKeys.forEach(function(key) {
            var d = detail[key];
            var isNewMember = d.member_code !== prevMember;
            if (isNewMember) { rowIdx++; prevMember = d.member_code; }
            var bgColor = rowIdx % 2 === 0 ? '#ffffff' : '#f8fafc';
            var borderTop = isNewMember && rowIdx > 1 ? 'border-top: 2px solid #e2e8f0;' : '';
            var rspan = memberRowCount[d.member_code] || 1;

            detailBodyHtml += '<tr data-member="' + d.member_code + '" data-company="' + d.company_name + '" style="background: ' + bgColor + '; ' + borderTop + '">';
            if (isNewMember) {
                detailBodyHtml += '<td class="text-center py-2 fw-bold" rowspan="' + rspan + '" style="color: #6366f1; border-right: 1px solid #f1f5f9; vertical-align: middle;">' + d.member_code + '</td>';
                detailBodyHtml += '<td class="text-center py-2" rowspan="' + rspan + '" style="color: #475569; border-right: 1px solid #f1f5f9; vertical-align: middle;">' + d.company_name + '</td>';
            }
            detailBodyHtml += '<td class="text-center py-2 fw-semibold" style="border-right: 2px solid #e2e8f0;">';
            var dcBadgeColors = { DC1: '#6366f1', DC2: '#0ea5e9', DC3: '#10b981', DR: '#f59e0b' };
            detailBodyHtml += '<span style="display: inline-block; padding: 1px 8px; border-radius: 4px; font-size: 0.65rem; color: #fff; background: ' + (dcBadgeColors[d.dc] || '#94a3b8') + ';">' + d.dc + '</span></td>';

            // ORD × 환경
            subEnvs.forEach(function(e, ei) {
                var v = (d.ue['ORD'] && d.ue['ORD'][e]) || 0;
                detailTotals.ue['ORD'][e] += v;
                detailBodyHtml += '<td class="text-center py-2" style="color: ' + (v ? '#334155' : '#cbd5e1') + ';' + (ei === subEnvs.length - 1 ? ' border-right: 1px solid #e2e8f0;' : '') + '">' + (v || '-') + '</td>';
            });
            // MPR × 환경
            subEnvs.forEach(function(e, ei) {
                var v = (d.ue['MPR'] && d.ue['MPR'][e]) || 0;
                detailTotals.ue['MPR'][e] += v;
                detailBodyHtml += '<td class="text-center py-2" style="color: ' + (v ? '#334155' : '#cbd5e1') + ';' + (ei === subEnvs.length - 1 ? ' border-right: 1px solid #e2e8f0;' : '') + '">' + (v || '-') + '</td>';
            });
            // MGT (환경 구분 없음)
            var mgtVal = 0;
            if (d.ue['MGT']) {
                Object.keys(d.ue['MGT']).forEach(function(e) { mgtVal += d.ue['MGT'][e]; });
            }
            detailTotals.ue['MGT']._all += mgtVal;
            detailBodyHtml += '<td class="text-center py-2" style="color: ' + (mgtVal ? '#334155' : '#cbd5e1') + '; border-right: 2px solid #e2e8f0;">' + (mgtVal || '-') + '</td>';

            // 주문회선(ORD) 상품 × 환경
            ordProducts.forEach(function(p, pi) {
                var borderR = pi === ordProducts.length - 1 ? '2px solid #e2e8f0' : '1px solid #e2e8f0';
                subEnvs.forEach(function(e, ei) {
                    var v = (d.pe[p] && d.pe[p][e]) || 0;
                    detailTotals.pe[p][e] += v;
                    detailBodyHtml += '<td class="text-center py-2" style="color: ' + (v ? '#334155' : '#cbd5e1') + ';' + (ei === subEnvs.length - 1 ? ' border-right: ' + borderR + ';' : '') + '">' + (v || '-') + '</td>';
                });
            });
            // 시세상품(MPR) 상품 × 환경
            mprProducts.forEach(function(p, pi) {
                var borderR = pi === mprProducts.length - 1 ? '2px solid #e2e8f0' : '1px solid #e2e8f0';
                subEnvs.forEach(function(e, ei) {
                    var v = (d.pe[p] && d.pe[p][e]) || 0;
                    detailTotals.pe[p][e] += v;
                    detailBodyHtml += '<td class="text-center py-2" style="color: ' + (v ? '#334155' : '#cbd5e1') + ';' + (ei === subEnvs.length - 1 ? ' border-right: ' + borderR + ';' : '') + '">' + (v || '-') + '</td>';
                });
            });

            detailTotals.sum += d.total;
            detailBodyHtml += '<td class="text-center py-2 fw-bold" style="color: #1e293b; background: #f1f5f9;">' + d.total + '</td>';
            detailBodyHtml += '</tr>';
        });
        $('#analysisDetailBody').html(detailBodyHtml);

        // 푸터
        var detailFooterHtml = '<td class="text-center py-2" colspan="3" style="color: #1e293b; border-right: 2px solid #cbd5e1;">합계</td>';
        // ORD 환경별 합계
        subEnvs.forEach(function(e, ei) {
            detailFooterHtml += '<td class="text-center py-2" style="color: #1e293b; font-weight: 700;' + (ei === subEnvs.length - 1 ? ' border-right: 1px solid #cbd5e1;' : '') + '">' + detailTotals.ue['ORD'][e] + '</td>';
        });
        // MPR 환경별 합계
        subEnvs.forEach(function(e, ei) {
            detailFooterHtml += '<td class="text-center py-2" style="color: #1e293b; font-weight: 700;' + (ei === subEnvs.length - 1 ? ' border-right: 1px solid #cbd5e1;' : '') + '">' + detailTotals.ue['MPR'][e] + '</td>';
        });
        // MGT 합계
        detailFooterHtml += '<td class="text-center py-2" style="color: #1e293b; font-weight: 700; border-right: 2px solid #cbd5e1;">' + detailTotals.ue['MGT']._all + '</td>';
        // 주문회선 상품별 환경 합계
        ordProducts.forEach(function(p, pi) {
            var borderR = pi === ordProducts.length - 1 ? '2px solid #cbd5e1' : '1px solid #cbd5e1';
            subEnvs.forEach(function(e, ei) {
                detailFooterHtml += '<td class="text-center py-2" style="color: #1e293b; font-weight: 700;' + (ei === subEnvs.length - 1 ? ' border-right: ' + borderR + ';' : '') + '">' + detailTotals.pe[p][e] + '</td>';
            });
        });
        // 시세상품별 환경 합계
        mprProducts.forEach(function(p, pi) {
            var borderR = pi === mprProducts.length - 1 ? '2px solid #cbd5e1' : '1px solid #cbd5e1';
            subEnvs.forEach(function(e, ei) {
                detailFooterHtml += '<td class="text-center py-2" style="color: #1e293b; font-weight: 700;' + (ei === subEnvs.length - 1 ? ' border-right: ' + borderR + ';' : '') + '">' + detailTotals.pe[p][e] + '</td>';
            });
        });
        detailFooterHtml += '<td class="text-center py-2" style="font-weight: 700; color: #fff; background: #475569;">' + detailTotals.sum + '</td>';
        $('#analysisDetailFooter').html(detailFooterHtml);

        // 검색 초기화
        $('#analysisSearch').val('');

        var modal = new bootstrap.Modal(document.getElementById('analysisModal'));
        modal.show();
    };

    // 분석 모달 검색 기능 (회원사 단위)
    $(document).on('input', '#analysisSearch', function() {
        var keyword = $(this).val().toLowerCase();
        if (keyword === '') {
            $('#analysisTabContent tbody tr').show();
            return;
        }
        // 통합 현황: 회원사 단위 그룹 필터 (rowspan 보호)
        var matchedMembers = {};
        $('#panel-detail tbody tr').each(function() {
            var mk = $(this).attr('data-member') || '';
            var cn = $(this).attr('data-company') || '';
            if (mk.toLowerCase().indexOf(keyword) !== -1 || cn.toLowerCase().indexOf(keyword) !== -1) {
                matchedMembers[mk] = true;
            }
        });
        $('#panel-detail tbody tr').each(function() {
            var mk = $(this).attr('data-member') || '';
            if (matchedMembers[mk]) {
                $(this).show();
            } else {
                $(this).hide();
            }
        });
        // 다른 탭: 텍스트 기반 필터
        $('#panel-dc tbody tr, #panel-usage tbody tr, #panel-product tbody tr').each(function() {
            var text = $(this).text().toLowerCase();
            if (text.indexOf(keyword) !== -1) {
                $(this).show();
            } else {
                $(this).hide();
            }
        });
    });

    $(document).ready(function() {
        initTable();
        loadMemberCodeOptions();
        loadProductOptions();
        loadFeeCodeOptions();

        // 용도 변경 시 상품 옵션 + 대역폭 + 추가회선 동적 변경
        $('#create_usage').on('change', function() {
            var val = $(this).val();
            updateProductByUsage(val, '#create_product');
            updateBandwidthByUsage(val, '#create_bandwidth');
            updateAdditionalCircuitByUsage(val, '#create_additional_circuit');
            filterFeeCodeByUsage(val, '#create_fee_code');
        });
        $('#edit_usage').on('change', function() {
            var val = $(this).val();
            updateProductByUsage(val, '#edit_product');
            updateBandwidthByUsage(val, '#edit_bandwidth');
            updateAdditionalCircuitByUsage(val, '#edit_additional_circuit');
            filterFeeCodeByUsage(val, '#edit_fee_code');
        });

        // 용도 미선택 시 상품 클릭 경고
        $('#create_product, #edit_product').on('mousedown', function(e) {
            var prefix = this.id.replace('_product', '');
            var usage = $('#' + prefix + '_usage').val();
            if (!usage) {
                e.preventDefault();
                showAlert('용도를 먼저 선택해주세요.', 'warning');
            }
        });

        // 요약 카드 호버 애니메이션
        $('#summaryCards > div > div').css('transition', 'transform 0.25s ease, box-shadow 0.25s ease');
        $('#summaryCards > div > div').on('mouseenter', function() {
            $(this).css({ 'transform': 'translateY(-4px) scale(1.02)', 'box-shadow': '0 8px 25px rgba(0,0,0,0.2)' });
        }).on('mouseleave', function() {
            $(this).css({ 'transform': 'translateY(0) scale(1)', 'box-shadow': '' });
        });
    });

}));
