(function (factory) {
    typeof define === 'function' && define.amd ? define(factory) :
    factory();
})((function () {
    'use strict';

    var codesTable = null;

    var initTable = function() {
        var loadingSpinner = '<div class="text-center py-4"><div class="spinner-border text-primary" role="status" style="width:2rem;height:2rem;"><span class="visually-hidden">Loading...</span></div><div class="mt-2 text-muted small">데이터를 불러오는 중...</div></div>';

        codesTable = $('#codesTable').DataTable({
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
                    title: '회원사코드_' + new Date().toISOString().slice(0,10),
                    exportOptions: {
                        columns: [0, 1, 2, 3, 4, 5, 6, 7]
                    }
                },
                {
                    extend: 'csv',
                    text: '<i class="fa-solid fa-file-csv me-2"></i>CSV',
                    className: 'btn btn-info btn-sm',
                    title: '회원사코드_' + new Date().toISOString().slice(0,10),
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
                url: '/subscriber_codes/get_codes',
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
                { data: 'subscription_type' },
                { data: 'is_pb' },
                { data: 'created_at' },
                { data: 'updated_at' },
                { data: null, defaultContent: '' }
            ],
            columnDefs: [
                {
                    targets: 0, // ID
                    width: '50px',
                    className: 'text-center py-2 align-middle'
                },
                {
                    targets: 1, // 회원사코드
                    width: '80px',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (!data) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-primary">' + data + '</span>';
                    }
                },
                {
                    targets: 2, // 회원사넘버
                    width: '70px',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (!data && data !== 0) return '-';
                        return '<span class="badge badge-phoenix badge-phoenix-info">' + data + '</span>';
                    }
                },
                {
                    targets: 3, // 회사명
                    width: '150px',
                    className: 'text-center py-2 align-middle'
                },
                {
                    targets: 4, // 가입유형
                    width: '90px',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (!data) return '-';
                        var badgeClass = '';
                        if (data === '회원사') {
                            badgeClass = 'badge-phoenix-success';
                        } else if (data === '정보이용사') {
                            badgeClass = 'badge-phoenix-info';
                        } else if (data === '기타') {
                            badgeClass = 'badge-phoenix-secondary';
                        } else {
                            // 기존 데이터 호환성 (정회원, 준회원, 특별회원)
                            badgeClass = 'badge-phoenix-warning';
                        }
                        return '<span class="badge badge-phoenix ' + badgeClass + '">' + data + '</span>';
                    }
                },
                {
                    targets: 5, // PB
                    width: '60px',
                    className: 'text-center py-2 align-middle',
                    render: function(data, type, row) {
                        if (data === true) {
                            return '<span class="badge badge-phoenix badge-phoenix-danger">PB</span>';
                        } else {
                            return '<span class="badge badge-phoenix badge-phoenix-secondary">일반</span>';
                        }
                    }
                },
                {
                    targets: 6, // 생성일시
                    width: '130px',
                    className: 'text-center py-2 align-middle'
                },
                {
                    targets: 7, // 수정일시
                    width: '130px',
                    className: 'text-center py-2 align-middle'
                },
                {
                    targets: 8, // 작업
                    width: '90px',
                    className: 'text-center py-2 align-middle white-space-nowrap',
                    orderable: false,
                    render: function(data, type, row) {
                        return `
                            <button class="btn btn-sm btn-phoenix-secondary me-1" onclick="editCode(${row.id})" title="수정">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn btn-sm btn-phoenix-danger" onclick="deleteCode(${row.id})" title="삭제">
                                <i class="fas fa-trash-alt"></i>
                            </button>
                        `;
                    }
                }
            ],
            initComplete: function(settings) {
                settings.oLanguage.sEmptyTable = '검색 결과가 없습니다';
                settings.oLanguage.sInfoEmpty = '데이터가 없습니다';
            }
        });

        // 행 클릭 시 수정 모달 열기 (버튼 클릭은 제외)
        $('#codesTable tbody').on('click', 'tr', function(e) {
            if ($(e.target).closest('button').length) return;
            var data = codesTable.row(this).data();
            if (data) editCode(data.id);
        });

        // 커스텀 필터 연동
        setupCustomFilters();
    };

    function setupCustomFilters() {
        // 통합 검색
        $('#searchInput').on('input', function() {
            codesTable.search(this.value).draw();
        });

        // 가입유형 필터
        $('#subscriptionFilter').on('change', function() {
            var value = $(this).val();
            if (value) {
                codesTable.column(4).search('^' + value + '$', true, false).draw();
            } else {
                codesTable.column(4).search('').draw();
            }
        });

        // PB 필터
        $('#pbFilter').on('change', function() {
            var value = $(this).val();
            if (value === 'true') {
                codesTable.column(5).search('PB', false, false).draw();
            } else if (value === 'false') {
                codesTable.column(5).search('일반', false, false).draw();
            } else {
                codesTable.column(5).search('').draw();
            }
        });
    }

    function updateFilters(data) {
        // 가입유형 필터 업데이트
        var subscriptionTypes = [...new Set(data.map(item => item.subscription_type))].sort();
        var subscriptionFilter = $('#subscriptionFilter');
        subscriptionFilter.html('<option value="">전체</option>');
        subscriptionTypes.forEach(function(type) {
            if (type) {
                subscriptionFilter.append('<option value="' + type + '">' + type + '</option>');
            }
        });
    }

    window.resetFilters = function() {
        $('#searchInput').val('');
        $('#subscriptionFilter').val('');
        $('#pbFilter').val('');
        if (codesTable) {
            codesTable.search('').columns().search('').draw();
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
        if (codesTable) {
            codesTable.ajax.reload(function(json) {
                console.log('[DEBUG] 데이터 새로고침 완료:', json);
                spinner.remove();
            }, false);
        } else {
            console.error('[DEBUG] codesTable이 초기화되지 않음');
            spinner.remove();
            showAlert('테이블이 초기화되지 않았습니다.', 'danger');
        }
    };

    window.showCreateModal = function() {
        // 폼 초기화
        $('#createForm')[0].reset();
        $('#create_is_pb').prop('checked', false).prop('disabled', false);

        var modal = new bootstrap.Modal(document.getElementById('createModal'));
        modal.show();
    };

    window.saveCreate = function() {
        var data = {
            member_code: $('#create_member_code').val().trim(),
            member_number: parseInt($('#create_member_number').val()),
            company_name: $('#create_company_name').val().trim(),
            subscription_type: $('#create_subscription_type').val(),
            is_pb: $('#create_is_pb').is(':checked')
        };

        if (!data.member_code || !data.member_number || !data.company_name || !data.subscription_type) {
            showAlert('필수 필드를 모두 입력해주세요.', 'warning');
            return;
        }

        fetch('/subscriber_codes/create_code', {
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

    window.editCode = function(id) {
        var rowData = codesTable.rows().data().toArray();
        var code = rowData.find(item => item.id === id);
        if (!code) return;

        $('#edit_id').val(code.id);
        $('#edit_member_code').val(code.member_code);
        $('#edit_member_number').val(code.member_number);
        $('#edit_company_name').val(code.company_name);
        $('#edit_subscription_type').val(code.subscription_type);
        $('#edit_is_pb').prop('checked', code.is_pb);
        togglePbBySubscriptionType('#edit_subscription_type', '#edit_is_pb');

        var modal = new bootstrap.Modal(document.getElementById('editModal'));
        modal.show();
    };

    window.saveEdit = function() {
        var data = {
            id: parseInt($('#edit_id').val()),
            member_code: $('#edit_member_code').val().trim(),
            member_number: parseInt($('#edit_member_number').val()),
            company_name: $('#edit_company_name').val().trim(),
            subscription_type: $('#edit_subscription_type').val(),
            is_pb: $('#edit_is_pb').is(':checked')
        };

        if (!data.member_code || !data.member_number || !data.company_name || !data.subscription_type) {
            showAlert('필수 필드를 모두 입력해주세요.', 'warning');
            return;
        }

        fetch('/subscriber_codes/update_code', {
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

    window.deleteCode = function(id) {
        var rowData = codesTable.rows().data().toArray();
        var code = rowData.find(item => item.id === id);
        if (!code) return;

        if (!confirm(code.company_name + ' (' + code.member_code + ')를 삭제하시겠습니까?\n\n※ 주의: 이 회원사와 연결된 모든 주소 정보도 함께 삭제됩니다.')) {
            return;
        }

        fetch('/subscriber_codes/delete_code', {
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

    function togglePbBySubscriptionType(typeSelector, pbSelector) {
        var type = $(typeSelector).val();
        if (type === '정보이용사' || type === '기타') {
            $(pbSelector).prop('checked', false).prop('disabled', true);
        } else {
            $(pbSelector).prop('disabled', false);
        }
    }

    // 입력 검증 함수
    function setupInputValidation() {
        // 회원사 코드 - 영어만 입력
        $('#create_member_code, #edit_member_code').on('input', function() {
            this.value = this.value.replace(/[^A-Za-z]/g, '');
        });

        // 회원사 넘버 - 정수만 입력
        $('#create_member_number, #edit_member_number').on('input', function() {
            var value = $(this).val();
            if (value < 0) {
                $(this).val(0);
            }
            // 소수점 제거
            if (value.indexOf('.') !== -1) {
                $(this).val(Math.floor(value));
            }
        });

        // 가입유형 변경 시 PB여부 비활성화
        $('#create_subscription_type').on('change', function() {
            togglePbBySubscriptionType('#create_subscription_type', '#create_is_pb');
        });
        $('#edit_subscription_type').on('change', function() {
            togglePbBySubscriptionType('#edit_subscription_type', '#edit_is_pb');
        });
    }

    // 페이지 로드 시 초기화
    $(document).ready(function() {
        initTable();
        setupInputValidation();
    });

}));
