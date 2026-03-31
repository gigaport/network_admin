(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
})((function () {
    'use strict';

    var infoCompanyCircuitsTable = null;

    // 요약 통계 업데이트
    function updateSummary(data) {
        var members = {};
        var lgu = 0, skb = 0, ktc = 0, pr = 0, dr = 0, ts = 0;
        var mkd = 0, mgt = 0, expiring = 0;
        var dc1 = 0, dc2 = 0, dcDr = 0;
        var today = new Date();
        var d90 = new Date(today.getTime() + 90 * 24 * 60 * 60 * 1000);
        data.forEach(function(r) {
            if (r.member_code) members[r.member_code] = true;
            if (r.provider === 'LGU') lgu++;
            else if (r.provider === 'SKB') skb++;
            else if (r.provider === 'KTC') ktc++;
            if (r.env === 'PR') pr++;
            else if (r.env === 'DR') dr++;
            else if (r.env === 'TS') ts++;
            if (r.usage === 'MKD') mkd++;
            else if (r.usage === 'MGT') mgt++;
            if (r.datacenter_code === 'DC1') dc1++;
            else if (r.datacenter_code === 'DC2') dc2++;
            else if (r.datacenter_code === 'DR') dcDr++;
            if (r.expiry_date) {
                var exp = new Date(r.expiry_date);
                if (exp >= today && exp <= d90) expiring++;
            }
        });
        $('#stat_total').text(data.length.toLocaleString());
        $('#stat_members').text(Object.keys(members).length.toLocaleString());
        $('#stat_lgu').text(lgu); $('#stat_skb').text(skb); $('#stat_ktc').text(ktc);
        $('#stat_pr').text(pr); $('#stat_dr').text(dr); $('#stat_ts').text(ts);
        $('#stat_mkd').text(mkd); $('#stat_mgt').text(mgt);
        $('#stat_expiring').text(expiring);
        $('#stat_dc1').text(dc1); $('#stat_dc2').text(dc2); $('#stat_dc_dr').text(dcDr);

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


    // sise_products 목록 로드 (MKD용 캐시)
    var mkdProductOptions = '<option value="">선택</option>';
    function loadProductOptions() {
        fetch('/sise_products/get_products')
            .then(function(res) { return res.json(); })
            .then(function(result) {
                if (result.success && result.data) {
                    mkdProductOptions = '<option value="">선택</option>';
                    result.data.forEach(function(p) {
                        mkdProductOptions += '<option value="' + p.product_name + '">' + p.product_name + '</option>';
                    });
                }
            })
            .catch(function(err) { console.error('상품 목록 로드 실패:', err); });
    }

    var allFeeData = [];

    function loadFeeCodeOptions() {
        fetch('/info_fee_schedule/get_info_fee_schedule')
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
        if (usage === 'MKD') {
            options = mkdProductOptions;
        } else if (usage === 'MGT') {
            options += '<option value="MGT">MGT</option>';
        }
        $(productSelect).html(options);
    }

    var allBandwidthOptions = '<option value="">선택</option>' +
        '<option value="1M">1M</option><option value="20M">20M</option>' +
        '<option value="100M">100M</option><option value="110M">110M</option>';

    function updateBandwidthByUsage(usage, bwSelect) {
        if (usage === 'MKD') {
            $(bwSelect).html(allBandwidthOptions);
        } else if (usage === 'MGT') {
            $(bwSelect).html('<option value="1M">1M</option>').val('1M');
        } else {
            var current = $(bwSelect).val();
            $(bwSelect).html(allBandwidthOptions);
            if (current) $(bwSelect).val(current);
        }
    }

    // 용도에 따른 추가회선 체크박스 활성/비활성화
    function updateAdditionalCircuitByUsage(usage, checkboxId) {
        var $cb = $(checkboxId);
        $cb.prop('disabled', false);
    }

    var initTable = function() {
        infoCompanyCircuitsTable = $('#infoCompanyCircuitsTable').DataTable({
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
                    title: '정보이용사_회선내역_' + new Date().toISOString().slice(0,10),
                    exportOptions: {
                        columns: ':visible',
                        modifier: { page: 'all' }
                    }
                },
                {
                    extend: 'csv',
                    text: '<i class="fa-solid fa-file-csv me-2"></i>CSV',
                    className: 'btn btn-info btn-sm',
                    title: '정보이용사_회선내역_' + new Date().toISOString().slice(0,10),
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
                url: '/info_company_circuits/get_info_company_circuits',
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
                { data: 'company_name' },
                { data: 'datacenter_code' },
                { data: 'summary_address' },
                { data: 'gubn' },
                { data: 'provider' },
                { data: 'circuit_id' },
                { data: 'env' },
                { data: 'usage' },
                { data: 'product' },
                { data: 'bandwidth' },
                { data: 'additional_circuit' },
                { data: 'phase' },
                { data: 'fee_price' },
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
                    className: 'text-center py-2 align-middle fw-semibold',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-primary">' + data + '</span>';
                    }
                },
                {
                    targets: 1, // 회사명
                    width: '6%',
                    className: 'text-center py-2 align-middle fw-semibold'
                },
                {
                    targets: 2, // DC코드
                    width: '3%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        var badgeClass = 'badge-phoenix-secondary';
                        if (data === 'DC1') badgeClass = 'badge-phoenix-primary';
                        else if (data === 'DC2') badgeClass = 'badge-phoenix-info';
                        else if (data === 'DR') badgeClass = 'badge-phoenix-warning';
                        return '<span class="badge badge-phoenix ' + badgeClass + '">' + data + '</span>';
                    }
                },
                {
                    targets: 3, // 요약주소
                    width: '8%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        return '<span title="' + data + '">' + data + '</span>';
                    }
                },
                {
                    targets: 4, // 구분
                    width: '3%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        var badgeClass = 'badge-phoenix-secondary';
                        if (data === '메인') badgeClass = 'badge-phoenix-primary';
                        else if (data === '백업') badgeClass = 'badge-phoenix-success';
                        else if (data === '테스트') badgeClass = 'badge-phoenix-warning';
                        else if (data === 'DR') badgeClass = 'badge-phoenix-danger';
                        return '<span class="badge badge-phoenix ' + badgeClass + '">' + data + '</span>';
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
                    targets: 7, // 환경
                    width: '3%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        var badgeClass = 'badge-phoenix-secondary';
                        if (data === 'PR') badgeClass = 'badge-phoenix-success';
                        else if (data === 'DR') badgeClass = 'badge-phoenix-warning';
                        else if (data === 'TS') badgeClass = 'badge-phoenix-info';
                        return '<span class="badge badge-phoenix ' + badgeClass + '">' + data + '</span>';
                    }
                },
                {
                    targets: 8, // 용도
                    width: '3%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) { return data || '-'; }
                },
                {
                    targets: 9, // 상품
                    width: '5%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) { return data || '-'; }
                },
                {
                    targets: 10, // 대역폭
                    width: '3%',
                    className: 'text-center py-2 align-middle fw-semibold',
                    render: function(data) { return data || '-'; }
                },
                {
                    targets: 11, // 추가회선
                    width: '3%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (data === true) return '<span class="badge badge-phoenix badge-phoenix-info">Y</span>';
                        return '<span class="text-muted">N</span>';
                    }
                },
                {
                    targets: 12, // 가입 Phase
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
                    targets: 13, // 요금
                    width: '4%',
                    className: 'text-end py-2 align-middle fw-semibold',
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return Number(data).toLocaleString() + '원';
                    }
                },
                {
                    targets: 14, // 계약일
                    width: '5%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) { return data || '-'; }
                },
                {
                    targets: 15, // 만료일
                    width: '5%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) { return data || '-'; }
                },
                {
                    targets: 16, // 약정기간
                    width: '3%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data && data !== 0) return '-';
                        return data + '개월';
                    }
                },
                {
                    targets: 17, // 문서번호
                    width: '6%',
                    className: 'text-center py-2 align-middle',
                    render: function(data) {
                        if (!data) return '-';
                        if (data.length > 20) {
                            return '<span title="' + data + '">' + data.substring(0, 20) + '...</span>';
                        }
                        return data;
                    }
                },
                {
                    targets: 18, // 비고
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
        $('#infoCompanyCircuitsTable tbody').css('cursor', 'pointer');

        // tfoot의 각 열에 검색 입력 필드 추가
        $('#infoCompanyCircuitsTable tfoot th').each(function(i) {
            var title = $(this).text();
            $(this).css({'font-size': '0.7rem', 'white-space': 'nowrap'});
            $(this).html('<input type="text" class="form-control form-control-sm" placeholder="' + title + ' 검색" style="font-size:0.65rem; padding:2px 4px;" />');
        });

        // 개별 열 검색 기능 적용
        infoCompanyCircuitsTable.columns().every(function() {
            var that = this;
            $('input', this.footer()).on('keyup change', function() {
                if (that.search() !== this.value) {
                    that.search(this.value).draw();
                }
            });
        });

        // 행 클릭 시 상세보기 팝업
        $('#infoCompanyCircuitsTable tbody').on('click', 'tr', function() {
            var data = infoCompanyCircuitsTable.row(this).data();
            if (!data) return;
            showDetailModal(data);
        });
    };

    window.resetFilters = function() {
        $('#infoCompanyCircuitsTable tfoot input').val('');
        if (infoCompanyCircuitsTable) {
            infoCompanyCircuitsTable.columns().search('').draw();
        }
    };

    window.refreshTable = function() {
        var spinner = $('<div class="position-fixed top-50 start-50 translate-middle" style="z-index: 10000;">' +
            '<div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">' +
            '<span class="visually-hidden">Loading...</span>' +
            '</div></div>');
        $('body').append(spinner);

        resetFilters();
        if (infoCompanyCircuitsTable) {
            infoCompanyCircuitsTable.ajax.reload(function() {
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
            gubn: $('#create_gubn').val() || null,
            provider: $('input[name="create_provider"]:checked').val() || null,
            circuit_id: $('#create_circuit_id').val().trim() || null,
            env: $('input[name="create_env"]:checked').val() || null,
            usage: $('#create_usage').val().trim() || null,
            product: $('#create_product').val().trim() || null,
            bandwidth: $('#create_bandwidth').val().trim() || null,
            additional_circuit: $('#create_additional_circuit').is(':checked'),
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

        fetch('/info_company_circuits/create_info_company_circuit', {
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
            'member_code', 'company_name', 'datacenter_code', 'summary_address', 'gubn',
            'provider', 'circuit_id',
            'env', 'usage', 'product', 'bandwidth',
            'contract_date', 'expiry_date',
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
        var usageColors = { 'MKD': ['#2563eb','#eff6ff'], 'MGT': ['#7c3aed','#f5f3ff'] };
        var uc = usageColors[circuit.usage] || ['#d97706','#fffbeb'];
        if (circuit.usage) badges += makeBadge(circuit.usage, uc[0], uc[1]);
        if (circuit.env) badges += makeBadge(circuit.env, '#0369a1', '#f0f9ff');
        if (circuit.gubn) badges += makeBadge(circuit.gubn, '#7c3aed', '#f5f3ff');
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
        var rowData = infoCompanyCircuitsTable.rows().data().toArray();
        var circuit = rowData.find(function(item) { return item.id === id; });
        if (!circuit) return;

        bootstrap.Modal.getInstance(document.getElementById('detailModal')).hide();

        $('#edit_id').val(circuit.id);
        $('#edit_member_code').val(circuit.member_code);
        $('input[name="edit_datacenter_code"]').prop('checked', false);
        if (circuit.datacenter_code) $('input[name="edit_datacenter_code"][value="' + circuit.datacenter_code + '"]').prop('checked', true);
        $('#edit_gubn').val(circuit.gubn || '');
        $('input[name="edit_provider"]').prop('checked', false);
        if (circuit.provider) $('input[name="edit_provider"][value="' + circuit.provider + '"]').prop('checked', true);
        $('#edit_circuit_id').val(circuit.circuit_id);
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
        var rowData = infoCompanyCircuitsTable.rows().data().toArray();
        var circuit = rowData.find(function(item) { return item.id === id; });
        if (!circuit) return;

        var name = circuit.company_name ? circuit.company_name + ' (' + circuit.member_code + ')' : circuit.member_code;
        if (!confirm(name + '의 회선 (ID: ' + circuit.id + ')을 삭제하시겠습니까?')) {
            return;
        }

        fetch('/info_company_circuits/delete_info_company_circuit', {
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
            gubn: $('#edit_gubn').val() || null,
            provider: $('input[name="edit_provider"]:checked').val() || null,
            circuit_id: $('#edit_circuit_id').val().trim() || null,
            env: $('input[name="edit_env"]:checked').val() || null,
            usage: $('#edit_usage').val().trim() || null,
            product: $('#edit_product').val().trim() || null,
            bandwidth: $('#edit_bandwidth').val().trim() || null,
            additional_circuit: $('#edit_additional_circuit').is(':checked'),
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

        fetch('/info_company_circuits/update_info_company_circuit', {
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
