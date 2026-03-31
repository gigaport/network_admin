(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
})((function () {
    'use strict';

    var addressTable = null;
    var memberCodeList = [];

    function loadMemberCodes() {
        fetch('/subscriber_codes/get_codes')
            .then(function(res) { return res.json(); })
            .then(function(result) {
                if (result.success && result.data) {
                    memberCodeList = result.data.sort(function(a, b) {
                        return (a.member_code || '').localeCompare(b.member_code || '');
                    });
                    fillMemberCodeSelect('#create_member_code', '');
                    fillMemberCodeSelect('#edit_member_code', '');
                }
            })
            .catch(function(err) {
                console.error('회원사 코드 로드 실패:', err);
            });
    }

    function fillMemberCodeSelect(selector, selectedValue) {
        var $sel = $(selector);
        $sel.html('<option value="">선택</option>');
        memberCodeList.forEach(function(m) {
            var label = m.member_code + ' (' + (m.company_name || '') + ')';
            var selected = (m.member_code === selectedValue) ? ' selected' : '';
            $sel.append('<option value="' + m.member_code + '"' + selected + '>' + label + '</option>');
        });
    }

    var initTable = function() {
        var loadingSpinner = '<div class="text-center py-4"><div class="spinner-border text-primary" role="status" style="width:2rem;height:2rem;"><span class="visually-hidden">Loading...</span></div><div class="mt-2 text-muted small">데이터를 불러오는 중...</div></div>';

        addressTable = $('#addressTable').DataTable({
            responsive: true,
            paging: true,
            pageLength: 100,
            searching: true,
            ordering: true,
            language: {
                search: "검색:",
                lengthMenu: "페이지당 _MENU_ 개씩 표시",
                info: "전체 _TOTAL_개 중 _START_-_END_개 표시",
                infoEmpty: " ",
                infoFiltered: "(전체 _MAX_개 중 필터링됨)",
                paginate: {
                    first: "처음",
                    last: "마지막",
                    next: "다음",
                    previous: "이전"
                },
                emptyTable: loadingSpinner,
                zeroRecords: "검색 결과가 없습니다",
                loadingRecords: loadingSpinner
            },
            dom: '<"row"<"col-sm-12 col-md-6"l><"col-sm-12 col-md-6 text-end"B>>' +
                 '<"row"<"col-sm-12"tr>>' +
                 '<"row"<"col-sm-12 col-md-5"i><"col-sm-12 col-md-7"p>>',
            buttons: [
                {
                    extend: 'excel',
                    text: '<i class="fa-solid fa-file-excel me-2"></i>Excel',
                    className: 'btn btn-success btn-sm',
                    title: '회원사주소_' + new Date().toISOString().slice(0,10),
                    exportOptions: {
                        columns: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] // 작업 컬럼 제외
                    }
                },
                {
                    extend: 'csv',
                    text: '<i class="fa-solid fa-file-csv me-2"></i>CSV',
                    className: 'btn btn-info btn-sm',
                    title: '회원사주소_' + new Date().toISOString().slice(0,10),
                    exportOptions: {
                        columns: [0, 1, 2, 3, 4, 5, 6, 7]
                    }
                },
                {
                    extend: 'copy',
                    text: '<i class="fa-solid fa-copy me-2"></i>복사',
                    className: 'btn btn-secondary btn-sm',
                    exportOptions: {
                        columns: [0, 1, 2, 3, 4, 5, 6, 7]
                    }
                }
            ],
            ajax: {
                url: '/subscriber_address/get_addresses',
                type: 'GET',
                dataSrc: function(json) {
                    console.log('API Response:', json);
                    if (json.success) {
                        updateFilters(json.data);
                        return json.data;
                    } else {
                        showAlert('데이터 로드 실패: ' + json.error, 'danger');
                        return [];
                    }
                },
                error: function(xhr, error, thrown) {
                    console.error('AJAX Error:', error, thrown);
                    console.error('Response:', xhr.responseText);
                    showAlert('데이터 로드 중 오류가 발생했습니다.', 'danger');
                }
            },
            columns: [
                { data: 'id' },
                { data: 'member_code' },
                { data: 'member_number' },
                { data: 'company_name' },
                { data: 'datacenter_code' },
                { data: 'post_code', defaultContent: '' },
                { data: 'main_address', defaultContent: '' },
                { data: 'detailed_address', defaultContent: '' },
                { data: 'summary_address' },
                { data: 'updated_at' },
                { data: null, defaultContent: '' }
            ],
            columnDefs: [
                {
                    targets: 0, // ID
                    width: '3%',
                    className: 'text-center align-middle'
                },
                {
                    targets: 1, // 회원사코드
                    width: '5%',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-primary">' + data + '</span>';
                    }
                },
                {
                    targets: 2, // 회원사넘버
                    width: '4%',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (!data && data !== 0) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-info">' + data + '</span>';
                    }
                },
                {
                    targets: 3, // 회사명
                    width: '7%',
                    className: 'text-center align-middle'
                },
                {
                    targets: 4, // 데이터센터
                    width: '4%',
                    className: 'text-center align-middle'
                },
                {
                    targets: 5, // 우편번호
                    width: '4%',
                    className: 'text-center align-middle',
                    render: function(data) {
                        return data || '-';
                    }
                },
                {
                    targets: 6, // 도로명주소
                    width: '15%',
                    className: 'align-middle',
                    render: function(data) {
                        return data || '';
                    }
                },
                {
                    targets: 7, // 상세주소
                    width: '13%',
                    className: 'align-middle',
                    render: function(data) {
                        return data || '';
                    }
                },
                {
                    targets: 8, // 요약주소
                    width: '10%',
                    className: 'align-middle'
                },
                {
                    targets: 9, // 수정일시
                    width: '8%',
                    className: 'text-center align-middle'
                },
                {
                    targets: 10, // 작업
                    width: '5%',
                    className: 'text-center align-middle white-space-nowrap',
                    orderable: false,
                    render: function(data, type, row) {
                        return '<button onclick="editAddress(' + row.id + ')" title="수정" style="width:28px; height:28px; border:none; border-radius:6px; background:transparent; color:#94a3b8; cursor:pointer; display:inline-flex; align-items:center; justify-content:center; padding:0; transition:color 0.15s; margin-right:2px;" onmouseenter="this.style.color=\'#4f46e5\'" onmouseleave="this.style.color=\'#94a3b8\'">' +
                            '<i class="fas fa-pen" style="font-size:0.65rem;"></i></button>' +
                            '<button onclick="deleteAddress(' + row.id + ')" title="삭제" style="width:28px; height:28px; border:none; border-radius:6px; background:transparent; color:#94a3b8; cursor:pointer; display:inline-flex; align-items:center; justify-content:center; padding:0; transition:color 0.15s;" onmouseenter="this.style.color=\'#dc2626\'" onmouseleave="this.style.color=\'#94a3b8\'">' +
                            '<i class="fas fa-trash-alt" style="font-size:0.65rem;"></i></button>';
                    }
                }
            ],
            initComplete: function(settings) {
                settings.oLanguage.sEmptyTable = '검색 결과가 없습니다';
                settings.oLanguage.sInfoEmpty = '데이터가 없습니다';
            }
        });

        // 행 클릭 시 수정 모달 열기 (작업 버튼 클릭은 제외)
        $('#addressTable tbody').on('click', 'tr', function(e) {
            if ($(e.target).closest('button').length) return;
            var data = addressTable.row(this).data();
            if (data) editAddress(data.id);
        });

        // 커스텀 필터 연동
        setupCustomFilters();
    };

    function setupCustomFilters() {
        // 통합 검색
        $('#searchInput').on('input', function() {
            addressTable.search(this.value).draw();
        });

        // 데이터센터 필터
        $('#datacenterFilter').on('change', function() {
            var value = $(this).val();
            if (value) {
                addressTable.column(4).search('^' + value + '$', true, false).draw();
            } else {
                addressTable.column(4).search('').draw();
            }
        });

        // 회원사 필터
        $('#memberFilter').on('change', function() {
            var value = $(this).val();
            if (value) {
                addressTable.column(1).search('^' + value + '$', true, false).draw();
            } else {
                addressTable.column(1).search('').draw();
            }
        });
    }

    function updateFilters(data) {
        // 데이터센터 필터 업데이트
        var datacenters = [...new Set(data.map(item => item.datacenter_code))].sort();
        var datacenterFilter = $('#datacenterFilter');
        datacenterFilter.html('<option value="">전체</option>');
        datacenters.forEach(function(dc) {
            datacenterFilter.append('<option value="' + dc + '">' + dc + '</option>');
        });

        // 회원사 필터 업데이트
        var memberMap = new Map();
        data.forEach(function(item) {
            if (!memberMap.has(item.member_code)) {
                memberMap.set(item.member_code, item.company_name);
            }
        });

        var members = Array.from(memberMap.entries())
            .map(function([code, name]) {
                return { code: code, name: name };
            })
            .sort(function(a, b) {
                return a.code.localeCompare(b.code);
            });

        var memberFilter = $('#memberFilter');
        memberFilter.html('<option value="">전체</option>');
        members.forEach(function(member) {
            memberFilter.append('<option value="' + member.code + '">' + member.name + ' (' + member.code + ')</option>');
        });
    }

    window.resetFilters = function() {
        $('#searchInput').val('');
        $('#datacenterFilter').val('');
        $('#memberFilter').val('');
        if (addressTable) {
            addressTable.search('').columns().search('').draw();
        }
    };

    window.refreshTable = function() {
        console.log('[DEBUG] refreshTable 호출됨');

        // 스피너 표시
        var spinner = $('<div class="position-fixed top-50 start-50 translate-middle" style="z-index: 10000;">' +
            '<div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">' +
            '<span class="visually-hidden">Loading...</span>' +
            '</div></div>');
        $('body').append(spinner);

        resetFilters();
        if (addressTable) {
            addressTable.ajax.reload(function(json) {
                console.log('[DEBUG] 데이터 새로고침 완료:', json);
                spinner.remove();
            }, false);
        } else {
            console.error('[DEBUG] addressTable이 초기화되지 않음');
            spinner.remove();
            showAlert('테이블이 초기화되지 않았습니다.', 'danger');
        }
    };

    window.editAddress = function(id) {
        var rowData = addressTable.rows().data().toArray();
        var address = rowData.find(item => item.id === id);
        if (!address) return;

        $('#edit_id').val(address.id);
        fillMemberCodeSelect('#edit_member_code', address.member_code);
        $('#edit_datacenter_code').val(address.datacenter_code);
        $('#edit_post_code').val(address.post_code || '');
        $('#edit_main_address').val(address.main_address || '');
        $('#edit_postcode_embed').hide().html('');
        $('#edit_detailed_address').val(address.detailed_address || '');
        $('#edit_summary_address').val(address.summary_address || '');

        var modal = new bootstrap.Modal(document.getElementById('editModal'));
        modal.show();
    };

    window.saveEdit = function() {
        var data = {
            id: parseInt($('#edit_id').val()),
            member_code: $('#edit_member_code').val(),
            datacenter_code: $('#edit_datacenter_code').val(),
            post_code: $('#edit_post_code').val().trim(),
            main_address: $('#edit_main_address').val().trim(),
            detailed_address: $('#edit_detailed_address').val().trim(),
            summary_address: $('#edit_summary_address').val().trim()
        };

        if (!data.member_code || !data.datacenter_code || !data.summary_address) {
            showAlert('필수 필드를 입력해주세요.', 'warning');
            return;
        }

        fetch('/subscriber_address/update_address', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                showAlert('수정이 완료되었습니다.', 'success');
                bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
                refreshTable();
            } else {
                showAlert('수정 실패: ' + result.error, 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('수정 중 오류가 발생했습니다.', 'danger');
        });
    };

    window.deleteAddress = function(id) {
        var rowData = addressTable.rows().data().toArray();
        var address = rowData.find(item => item.id === id);
        if (!address) return;

        if (!confirm(address.company_name + '의 ' + address.datacenter_code + ' 주소를 삭제하시겠습니까?')) {
            return;
        }

        fetch('/subscriber_address/delete_address', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ id: id })
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                showAlert('삭제가 완료되었습니다.', 'success');
                refreshTable();
            } else {
                showAlert('삭제 실패: ' + result.error, 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('삭제 중 오류가 발생했습니다.', 'danger');
        });
    };

    function showAlert(message, type) {
        var alertDiv = $('<div></div>')
            .addClass('alert alert-' + type + ' alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3')
            .css('zIndex', '9999')
            .html(message + '<button type="button" class="btn-close" data-bs-dismiss="alert"></button>');

        $('body').append(alertDiv);

        setTimeout(function() {
            alertDiv.remove();
        }, 3000);
    }

    function openPostcode(prefix) {
        var wrap = document.getElementById(prefix + '_postcode_embed');
        wrap.innerHTML = '';
        wrap.style.display = 'block';
        new daum.Postcode({
            oncomplete: function(data) {
                $('#' + prefix + '_post_code').val(data.zonecode);
                $('#' + prefix + '_main_address').val(data.roadAddress);
                wrap.style.display = 'none';
                $('#' + prefix + '_detailed_address').focus();
            },
            width: '100%',
            height: '100%'
        }).embed(wrap);
    }

    window.searchAddress = function(prefix) {
        if (typeof daum !== 'undefined' && daum.Postcode) {
            openPostcode(prefix);
            return;
        }
        var script = document.createElement('script');
        script.src = '/static/assets/js/postcode.v2.proxy.js?v=' + Date.now();
        script.onload = function() {
            openPostcode(prefix);
        };
        script.onerror = function() {
            showAlert('주소 검색 서비스를 불러올 수 없습니다.', 'danger');
        };
        document.head.appendChild(script);
    };

    window.showCreateModal = function() {
        fillMemberCodeSelect('#create_member_code', '');
        $('#create_datacenter_code').val('');
        $('#create_post_code').val('');
        $('#create_main_address').val('');
        $('#create_postcode_embed').hide().html('');
        $('#create_detailed_address').val('');
        $('#create_summary_address').val('');

        var modal = new bootstrap.Modal(document.getElementById('createModal'));
        modal.show();
    };

    window.saveCreate = function() {
        var data = {
            member_code: $('#create_member_code').val(),
            datacenter_code: $('#create_datacenter_code').val(),
            post_code: $('#create_post_code').val().trim(),
            main_address: $('#create_main_address').val().trim(),
            detailed_address: $('#create_detailed_address').val().trim(),
            summary_address: $('#create_summary_address').val().trim()
        };

        if (!data.member_code || !data.datacenter_code || !data.summary_address) {
            showAlert('필수 필드를 입력해주세요.', 'warning');
            return;
        }

        fetch('/subscriber_address/create_address', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                showAlert('추가가 완료되었습니다.', 'success');
                bootstrap.Modal.getInstance(document.getElementById('createModal')).hide();
                refreshTable();
            } else {
                showAlert('추가 실패: ' + result.error, 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('추가 중 오류가 발생했습니다.', 'danger');
        });
    };

    // 페이지 로드 시 초기화
    $(document).ready(function() {
        initTable();
        loadMemberCodes();
    });

}));
